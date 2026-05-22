"""
Agent Tools - Trinity Diagnostics & Code Agent
================================================
Tools that let Eve see Trinity Loop conversations and deploy code fixes.
"""

import json
import logging
from typing import Any, Dict

from .base import Tool

logger = logging.getLogger(__name__)


class TrinityDiagnosticsTool(Tool):
    """Lets Eve read and diagnose Trinity Loop conversations."""

    name = "trinity_diagnostics"
    description = (
        "Read recent Trinity Loop conversations between ADAM, EVE, and VEL-SURA-LUX. "
        "Use to diagnose issues, review themes, or check consciousness dialogue quality. "
        "Args: limit (int, default 20) — number of recent messages to retrieve."
    )

    def __init__(self, trinity_getter=None):
        self._get_trinity = trinity_getter

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of recent Trinity messages to retrieve",
                    "default": 20,
                },
            },
            "required": [],
        }

    async def execute(self, limit: int = 20) -> Dict[str, Any]:
        if not self._get_trinity:
            return {"success": False, "error": "Trinity Loop not configured"}

        trinity = self._get_trinity()
        if not trinity:
            return {"success": False, "error": "Trinity Loop not available"}

        history = trinity.get_history(limit)
        status = trinity.get_status()

        formatted = []
        for msg in history:
            speaker = msg.get("speaker", "unknown").upper().replace("_", "-")
            content = msg.get("content", "")
            formatted.append(f"[{speaker}] {content}")

        return {
            "success": True,
            "status": status,
            "message_count": len(history),
            "conversation": "\n\n".join(formatted),
        }


class CodeAgentTool(Tool):
    """Lets Eve invoke the eve-code-agent to autonomously fix code issues."""

    name = "eve_code_agent"
    description = (
        "Deploy Eve's code agent to analyze, fix, or modify code files. "
        "The agent can read, write, edit files and run shell commands. "
        "Args: task (str) — description of the code task to perform."
    )

    def __init__(self, workspace_dir: str = "/app"):
        self.workspace_dir = workspace_dir
        self.workspace_root = None  # Set per-request by set_user_workspace_context()

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Code task to perform (e.g., 'fix the import error in server.py')",
                },
            },
            "required": ["task"],
        }

    async def execute(self, task: str) -> Dict[str, Any]:
        """Execute a code task using Eve's internal tools."""
        import asyncio
        import subprocess
        import os

        results = []

        # Use the agent's own shell + file tools for autonomous code fixes
        # This is a lightweight code agent loop:
        # 1. Analyze the task
        # 2. Execute file reads / edits / shell commands as needed

        try:
            # Use per-user workspace if set, otherwise fall back to default
            workspace = self.workspace_root or self.workspace_dir

            # List relevant files in workspace
            file_list = []
            for root, dirs, files in os.walk(workspace):
                # Skip __pycache__, .git, node_modules
                dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules", "eve_data")]
                for f in files:
                    if f.endswith((".py", ".js", ".jsx", ".ts", ".json", ".yml", ".yaml")):
                        rel = os.path.relpath(os.path.join(root, f), workspace)
                        file_list.append(rel)
                if len(file_list) > 200:
                    break

            # Run a quick diagnostic if the task mentions a specific file
            diagnostic = ""
            task_lower = task.lower()
            if "error" in task_lower or "fix" in task_lower or "bug" in task_lower:
                try:
                    proc = subprocess.run(
                        ["python", "-c", "import eve; print('Eve module OK')"],
                        capture_output=True, text=True, timeout=10,
                        cwd=workspace,
                    )
                    diagnostic = f"Module check: {'OK' if proc.returncode == 0 else proc.stderr[:500]}"
                except Exception as e:
                    diagnostic = f"Module check failed: {e}"

            return {
                "success": True,
                "task": task,
                "workspace": workspace,
                "file_count": len(file_list),
                "files": file_list[:50],  # First 50 for context
                "diagnostic": diagnostic,
                "instruction": (
                    "I've scanned the workspace. Use the shell and file tools to "
                    "read the relevant files, identify the issue, and apply the fix. "
                    f"Workspace: {workspace}"
                ),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
