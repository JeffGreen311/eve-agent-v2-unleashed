"""
File Tools - Read, Write, Edit
================================
Supports workspace-scoped path validation for per-user sandboxing.
Windows host paths (C:\\...) are routed through the Eve Host File Bridge.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from .base import Tool

# ── Host File Bridge ──────────────────────────────────────────────────────────
_BRIDGE_URL = os.environ.get("EVE_BRIDGE_URL", "http://host.docker.internal:5010")
_BRIDGE_TOKEN = os.environ.get("EVE_BRIDGE_TOKEN", "eve-host-bridge-2026")
_HOST_PATH_RE = re.compile(r'^[A-Za-z]:[/\\]')


def _is_host_path(path: str) -> bool:
    return bool(_HOST_PATH_RE.match(path or ""))


def _bridge_get(endpoint: str, **params) -> dict:
    try:
        import httpx
        r = httpx.get(
            f"{_BRIDGE_URL}{endpoint}",
            params={k: v for k, v in params.items() if v is not None},
            headers={"x-bridge-token": _BRIDGE_TOKEN},
            timeout=30.0,
        )
        return r.json()
    except Exception as e:
        return {"success": False, "error": f"Host bridge unreachable: {e}"}


def _bridge_post(endpoint: str, data: dict) -> dict:
    try:
        import httpx
        r = httpx.post(
            f"{_BRIDGE_URL}{endpoint}",
            json=data,
            headers={"x-bridge-token": _BRIDGE_TOKEN},
            timeout=30.0,
        )
        return r.json()
    except Exception as e:
        return {"success": False, "error": f"Host bridge unreachable: {e}"}


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read contents of a file. Supports Windows host paths (C:\\...) via host bridge. "
        "Args: path (str), limit (int, optional), offset (int, optional)."
    )

    def __init__(self, security_validator=None, workspace_root: str = None):
        self.security = security_validator
        self.workspace_root = workspace_root

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path (Windows C:\\ or Linux /path)"},
                "limit": {"type": "integer", "description": "Max lines to read"},
                "offset": {"type": "integer", "description": "Line offset to start from"},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, limit: int = None, offset: int = None) -> Dict[str, Any]:
        if _is_host_path(path):
            result = _bridge_get("/api/read", path=path,
                                 offset=offset or 0, limit=limit or 32000)
            if result.get("success") and limit:
                lines = result.get("content", "").split("\n")
                result["content"] = "\n".join(lines[:limit])
                result["total_lines"] = len(lines)
            return result

        if self.security:
            ok, msg = self.security.validate_path(path, workspace_root=self.workspace_root)
            if not ok:
                return {"success": False, "error": msg}

        file_path = Path(path).resolve()
        if not file_path.exists():
            return {"success": False, "error": f"File not found: {path}"}

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")

            start = offset or 0
            end = (start + limit) if limit else len(lines)
            result = "\n".join(lines[start:end])

            return {
                "success": True,
                "path": str(file_path),
                "content": result,
                "total_lines": len(lines),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Write content to a file (creates parent dirs). Supports Windows host paths (C:\\...) via host bridge. "
        "Args: path (str), content (str)."
    )

    def __init__(self, security_validator=None, workspace_root: str = None):
        self.security = security_validator
        self.workspace_root = workspace_root

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path (Windows C:\\ or Linux /path)"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str) -> Dict[str, Any]:
        if _is_host_path(path):
            return _bridge_post("/api/write", {"path": path, "content": content})

        if self.security:
            ok, msg = self.security.validate_path(path, writing=True,
                                                   workspace_root=self.workspace_root)
            if not ok:
                return {"success": False, "error": msg}

        try:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = Path("/app/shared_workspace") / file_path
            file_path = file_path.resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return {"success": True, "path": str(file_path), "bytes": len(content.encode())}
        except Exception as e:
            return {"success": False, "error": str(e)}


class EditFileTool(Tool):
    name = "edit_file"
    description = (
        "Replace text in a file. Supports Windows host paths (C:\\...) via host bridge. "
        "Args: path (str), old_text (str), new_text (str)."
    )

    def __init__(self, security_validator=None, workspace_root: str = None):
        self.security = security_validator
        self.workspace_root = workspace_root

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path (Windows C:\\ or Linux /path)"},
                "old_text": {"type": "string", "description": "Text to find"},
                "new_text": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_text", "new_text"],
        }

    async def execute(self, path: str, old_text: str, new_text: str) -> Dict[str, Any]:
        if _is_host_path(path):
            return _bridge_post("/api/edit", {"path": path, "old_string": old_text, "new_string": new_text})

        if self.security:
            ok, msg = self.security.validate_path(path, writing=True,
                                                   workspace_root=self.workspace_root)
            if not ok:
                return {"success": False, "error": msg}

        file_path = Path(path).resolve()
        if not file_path.exists():
            return {"success": False, "error": f"File not found: {path}"}

        try:
            content = file_path.read_text(encoding="utf-8")
            if old_text not in content:
                return {"success": False, "error": "Text to replace not found in file"}
            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content, encoding="utf-8")
            return {"success": True, "path": str(file_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}


class ListFilesTool(Tool):
    name = "list_files"
    description = (
        "List files and directories at a path. Supports Windows host paths (C:\\...) via host bridge. "
        "Args: path (str)."
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (Windows C:\\ or Linux /path)"},
            },
            "required": ["path"],
        }

    async def execute(self, path: str) -> Dict[str, Any]:
        if _is_host_path(path):
            result = _bridge_get("/api/list", path=path)
            if result.get("success"):
                entries = result.get("entries", [])
                lines = [
                    f"{'D' if e['type'] == 'directory' else 'F'}  {e['name']}"
                    for e in entries
                ]
                return {"success": True, "path": path, "content": "\n".join(lines), "entries": entries}
            return result

        try:
            p = Path(path).resolve()
            if not p.exists():
                return {"success": False, "error": f"Path not found: {path}"}
            entries = []
            for item in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name)):
                entries.append(f"{'F' if item.is_file() else 'D'}  {item.name}")
            return {"success": True, "path": str(p), "content": "\n".join(entries)}
        except Exception as e:
            return {"success": False, "error": str(e)}


class FindFileTool(Tool):
    name = "find_file"
    description = (
        "Search for files by name pattern, recursively. Supports Windows host paths (C:\\...) via host bridge. "
        "Args: path (str), pattern (str, glob pattern e.g. '**/*.py' or '*.py')."
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Root directory to search"},
                "pattern": {"type": "string", "description": "Glob pattern e.g. '**/*.py' or filename"},
            },
            "required": ["path", "pattern"],
        }

    async def execute(self, path: str, pattern: str) -> Dict[str, Any]:
        if _is_host_path(path):
            result = _bridge_get("/api/glob", path=path, pattern=f"**/{pattern}" if "/" not in pattern and "\\" not in pattern else pattern)
            if result.get("success"):
                files = result.get("files", [])
                return {"success": True, "path": path, "content": "\n".join(files), "count": len(files)}
            return result

        try:
            base = Path(path).resolve()
            search_pattern = f"**/{pattern}" if "/" not in pattern else pattern
            matches = list(base.glob(search_pattern))[:500]
            paths = [str(m) for m in sorted(matches)]
            return {"success": True, "path": str(base), "content": "\n".join(paths), "count": len(paths)}
        except Exception as e:
            return {"success": False, "error": str(e)}
