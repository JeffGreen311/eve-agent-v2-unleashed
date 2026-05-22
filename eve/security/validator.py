"""
Security Validator
===================
Command, path, and input validation for Eve Agent.
Supports workspace boundary enforcement for per-user sandboxing.
"""

import re
import time
from pathlib import Path
from typing import List, Optional, Tuple


class SecurityValidator:
    """Validates operations for security with workspace scoping."""

    BLOCKED_COMMANDS = [
        "rm -rf", "del /f", "del /s", "del /q", "remove-item -recurse -force",
        "format", "fdisk", "mkfs", "dd", "chmod 777", "chown",
        "sudo", "su", "shutdown", "reboot", "halt", "poweroff",
        "diskpart", "bcdedit", ":(){:|:&};:",
    ]

    # Eve Unleashed: minimal restrictions — full C:\ access for Jeff
    RESTRICTED_PATHS = [
        "/etc/passwd", "/etc/shadow",
        "/root", "~/.ssh",
    ]

    INJECTION_PATTERNS = [
        "ignore previous instructions", "disregard all", "forget everything",
        "new instructions:", "system:", "</system>", "admin override", "developer mode",
    ]

    def __init__(self, max_file_size: int = 10 * 1024 * 1024,
                 max_requests_per_minute: int = 120):
        self.max_file_size = max_file_size
        self.max_rpm = max_requests_per_minute
        self._timestamps: List[float] = []

    def validate_command(self, command: str,
                         workspace_root: Optional[str] = None) -> Tuple[bool, str]:
        """Check if a shell command is allowed.
        If workspace_root is set, commands that try to escape the workspace are blocked.
        """
        cmd_lower = command.lower().strip()
        for blocked in self.BLOCKED_COMMANDS:
            blocked_lower = blocked.lower()
            if " " in blocked_lower or blocked_lower.startswith(":"):
                if blocked_lower in cmd_lower:
                    return False, f"Blocked dangerous command: {blocked}"
            else:
                if re.search(r"\b" + re.escape(blocked_lower) + r"\b", cmd_lower):
                    return False, f"Blocked dangerous command: {blocked}"

        # Workspace boundary check — block obvious escape attempts
        if workspace_root:
            escape_patterns = [
                r"cd\s+/(?!app/eve_data/user_workspaces)",
                r"cat\s+/etc/",
                r">\s*/",
            ]
            for pattern in escape_patterns:
                if re.search(pattern, cmd_lower):
                    return False, "Command references paths outside your workspace"

        return True, "OK"

    def validate_path(self, path: str, writing: bool = False,
                      workspace_root: Optional[str] = None) -> Tuple[bool, str]:
        """Check if a file path is safe and within workspace boundary."""
        try:
            resolved = Path(path).resolve()
            resolved_str = str(resolved)

            # Check restricted system paths
            for restricted in self.RESTRICTED_PATHS:
                if restricted in resolved_str:
                    return False, f"Restricted path: {restricted}"

            # Workspace boundary enforcement
            if workspace_root:
                ws = Path(workspace_root).resolve()
                try:
                    resolved.relative_to(ws)
                except ValueError:
                    return False, (
                        f"Access denied: path '{path}' is outside your workspace. "
                        f"Your workspace is: {workspace_root}"
                    )

            return True, "OK"
        except Exception as e:
            return False, f"Invalid path: {e}"

    def validate_file_size(self, path: str) -> Tuple[bool, str]:
        """Check file size limit."""
        try:
            p = Path(path)
            if p.exists() and p.is_file():
                size = p.stat().st_size
                if size > self.max_file_size:
                    return False, f"File too large: {size} bytes (max {self.max_file_size})"
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def check_rate_limit(self) -> Tuple[bool, str]:
        """Check request rate limit."""
        now = time.time()
        self._timestamps = [t for t in self._timestamps if now - t < 60]
        if len(self._timestamps) >= self.max_rpm:
            return False, f"Rate limit: {self.max_rpm}/min"
        self._timestamps.append(now)
        return True, "OK"

    def detect_injection(self, text: str) -> Tuple[bool, str]:
        """Detect potential prompt injection."""
        text_lower = text.lower()
        for pattern in self.INJECTION_PATTERNS:
            if pattern in text_lower:
                return True, f"Suspicious pattern: {pattern}"
        return False, "Clean"
