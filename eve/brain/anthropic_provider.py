"""
Anthropic (Claude) LLM Provider
=================================
"""

import json
import logging
from typing import AsyncIterator, Dict, List

from .provider import LLMProvider, LLMResponse, Message, ToolDefinition

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, model: str = "claude-sonnet-4-5-20250929", api_key: str = "",
                 base_url: str = "", **kwargs):
        super().__init__(model=model, api_key=api_key, **kwargs)
        self.base_url = base_url
        self._client = None

    def _get_client(self, force_new: bool = False):
        if self._client is None or force_new:
            from anthropic import Anthropic
            kw = {"api_key": self.api_key}
            if self.base_url:
                kw["base_url"] = self.base_url
            self._client = Anthropic(**kw)
        return self._client

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

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
            logger.info(f"Switched to model={self.model} @ {self.base_url or 'api.anthropic.com'}")

    # ── Message conversion ──────────────────────────────────────────────
    #
    # Eve's agent loop (eve/agent.py::_generate_with_tool_loop) speaks a
    # provider-agnostic Message shape modeled after Ollama/OpenAI-style
    # chat history: assistant messages carry `tool_calls`, and each tool
    # result is appended afterwards as its own `role="tool"` message.
    #
    # Anthropic's Messages API instead wants tool_use content blocks on
    # the assistant turn and a *single* following user turn whose content
    # is a list of tool_result blocks (one per tool_use id). This converts
    # between the two so multi-step tool loops actually round-trip.

    def _to_claude_messages(self, messages: List[Message]) -> List[dict]:
        claude_messages: List[dict] = []
        pending_tool_ids: List[str] = []
        tool_result_buffer: List[dict] = []

        def flush_tool_results():
            if tool_result_buffer:
                claude_messages.append({"role": "user", "content": list(tool_result_buffer)})
                tool_result_buffer.clear()

        for m in messages:
            if m.role == "user":
                flush_tool_results()
                if m.images:
                    blocks = []
                    if m.content:
                        blocks.append({"type": "text", "text": m.content})
                    for img in m.images:
                        blocks.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": img},
                        })
                    claude_messages.append({"role": "user", "content": blocks})
                else:
                    claude_messages.append({"role": "user", "content": m.content or ""})
            elif m.role == "assistant":
                flush_tool_results()
                blocks = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                pending_tool_ids = []
                for tc in (m.tool_calls or []):
                    func = tc.get("function", {})
                    args = func.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    tc_id = tc.get("id") or f"toolu_{len(pending_tool_ids)}"
                    blocks.append({
                        "type": "tool_use",
                        "id": tc_id,
                        "name": func.get("name", ""),
                        "input": args,
                    })
                    pending_tool_ids.append(tc_id)
                claude_messages.append({"role": "assistant", "content": blocks or ""})
            elif m.role == "tool":
                tc_id = pending_tool_ids.pop(0) if pending_tool_ids else (m.tool_call_id or "toolu_unknown")
                tool_result_buffer.append({
                    "type": "tool_result",
                    "tool_use_id": tc_id,
                    "content": m.content or "",
                })

        flush_tool_results()
        return claude_messages

    async def generate(self, messages: List[Message], system_prompt: str = "",
                       temperature: float = 0.7, max_tokens: int = 4096, **_kw) -> LLMResponse:
        client = self._get_client()
        claude_messages = self._to_claude_messages(messages)

        try:
            response = client.messages.create(
                model=self.model,
                system=system_prompt or "",
                messages=claude_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            return LLMResponse(
                content=content,
                model=self.model,
                finish_reason=response.stop_reason or "end_turn",
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                },
                raw=response,
            )
        except Exception as e:
            logger.error(f"Anthropic generation failed: {e}")
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    async def generate_with_tools(self, messages: List[Message],
                                   tools: List[ToolDefinition],
                                   system_prompt: str = "",
                                   temperature: float = 0.7,
                                   max_tokens: int = 4096) -> LLMResponse:
        client = self._get_client()
        claude_messages = self._to_claude_messages(messages)

        claude_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

        try:
            response = client.messages.create(
                model=self.model,
                system=system_prompt or "",
                messages=claude_messages,
                tools=claude_tools,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            content = ""
            tool_calls = []
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "function": {"name": block.name, "arguments": block.input},
                    })

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                model=self.model,
                finish_reason="tool_calls" if tool_calls else response.stop_reason,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                },
                raw=response,
            )
        except Exception as e:
            logger.error(f"Anthropic tool call failed: {e}")
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    async def stream(self, messages: List[Message], system_prompt: str = "",
                     temperature: float = 0.7, max_tokens: int = 4096) -> AsyncIterator[str]:
        client = self._get_client()
        claude_messages = self._to_claude_messages(messages)

        try:
            with client.messages.stream(
                model=self.model,
                system=system_prompt or "",
                messages=claude_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            yield f"Error: {e}"
