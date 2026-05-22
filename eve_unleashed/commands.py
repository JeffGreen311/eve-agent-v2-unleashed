#!/usr/bin/env python3
"""
Custom Commands System for EveUnleashed

Allows users to define custom slash commands in markdown files with YAML frontmatter.
Commands are loaded from:
- ~/.eve_unleashed/commands/ (global)
- .eve_unleashed/commands/ (project-specific, overrides global)
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class Command:
    """Represents a custom slash command"""
    name: str
    description: str
    content: str
    source: str  # 'global' or 'project'
    file_path: Path
    
    # Optional metadata
    model: Optional[str] = None
    auto_mode: bool = False
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class CommandManager:
    """
    Manages custom slash commands.
    
    Commands are markdown files with YAML frontmatter:
    
    ```markdown
    ---
    name: fix-lint
    description: Fix all lint errors
    auto_mode: true
    ---
    Find and fix all lint errors in the project. 
    Use ruff or eslint depending on the project type.
    ```
    """
    
    # All command/skill source directories
    EVE_COMMAND_DIRS = [
        Path.home() / ".eve_unleashed" / "commands",
        Path.home() / ".qwen" / "skills",
        Path(__file__).parent.parent / ".claude" / "commands",
        Path(__file__).parent.parent / ".claude" / "skills",
    ]

    def __init__(self, project_dir: Optional[Path] = None):
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.global_commands_dir = Path.home() / ".eve_unleashed" / "commands"
        self.project_commands_dir = self.project_dir / ".eve_unleashed" / "commands"

        self._commands: Dict[str, Command] = {}
        
        # Load commands on init
        self.reload_commands()
    
    def reload_commands(self) -> None:
        """Reload all commands from all Eve source directories"""
        self._commands = {}

        # Load from all Eve command/skill directories
        for cmd_dir in self.EVE_COMMAND_DIRS:
            if cmd_dir.exists():
                self._load_commands_from_dir(cmd_dir, source=str(cmd_dir.name))
                # Also scan subdirectories (skills have nested dirs)
                for sub in cmd_dir.iterdir():
                    if sub.is_dir():
                        self._load_commands_from_dir(sub, source=str(sub.name))

        # Load global commands
        if self.global_commands_dir.exists():
            self._load_commands_from_dir(self.global_commands_dir, source='global')

        # Load project commands (override everything)
        if self.project_commands_dir.exists():
            self._load_commands_from_dir(self.project_commands_dir, source='project')
    
    def _load_commands_from_dir(self, directory: Path, source: str) -> None:
        """Load all command files from a directory"""
        for file_path in directory.glob("*.md"):
            try:
                command = self._parse_command_file(file_path, source)
                if command:
                    self._commands[command.name] = command
            except Exception:
                # Skip invalid command files
                pass
    
    def _parse_command_file(self, file_path: Path, source: str) -> Optional[Command]:
        """Parse a command file with YAML frontmatter"""
        content = file_path.read_text()
        
        # Parse YAML frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        
        if frontmatter_match:
            try:
                metadata = yaml.safe_load(frontmatter_match.group(1))
                body = content[frontmatter_match.end():].strip()
            except yaml.YAMLError:
                metadata = {}
                body = content
        else:
            # No frontmatter, use filename as name
            metadata = {}
            body = content.strip()
        
        # Get name from frontmatter or filename
        name = metadata.get('name', file_path.stem)
        
        # Ensure name starts with / for consistency
        if not name.startswith('/'):
            name = f"/{name}"
        
        return Command(
            name=name,
            description=metadata.get('description', f'Custom command: {name}'),
            content=body,
            source=source,
            file_path=file_path,
            model=metadata.get('model'),
            auto_mode=metadata.get('auto_mode', False),
            tags=metadata.get('tags', [])
        )
    
    def get_command(self, name: str) -> Optional[Command]:
        """Get a command by name"""
        # Normalize name
        if not name.startswith('/'):
            name = f"/{name}"
        return self._commands.get(name)
    
    def list_commands(self) -> List[Command]:
        """List all available commands"""
        return list(self._commands.values())
    
    def get_completions(self) -> List[str]:
        """Get command names for tab completion"""
        return list(self._commands.keys())
    
    def execute_command(self, name: str, args: str = "") -> Dict[str, Any]:
        """
        Prepare a command for execution.
        
        Returns a dict with:
        - prompt: The prompt to send to the AI
        - auto_mode: Whether to run in auto mode
        - model: Optional model override
        """
        command = self.get_command(name)
        if not command:
            return {"error": f"Unknown command: {name}"}
        
        # Build the prompt
        prompt = command.content
        if args:
            prompt = f"{prompt}\n\nAdditional context: {args}"
        
        return {
            "prompt": prompt,
            "auto_mode": command.auto_mode,
            "model": command.model,
            "description": command.description
        }
    
    def create_example_commands(self) -> None:
        """Create example command files if none exist"""
        # Only create if directory doesn't exist or is empty
        if self.global_commands_dir.exists() and list(self.global_commands_dir.glob("*.md")):
            return
        
        self.global_commands_dir.mkdir(parents=True, exist_ok=True)
        
        examples = [
            {
                "filename": "fix-lint.md",
                "content": """---
name: /fix-lint
description: Find and fix lint errors
auto_mode: true
tags: [code-quality]
---
Find and fix all lint errors in this project.

1. Identify the project type (Python, JavaScript, TypeScript, etc.)
2. Run the appropriate linter (ruff, eslint, etc.)
3. Fix any auto-fixable issues
4. Report remaining issues that need manual attention
"""
            },
            {
                "filename": "review.md",
                "content": """---
name: /review
description: Code review the recent changes
---
Review the recent code changes in this project.

1. Check git diff or recent commits
2. Look for potential bugs or issues
3. Suggest improvements for code quality
4. Check for security concerns
5. Provide a summary of findings
"""
            },
            {
                "filename": "test.md",
                "content": """---
name: /test
description: Run tests and fix failures
auto_mode: true
---
Run all tests in this project and fix any failures.

1. Identify the test framework (pytest, jest, etc.)
2. Run the test suite
3. Analyze any failures
4. Attempt to fix failing tests
5. Re-run to verify fixes
"""
            }
        ]
        
        for example in examples:
            file_path = self.global_commands_dir / example["filename"]
            if not file_path.exists():
                file_path.write_text(example["content"])
    
    def get_help_text(self) -> str:
        """Get help text listing all custom commands"""
        if not self._commands:
            return "No custom commands defined. Create .md files in ~/.eve_unleashed/commands/"
        
        lines = ["Custom Commands:"]
        for name, cmd in sorted(self._commands.items()):
            source_tag = f"[{cmd.source}]" if cmd.source == 'project' else ""
            lines.append(f"  {name}: {cmd.description} {source_tag}")
        
        return "\n".join(lines)
