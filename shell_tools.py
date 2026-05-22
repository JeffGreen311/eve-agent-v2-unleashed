"""
Shell Tools - Command Execution
=================================
Supports workspace-scoped cwd for per-user sandboxing.
Windows host paths route through the Eve Host File Bridge.
"""

import os
import re
import subprocess
from typing import Any, Dict, Optional

from .base import Tool

_BRIDGE_URL = os.environ.get("EVE_BRIDGE_URL", "http://host.docker.internal:5010")
_BRIDGE_TOKEN = os.environ.get("EVE_BRIDGE_TOKEN", "eve-host-bridge-2026")
_HOST_PATH_RE = re.compile(r'^[A-Za-z]:[/\\]')


def _is_host_path(path: str) -> bool:
    return bool(_HOST_PATH_RE.match(path or ""))


def _bridge_bash(command: str, cwd: str, timeout: int) -> dict:
    try:
        import httpx
        r = httpx.post(
            f"{_BRIDGE_URL}/api/bash",
            json={"command": command, "cwd": cwd, "timeout": timeout},
            headers={"x-bridge-token": _BRIDGE_TOKEN},
            timeout=float(timeout) + 5,
        )
        return r.json()
    except Exception as e:
        return {"success": False, "error": f"Host bridge unreachable: {e}"}


class ShellTool(Tool):
    name = "shell"
    description = (
        "Execute a shell command. When working with Windows host paths (C:\\...) "
        "commands run on the Windows host via bridge (use PowerShell/cmd syntax). "
        "Args: command (str), cwd (str, optional), timeout (int, optional, default 30)"
    )

    def __init__(self, security_validator=None, workspace_root: str = None):
        self.security = security_validator
        self.workspace_root = workspace_root

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "cwd": {"type": "string", "description": "Working directory (use Windows path for host, Linux path for container)"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
            },
            "required": ["command"],
        }

    async def execute(self, command: str, cwd: str = None, timeout: int = 30) -> Dict[str, Any]:
        if self.security:
            ok, msg = self.security.validate_command(command,
                                                      workspace_root=self.workspace_root)
            if not ok:
                return {"success": False, "error": msg}

        effective_cwd = cwd or self.workspace_root or "/app/shared_workspace"

        # Also detect Windows paths referenced inside the command itself
        _win_in_cmd = re.search(r'([A-Za-z]:[/\\][\w/\\]*)', command)

        # Route to host bridge when cwd is Windows OR command references a Windows path
        if _is_host_path(effective_cwd) or _win_in_cmd:
            bridge_cwd = effective_cwd if _is_host_path(effective_cwd) else (_win_in_cmd.group(1) if _win_in_cmd else "C:\\")
            return _bridge_bash(command, bridge_cwd, min(timeout, 120))

        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["powershell", "-Command", command],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=timeout, cwd=effective_cwd,
                )
            else:
                result = subprocess.run(
                    command, shell=True,
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=timeout, cwd=effective_cwd,
                )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:5000],
                "returncode": result.returncode,
                "content": result.stdout[:10000] or result.stderr[:5000],
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Command timed out ({timeout}s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}
