"""
Claude Sonnet 5 via Comfy Cloud
=================================
Calls Anthropic's Claude Sonnet 5 through a ComfyUI Cloud workflow graph
(the built-in `ClaudeNode`) — the same cloud.comfy.org infrastructure and
X-API-Key auth Eve already uses for image generation in
eve/tools/x_content_agent.py. This deliberately does NOT talk to
api.anthropic.com directly: Comfy Cloud fronts the model call and bills
against COMFY_CLOUD_API_KEY, so no separate Anthropic key is needed.

The graph is a single-shot node (one prompt in, one completion out) — it
has no native multi-turn tool-calling protocol, so this provider is used
with Eve's tool loop disabled (see `supports_tools`) and instead flattens
recent conversation turns into the node's `prompt` input.
"""

import asyncio
import json
import logging
import random
import time
import urllib.error
import urllib.request
from typing import AsyncIterator, List, Optional

from .provider import LLMProvider, LLMResponse, Message, ToolDefinition

logger = logging.getLogger(__name__)


def _build_workflow(prompt: str, system_prompt: str, max_tokens: int, seed: int) -> dict:
    """Mirrors the ClaudeNode workflow graph exported from Comfy Cloud —
    just the text-completion path, with the LoadImage/vision branch dropped."""
    return {
        "1": {
            "class_type": "ClaudeNode",
            "inputs": {
                "prompt": ["5", 0],
                "model": "Sonnet 5",
                "model.max_tokens": max_tokens,
                "model.reasoning_effort": "off",
                "seed": seed,
                "system_prompt": system_prompt,
            },
            "_meta": {"title": "Anthropic Claude"},
        },
        "5": {
            "class_type": "PrimitiveStringMultiline",
            "inputs": {"value": prompt},
            "_meta": {"title": "Text (User Prompt)"},
        },
        "9": {
            "class_type": "PreviewAny",
            "inputs": {"source": ["1", 0]},
            "_meta": {"title": "Preview as Text"},
        },
    }


class ComfyClaudeProvider(LLMProvider):
    """Claude Sonnet 5, routed through ComfyUI Cloud instead of api.anthropic.com."""

    supports_tools = False  # single-shot node graph — no native tool-calling loop

    def __init__(self, model: str = "Sonnet 5", api_key: str = "",
                 base_url: str = "https://cloud.comfy.org", **kwargs):
        super().__init__(model=model, api_key=api_key, **kwargs)
        self.base_url = (base_url or "https://cloud.comfy.org").rstrip("/")

    @property
    def name(self) -> str:
        return "comfy_claude"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def switch_model(self, model: str = "", base_url: str = ""):
        if model:
            self.model = model
        if base_url:
            self.base_url = base_url.rstrip("/")

    @staticmethod
    def _flatten(messages: List[Message]) -> str:
        """Collapse Eve's message history into the single prompt string the
        ClaudeNode graph expects (it has no conversation-array input)."""
        lines = []
        for m in messages:
            if m.role == "user":
                lines.append(f"User: {m.content}")
            elif m.role == "assistant" and m.content:
                lines.append(f"Eve: {m.content}")
            elif m.role == "tool":
                lines.append(f"[Tool result — {m.name}]: {m.content}")
        return "\n\n".join(lines) or "Hello"

    # ── ComfyUI Cloud API — mirrors ComfyUIImageEngine in x_content_agent.py ──

    def _queue_prompt(self, workflow: dict) -> Optional[str]:
        payload = json.dumps({"prompt": workflow}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/prompt",
            data=payload,
            headers={"Content-Type": "application/json", "X-API-Key": self.api_key},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("prompt_id")

    def _download_output_file(self, info: dict) -> str:
        params = (
            f"filename={info['filename']}"
            f"&subfolder={info.get('subfolder', '')}"
            f"&type={info.get('type', 'output')}"
        )
        req = urllib.request.Request(
            f"{self.base_url}/api/view?{params}", headers={"X-API-Key": self.api_key},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _extract_text(self, history: dict, prompt_id: str) -> str:
        for node_output in history.get(prompt_id, {}).get("outputs", {}).values():
            # Inline text value (text-preview/primitive nodes commonly expose this)
            for key in ("text", "string", "value", "strings"):
                val = node_output.get(key)
                if val:
                    return "\n".join(str(v) for v in val) if isinstance(val, list) else str(val)
            # Saved-file reference (SaveText-style — mirrors SaveImage's "images" list)
            for key in ("files", "text_files"):
                files = node_output.get(key)
                if files:
                    return self._download_output_file(files[0])
        return ""

    def _wait_for_text(self, prompt_id: str, timeout: int = 180) -> str:
        auth = {"X-API-Key": self.api_key}
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(2)
            req = urllib.request.Request(f"{self.base_url}/api/job/{prompt_id}/status", headers=auth)
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = json.loads(resp.read()).get("status", "")
            if status in ("completed", "success"):
                break
            if status in ("failed", "cancelled", "error"):
                raise RuntimeError(f"Comfy Cloud job {status}")
        else:
            raise TimeoutError("Comfy Cloud job timed out")

        req = urllib.request.Request(f"{self.base_url}/api/history_v2/{prompt_id}", headers=auth)
        with urllib.request.urlopen(req, timeout=10) as resp:
            history = json.loads(resp.read())
        return self._extract_text(history, prompt_id)

    def _generate_sync(self, messages: List[Message], system_prompt: str, max_tokens: int) -> LLMResponse:
        prompt = self._flatten(messages)
        workflow = _build_workflow(prompt, system_prompt, max_tokens, random.randint(0, 2**31 - 1))
        try:
            prompt_id = self._queue_prompt(workflow)
            if not prompt_id:
                return LLMResponse(content="Error: Comfy Cloud did not return a prompt_id", finish_reason="error")
            text = self._wait_for_text(prompt_id)
            return LLMResponse(content=text, model=self.model, finish_reason="end_turn")
        except urllib.error.HTTPError as e:
            logger.error(f"Comfy Cloud Claude call failed: HTTP {e.code} {e.reason}")
            return LLMResponse(content=f"Error: Comfy Cloud HTTP {e.code} — check COMFY_CLOUD_API_KEY", finish_reason="error")
        except Exception as e:
            logger.error(f"Comfy Cloud Claude call failed: {e}")
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    async def generate(self, messages: List[Message], system_prompt: str = "",
                       temperature: float = 0.7, max_tokens: int = 4096, **_kw) -> LLMResponse:
        return await asyncio.to_thread(self._generate_sync, messages, system_prompt, max_tokens)

    async def generate_with_tools(self, messages: List[Message], tools: List[ToolDefinition],
                                   system_prompt: str = "", temperature: float = 0.7,
                                   max_tokens: int = 4096) -> LLMResponse:
        # No native tool-calling on this graph — callers should check
        # `supports_tools` and route through generate() with Eve's tool
        # loop disabled instead. Kept as a plain-text fallback so the
        # LLMProvider contract is still satisfied if it's ever called.
        return await self.generate(messages, system_prompt=system_prompt, max_tokens=max_tokens)

    async def stream(self, messages: List[Message], system_prompt: str = "",
                     temperature: float = 0.7, max_tokens: int = 4096) -> AsyncIterator[str]:
        response = await self.generate(messages, system_prompt=system_prompt, max_tokens=max_tokens)
        yield response.content
