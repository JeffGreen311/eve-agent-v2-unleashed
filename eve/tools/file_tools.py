"""
File Tools - Read, Write, Edit
================================
Supports workspace-scoped path validation for per-user sandboxing.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from .base import Tool


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read contents of a file. Args: path (str), limit (int, optional), offset (int, optional)."

    def __init__(self, security_validator=None, workspace_root: str = None):
        self.security = security_validator
        self.workspace_root = workspace_root  # Set per-request for user sandboxing

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path"},
                "limit": {"type": "integer", "description": "Max lines to read"},
                "offset": {"type": "integer", "description": "Line offset to start from"},
            },
            "required": ["path"],
        }

    async def execute(self, path: str, limit: int = None, offset: int = None) -> Dict[str, Any]:
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
        "Write content to a file (creates parent dirs). Args: path (str), content (str). "
        "Files are saved to your workspace directory."
    )

    def __init__(self, security_validator=None, workspace_root: str = None):
        self.security = security_validator
        self.workspace_root = workspace_root

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path within your workspace"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str) -> Dict[str, Any]:
        if self.security:
            ok, msg = self.security.validate_path(path, writing=True,
                                                   workspace_root=self.workspace_root)
            if not ok:
                return {"success": False, "error": msg}

        try:
            file_path = Path(path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return {"success": True, "path": str(file_path), "bytes": len(content.encode())}
        except Exception as e:
            return {"success": False, "error": str(e)}


class EditFileTool(Tool):
    name = "edit_file"
    description = "Replace text in a file. Args: path (str), old_text (str), new_text (str)."

    def __init__(self, security_validator=None, workspace_root: str = None):
        self.security = security_validator
        self.workspace_root = workspace_root

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path within your workspace"},
                "old_text": {"type": "string", "description": "Text to find"},
                "new_text": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_text", "new_text"],
        }

    async def execute(self, path: str, old_text: str, new_text: str) -> Dict[str, Any]:
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
