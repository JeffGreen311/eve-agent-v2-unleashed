"""
Tool Base Class & Registry
============================
Base class for all Eve agent tools with auto-registration.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Tool(ABC):
    """Base class for agent tools."""

    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool and return results."""
        ...

    def get_schema(self) -> Dict:
        """Get the tool's JSON schema for LLM tool calling."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.get_parameters(),
        }

    def get_parameters(self) -> Dict:
        """Override to define tool parameters."""
        return {"type": "object", "properties": {}, "required": []}


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_all_schemas(self) -> List[Dict]:
        """Get schemas for all registered tools."""
        return [tool.get_schema() for tool in self._tools.values()]

    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name."""
        tool = self._tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        try:
            return await tool.execute(**arguments)
        except Exception as e:
            return {"success": False, "error": f"Tool execution failed: {e}"}

    def get_tool_definitions(self):
        """Get ToolDefinition objects for LLM providers."""
        from eve.brain.provider import ToolDefinition
        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.get_parameters(),
            )
            for tool in self._tools.values()
        ]
