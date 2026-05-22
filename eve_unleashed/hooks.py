#!/usr/bin/env python3
"""
Hooks System for EveUnleashed

Provides safety and verification hooks for tool execution:
- BashSafetyParser: Blocks dangerous bash commands
- HookManager: Manages pre/post hooks for all tools
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass


@dataclass
class HookResult:
    """Result from a hook execution"""
    allowed: bool
    message: str = ""
    
    
class BashSafetyParser:
    """
    Analyzes bash commands for dangerous patterns.
    
    Blocks commands that could:
    - Delete critical system files
    - Modify system with elevated privileges
    - Format disks or overwrite devices
    - Execute arbitrary remote code
    - Create fork bombs
    """
    
    # Patterns that are always blocked (compiled regex)
    BLOCKED_PATTERNS = [
        # Destructive file operations on root/system paths
        # Matches: rm -rf /, rm --recursive --force /, rm -r /, etc.
        (r'rm\s+(-[rfvI]+\s+)*/', "Delete from root path"),
        (r'rm\s+(-[rfvI]+\s+)*(~|/home|/Users)', "Delete user home directory"),
        (r'rm\s+(-[rfvI]+\s+)*/etc', "Delete system config"),
        (r'rm\s+(-[rfvI]+\s+)*/usr', "Delete system binaries"),
        (r'rm\s+(-[rfvI]+\s+)*/var', "Delete system data"),
        (r'rm\s+(-[rfvI]+\s+)*/boot', "Delete boot files"),
        # Long-form flag handling
        (r'rm\s+.*--recursive.*/', "Delete recursively from root"),
        (r'rm\s+.*--force.*/', "Force delete from root"),
        
        # Elevated privilege commands
        (r'\bsudo\s+', "Elevated privileges (sudo)"),
        (r'\bsu\s+-', "Switch user"),
        (r'\bdoas\s+', "Elevated privileges (doas)"),
        
        # Dangerous permission changes
        (r'chmod\s+(-[R]+\s+)?777\s+/', "Dangerous permissions on root"),
        (r'chmod\s+(-[R]+\s+)?777\s+~', "Dangerous permissions on home"),
        (r'chown\s+(-[R]+\s+)?root', "Change ownership to root"),
        
        # Disk/device operations
        (r'>\s*/dev/sd[a-z]', "Write to disk device"),
        (r'>\s*/dev/nvme', "Write to NVMe device"),
        (r'\bmkfs\.', "Format filesystem"),
        (r'\bdd\s+.*of=/dev/', "Direct disk write"),
        (r'\bfdisk\s+', "Partition disk"),
        (r'\bparted\s+', "Partition disk"),
        
        # Fork bombs and resource exhaustion
        (r':\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;?\s*:', "Fork bomb"),
        (r'\bfork\s*\(\s*\)\s*while', "Fork bomb"),
        
        # Remote code execution
        (r'curl\s+.*\|\s*(ba)?sh', "Piped remote execution (curl)"),
        (r'wget\s+.*\|\s*(ba)?sh', "Piped remote execution (wget)"),
        (r'curl\s+.*\|\s*python', "Piped remote execution (curl to python)"),
        (r'wget\s+.*\|\s*python', "Piped remote execution (wget to python)"),
        
        # Dangerous eval patterns
        (r'\beval\s+.*\$\(', "Eval with command substitution"),
        (r'\beval\s+.*`', "Eval with backtick substitution"),
        
        # System shutdown/reboot
        (r'\bshutdown\s+', "System shutdown"),
        (r'\breboot\b', "System reboot"),
        (r'\binit\s+[06]', "System halt/reboot"),
        (r'\bhalt\b', "System halt"),
        (r'\bpoweroff\b', "System poweroff"),
        
        # Network attacks (basic patterns)
        (r'\bnmap\s+-', "Network scanning"),
        
        # History manipulation (potential evidence hiding)
        (r'history\s+-[cd]', "Clear command history"),
        (r'>\s*~/\..*_history', "Overwrite history file"),
    ]
    
    # Commands that are always allowed (override blocks)
    ALLOWED_OVERRIDES = [
        r'rm\s+(-[rfvI]+\s+)*/tmp/',  # Cleaning temp is OK
        r'rm\s+(-[rfvI]+\s+)*\./node_modules',  # Project cleanup
        r'rm\s+(-[rfvI]+\s+)*\./__pycache__',  # Python cleanup
    ]
    
    def __init__(self, custom_blocked: Optional[List[str]] = None, 
                 custom_allowed: Optional[List[str]] = None):
        """
        Initialize the safety parser.
        
        Args:
            custom_blocked: Additional patterns to block
            custom_allowed: Additional patterns to allow (override blocks)
        """
        self.custom_blocked = custom_blocked or []
        self.custom_allowed = custom_allowed or []
        
        # Compile all patterns for efficiency
        self._compiled_blocked = [
            (re.compile(pattern, re.IGNORECASE), reason) 
            for pattern, reason in self.BLOCKED_PATTERNS
        ]
        self._compiled_custom_blocked = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.custom_blocked
        ]
        self._compiled_allowed = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.ALLOWED_OVERRIDES + self.custom_allowed
        ]
    
    def check_command(self, command: str) -> Tuple[bool, str]:
        """
        Check if a bash command is safe to execute.
        
        Args:
            command: The bash command to check
            
        Returns:
            Tuple of (is_safe, reason)
            - is_safe: True if command is safe to execute
            - reason: Explanation if blocked, empty string if safe
        """
        if not command or not command.strip():
            return True, ""
        
        # Normalize command (collapse whitespace, strip)
        normalized = ' '.join(command.split())
        
        # Check allowed overrides first
        for pattern in self._compiled_allowed:
            if pattern.search(normalized):
                return True, ""
        
        # Check blocked patterns
        for pattern, reason in self._compiled_blocked:
            if pattern.search(normalized):
                return False, f"Dangerous command blocked: {reason}"
        
        # Check custom blocked patterns
        for pattern in self._compiled_custom_blocked:
            if pattern.search(normalized):
                return False, "Command matches custom blocked pattern"
        
        return True, ""
    
    def add_blocked_pattern(self, pattern: str) -> None:
        """Add a pattern to the blocked list"""
        self.custom_blocked.append(pattern)
        self._compiled_custom_blocked.append(
            re.compile(pattern, re.IGNORECASE)
        )
    
    def add_allowed_pattern(self, pattern: str) -> None:
        """Add a pattern to the allowed override list"""
        self.custom_allowed.append(pattern)
        self._compiled_allowed.append(
            re.compile(pattern, re.IGNORECASE)
        )


class HookManager:
    """
    Manages pre/post hooks for tool execution.
    
    Hook events:
    - pre_bash: Before bash command execution
    - post_bash: After bash command execution
    - pre_edit: Before file edit
    - post_edit: After file edit
    - pre_write: Before file write
    - post_write: After file write
    - pre_tool: Before any tool (generic)
    - post_tool: After any tool (generic)
    
    Hooks are loaded from:
    1. ~/.eve_unleashed/hooks/ (global)
    2. .eve_unleashed/hooks/ (project, overrides global)
    """
    
    def __init__(self, project_dir: Optional[Path] = None):
        """
        Initialize the hook manager.
        
        Args:
            project_dir: Project directory for project-specific hooks
        """
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.global_hooks_dir = Path.home() / ".eve_unleashed" / "hooks"
        self.project_hooks_dir = self.project_dir / ".eve_unleashed" / "hooks"
        
        # Initialize safety parser
        self.safety_parser = BashSafetyParser()
        
        # Hook configuration
        self.config: Dict[str, Any] = {}
        
        # Registered hooks (event -> list of callables)
        self._hooks: Dict[str, List[Callable]] = {}
        
        # Load configuration
        self._load_config()
        
        # Register built-in hooks
        self._register_builtin_hooks()
    
    def _load_config(self) -> None:
        """Load hook configuration from yaml files"""
        # Try global config first
        global_config_path = self.global_hooks_dir / "config.yaml"
        if global_config_path.exists():
            try:
                with open(global_config_path, 'r') as f:
                    self.config = yaml.safe_load(f) or {}
            except Exception:
                self.config = {}
        
        # Override with project config
        project_config_path = self.project_hooks_dir / "config.yaml"
        if project_config_path.exists():
            try:
                with open(project_config_path, 'r') as f:
                    project_config = yaml.safe_load(f) or {}
                    self._deep_merge(self.config, project_config)
            except Exception:
                pass
        
        # Load custom blocked patterns
        self._load_custom_patterns()
    
    def _load_custom_patterns(self) -> None:
        """Load custom blocked/allowed patterns from files"""
        # Load blocked patterns
        for hooks_dir in [self.global_hooks_dir, self.project_hooks_dir]:
            blocked_file = hooks_dir / "blocked.txt"
            if blocked_file.exists():
                try:
                    with open(blocked_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                self.safety_parser.add_blocked_pattern(line)
                except Exception:
                    pass
            
            # Load allowed patterns
            allowed_file = hooks_dir / "allowed.txt"
            if allowed_file.exists():
                try:
                    with open(allowed_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                self.safety_parser.add_allowed_pattern(line)
                except Exception:
                    pass
    
    def _deep_merge(self, base: Dict, override: Dict) -> None:
        """Deep merge override into base dict"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _register_builtin_hooks(self) -> None:
        """Register built-in safety hooks"""
        # Bash safety hook
        self.register_hook("pre_bash", self._bash_safety_hook)
    
    def _bash_safety_hook(self, context: Dict[str, Any]) -> HookResult:
        """Built-in bash safety hook"""
        command = context.get("command", "")
        is_safe, reason = self.safety_parser.check_command(command)
        return HookResult(allowed=is_safe, message=reason)
    
    def register_hook(self, event: str, hook: Callable[[Dict[str, Any]], HookResult]) -> None:
        """
        Register a hook for an event.
        
        Args:
            event: Event name (e.g., 'pre_bash', 'post_edit')
            hook: Callable that takes context dict and returns HookResult
        """
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(hook)
    
    def unregister_hook(self, event: str, hook: Callable) -> None:
        """Unregister a hook from an event"""
        if event in self._hooks and hook in self._hooks[event]:
            self._hooks[event].remove(hook)
    
    def run_pre_hook(self, event: str, context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Run pre-hooks for an event.
        
        Pre-hooks can block execution by returning HookResult(allowed=False, ...).
        All hooks must pass for execution to proceed.
        
        Args:
            event: Event name (e.g., 'pre_bash')
            context: Context dictionary with relevant data
            
        Returns:
            Tuple of (allowed, message)
            - allowed: True if all hooks passed
            - message: First failure message, or empty if all passed
        """
        # Check if hooks are enabled in config
        hook_config = self.config.get("hooks", {})
        if hook_config.get("disabled", False):
            return True, ""
        
        # Run all registered hooks for this event
        hooks = self._hooks.get(event, [])
        for hook in hooks:
            try:
                result = hook(context)
                if not result.allowed:
                    return False, result.message
            except Exception as e:
                # Log but don't block on hook errors
                pass
        
        return True, ""
    
    def run_post_hook(self, event: str, context: Dict[str, Any]) -> None:
        """
        Run post-hooks for an event.
        
        Post-hooks are informational only and cannot block execution.
        They can be used for logging, metrics, or async verification.
        
        Args:
            event: Event name (e.g., 'post_bash')
            context: Context dictionary with relevant data
        """
        # Check if hooks are enabled in config
        hook_config = self.config.get("hooks", {})
        if hook_config.get("disabled", False):
            return
        
        # Run all registered hooks for this event
        hooks = self._hooks.get(event, [])
        for hook in hooks:
            try:
                hook(context)
            except Exception:
                # Silently ignore post-hook errors
                pass
    
    def is_bash_safe(self, command: str) -> Tuple[bool, str]:
        """
        Convenience method to check bash command safety.
        
        Args:
            command: Bash command to check
            
        Returns:
            Tuple of (is_safe, reason)
        """
        return self.safety_parser.check_command(command)
    
    def get_hook_status(self) -> Dict[str, Any]:
        """Get current hook system status"""
        return {
            "enabled": not self.config.get("hooks", {}).get("disabled", False),
            "global_dir": str(self.global_hooks_dir),
            "project_dir": str(self.project_hooks_dir),
            "registered_events": list(self._hooks.keys()),
            "blocked_patterns": len(self.safety_parser.BLOCKED_PATTERNS) + len(self.safety_parser.custom_blocked),
        }


# Convenience function for quick safety checks
def check_bash_safety(command: str) -> Tuple[bool, str]:
    """
    Quick check if a bash command is safe.
    
    Args:
        command: The bash command to check
        
    Returns:
        Tuple of (is_safe, reason)
    """
    parser = BashSafetyParser()
    return parser.check_command(command)
