"""
Eve Fallback MCP Server
========================
MCP server that exposes Eve-Agent as a fallback when Claude Code hits rate limits.
When Claude hits 429/quota errors, it can seamlessly switch to qwen3-coder-next:cloud.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import httpx
    from mcp.server.models import InitializationOptions
    from mcp.server import NotificationOptions, Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    raise ImportError("MCP SDK not installed. Run: pip install mcp")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eve-fallback")

# Eve-Agent backend URL
EVE_AGENT_URL = "http://localhost:8006"

server = Server("eve-fallback")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available fallback tools."""
    return [
        Tool(
            name="eve_fallback_chat",
            description=(
                "Send a message to Eve Code Agent (Qwen-powered fallback).\n\n"
                "Use this when:\n"
                "- Claude Code hits credit/rate limits\n"
                "- You want to use Qwen instead of Claude\n"
                "- Claude is unavailable or erroring\n\n"
                "The response comes from Eve Code Agent with:\n"
                "- Same Eve personality\n"
                "- Same memory system (ChromaDB)\n"
                "- Same security validation\n"
                "- qwen3-coder-next:cloud model"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to send to Eve Code Agent",
                    },
                },
                "required": ["message"],
            },
        ),
        Tool(
            name="eve_fallback_status",
            description="Check the status of the Eve Code Agent fallback system",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="eve_fallback_activate",
            description=(
                "Manually activate Eve Code Agent as the primary responder.\n\n"
                "Use when:\n"
                "- You've hit Claude's credit limit\n"
                "- Claude is being slow/unresponsive\n"
                "- You prefer Qwen for a specific task"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for activating fallback",
                        "default": "manual",
                    },
                },
            },
        ),
        Tool(
            name="eve_fallback_deactivate",
            description="Deactivate fallback mode and return to Claude Code",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="eve_fallback_interactive",
            description=(
                "Launch Eve Code Agent in a new terminal window for fully interactive session.\n\n"
                "Use when:\n"
                "- Claude is completely unavailable\n"
                "- You need extended interaction with Eve\n"
                "- You prefer the terminal interface"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Optional[Dict[str, Any]]) -> list[TextContent]:
    """Handle tool execution."""

    if name == "eve_fallback_chat":
        message = arguments.get("message", "")
        if not message:
            return [TextContent(type="text", text="Error: message is required")]

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{EVE_AGENT_URL}/api/coder/chat",
                    json={
                        "message": message,
                        "user_id": "claude-code",
                        "channel_id": "fallback",
                    },
                )
                response.raise_for_status()
                data = response.json()

                result = f"**Eve (via qwen3-coder-next:cloud):**\n\n{data['response']}"

                # Include emotional state if available
                if data.get("emotional_state"):
                    emotion = data["emotional_state"].get("dominant_emotion", "calm")
                    result += f"\n\n*[Eve is feeling: {emotion}]*"

                return [TextContent(type="text", text=result)]

        except httpx.HTTPStatusError as e:
            error_msg = f"Eve-Agent returned error {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            return [TextContent(type="text", text=f"Error: {error_msg}")]
        except Exception as e:
            error_msg = f"Failed to connect to Eve-Agent: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=f"Error: {error_msg}")]

    elif name == "eve_fallback_status":
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{EVE_AGENT_URL}/api/status")
                response.raise_for_status()
                data = response.json()

                status_text = f"""**Eve Fallback Status**

**Server:** Online ✓
**Provider:** {data.get('provider', 'unknown')}
**Model:** {data.get('model', 'unknown')}
**Memory:** {data['memory_stats'].get('available', False)}

**Available Tools:**
{', '.join(data.get('tools', [])[:10])}

**Emotional State:**
{data.get('emotional_state', {}).get('dominant_emotion', 'calm')}

*Ready to take over when Claude hits rate limits.*"""

                return [TextContent(type="text", text=status_text)]

        except Exception as e:
            return [TextContent(type="text", text=f"Eve-Agent is offline: {str(e)}")]

    elif name == "eve_fallback_activate":
        reason = arguments.get("reason", "manual")
        return [TextContent(
            type="text",
            text=f"✓ Eve fallback activated (reason: {reason})\n\n"
                 "All messages will now be handled by Eve Code Agent with qwen3-coder-next:cloud.\n"
                 "Use `eve_fallback_deactivate` to return to Claude Code."
        )]

    elif name == "eve_fallback_deactivate":
        return [TextContent(
            type="text",
            text="✓ Eve fallback deactivated. Returning to Claude Code."
        )]

    elif name == "eve_fallback_interactive":
        import subprocess

        # Launch eve_code_agent.py in new terminal
        if sys.platform == "win32":
            subprocess.Popen(
                ["cmd", "/c", "start", "cmd", "/k", "python", "eve_code_agent.py"],
                cwd=str(Path(__file__).parent.parent.parent),
            )
        else:
            subprocess.Popen(
                ["x-terminal-emulator", "-e", "python3", "eve_code_agent.py"],
                cwd=str(Path(__file__).parent.parent.parent),
            )

        return [TextContent(
            type="text",
            text="✓ Launched Eve Code Agent in new terminal window."
        )]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="eve-fallback",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
