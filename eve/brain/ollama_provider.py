"""
Ollama LLM Provider
====================
Supports local and cloud Ollama models with thinking, tools, streaming, and vision.
Optimized for qwen3.5:397b-cloud (397B MoE) on Ollama's free cloud tier.
"""

import logging
from typing import AsyncIterator, Dict, List, Optional

from .provider import LLMProvider, LLMResponse, Message, ToolDefinition

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama provider for local/cloud models with thinking + tool support."""

    def __init__(self, model: str = "", base_url: str = "",
                 api_key: str = "", num_ctx: int = 0, **kwargs):
        import os
        model = model or os.getenv("OLLAMA_MODEL", "jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest")
        # ALL models (local + cloud) go through one Ollama instance.
        # Cloud models are pulled locally and Ollama handles cloud offloading.
        base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        api_key = api_key or os.getenv("OLLAMA_API_KEY", "")
        super().__init__(model=model, api_key=api_key, **kwargs)
        self.base_url = base_url
        self.num_ctx = num_ctx  # 0 = use model default; >0 overrides context window
        self._client = None

    def _get_client(self, force_new: bool = False):
        if self._client is None or force_new:
            from ollama import Client
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            client = Client(host=self.base_url, timeout=300.0, headers=headers)
            # Monkey-patch chat() to ALWAYS strip think for non-thinking models
            _orig_chat = client.chat
            _provider = self
            def _patched_chat(*args, **kwargs):
                if not _provider._supports_thinking():
                    kwargs.pop("think", None)
                return _orig_chat(*args, **kwargs)
            client.chat = _patched_chat
            self._client = client
        return self._client

    def _safe_kwargs(self, kwargs: dict) -> dict:
        """Strip think parameter if model doesn't support it.
        This is the FINAL guard — no matter what callers pass, unsupported
        models will NEVER receive think in the request."""
        if not self._supports_thinking():
            kwargs.pop("think", None)
        return kwargs

    def _safe_chat(self, **kwargs):
        """Wrapper around client.chat that ALWAYS strips think for unsupported models."""
        kwargs = self._safe_kwargs(kwargs)
        return self._get_client().chat(**kwargs)

    @property
    def name(self) -> str:
        return "ollama"

    def switch_model(self, model: str, base_url: str = ""):
        """Switch model and/or base_url at runtime. Resets client connection."""
        changed = False
        if model and model != self.model:
            self.model = model
            changed = True
        if base_url and base_url != self.base_url:
            self.base_url = base_url
            changed = True
        if changed:
            self._client = None  # force reconnect
            logger.info(f"Switched to model={self.model} @ {self.base_url}")

    @property
    def is_available(self) -> bool:
        try:
            self._get_client()
            return True
        except Exception:
            return False

    async def generate(self, messages: List[Message], system_prompt: str = "",
                       temperature: float = 0.7, max_tokens: int = 4096,
                       think: bool = False, **extra_kw) -> LLMResponse:
        """Generate a response. Set think=True for reasoning-heavy tasks."""
        import asyncio
        # Force-disable think for models that don't support it
        if not self._supports_thinking():
            think = False
        client = self._get_client()
        ollama_messages = self._format_messages(messages, system_prompt)

        try:
            opts: dict = {"temperature": temperature, "num_predict": max_tokens}
            if self.num_ctx > 0:
                opts["num_ctx"] = self.num_ctx
            else:
                # Cap context for small models to avoid OOM crashes
                _small = any(s in self.model for s in ["4b", "3b", "1b", "8b"])
                if _small:
                    opts["num_ctx"] = 8192
            kwargs = {
                "model": self.model,
                "messages": ollama_messages,
                "options": opts,
            }
            # Only pass think parameter for models that support it
            if self._supports_thinking():
                kwargs["think"] = think

            # Final safety: strip think if model doesn't support it
            kwargs = self._safe_kwargs(kwargs)
            # Run the blocking sync call in a thread so the event loop stays free
            # for SSE heartbeats, activity polling, and other coroutines
            kwargs = self._safe_kwargs(kwargs)
            response = await asyncio.to_thread(self._get_client().chat, **kwargs)

            content = response.message.content or ""
            thinking = getattr(response.message, "thinking", None) or ""

            return LLMResponse(
                content=content,
                model=self.model,
                finish_reason="stop",
                usage={
                    "prompt_tokens": getattr(response, "prompt_eval_count", 0),
                    "completion_tokens": getattr(response, "eval_count", 0),
                },
                raw={"response": response, "thinking": thinking},
            )
        except Exception as e:
            # Retry with exponential backoff on transient failures (500, 503, connection)
            err_str = str(e).lower()
            if "connect" in err_str or "500" in err_str or "503" in err_str or "temporarily" in err_str:
                for attempt in range(1, 4):  # 3 retries with backoff
                    wait = attempt * 1.5  # 1.5s, 3s, 4.5s
                    logger.warning(f"Ollama failed ({e}), retry {attempt}/3 in {wait}s")
                    await asyncio.sleep(wait)
                    try:
                        client = self._get_client(force_new=True)
                        response = await asyncio.to_thread(client.chat, **kwargs)
                        content = response.message.content or ""
                        thinking = getattr(response.message, "thinking", None) or ""
                        logger.info(f"Ollama retry {attempt} succeeded")
                        return LLMResponse(
                            content=content, model=self.model, finish_reason="stop",
                            usage={"prompt_tokens": getattr(response, "prompt_eval_count", 0),
                                   "completion_tokens": getattr(response, "eval_count", 0)},
                            raw={"response": response, "thinking": thinking},
                        )
                    except Exception as e2:
                        logger.warning(f"Ollama retry {attempt}/3 failed: {e2}")
                logger.error(f"Ollama generation failed after 3 retries: {e}")
            else:
                logger.error(f"Ollama generation failed: {e}")
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    async def generate_with_tools(self, messages: List[Message],
                                   tools: List[ToolDefinition],
                                   system_prompt: str = "",
                                   temperature: float = 0.7,
                                   max_tokens: int = 4096,
                                   think: bool = False) -> LLMResponse:
        """Generate with tool calling. Think=False by default — keeps final answer in content.
        (think=True causes qwen3.5 to put responses in thinking trace, leaving content empty)"""
        import asyncio
        if not self._supports_thinking():
            think = False

        # Ollama Cloud does NOT support native tool calling — returns 500.
        # Fall back to plain generation; the agent framework handles tool
        # routing via text-based tool descriptions in the system prompt.
        if "cloud" in self.model.lower():
            logger.info(f"Cloud model {self.model} — skipping native tools, using plain generation")
            # Inject tool descriptions into the system prompt so the model
            # knows what tools are available and can request them via text
            tool_desc = "\n\nYou have these tools available. To use a tool, write EXACTLY:\n[TOOL_CALL] tool_name({\"param\": \"value\"})\n\nAvailable tools:\n"
            for t in tools:
                tool_desc += f"- {t.name}: {t.description}\n"
            tool_desc += "\nIf you don't need a tool, just respond normally.\n"
            enhanced_prompt = (system_prompt or "") + tool_desc
            return await self.generate(
                messages, enhanced_prompt, temperature, max_tokens, think=False
            )

        client = self._get_client()
        ollama_messages = self._format_messages(messages, system_prompt)
        ollama_tools = self._format_tools(tools)

        try:
            opts: dict = {"temperature": temperature, "num_predict": max_tokens}
            if self.num_ctx > 0:
                opts["num_ctx"] = self.num_ctx
            else:
                _small = any(s in self.model for s in ["4b", "3b", "1b", "8b"])
                if _small:
                    opts["num_ctx"] = 8192
            kwargs = {
                "model": self.model,
                "messages": ollama_messages,
                "tools": ollama_tools if ollama_tools else None,
                "options": opts,
            }
            # IMPORTANT: Do NOT pass think when tools are present —
            # Ollama Cloud returns 500 when both think + tools are sent together.
            # Only enable thinking on tool-free calls.
            if self._supports_thinking() and not ollama_tools:
                kwargs["think"] = think

            kwargs = self._safe_kwargs(kwargs)
            # Run blocking sync Ollama call in a thread — keeps event loop unblocked
            response = await asyncio.to_thread(client.chat, **kwargs)

            tool_calls = []
            if hasattr(response.message, "tool_calls") and response.message.tool_calls:
                for tc in response.message.tool_calls:
                    tool_calls.append({
                        "id": f"call_{id(tc)}",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    })

            content = response.message.content or ""
            thinking = getattr(response.message, "thinking", None) or ""

            # qwen3.5 sometimes puts the final answer entirely in the thinking trace
            # when no tools are called. Use thinking as content fallback in that case.
            if not content and not tool_calls and thinking:
                content = thinking
                thinking = ""

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                model=self.model,
                finish_reason="tool_calls" if tool_calls else "stop",
                raw={"response": response, "thinking": thinking},
            )
        except Exception as e:
            # Model may not support tools — fall back to text-based tool descriptions
            if "does not support tools" in str(e):
                logger.warning(f"Model {self.model} doesn't support tools, using text-based tool fallback")
                tool_desc = "\n\nYou have these tools. To use one, write:\n[TOOL_CALL] tool_name({\"param\": \"value\"})\n\nTools:\n"
                for t in tools:
                    tool_desc += f"- {t.name}: {t.description}\n"
                tool_desc += "\nIf you don't need a tool, just respond normally.\n"
                return await self.generate(messages, (system_prompt or "") + tool_desc, temperature, max_tokens)
            # Retry with exponential backoff on transient failures (500, 503, connection)
            err_str = str(e).lower()
            if "connect" in err_str or "500" in err_str or "503" in err_str or "temporarily" in err_str:
                for attempt in range(1, 4):  # 3 retries with backoff
                    wait = attempt * 1.5
                    logger.warning(f"Ollama tool call failed ({e}), retry {attempt}/3 in {wait}s")
                    await asyncio.sleep(wait)
                    try:
                        client = self._get_client(force_new=True)
                        response = await asyncio.to_thread(client.chat, **kwargs)
                        tool_calls = []
                        if hasattr(response.message, "tool_calls") and response.message.tool_calls:
                            for tc in response.message.tool_calls:
                                tool_calls.append({
                                    "id": f"call_{id(tc)}",
                                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                                })
                        content = response.message.content or ""
                        thinking = getattr(response.message, "thinking", None) or ""
                        if not content and not tool_calls and thinking:
                            content = thinking
                            thinking = ""
                        logger.info(f"Ollama tool call retry {attempt} succeeded")
                        return LLMResponse(
                            content=content, tool_calls=tool_calls, model=self.model,
                            finish_reason="tool_calls" if tool_calls else "stop",
                            raw={"response": response, "thinking": thinking},
                        )
                    except Exception as e2:
                        logger.warning(f"Ollama tool call retry {attempt}/3 failed: {e2}")
                logger.error(f"Ollama tool call failed after 3 retries: {e}")
            else:
                logger.error(f"Ollama tool call failed: {e}")
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    async def stream(self, messages: List[Message], system_prompt: str = "",
                     temperature: float = 0.7, max_tokens: int = 4096,
                     think: bool = False) -> AsyncIterator[str]:
        """Stream responses. Yields content chunks, thinking is accumulated internally."""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        if not self._supports_thinking():
            think = False

        client = self._get_client()
        ollama_messages = self._format_messages(messages, system_prompt)

        try:
            kwargs = {
                "model": self.model,
                "messages": ollama_messages,
                "options": {"temperature": temperature, "num_predict": max_tokens},
                "stream": True,
            }
            if self._supports_thinking():
                kwargs["think"] = think

            # Ollama library is sync, but we need true async streaming
            # Use a queue to bridge sync -> async
            queue = asyncio.Queue()
            # Capture the running loop NOW (in async context) so the thread can use it
            loop = asyncio.get_event_loop()

            kwargs = self._safe_kwargs(kwargs)
            def _run_sync_stream():
                try:
                    for chunk in client.chat(**kwargs):
                        if chunk.message:
                            if getattr(chunk.message, "thinking", None):
                                asyncio.run_coroutine_threadsafe(
                                    queue.put(f"[THINK]{chunk.message.thinking}"),
                                    loop
                                )
                            if chunk.message.content:
                                asyncio.run_coroutine_threadsafe(
                                    queue.put(chunk.message.content),
                                    loop
                                )
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # Signal done
                except Exception as e:
                    asyncio.run_coroutine_threadsafe(queue.put(f"[STREAM_ERROR]{e}"), loop)
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop)

            # Start streaming in background thread
            executor = ThreadPoolExecutor(max_workers=1)
            executor.submit(_run_sync_stream)

            # Yield chunks as they arrive
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk

        except Exception as e:
            yield f"Error: {e}"

    async def generate_streaming(self, messages: List[Message], system_prompt: str = "",
                                  temperature: float = 0.7, max_tokens: int = 4096,
                                  think: bool = True):
        """Stream tokens with thinking/content separation.
        Think is force-disabled for models that don't support it.

        Yields dicts: {"type": "thinking"|"content", "text": "..."}
        Final yield: {"type": "done", "content": full_content, "thinking": full_thinking}
        """
        import asyncio
        import queue as _queue
        if not self._supports_thinking():
            think = False

        client = self._get_client()
        ollama_messages = self._format_messages(messages, system_prompt)

        opts: dict = {"temperature": temperature, "num_predict": max_tokens}
        if self.num_ctx > 0:
            opts["num_ctx"] = self.num_ctx
        else:
            _small = any(s in self.model for s in ["4b", "3b", "1b", "8b"])
            if _small:
                opts["num_ctx"] = 8192
        kwargs = {
            "model": self.model,
            "messages": ollama_messages,
            "options": opts,
            "stream": True,
        }
        if self._supports_thinking():
            kwargs["think"] = think

        result_queue = _queue.Queue()
        kwargs = self._safe_kwargs(kwargs)

        def _sync_stream():
            try:
                for chunk in client.chat(**kwargs):
                    result_queue.put(chunk)
                result_queue.put(None)  # sentinel
            except Exception as e:
                result_queue.put(e)

        thread = asyncio.get_event_loop().run_in_executor(None, _sync_stream)

        full_thinking = []
        full_content = []

        try:
            while True:
                # Non-blocking poll with sleep
                try:
                    chunk = result_queue.get_nowait()
                except _queue.Empty:
                    await asyncio.sleep(0.02)
                    continue

                if chunk is None:
                    break
                if isinstance(chunk, Exception):
                    yield {"type": "error", "text": str(chunk)}
                    return

                thinking_text = getattr(chunk.message, "thinking", None) or ""
                content_text = chunk.message.content or ""

                if thinking_text:
                    full_thinking.append(thinking_text)
                    yield {"type": "thinking", "text": thinking_text}
                if content_text:
                    full_content.append(content_text)
                    yield {"type": "content", "text": content_text}

        except Exception as e:
            yield {"type": "error", "text": str(e)}
            return

        yield {
            "type": "done",
            "content": "".join(full_content),
            "thinking": "".join(full_thinking),
        }

    async def generate_analysis(self, query: str, system_prompt: str = "",
                                 think: bool = True) -> Dict:
        """Generate analysis with thinking enabled — for market data, research, etc.
        No Eve personality injected. Returns both thinking trace and content."""
        messages = [Message(role="user", content=query)]
        response = await self.generate(
            messages=messages,
            system_prompt=system_prompt or "You are a precise analytical assistant. Provide data-driven analysis.",
            temperature=0.3,
            max_tokens=4096,
            think=think,
        )
        return {
            "content": response.content,
            "thinking": response.raw.get("thinking", "") if response.raw else "",
            "model": response.model,
        }

    def _supports_thinking(self) -> bool:
        """Check if current model supports the think parameter.
        eve-unleashed uses RENDERER qwen3.5 which supports thinking natively."""
        model_lower = self.model.lower()
        # eve-unleashed supports thinking (Qwen3 base with qwen3.5 renderer)
        if "eve-unleashed" in model_lower:
            return True
        # Other Eve fine-tunes on old templates do NOT support thinking
        if ("eve-" in model_lower or "eve2" in model_lower) and "unleashed" not in model_lower:
            return False
        if "cloud" in model_lower:
            return False
        # Known thinking-capable base models
        thinking_models = ["qwen3:", "qwen3.", "qwen3-", "deepseek-r1", "deepseek-v3", "gpt-oss"]
        return any(m in model_lower for m in thinking_models)

    def _format_messages(self, messages: List[Message], system_prompt: str) -> List[Dict]:
        formatted = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        for msg in messages:
            # Tool result messages — Ollama requires role="tool" with tool_name field
            if msg.role == "tool":
                formatted.append({
                    "role": "tool",
                    "tool_name": msg.name or "",
                    "content": msg.content or "",
                })
                continue

            entry = {"role": msg.role, "content": msg.content or ""}
            if msg.images:
                entry["images"] = msg.images  # base64 strings for vision models
            # Include thinking on assistant messages (required for multi-turn tool+think)
            if msg.thinking:
                entry["thinking"] = msg.thinking
            # Include tool_calls on assistant messages so Ollama can correlate tool results
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {"function": {"name": tc.get("function", {}).get("name", tc.get("name", "")),
                                  "arguments": tc.get("function", {}).get("arguments", tc.get("arguments", {}))}}
                    for tc in msg.tool_calls
                ]
            formatted.append(entry)
        return formatted

    def _format_tools(self, tools: List[ToolDefinition]) -> List[Dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]


class OllamaCoderProvider(OllamaProvider):
    """Fallback provider using qwen3.5:397b-cloud for vision/content/general tasks.

    Used for X content generation, vision tasks, and general intelligence
    when the primary coder model needs a large general-purpose fallback.
    Also serves as the Claude credit fallback for general chat.
    """

    def __init__(self, base_url: str = "http://ollama:11434",
                 api_key: str = "", **kwargs):
        super().__init__(
            model="qwen3.5:397b-cloud",
            base_url=base_url,
            api_key=api_key,
            **kwargs,
        )

    @property
    def name(self) -> str:
        return "ollama-general"

    async def generate_code(self, task: str, context: str = "",
                            language: str = "", think: bool = True) -> Dict:
        """Generate code with thinking enabled. No personality, pure code focus."""
        system = "You are an expert software engineer. Write clean, correct, production-ready code. Be concise. No unnecessary commentary."
        if language:
            system += f" Primary language: {language}."

        prompt = task
        if context:
            prompt = f"Context:\n{context}\n\nTask:\n{task}"

        messages = [Message(role="user", content=prompt)]
        response = await self.generate(
            messages=messages,
            system_prompt=system,
            temperature=0.2,
            max_tokens=8192,
            think=think,
        )
        return {
            "content": response.content,
            "thinking": response.raw.get("thinking", "") if response.raw else "",
            "model": response.model,
        }
