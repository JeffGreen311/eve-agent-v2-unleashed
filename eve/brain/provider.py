"""
LLM Provider Abstraction
=========================
Base class for all LLM providers with unified interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional


@dataclass
class Message:
    """A conversation message."""
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    images: Optional[List[str]] = None  # base64-encoded images for vision models
    thinking: Optional[str] = None  # Ollama thinking trace for assistant messages in tool loops


@dataclass
class ToolDefinition:
    """Definition of a tool for the LLM."""
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str = ""
    tool_calls: List[Dict] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: Dict[str, int] = field(default_factory=dict)
    model: str = ""
    raw: Any = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, model: str, api_key: str = "", **kwargs):
        self.model = model
        self.api_key = api_key
        self._kwargs = kwargs

    @abstractmethod
    async def generate(self, messages: List[Message],
                       system_prompt: str = "",
                       temperature: float = 0.7,
                       max_tokens: int = 4096) -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    @abstractmethod
    async def generate_with_tools(self, messages: List[Message],
                                   tools: List[ToolDefinition],
                                   system_prompt: str = "",
                                   temperature: float = 0.7,
                                   max_tokens: int = 4096) -> LLMResponse:
        """Generate a response with tool calling support."""
        ...

    @abstractmethod
    async def stream(self, messages: List[Message],
                     system_prompt: str = "",
                     temperature: float = 0.7,
                     max_tokens: int = 4096) -> AsyncIterator[str]:
        """Stream a response token by token."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...

    @property
    def is_available(self) -> bool:
        """Check if this provider is available."""
        return True
