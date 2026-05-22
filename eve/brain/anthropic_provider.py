"""
Anthropic (Claude) LLM Provider
=================================
"""

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

    def _get_client(self):
        if self._client is None:
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

    async def generate(self, messages: List[Message], system_prompt: str = "",
                       temperature: float = 0.7, max_tokens: int = 4096) -> LLMResponse:
        client = self._get_client()
        claude_messages = [{"role": m.role, "content": m.content} for m in messages
                          if m.role in ("user", "assistant")]

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
        claude_messages = [{"role": m.role, "content": m.content} for m in messages
                          if m.role in ("user", "assistant")]

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
                if hasattr(block, "text"):
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
        claude_messages = [{"role": m.role, "content": m.content} for m in messages
                          if m.role in ("user", "assistant")]

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
