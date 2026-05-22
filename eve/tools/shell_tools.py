"""
Shell Tools - Command Execution
=================================
Supports workspace-scoped cwd for per-user sandboxing.
"""

import os
import subprocess
from typing import Any, Dict, Optional

from .base import Tool


class ShellTool(Tool):
    name = "shell"
    description = "Execute a shell command. Args: command (str), timeout (int, optional, default 30)"

    def __init__(self, security_validator=None, workspace_root: str = None):
        self.security = security_validator
        self.workspace_root = workspace_root  # Set per-request for user sandboxing

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
            },
            "required": ["command"],
        }

    async def execute(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        if self.security:
            ok, msg = self.security.validate_command(command,
                                                      workspace_root=self.workspace_root)
            if not ok:
                return {"success": False, "error": msg}

        # Lock subprocess cwd to user's workspace (or /app for owner)
        cwd = self.workspace_root or None

        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["powershell", "-Command", command],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=timeout, cwd=cwd,
                )
            else:
                result = subprocess.run(
                    command, shell=True,
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=timeout, cwd=cwd,
                )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:5000],
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Command timed out ({timeout}s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}
