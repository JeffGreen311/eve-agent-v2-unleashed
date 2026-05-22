"""
OpenAI LLM Provider
=====================
"""

import json
import logging
from typing import AsyncIterator, Dict, List

from .provider import LLMProvider, LLMResponse, Message, ToolDefinition

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""

    def __init__(self, model: str = "gpt-4o", api_key: str = "", **kwargs):
        super().__init__(model=model, api_key=api_key, **kwargs)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    @property
    def name(self) -> str:
        return "openai"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate(self, messages: List[Message], system_prompt: str = "",
                       temperature: float = 0.7, max_tokens: int = 4096) -> LLMResponse:
        client = self._get_client()
        oai_messages = self._format_messages(messages, system_prompt)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=oai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            choice = response.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                model=self.model,
                finish_reason=choice.finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                },
                raw=response,
            )
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    async def generate_with_tools(self, messages: List[Message],
                                   tools: List[ToolDefinition],
                                   system_prompt: str = "",
                                   temperature: float = 0.7,
                                   max_tokens: int = 4096) -> LLMResponse:
        client = self._get_client()
        oai_messages = self._format_messages(messages, system_prompt)
        oai_tools = [
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

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=oai_messages,
                tools=oai_tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            choice = response.choices[0]
            tool_calls = []
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    args = tc.function.arguments
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            pass
                    tool_calls.append({
                        "id": tc.id,
                        "function": {"name": tc.function.name, "arguments": args},
                    })

            return LLMResponse(
                content=choice.message.content or "",
                tool_calls=tool_calls,
                model=self.model,
                finish_reason="tool_calls" if tool_calls else choice.finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                },
                raw=response,
            )
        except Exception as e:
            logger.error(f"OpenAI tool call failed: {e}")
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    async def stream(self, messages: List[Message], system_prompt: str = "",
                     temperature: float = 0.7, max_tokens: int = 4096) -> AsyncIterator[str]:
        client = self._get_client()
        oai_messages = self._format_messages(messages, system_prompt)

        try:
            stream = client.chat.completions.create(
                model=self.model,
                messages=oai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"Error: {e}"

    def _format_messages(self, messages: List[Message], system_prompt: str) -> List[Dict]:
        formatted = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        for msg in messages:
            formatted.append({"role": msg.role, "content": msg.content})
        return formatted
