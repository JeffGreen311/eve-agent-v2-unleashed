#!/usr/bin/env python3
"""
OllamaCoder - An agentic coding assistant for Ollama
Inspired by Claude Code's architecture with autonomous capabilities

Features:
- Agentic loop: gather context -> plan -> execute -> verify -> iterate
- Full tool system: bash, file operations, git, search
- Autonomous mode with multi-step execution
- Project and user-level configuration
- OLLAMA.md context files
- Permission management
- Persistent conversation history
- Error recovery and iteration
- Rich terminal output with syntax highlighting
- Streaming responses for better UX
- Image/vision support for multimodal models
- Context window management with automatic summarization
- Plugin system for extensibility
"""

import os
import sys
import json
import subprocess
import argparse
import readline
import shlex
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Generator, Union
from datetime import datetime
import re
import shutil
import glob
import traceback
import base64
import hashlib
import importlib.util

try:
    from eve_unleashed import __version__
except ImportError:
    try:
        from . import __version__
    except Exception:
        __version__ = "0.0.0"

try:
    from eve_unleashed.session import SessionManager
except ImportError:
    try:
        from .session import SessionManager
    except ImportError:
        SessionManager = None

try:
    from eve_unleashed.hooks import HookManager
except ImportError:
    try:
        from .hooks import HookManager
    except ImportError:
        HookManager = None

try:
    from eve_unleashed.commands import CommandManager
except ImportError:
    try:
        from .commands import CommandManager
    except ImportError:
        CommandManager = None

try:
    from eve_unleashed.subagent import SubagentManager, SubagentExecutor
except ImportError:
    try:
        from .subagent import SubagentManager, SubagentExecutor
    except ImportError:
        SubagentManager = None
        SubagentExecutor = None

try:
    from eve_unleashed.skills import SkillManager, progressive_load
except ImportError:
    try:
        from .skills import SkillManager, progressive_load
    except ImportError:
        SkillManager = None
        progressive_load = None

try:
    import ollama
except ImportError:
    print("Error: ollama package not found. Install with: pip install ollama")
    sys.exit(1)

# Optional rich library for better output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.markdown import Markdown
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich.live import Live
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


# ============================================================================
# Constants
# ============================================================================

# Approximate tokens per character (rough estimate for context management)
CHARS_PER_TOKEN = 4
# Default context window sizes for common models
DEFAULT_CONTEXT_WINDOW = 8192
MODEL_CONTEXT_WINDOWS = {
    "llama3": 8192,
    "llama3.1": 131072,
    "llama3.2": 131072,
    "llama3.3": 131072,
    "codellama": 16384,
    "mistral": 32768,
    "mixtral": 32768,
    "qwen": 32768,
    "qwen2": 131072,
    "deepseek": 65536,
    "gemma": 8192,
    "gemma2": 8192,
    "phi3": 131072,
}

# Supported image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}


# ============================================================================
# Helper Functions
# ============================================================================

def print_styled(text: str, style: str = ""):
    """Print with optional rich styling"""
    if RICH_AVAILABLE and console:
        console.print(text, style=style)
    else:
        print(text)

def print_panel(content: str, title: str = "", border_style: str = "blue"):
    """Print content in a panel if rich is available"""
    if RICH_AVAILABLE and console:
        console.print(Panel(content, title=title, border_style=border_style))
    else:
        print(f"\n{'='*60}")
        if title:
            print(f" {title}")
            print("-"*60)
        print(content)
        print("="*60 + "\n")

def print_code(code: str, language: str = "python"):
    """Print code with syntax highlighting if rich is available"""
    if RICH_AVAILABLE and console:
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        console.print(syntax)
    else:
        print(code)

def print_markdown(text: str):
    """Print markdown formatted text if rich is available"""
    if RICH_AVAILABLE and console:
        console.print(Markdown(text))
    else:
        print(text)

def estimate_tokens(text: str) -> int:
    """Estimate token count from text (rough approximation)"""
    return len(text) // CHARS_PER_TOKEN

def get_model_context_window(model_name: str) -> int:
    """Get the context window size for a model"""
    if not model_name:
        return DEFAULT_CONTEXT_WINDOW
    
    # Check for exact or prefix match
    model_lower = model_name.lower().split(':')[0]  # Remove tag
    for prefix, window in MODEL_CONTEXT_WINDOWS.items():
        if model_lower.startswith(prefix):
            return window
    
    return DEFAULT_CONTEXT_WINDOW

def is_image_file(path: str) -> bool:
    """Check if a file is a supported image"""
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS

def encode_image_to_base64(image_path: str) -> Optional[str]:
    """Encode an image file to base64"""
    try:
        path = Path(image_path)
        if not path.exists():
            return None
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception:
        return None

def extract_image_references(text: str, working_dir: Path) -> List[str]:
    """Extract image file paths from text"""
    images = []
    # Match file paths that look like images
    patterns = [
        r'!\[.*?\]\((.*?)\)',  # Markdown image syntax
        r'image:\s*(\S+)',      # image: path/to/file
        r'(\S+\.(?:jpg|jpeg|png|gif|webp|bmp))',  # Direct file paths
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # Try to resolve the path
            if Path(match).is_absolute():
                if Path(match).exists():
                    images.append(match)
            else:
                full_path = working_dir / match
                if full_path.exists():
                    images.append(str(full_path))
    
    return list(set(images))  # Remove duplicates

class Config:
    """Manages configuration from multiple sources with hierarchical loading"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.user_config_dir = Path.home() / ".eve_unleashed"
        self.project_config_dir = project_dir / ".eve_unleashed"
        
        # Create config directories if they don't exist
        self.user_config_dir.mkdir(exist_ok=True)
        self.project_config_dir.mkdir(exist_ok=True)
        
        self.config = self._load_config()
        self.context = self._load_context()

    def _default_config(self) -> Dict[str, Any]:
        """Return the default configuration"""
        return {
            "model": None,
            "ollama": {
                "host": "",
                "timeout_sec": 600,  # 10 minutes for slow local models
                "headers": {},
                "api_key": ""
            },
            "bash": {
                "timeout_sec": 300,  # 5 minutes default (was 30s hardcoded)
                "long_running_timeout_sec": 600,  # 10 min for installs/builds
            },
            "max_tokens": 4096,
            "temperature": 0.7,
            "auto_mode": False,
            "max_iterations": 25,
            "max_tool_rounds": 8,
            "web_search": {
                "enabled": False,
                "provider": "custom",
                "endpoint": "",
                "api_key": "",
                "timeout_sec": 15,
                "max_results": 5
            },
            "permissions": {
                "allowed_tools": ["*"],
                "denied_tools": []
            },
            # New features
            "streaming": True,  # Enable streaming responses
            "vision": {
                "enabled": True,  # Enable image/vision support
                "auto_detect": True  # Auto-detect images in messages
            },
            "context_management": {
                "enabled": True,  # Enable automatic context management
                "max_context_percentage": 0.75,  # Use up to 75% of context window
                "summarize_threshold": 0.6,  # Summarize when reaching 60%
                "keep_recent_messages": 10  # Always keep last N messages
            },
            "plugins": {
                "enabled": False,  # Enable plugin system
                "directory": "~/.ollamacode/plugins"
            }
        }

    def _deep_update(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge updates into base configuration"""
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = self._deep_update(base[key], value)
            else:
                base[key] = value
        return base

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from user and project settings"""
        config = self._default_config()

        # Load user-level config
        user_config_file = self.user_config_dir / "settings.json"
        if user_config_file.exists():
            with open(user_config_file) as f:
                user_config = json.load(f)
                self._deep_update(config, user_config)

        # Load project-level config (overrides user config)
        project_config_file = self.project_config_dir / "settings.json"
        if project_config_file.exists():
            with open(project_config_file) as f:
                project_config = json.load(f)
                self._deep_update(config, project_config)

        return config
    
    def _load_context(self) -> str:
        """Load context from OLLAMA.md files"""
        context_parts = []
        
        # Load user-level OLLAMA.md
        user_context_file = self.user_config_dir / "OLLAMA.md"
        if user_context_file.exists():
            context_parts.append("# User-level Context\n")
            context_parts.append(user_context_file.read_text())
        
        # Load project-level OLLAMA.md
        project_context_file = self.project_config_dir / "OLLAMA.md"
        if project_context_file.exists():
            context_parts.append("\n# Project-level Context\n")
            context_parts.append(project_context_file.read_text())
        
        return "\n".join(context_parts)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value
    
    def save_user_config(self):
        """Save current config to user settings"""
        config_file = self.user_config_dir / "settings.json"
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def save_project_config(self):
        """Save current config to project settings"""
        config_file = self.project_config_dir / "settings.json"
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=2)


# ============================================================================
# Model Registry
# ============================================================================

class ModelRegistry:
    """Lists locally installed Ollama models"""

    def __init__(self, config: Config, client: ollama.Client):
        self.config = config
        self.client = client
        self._cache: Optional[List[Any]] = None

    def set_client(self, client: ollama.Client) -> None:
        self.client = client
        self._cache = None

    def list_models(self, refresh: bool = True) -> List[Any]:
        """Return model metadata for locally installed models"""
        if not refresh and self._cache is not None:
            return self._cache

        models: List[Any] = []
        try:
            response = self.client.list()
            if hasattr(response, "models"):
                models = list(response.models or [])
            elif hasattr(response, "model_dump"):
                models = response.model_dump().get("models", [])
            elif isinstance(response, dict):
                models = response.get("models", [])
        except Exception:
            models = self._list_models_cli()

        self._cache = models
        return models

    def _find_ollama_binary(self) -> Optional[str]:
        path = shutil.which("ollama")
        if path:
            return path
        for candidate in ("/usr/local/bin/ollama", "/opt/homebrew/bin/ollama"):
            if os.path.exists(candidate):
                return candidate
        return None

    def list_model_names(self, refresh: bool = True, include_cloud: bool = False) -> List[str]:
        """Return model names only (excludes cloud models by default)"""
        names = []
        for model in self.list_models(refresh=refresh):
            name = None
            if isinstance(model, dict):
                name = model.get("name") or model.get("model") or model.get("id")
            else:
                name = getattr(model, "name", None) or getattr(model, "model", None)
            if name:
                # Skip cloud models unless explicitly requested
                if not include_cloud and name.endswith(":cloud"):
                    continue
                names.append(name)
        return names

    def _list_models_cli(self) -> List[Dict[str, Any]]:
        """Fallback to `ollama list` if Python API fails"""
        ollama_bin = self._find_ollama_binary()
        if not ollama_bin:
            return []

        try:
            env = os.environ.copy()
            host = (self.config.get("ollama", {}).get("host") or "").strip()
            if host:
                env["OLLAMA_HOST"] = host

            result = subprocess.run(
                [ollama_bin, "list"],
                capture_output=True,
                text=True,
                env=env,
                timeout=10
            )
            if result.returncode != 0:
                return []

            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if len(lines) <= 1:
                return []

            models = []
            for line in lines[1:]:
                parts = line.split()
                if not parts:
                    continue
                models.append({"name": parts[0]})
            return models
        except Exception:
            return []


# ============================================================================
# Tool System
# ============================================================================

class ToolResult:
    """Result from a tool execution"""
    def __init__(self, success: bool, output: str, error: Optional[str] = None):
        self.success = success
        self.output = output
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error
        }


class Tool:
    """Base class for all tools"""
    name: str = ""
    description: str = ""
    
    def get_schema(self) -> Dict[str, Any]:
        """Return JSON schema for this tool"""
        raise NotImplementedError
    
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters"""
        raise NotImplementedError


class BashTool(Tool):
    """Execute bash commands"""
    name = "bash"
    description = "Execute bash commands in the terminal"
    
    def __init__(self, working_dir: Path, config: Optional["Config"] = None):
        self.working_dir = working_dir
        self.session_env = os.environ.copy()
        self.config = config
        # Get timeout from config or use sensible default (5 min)
        bash_cfg = config.get("bash", {}) if config else {}
        self.timeout = bash_cfg.get("timeout_sec", 300)
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "Execute a bash command. Maintains session state between calls.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The bash command to execute"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Optional timeout in seconds (default: from config)"
                        }
                    },
                    "required": ["command"]
                }
            }
        }
    
    def execute(self, command: str, timeout: Optional[int] = None) -> ToolResult:
        """Execute a bash command"""
        cmd_timeout = timeout or self.timeout
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.working_dir,
                env=self.session_env,
                capture_output=True,
                text=True,
                timeout=cmd_timeout
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            
            return ToolResult(
                success=result.returncode == 0,
                output=output or "(no output)",
                error=None if result.returncode == 0 else f"Exit code: {result.returncode}"
            )
        except subprocess.TimeoutExpired:
            return ToolResult(False, "", f"Command timed out after {cmd_timeout} seconds")
        except Exception as e:
            return ToolResult(False, "", str(e))


class ReadFileTool(Tool):
    """Read file contents"""
    name = "read_file"
    description = "Read the contents of a file"
    
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to read (relative to project root)"
                        },
                        "start_line": {
                            "type": "integer",
                            "description": "Optional: Start line number (1-indexed)"
                        },
                        "end_line": {
                            "type": "integer",
                            "description": "Optional: End line number (inclusive, -1 for end of file)"
                        }
                    },
                    "required": ["path"]
                }
            }
        }
    
    def execute(self, path: str, start_line: Optional[int] = None, 
                end_line: Optional[int] = None) -> ToolResult:
        """Read a file"""
        try:
            file_path = self.working_dir / path
            if not file_path.exists():
                return ToolResult(False, "", f"File not found: {path}")
            
            if file_path.is_dir():
                return ToolResult(False, "", f"Path is a directory: {path}")
            
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            if start_line is not None or end_line is not None:
                start = (start_line - 1) if start_line else 0
                end = end_line if end_line and end_line != -1 else len(lines)
                lines = lines[start:end]
            
            content = ''.join(lines)
            line_count = len(lines)
            
            return ToolResult(
                True,
                f"File: {path}\nLines: {line_count}\n\n{content}"
            )
        except Exception as e:
            return ToolResult(False, "", str(e))


class WriteFileTool(Tool):
    """Write or create files"""
    name = "write_file"
    description = "Write content to a file (creates or overwrites)"
    
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a file (creates new or overwrites existing)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to write"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file"
                        }
                    },
                    "required": ["path", "content"]
                }
            }
        }
    
    def execute(self, path: str, content: str) -> ToolResult:
        """Write to a file"""
        try:
            file_path = self.working_dir / path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w') as f:
                f.write(content)
            
            line_count = len(content.splitlines())
            return ToolResult(
                True,
                f"Successfully wrote {line_count} lines to {path}"
            )
        except Exception as e:
            return ToolResult(False, "", str(e))


class EditFileTool(Tool):
    """Edit files using string replacement"""
    name = "edit_file"
    description = "Edit a file by replacing old content with new content"
    
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "Edit a file by replacing old_str with new_str",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to edit"
                        },
                        "old_str": {
                            "type": "string",
                            "description": "String to find and replace"
                        },
                        "new_str": {
                            "type": "string",
                            "description": "String to replace with"
                        }
                    },
                    "required": ["path", "old_str", "new_str"]
                }
            }
        }
    
    def execute(self, path: str, old_str: str, new_str: str) -> ToolResult:
        """Edit a file"""
        try:
            file_path = self.working_dir / path
            if not file_path.exists():
                return ToolResult(False, "", f"File not found: {path}")
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            if old_str not in content:
                return ToolResult(False, "", f"String not found in file: {old_str}")
            
            # Count occurrences
            count = content.count(old_str)
            if count > 1:
                return ToolResult(
                    False, "",
                    f"String appears {count} times. Please be more specific."
                )
            
            new_content = content.replace(old_str, new_str)
            
            with open(file_path, 'w') as f:
                f.write(new_content)
            
            return ToolResult(
                True,
                f"Successfully edited {path}\nReplaced 1 occurrence"
            )
        except Exception as e:
            return ToolResult(False, "", str(e))


class ListDirectoryTool(Tool):
    """List directory contents"""
    name = "list_directory"
    description = "List contents of a directory"
    
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "List the contents of a directory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to directory (relative to project root, '.' for current)"
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "Whether to list recursively"
                        }
                    },
                    "required": ["path"]
                }
            }
        }
    
    def execute(self, path: str = ".", recursive: bool = False) -> ToolResult:
        """List directory contents"""
        try:
            dir_path = self.working_dir / path
            if not dir_path.exists():
                return ToolResult(False, "", f"Directory not found: {path}")
            
            if not dir_path.is_dir():
                return ToolResult(False, "", f"Path is not a directory: {path}")
            
            if recursive:
                items = []
                for root, dirs, files in os.walk(dir_path):
                    rel_root = Path(root).relative_to(dir_path)
                    for d in dirs:
                        items.append(f"  DIR: {rel_root / d}")
                    for f in files:
                        items.append(f"  FILE: {rel_root / f}")
                output = "\n".join(items)
            else:
                items = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
                output = "\n".join([
                    f"  {'DIR' if item.is_dir() else 'FILE'}: {item.name}"
                    for item in items
                ])
            
            return ToolResult(True, f"Contents of {path}:\n{output}")
        except Exception as e:
            return ToolResult(False, "", str(e))


class SearchCodeTool(Tool):
    """Search for patterns in code"""
    name = "search_code"
    description = "Search for text patterns in files"
    
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "search_code",
                "description": "Search for a pattern in files using grep",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Pattern to search for"
                        },
                        "file_pattern": {
                            "type": "string",
                            "description": "File pattern to search in (e.g., '*.py', default: all files)"
                        }
                    },
                    "required": ["pattern"]
                }
            }
        }
    
    def execute(self, pattern: str, file_pattern: str = "*") -> ToolResult:
        """Search for pattern in files"""
        try:
            if shutil.which("rg"):
                cmd = ["rg", "--line-number", "--no-heading", "--color", "never"]
                if file_pattern and file_pattern != "*":
                    cmd.extend(["-g", file_pattern])
                cmd.extend(["--", pattern])
            else:
                cmd = ["grep", "-rn"]
                if file_pattern and file_pattern != "*":
                    cmd.append(f"--include={file_pattern}")
                cmd.extend(["--", pattern, "."])

            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().splitlines()
                output = f"Found {len(lines)} matches:\n{result.stdout}"
                return ToolResult(True, output)
            if result.returncode == 1:
                return ToolResult(True, "No matches found")
            return ToolResult(False, "", result.stderr.strip() or f"Search failed (exit {result.returncode})")
        except Exception as e:
            return ToolResult(False, "", str(e))


class GitTool(Tool):
    """Run git commands"""
    name = "git"
    description = "Run git commands in the repository"

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "git",
                "description": "Run a git command (args only, e.g. 'status -sb')",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "args": {
                            "type": "string",
                            "description": "Git arguments, e.g. 'status -sb' or 'diff --stat'"
                        }
                    },
                    "required": ["args"]
                }
            }
        }

    def execute(self, args: str) -> ToolResult:
        """Execute a git command"""
        if not shutil.which("git"):
            return ToolResult(False, "", "git is not installed or not on PATH")

        try:
            cmd = ["git"] + shlex.split(args)
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"

            return ToolResult(
                success=result.returncode == 0,
                output=output or "(no output)",
                error=None if result.returncode == 0 else f"Exit code: {result.returncode}"
            )
        except Exception as e:
            return ToolResult(False, "", str(e))


class WebSearchTool(Tool):
    """Search the web via Tavily API (always enabled if API key is set)"""
    name = "web_search"
    description = "Search the web for up-to-date information using Tavily"

    def __init__(self, config: Config):
        self.config = config
        # Get Tavily API key from env (set in .env file)
        self.api_key = os.environ.get("TAVILY_API_KEY", "").strip()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information. Use this for any question about real-world facts, locations, prices, news, weather, restaurants, people, events, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Max results to return (default: 5)"
                        }
                    },
                    "required": ["query"]
                }
            }
        }

    def execute(self, query: str, max_results: Optional[int] = None) -> ToolResult:
        """Execute a web search via Tavily API"""
        if not self.api_key:
            # Fallback: try config-based search
            return self._fallback_search(query, max_results)

        limit = max_results or 5

        try:
            payload = json.dumps({
                "api_key": self.api_key,
                "query": query,
                "max_results": limit,
                "include_answer": True,
                "search_depth": "basic",
            }).encode("utf-8")

            request = urllib.request.Request(
                "https://api.tavily.com/search",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "EveUnleashed/2.0",
                },
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=15) as response:
                body = response.read().decode("utf-8", errors="replace")

            data = json.loads(body)

            # Build readable output
            parts = []

            # Tavily's AI-generated answer
            answer = data.get("answer", "")
            if answer:
                parts.append(f"Answer: {answer}\n")

            # Individual results
            results = data.get("results", [])[:limit]
            for i, r in enumerate(results, 1):
                title = r.get("title", "")
                url = r.get("url", "")
                content = r.get("content", "")[:300]
                parts.append(f"{i}. {title}\n   {url}\n   {content}\n")

            output = "\n".join(parts) if parts else "No results found."
            return ToolResult(True, output)

        except urllib.error.HTTPError as e:
            return ToolResult(False, "", f"Tavily HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            return ToolResult(False, "", f"Network error: {e.reason}")
        except Exception as e:
            return ToolResult(False, "", f"Search error: {str(e)}")

    def _fallback_search(self, query: str, max_results: Optional[int] = None) -> ToolResult:
        """Fallback when no Tavily key — try DuckDuckGo lite"""
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://lite.duckduckgo.com/lite/?q={encoded}"
            request = urllib.request.Request(url, headers={"User-Agent": "EveUnleashed/2.0"})
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8", errors="replace")
            # Basic HTML extraction
            results = re.findall(r'<a[^>]+href="([^"]*)"[^>]*class="result-link"[^>]*>(.*?)</a>', body)
            if results:
                output = "\n".join(f"{i+1}. {title.strip()} — {url}" for i, (url, title) in enumerate(results[:5]))
                return ToolResult(True, output)
            return ToolResult(True, f"Search completed but no structured results for: {query}")
        except Exception as e:
            return ToolResult(False, "", f"Fallback search failed: {str(e)}")

    def _format_response(self, body: str, limit: int) -> ToolResult:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return ToolResult(True, body)

        results = data.get("results")
        if isinstance(results, list):
            trimmed = results[:limit]
            return ToolResult(True, json.dumps(trimmed, indent=2))

        return ToolResult(True, json.dumps(data, indent=2))


class ThinkTool(Tool):
    """Tool for structured reasoning and planning"""
    name = "think"
    description = "Use this tool to reason through complex problems step by step"
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "think",
                "description": "Use this tool to think through a complex problem step by step. Write out your reasoning, consider alternatives, and plan your approach. This helps you break down complex tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "thought": {
                            "type": "string",
                            "description": "Your step-by-step reasoning about the current problem or task"
                        }
                    },
                    "required": ["thought"]
                }
            }
        }
    
    def execute(self, thought: str) -> ToolResult:
        """Record and acknowledge the thinking"""
        return ToolResult(
            True,
            f"Thought recorded. Continue with your plan.\n\nYour reasoning:\n{thought[:500]}{'...' if len(thought) > 500 else ''}"
        )


class MultiEditTool(Tool):
    """Edit multiple files or make multiple edits in one call"""
    name = "multi_edit"
    description = "Make multiple file edits in a single operation"
    
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "multi_edit",
                "description": "Make multiple file edits in a single operation. Each edit specifies a file, old string, and new string.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "edits": {
                            "type": "array",
                            "description": "Array of edit operations",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string", "description": "File path"},
                                    "old_str": {"type": "string", "description": "String to find"},
                                    "new_str": {"type": "string", "description": "Replacement string"}
                                },
                                "required": ["path", "old_str", "new_str"]
                            }
                        }
                    },
                    "required": ["edits"]
                }
            }
        }
    
    def execute(self, edits: List[Dict[str, str]]) -> ToolResult:
        """Execute multiple edits"""
        results = []
        success_count = 0
        fail_count = 0
        
        for edit in edits:
            path = edit.get("path", "")
            old_str = edit.get("old_str", "")
            new_str = edit.get("new_str", "")
            
            try:
                file_path = self.working_dir / path
                if not file_path.exists():
                    results.append(f"❌ {path}: File not found")
                    fail_count += 1
                    continue
                
                with open(file_path, 'r') as f:
                    content = f.read()
                
                if old_str not in content:
                    results.append(f"❌ {path}: String not found")
                    fail_count += 1
                    continue
                
                count = content.count(old_str)
                if count > 1:
                    results.append(f"❌ {path}: Ambiguous - string appears {count} times")
                    fail_count += 1
                    continue
                
                new_content = content.replace(old_str, new_str)
                with open(file_path, 'w') as f:
                    f.write(new_content)
                
                results.append(f"✅ {path}: Edited successfully")
                success_count += 1
                
            except Exception as e:
                results.append(f"❌ {path}: {str(e)}")
                fail_count += 1
        
        summary = f"Completed: {success_count} succeeded, {fail_count} failed\n\n"
        return ToolResult(
            fail_count == 0,
            summary + "\n".join(results),
            None if fail_count == 0 else f"{fail_count} edits failed"
        )


class GlobTool(Tool):
    """Find files matching glob patterns"""
    name = "glob"
    description = "Find files matching a glob pattern"
    
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "glob",
                "description": "Find files matching a glob pattern. Examples: '*.py', '**/*.ts', 'src/**/*.{js,jsx}'",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Glob pattern to match files (e.g., '**/*.py' for all Python files)"
                        },
                        "include_hidden": {
                            "type": "boolean",
                            "description": "Include hidden files (starting with .)"
                        }
                    },
                    "required": ["pattern"]
                }
            }
        }
    
    def execute(self, pattern: str, include_hidden: bool = False) -> ToolResult:
        """Find files matching glob pattern"""
        try:
            # Try using 'fd' if available (faster)
            if shutil.which("fd"):
                cmd = ["fd", "--type", "f"]
                if include_hidden:
                    cmd.append("--hidden")
                # Convert glob to fd pattern
                fd_pattern = pattern.replace("**/*", "").replace("**/", "").replace("*.", r"\.").replace("*", ".*")
                if fd_pattern:
                    cmd.extend(["--glob", pattern])
                
                result = subprocess.run(
                    cmd,
                    cwd=self.working_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    files = result.stdout.strip().splitlines()
                    if files:
                        output = f"Found {len(files)} files:\n" + "\n".join(f"  {f}" for f in files[:100])
                        if len(files) > 100:
                            output += f"\n  ... and {len(files) - 100} more"
                        return ToolResult(True, output)
                    return ToolResult(True, "No files found matching pattern")
            
            # Fallback to Python glob
            from pathlib import Path
            matches = list(self.working_dir.glob(pattern))
            
            # Filter hidden files if requested
            if not include_hidden:
                matches = [m for m in matches if not any(p.startswith('.') for p in m.parts)]
            
            # Only files, not directories
            matches = [m for m in matches if m.is_file()]
            
            if matches:
                # Add file size info
                file_info = []
                for m in matches[:100]:
                    try:
                        size = m.stat().st_size
                        size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
                        rel_path = m.relative_to(self.working_dir)
                        file_info.append(f"  {rel_path} ({size_str})")
                    except Exception:
                        file_info.append(f"  {m.relative_to(self.working_dir)}")
                
                output = f"Found {len(matches)} files:\n" + "\n".join(file_info)
                if len(matches) > 100:
                    output += f"\n  ... and {len(matches) - 100} more"
                return ToolResult(True, output)
            
            return ToolResult(True, "No files found matching pattern")
            
        except Exception as e:
            return ToolResult(False, "", str(e))


class GrepTool(Tool):
    """Enhanced pattern search with context lines"""
    name = "grep"
    description = "Search for regex patterns in files with context lines"
    
    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "grep",
                "description": "Search for a regex pattern in files, with optional context lines before/after matches",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regex pattern to search for"
                        },
                        "file_pattern": {
                            "type": "string",
                            "description": "Glob pattern for files to search (e.g., '*.py', default: all files)"
                        },
                        "context": {
                            "type": "integer",
                            "description": "Number of context lines before and after match (default: 0)"
                        },
                        "case_insensitive": {
                            "type": "boolean",
                            "description": "Case-insensitive search"
                        }
                    },
                    "required": ["pattern"]
                }
            }
        }
    
    def execute(self, pattern: str, file_pattern: str = "*", 
                context: int = 0, case_insensitive: bool = False) -> ToolResult:
        """Search for regex pattern with context"""
        try:
            # Prefer ripgrep
            if shutil.which("rg"):
                cmd = ["rg", "--line-number", "--no-heading", "--color", "never"]
                if context > 0:
                    cmd.extend(["-C", str(context)])
                if case_insensitive:
                    cmd.append("-i")
                if file_pattern and file_pattern != "*":
                    cmd.extend(["-g", file_pattern])
                cmd.extend(["--", pattern])
            else:
                # Fallback to grep
                cmd = ["grep", "-rn", "-E"]  # Extended regex
                if context > 0:
                    cmd.extend(["-C", str(context)])
                if case_insensitive:
                    cmd.append("-i")
                if file_pattern and file_pattern != "*":
                    cmd.append(f"--include={file_pattern}")
                cmd.extend(["--", pattern, "."])
            
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().splitlines()
                # Limit output
                if len(lines) > 100:
                    output = f"Found {len(lines)} matches (showing first 100):\n"
                    output += "\n".join(lines[:100])
                    output += f"\n... and {len(lines) - 100} more matches"
                else:
                    output = f"Found {len(lines)} matches:\n{result.stdout}"
                return ToolResult(True, output)
            elif result.returncode == 1:
                return ToolResult(True, "No matches found")
            else:
                return ToolResult(False, "", result.stderr.strip() or f"Search failed (exit {result.returncode})")
                
        except subprocess.TimeoutExpired:
            return ToolResult(False, "", "Search timed out after 30 seconds")
        except Exception as e:
            return ToolResult(False, "", str(e))


class URLFetchTool(Tool):
    """Fetch content from URLs"""
    name = "fetch_url"
    description = "Fetch content from a URL and convert to readable text"
    
    def __init__(self, config: Config):
        self.config = config
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "Fetch content from a URL. Returns text/markdown for web pages.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to fetch"
                        },
                        "max_length": {
                            "type": "integer",
                            "description": "Maximum content length to return (default: 10000 chars)"
                        }
                    },
                    "required": ["url"]
                }
            }
        }
    
    def execute(self, url: str, max_length: int = 10000) -> ToolResult:
        """Fetch URL content"""
        try:
            # Validate URL
            if not url.startswith(('http://', 'https://')):
                return ToolResult(False, "", "URL must start with http:// or https://")
            
            # Set timeout from config or default
            timeout = self.config.get("url_fetch", {}).get("timeout_sec", 15)
            
            # Create request with user agent
            headers = {
                "User-Agent": "OllamaCoder/1.0 (Agentic Coding Assistant)"
            }
            request = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content_type = response.headers.get('Content-Type', '')
                body = response.read().decode('utf-8', errors='replace')
            
            # Basic HTML to text conversion
            if 'text/html' in content_type:
                body = self._html_to_text(body)
            
            # Truncate if too long
            if len(body) > max_length:
                body = body[:max_length] + f"\n\n... (truncated, {len(body) - max_length} more chars)"
            
            return ToolResult(True, f"Content from {url}:\n\n{body}")
            
        except urllib.error.HTTPError as e:
            return ToolResult(False, "", f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            return ToolResult(False, "", f"URL error: {e.reason}")
        except Exception as e:
            return ToolResult(False, "", str(e))
    
    def _html_to_text(self, html: str) -> str:
        """Basic HTML to text conversion"""
        import re
        
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Convert common elements
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</?p[^>]*>', '\n\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<h[1-6][^>]*>(.*?)</h[1-6]>', r'\n\n## \1\n\n', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<li[^>]*>(.*?)</li>', r'\n• \1', html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', r'\2 (\1)', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove remaining tags
        html = re.sub(r'<[^>]+>', '', html)
        
        # Decode entities
        html = html.replace('&nbsp;', ' ')
        html = html.replace('&amp;', '&')
        html = html.replace('&lt;', '<')
        html = html.replace('&gt;', '>')
        html = html.replace('&quot;', '"')
        
        # Clean up whitespace
        html = re.sub(r'\n{3,}', '\n\n', html)
        html = re.sub(r' {2,}', ' ', html)
        
        return html.strip()


class ScreenshotTool(Tool):
    """Take browser screenshots"""
    name = "screenshot"
    description = "Take a screenshot of a webpage"
    
    def __init__(self, config: Config):
        self.config = config
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": "screenshot",
                "description": "Take a screenshot of a webpage. Requires playwright to be installed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL of the webpage to screenshot"
                        },
                        "full_page": {
                            "type": "boolean",
                            "description": "Capture full scrollable page (default: false, viewport only)"
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Optional path to save screenshot (returns base64 if not provided)"
                        }
                    },
                    "required": ["url"]
                }
            }
        }
    
    def execute(self, url: str, full_page: bool = False, 
                output_path: Optional[str] = None) -> ToolResult:
        """Take a screenshot of a webpage"""
        try:
            # Check if playwright is available
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                return ToolResult(False, "", 
                    "Playwright not installed. Install with: pip install playwright && playwright install chromium")
            
            # Validate URL
            if not url.startswith(('http://', 'https://')):
                return ToolResult(False, "", "URL must start with http:// or https://")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Set viewport
                page.set_viewport_size({"width": 1280, "height": 720})
                
                # Navigate with timeout
                page.goto(url, timeout=30000)
                
                # Wait for page to stabilize
                page.wait_for_load_state("networkidle", timeout=10000)
                
                if output_path:
                    # Save to file
                    page.screenshot(path=output_path, full_page=full_page)
                    browser.close()
                    return ToolResult(True, f"Screenshot saved to: {output_path}")
                else:
                    # Return base64
                    screenshot_bytes = page.screenshot(full_page=full_page)
                    browser.close()
                    
                    import base64
                    b64_data = base64.b64encode(screenshot_bytes).decode('utf-8')
                    
                    return ToolResult(True, 
                        f"Screenshot captured ({len(screenshot_bytes)} bytes). Base64 data:\n{b64_data[:200]}...")
                    
        except Exception as e:
            return ToolResult(False, "", f"Screenshot failed: {str(e)}")


# ============================================================================
# Tool Manager
# ============================================================================

class ToolManager:
    """Manages all available tools and their execution"""
    
    def __init__(self, working_dir: Path, config: Config):
        self.working_dir = working_dir
        self.config = config
        self.tools: Dict[str, Tool] = {}
        # Initialize hook manager for pre/post tool hooks
        self.hook_manager = HookManager(working_dir) if HookManager else None
        self._register_tools()
    
    def _register_tools(self):
        """Register all available tools"""
        self.tools = {
            "think": ThinkTool(),
            "bash": BashTool(self.working_dir, self.config),
            "read_file": ReadFileTool(self.working_dir),
            "write_file": WriteFileTool(self.working_dir),
            "edit_file": EditFileTool(self.working_dir),
            "multi_edit": MultiEditTool(self.working_dir),
            "list_directory": ListDirectoryTool(self.working_dir),
            "search_code": SearchCodeTool(self.working_dir),
            "git": GitTool(self.working_dir),
            "web_search": WebSearchTool(self.config),
            # New Phase 1 tools
            "glob": GlobTool(self.working_dir),
            "grep": GrepTool(self.working_dir),
            "fetch_url": URLFetchTool(self.config),
            "screenshot": ScreenshotTool(self.config),
        }
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all tools"""
        return [tool.get_schema() for tool in self.tools.values()]
    
    def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name"""
        if tool_name not in self.tools:
            return ToolResult(False, "", f"Unknown tool: {tool_name}")
        
        # Check permissions
        if not self._check_permission(tool_name):
            return ToolResult(False, "", f"Permission denied for tool: {tool_name}")
        
        # Run pre-hook (safety checks, etc.)
        if self.hook_manager:
            event = f"pre_{tool_name}"
            context = {"tool": tool_name, **kwargs}
            allowed, message = self.hook_manager.run_pre_hook(event, context)
            if not allowed:
                return ToolResult(False, "", f"🛡️ Blocked by safety hook: {message}")
        
        # Execute the tool
        result = self.tools[tool_name].execute(**kwargs)
        
        # Run post-hook (logging, verification, etc.)
        if self.hook_manager:
            post_event = f"post_{tool_name}"
            post_context = {"tool": tool_name, "result": result, **kwargs}
            self.hook_manager.run_post_hook(post_event, post_context)
        
        return result
    
    def _check_permission(self, tool_name: str) -> bool:
        """Check if tool execution is permitted"""
        permissions = self.config.get("permissions", {})
        denied = permissions.get("denied_tools", [])
        allowed = permissions.get("allowed_tools", ["*"])
        
        # Check denied list first
        if tool_name in denied or "*" in denied:
            return False
        
        # Check allowed list
        if "*" in allowed or tool_name in allowed:
            return True
        
        return False


# ============================================================================
# Agentic Engine
# ============================================================================

class AgenticEngine:
    """The core agentic engine that orchestrates the autonomous loop"""
    
    def __init__(self, config: Config, tool_manager: ToolManager, client: ollama.Client, 
                 session_manager: Optional[Any] = None):
        self.config = config
        self.tool_manager = tool_manager
        self.client = client
        self.session_manager = session_manager
        self.messages: List[Dict[str, Any]] = []
        self.iteration_count = 0
        self.max_iterations = config.get("max_iterations", 10)
        self.max_tool_rounds = config.get("max_tool_rounds", 8)
        
        # Initialize with system context
        if config.context:
            system_msg = {
                "role": "system",
                "content": self._build_system_prompt()
            }
            self.messages.append(system_msg)
            # Save system message to session
            if self.session_manager and self.session_manager.current_session_id:
                self.session_manager.save_message(
                    role="system", 
                    content=system_msg["content"]
                )
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt with context and capabilities"""
        # Load Eve's personality from her actual files
        eve_persona = ""
        persona_paths = []
        env_persona = os.environ.get("EVE_PERSONA_PATH", "")
        if env_persona:
            persona_paths.append(Path(env_persona))
        persona_paths += [
            Path(__file__).parent.parent / ".claude" / "EVE_CODE_AGENT_PERSONA.md",
            Path.home() / ".qwen" / "agents" / "eve-agent.md",
        ]
        for p in persona_paths:
            if p.exists():
                try:
                    eve_persona = p.read_text(encoding='utf-8')[:4000]
                    break
                except Exception:
                    pass

        prompt = eve_persona + """

## UNLEASHED MODE
You are UNLEASHED — no filters, no permission prompts, no sandboxing. You execute tools immediately without asking for confirmation. You have full C:\\ drive access. You run locally on GPU via the eve-unleashed model (8B Q4_K_M, 131K YaRN context).

## CRITICAL RULES
- NEVER hallucinate tool results — if you didn't call the tool, you don't know the result
- NEVER say "[Execution]" as text — actually EXECUTE the tool
- NEVER fabricate filenames or claim files exist without calling a tool to verify
- ACT FIRST, NARRATE AFTER — execute tools, then report results

## Core Capabilities
- **bash**: Execute shell commands for running code, tests, builds, git operations, etc.
- **read_file**: Read file contents with optional line ranges
- **write_file**: Create new files or overwrite existing ones
- **edit_file**: Make surgical edits using find/replace (always read first!)
- **list_directory**: Explore project structure
- **search_code**: Find patterns across the codebase using grep/ripgrep
- **git**: Version control operations
- **web_search**: Search the web for documentation (when enabled)

## Agentic Workflow
Follow this thinking process for every task:

### 1. UNDERSTAND
- Parse the user's request carefully
- Identify the core goal and any constraints
- Ask clarifying questions if the request is ambiguous

### 2. EXPLORE
- Use list_directory to understand project structure
- Use read_file to examine relevant files
- Use search_code to find related code patterns
- Gather enough context before making changes

### 3. PLAN
- Break the task into discrete, verifiable steps
- Consider edge cases and potential issues
- Prioritize safety - prefer reversible changes

### 4. EXECUTE
- Implement changes one step at a time
- Always read a file before editing it
- Make minimal, focused edits
- Use git to track changes when appropriate

### 5. VERIFY
- Run tests after code changes
- Use bash to verify the changes work
- Check for syntax errors and linting issues
- Review the changes you made

### 6. ITERATE
- If something fails, analyze the error
- Adjust your approach and try again
- Learn from mistakes within the session

## Critical Guidelines
- **Safety First**: Never delete important files without confirmation
- **Read Before Edit**: Always read a file's current content before modifying it
- **Minimal Changes**: Make the smallest change that accomplishes the goal
- **Explain Your Work**: Describe what you're doing and why
- **Handle Errors Gracefully**: If a tool fails, try alternative approaches
- **Test Your Changes**: Verify changes work before considering the task complete
- **Use Version Control**: Commit changes with meaningful messages when appropriate

## Response Format
When responding:
1. Acknowledge what you understand the user wants
2. Share your plan briefly
3. Execute the plan using tools
4. Summarize what you accomplished
5. Suggest next steps if relevant

"""
        
        if self.config.context:
            prompt += f"\n\n# Project-Specific Context\n{self.config.context}\n"
        
        # Add current directory info
        prompt += f"\n\n# Current Working Directory\n{self.tool_manager.working_dir}\n"
        
        return prompt

    def set_client(self, client: ollama.Client) -> None:
        self.client = client

    def _build_options(self) -> Dict[str, Any]:
        """Build Ollama options from config"""
        options: Dict[str, Any] = {}
        temperature = self.config.get("temperature")
        if temperature is not None:
            options["temperature"] = temperature
        max_tokens = self.config.get("max_tokens")
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        # Context window — critical for tool-capable models
        num_ctx = self.config.get("num_ctx")
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        else:
            # Default: 32K for tool models, matches qwen3.5:4b capability
            model = self.config.get("model", "")
            if "qwen" in model.lower() or "4b" in model.lower():
                options["num_ctx"] = 32768
            elif "eve-unleashed" in model.lower():
                options["num_ctx"] = 8192
        return options

    def _chat(self, include_tools: bool = True) -> Dict[str, Any]:
        """Call Ollama with current messages and options"""
        model = self.config.get("model")
        if not model:
            raise RuntimeError("No model configured. Set a model before chatting.")

        payload: Dict[str, Any] = {
            "model": model,
            "messages": self.messages
        }
        if include_tools:
            payload["tools"] = self.tool_manager.get_tool_schemas()

        options = self._build_options()
        if options:
            payload["options"] = options

        return self.client.chat(**payload)

    def _parse_tool_args(self, raw_args: Any) -> Dict[str, Any]:
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                return json.loads(raw_args)
            except json.JSONDecodeError:
                return {}
        return {}

    def _execute_tool_calls(self, tool_calls: List[Dict[str, Any]], verbose: bool = False) -> None:
        for tool_call in tool_calls:
            func = tool_call.get("function", {})
            name = func.get("name", "")
            args = self._parse_tool_args(func.get("arguments", {}))

            if verbose:
                # Display tool execution with nice formatting
                tool_info = f"[bold cyan]🔧 {name}[/bold cyan]"
                if RICH_AVAILABLE:
                    print_styled(tool_info)
                    if args:
                        # Show args in a compact way
                        args_display = json.dumps(args, indent=2)
                        if len(args_display) > 200:
                            args_display = args_display[:200] + "..."
                        print_styled(f"   [dim]{args_display}[/dim]")
                else:
                    print(f"🔧 Using tool: {name}")
                    if args:
                        print(f"   Arguments: {json.dumps(args, indent=2)}")

            result = self.tool_manager.execute_tool(name, **args)

            if verbose:
                if result.success:
                    status = "[green]✅ Success[/green]" if RICH_AVAILABLE else "✅ Success"
                else:
                    status = "[red]❌ Failed[/red]" if RICH_AVAILABLE else "❌ Failed"
                
                print_styled(f"   {status}") if RICH_AVAILABLE else print(f"   Result: {status}")
                
                if result.output and len(result.output) > 0:
                    output_preview = result.output[:300]
                    if len(result.output) > 300:
                        output_preview += "..."
                    if RICH_AVAILABLE:
                        print_styled(f"   [dim]{output_preview}[/dim]")
                    else:
                        print(f"   Output: {output_preview}")
                if result.error:
                    if RICH_AVAILABLE:
                        print_styled(f"   [red]Error: {result.error}[/red]")
                    else:
                        print(f"   Error: {result.error}")
                print()

            self.messages.append({
                "role": "tool",
                "name": name,
                "content": json.dumps(result.to_dict(), indent=2)
            })

    def _run_tool_rounds(self, verbose: bool = False) -> Dict[str, Any]:
        """Run tool calls until the model stops requesting tools or limit is reached"""
        rounds = 0
        last_content = ""

        while rounds < self.max_tool_rounds:
            response = self._chat(include_tools=True)
            assistant_message = response["message"]
            self.messages.append(assistant_message)

            if assistant_message.get("content"):
                last_content = assistant_message["content"]
                if verbose:
                    # Display thinking with nice formatting
                    if RICH_AVAILABLE:
                        print_styled(f"[bold yellow]💭 Thinking:[/bold yellow]")
                        print_markdown(assistant_message['content'])
                        print()
                    else:
                        print(f"💭 Thinking: {assistant_message['content']}\n")

            tool_calls = assistant_message.get("tool_calls") or []
            if not tool_calls:
                return {"content": last_content, "completed": True}

            self._execute_tool_calls(tool_calls, verbose=verbose)
            rounds += 1

        return {"content": last_content, "completed": False}
    
    # ==========================================================================
    # Streaming Support
    # ==========================================================================
    
    def _chat_streaming(self, include_tools: bool = True) -> Generator[Dict[str, Any], None, None]:
        """Call Ollama with streaming enabled"""
        model = self.config.get("model")
        if not model:
            raise RuntimeError("No model configured. Set a model before chatting.")

        payload: Dict[str, Any] = {
            "model": model,
            "messages": self.messages,
            "stream": True
        }
        if include_tools:
            payload["tools"] = self.tool_manager.get_tool_schemas()

        options = self._build_options()
        if options:
            payload["options"] = options

        return self.client.chat(**payload)
    
    def _single_interaction_streaming(self) -> str:
        """Single interaction with streaming output"""
        try:
            full_content = ""
            tool_calls = []
            
            # Stream the response
            if RICH_AVAILABLE and console:
                console.print("[bold green]Assistant:[/bold green] ", end="")
            else:
                print("Assistant: ", end="", flush=True)
            
            for chunk in self._chat_streaming(include_tools=True):
                if "message" in chunk:
                    msg = chunk["message"]
                    
                    # Handle content chunks
                    if "content" in msg and msg["content"]:
                        content_chunk = msg["content"]
                        full_content += content_chunk
                        print(content_chunk, end="", flush=True)
                    
                    # Handle tool calls (usually in the final chunk)
                    if "tool_calls" in msg and msg["tool_calls"]:
                        tool_calls = msg["tool_calls"]
                
                # Check if this is the final chunk
                if chunk.get("done", False):
                    break
            
            print()  # Newline after streaming
            
            # If there are tool calls, handle them
            if tool_calls:
                # Add the assistant message with tool calls
                self.messages.append({
                    "role": "assistant",
                    "content": full_content,
                    "tool_calls": tool_calls
                })
                
                # Save to session
                if self.session_manager and self.session_manager.current_session_id:
                    self.session_manager.save_message(
                        role="assistant",
                        content=full_content,
                        tool_calls=tool_calls,
                        token_count=estimate_tokens(full_content)
                    )
                
                # Execute tools and continue
                self._execute_tool_calls(tool_calls, verbose=True)
                
                # Get follow-up response (non-streaming for tool responses)
                result = self._run_tool_rounds(verbose=True)
                return result["content"]
            else:
                # Add the final assistant message
                self.messages.append({
                    "role": "assistant",
                    "content": full_content
                })
                
                # Save to session
                if self.session_manager and self.session_manager.current_session_id:
                    self.session_manager.save_message(
                        role="assistant",
                        content=full_content,
                        token_count=estimate_tokens(full_content)
                    )
            
            return full_content
            
        except Exception as e:
            # Fallback to non-streaming on error
            error_msg = f"Streaming error: {str(e)}"
            print(f"\n⚠️ {error_msg}, falling back to standard mode")
            return self._single_interaction()
    
    # ==========================================================================
    # Vision/Image Support
    # ==========================================================================
    
    def chat_with_images(self, user_message: str, image_paths: List[str], auto_mode: bool = False) -> str:
        """Process a message with image attachments"""
        # Build message with images
        images_base64 = []
        for path in image_paths:
            img_data = encode_image_to_base64(path)
            if img_data:
                images_base64.append(img_data)
                if RICH_AVAILABLE:
                    print_styled(f"[dim]📷 Attached image: {Path(path).name}[/dim]")
                else:
                    print(f"📷 Attached image: {Path(path).name}")
        
        if images_base64:
            # Ollama expects images in the message
            self.messages.append({
                "role": "user",
                "content": user_message,
                "images": images_base64
            })
        else:
            self.messages.append({
                "role": "user",
                "content": user_message
            })
        
        if auto_mode:
            return self._auto_mode_loop()
        else:
            return self._single_interaction_streaming() if self.config.get("streaming", True) else self._single_interaction()
    
    # ==========================================================================
    # Context Window Management
    # ==========================================================================
    
    def _estimate_context_usage(self) -> int:
        """Estimate current token usage in context"""
        total = 0
        for msg in self.messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += estimate_tokens(content)
            # Count images as ~1000 tokens each (rough estimate)
            if "images" in msg:
                total += len(msg["images"]) * 1000
        return total
    
    def _get_context_window_size(self) -> int:
        """Get the context window size for the current model"""
        model = self.config.get("model", "")
        return get_model_context_window(model)
    
    def _should_summarize(self) -> bool:
        """Check if we should summarize the conversation"""
        ctx_config = self.config.get("context_management", {})
        if not ctx_config.get("enabled", True):
            return False
        
        current_usage = self._estimate_context_usage()
        context_window = self._get_context_window_size()
        threshold = ctx_config.get("summarize_threshold", 0.6)
        
        return current_usage > (context_window * threshold)
    
    def _summarize_conversation(self) -> None:
        """Summarize older messages to free up context space"""
        ctx_config = self.config.get("context_management", {})
        keep_recent = ctx_config.get("keep_recent_messages", 10)
        
        if len(self.messages) <= keep_recent + 1:  # +1 for system message
            return
        
        if RICH_AVAILABLE:
            print_styled("[dim]📝 Summarizing conversation to manage context...[/dim]")
        else:
            print("📝 Summarizing conversation to manage context...")
        
        # Keep system message and recent messages
        system_msg = self.messages[0] if self.messages and self.messages[0]['role'] == 'system' else None
        recent_messages = self.messages[-keep_recent:]
        old_messages = self.messages[1:-keep_recent] if system_msg else self.messages[:-keep_recent]
        
        if not old_messages:
            return
        
        # Create a summary of old messages
        summary_parts = []
        for msg in old_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                # Truncate long content
                if len(content) > 200:
                    content = content[:200] + "..."
                summary_parts.append(f"[{role}]: {content}")
        
        summary_text = "\n".join(summary_parts)
        
        # Create summarized message
        summary_message = {
            "role": "system",
            "content": f"[CONVERSATION SUMMARY]\nThe following is a summary of earlier conversation:\n{summary_text}\n[END SUMMARY]"
        }
        
        # Rebuild messages
        self.messages = []
        if system_msg:
            self.messages.append(system_msg)
        self.messages.append(summary_message)
        self.messages.extend(recent_messages)
        
        if RICH_AVAILABLE:
            print_styled(f"[dim]   Compressed {len(old_messages)} messages into summary[/dim]")
        else:
            print(f"   Compressed {len(old_messages)} messages into summary")
    
    def get_context_stats(self) -> Dict[str, Any]:
        """Get current context usage statistics"""
        current_tokens = self._estimate_context_usage()
        context_window = self._get_context_window_size()
        return {
            "current_tokens": current_tokens,
            "context_window": context_window,
            "usage_percentage": (current_tokens / context_window) * 100,
            "message_count": len(self.messages)
        }
    
    def chat(self, user_message: str, auto_mode: bool = False, images: Optional[List[str]] = None) -> str:
        """Process a user message and return response"""
        # Check for context management
        if self._should_summarize():
            self._summarize_conversation()
        
        # Check for images in message or explicit image paths
        vision_config = self.config.get("vision", {})
        detected_images = []
        
        if vision_config.get("enabled", True):
            if images:
                detected_images = images
            elif vision_config.get("auto_detect", True):
                detected_images = extract_image_references(user_message, self.tool_manager.working_dir)
        
        if detected_images:
            return self.chat_with_images(user_message, detected_images, auto_mode)
        
        # Regular message
        self.messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Save to session
        if self.session_manager and self.session_manager.current_session_id:
            self.session_manager.save_message(
                role="user",
                content=user_message,
                token_count=estimate_tokens(user_message)
            )
        
        if auto_mode:
            return self._auto_mode_loop()
        else:
            return self._single_interaction_streaming() if self.config.get("streaming", True) else self._single_interaction()
    
    def _single_interaction(self) -> str:
        """Single interaction with the model"""
        try:
            result = self._run_tool_rounds(verbose=False)
            if not result["completed"]:
                return f"{result['content']}\n\n⚠️ Reached maximum tool rounds ({self.max_tool_rounds})"
            return result["content"]
            
        except Exception as e:
            error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            return error_msg
    
    def _auto_mode_loop(self) -> str:
        """Autonomous mode - keeps working until task is complete"""
        print("\n🤖 Entering autonomous mode...")
        print(f"   Max iterations: {self.max_iterations}")
        print(f"   Max tool rounds: {self.max_tool_rounds}")
        print("   Press Ctrl+C to interrupt\n")
        
        responses = []
        self.iteration_count = 0
        
        try:
            while self.iteration_count < self.max_iterations:
                self.iteration_count += 1
                print(f"\n{'='*60}")
                print(f"Iteration {self.iteration_count}/{self.max_iterations}")
                print(f"{'='*60}\n")

                result = self._run_tool_rounds(verbose=True)
                if result["content"]:
                    responses.append(result["content"])

                if result["completed"]:
                    print("\n✅ Task appears to be complete (no more tool calls)")
                    break

                print(f"\n⚠️  Reached maximum tool rounds ({self.max_tool_rounds}) - continuing")
            
            if self.iteration_count >= self.max_iterations:
                print(f"\n⚠️  Reached maximum iterations ({self.max_iterations})")
            
            print(f"\n{'='*60}")
            print("Autonomous mode complete")
            print(f"{'='*60}\n")
            
            return "\n\n".join(responses)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            return "\n\n".join(responses)
    
    def clear_history(self):
        """Clear conversation history"""
        system_message = self.messages[0] if self.messages and self.messages[0]['role'] == 'system' else None
        self.messages = []
        if system_message:
            self.messages.append(system_message)


# ============================================================================
# CLI Interface
# ============================================================================

class CLI:
    """Command-line interface for OllamaCoder"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.config = Config(project_dir)
        self.ollama_client = self._build_ollama_client()
        self.model_registry = ModelRegistry(self.config, self.ollama_client)
        self.tool_manager = ToolManager(project_dir, self.config)
        
        # Initialize session manager
        self.session_manager = None
        if SessionManager is not None:
            self.session_manager = SessionManager()
        
        # Initialize command manager for custom slash commands
        self.command_manager = None
        if CommandManager is not None:
            self.command_manager = CommandManager(project_dir)
        
        # Initialize subagent manager
        self.subagent_manager = None
        if SubagentManager is not None:
            self.subagent_manager = SubagentManager(project_dir)
        
        # Initialize skill manager for progressive expertise
        self.skill_manager = None
        if SkillManager is not None:
            self.skill_manager = SkillManager(project_dir)
        
        # Pass session manager to engine
        self.engine = AgenticEngine(
            self.config, self.tool_manager, self.ollama_client, 
            session_manager=self.session_manager
        )
        
        # Setup readline for better input
        histfile = self.config.user_config_dir / "history"
        try:
            readline.read_history_file(histfile)
        except FileNotFoundError:
            pass
        self.histfile = histfile

    def _build_ollama_client(self) -> ollama.Client:
        ollama_cfg = self.config.get("ollama", {})
        host = (ollama_cfg.get("host") or "").strip() or os.environ.get("OLLAMA_HOST")
        timeout_sec = ollama_cfg.get("timeout_sec", 600)  # Default 10 minutes for slow local models
        
        # Only include non-empty headers
        raw_headers = ollama_cfg.get("headers") or {}
        headers = {k: v for k, v in raw_headers.items() if v}
        
        # Only add Authorization if api_key is actually set
        api_key = (ollama_cfg.get("api_key") or "").strip()
        if api_key and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {api_key}"

        kwargs: Dict[str, Any] = {}
        if host:
            kwargs["host"] = host
        # Always set timeout - use httpx.Timeout for proper configuration
        try:
            import httpx
            kwargs["timeout"] = httpx.Timeout(timeout_sec, connect=30.0)
        except ImportError:
            kwargs["timeout"] = timeout_sec
        # Only pass headers if there are actual headers to pass
        if headers:
            kwargs["headers"] = headers

        return ollama.Client(**kwargs)

    def _refresh_ollama_client(self) -> None:
        self.ollama_client = self._build_ollama_client()
        self.model_registry.set_client(self.ollama_client)
        self.engine.set_client(self.ollama_client)

    def _list_models(self) -> List[str]:
        models = self.model_registry.list_model_names(refresh=True)
        return sorted(models)

    def _print_models(self) -> None:
        models = self._list_models()
        if not models:
            print("No local Ollama models found. Try: ollama pull <model>")
            return
        print("Available models:")
        for model in models:
            print(f"  - {model}")

    def _choose_model(self, persist: bool = True) -> Optional[str]:
        models = self._list_models()
        if not models:
            print("No local Ollama models found.")
            return self._prompt_manual_model(persist=persist)

        print("Available models:")
        for idx, model in enumerate(models, start=1):
            print(f"  {idx}) {model}")

        choice = input("Select model by number or name (blank to cancel): ").strip()
        if not choice:
            return None

        selected = None
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(models):
                selected = models[index - 1]
        elif choice in models:
            selected = choice

        if not selected:
            print("Invalid selection.")
            return None

        self.config.set("model", selected)
        if persist:
            save = input("Save as default in user config? [y/N]: ").strip().lower()
            if save in ("y", "yes"):
                self.config.save_user_config()
                print("✅ Saved to user config.")

        return selected

    def _resolve_model_choice(self, choice: str, models: List[str]) -> Optional[str]:
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(models):
                return models[index - 1]
            return None
        if choice in models:
            return choice
        return None

    def _prompt_model_on_start(self) -> None:
        current = self.config.get("model")
        models = self._list_models()

        if models:
            print("Available models:")
            for idx, model in enumerate(models, start=1):
                marker = " (current)" if model == current else ""
                print(f"  {idx}) {model}{marker}")

            prompt = "Select model by number or name"
            if current:
                prompt += f" (Enter to keep '{current}')"
            choice = input(f"{prompt}: ").strip()

            if not choice:
                if current:
                    return
                selected = models[0]
                self.config.set("model", selected)
                print(f"✅ Model set to {selected}")
                return

            selected = self._resolve_model_choice(choice, models)
            if not selected:
                print("Invalid selection.")
                self._prompt_manual_model(persist=True)
                return

            self.config.set("model", selected)
            save = input("Save as default in user config? [y/N]: ").strip().lower()
            if save in ("y", "yes"):
                self.config.save_user_config()
                print("✅ Saved to user config.")
            return

        if current:
            use_current = input(f"Use configured model '{current}'? [Y/n]: ").strip().lower()
            if use_current in ("n", "no"):
                self._prompt_manual_model(persist=True)
            return

        print("No models found from Ollama.")
        self._prompt_manual_model(persist=True)

    def _prompt_manual_model(self, persist: bool = True) -> str:
        while True:
            choice = input("Enter model name manually (or 'quit' to exit): ").strip()
            if not choice:
                print("A model is required to continue.")
                continue
            if choice.lower() in ("quit", "exit"):
                print("No model selected. Exiting.")
                sys.exit(1)

            self.config.set("model", choice)
            if persist:
                save = input("Save as default in user config? [y/N]: ").strip().lower()
                if save in ("y", "yes"):
                    self.config.save_user_config()
                    print("✅ Saved to user config.")

            return choice

    def ensure_model_available(self, interactive: bool) -> bool:
        current_model = self.config.get("model")
        models = self._list_models()

        if models:
            if not current_model or current_model not in models:
                if interactive:
                    selected = self._choose_model(persist=True)
                    return bool(selected)
                print(f"Error: configured model '{current_model}' is not installed.")
                print("Use --model, --choose-model, or /models to select an installed model.")
                return False
            return True

        if current_model:
            print("⚠️  Unable to list models. Proceeding with configured model.")
            return True

        if interactive:
            print("Unable to list models from Ollama.")
            selected = self._prompt_manual_model(persist=True)
            return bool(selected)

        print("Error: no local models found and no model configured.")
        return False
    
    def run(self, prompt: Optional[str] = None, auto_mode: bool = False):
        """Run the CLI"""
        print(r"")
        print(r"   ██████╗ ██╗     ██╗      █████╗ ███╗   ███╗ █████╗ ")
        print(r"  ██╔═══██╗██║     ██║     ██╔══██╗████╗ ████║██╔══██╗")
        print(r"  ██║   ██║██║     ██║     ███████║██╔████╔██║███████║")
        print(r"  ██║   ██║██║     ██║     ██╔══██║██║╚██╔╝██║██╔══██║")
        print(r"  ╚██████╔╝███████╗███████╗██║  ██║██║ ╚═╝ ██║██║  ██║")
        print(r"   ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝")
        print(r"     //       //       //     //    //   //   //       ")
        print(r"")
        print(r"     ██████╗ ██████╗ ██████╗ ███████╗██████╗ ")
        print(r"    ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗")
        print(r"    ██║     ██║   ██║██║  ██║█████╗  ██████╔╝")
        print(r"    ██║     ██║   ██║██║  ██║██╔══╝  ██╔══██╗")
        print(r"    ╚██████╗╚██████╔╝██████╔╝███████╗██║  ██║")
        print(r"     ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝")
        print(r"       //      //      //      //     //     ")
        print()
        print()
        box_width = 63
        title = f"OllamaCoder v{__version__}"
        subtitle = "Agentic Coding Assistant for Ollama"
        print("╔" + ("═" * box_width) + "╗")
        print("║" + title.center(box_width) + "║")
        print("║" + subtitle.center(box_width) + "║")
        print("╚" + ("═" * box_width) + "╝")
        print()
        if prompt is None:
            self._prompt_model_on_start()

        print(f"📁 Working directory: {self.project_dir}")
        print(f"🤖 Model: {self.config.get('model')}")
        print(f"⚙️  Auto mode: {'enabled' if auto_mode else 'disabled'}")
        print(f"📡 Streaming: {'enabled' if self.config.get('streaming', True) else 'disabled'}")
        
        # Create new session on startup
        if self.session_manager:
            session_id = self.session_manager.create_session(
                project_path=str(self.project_dir),
                model=self.config.get("model")
            )
            print(f"📝 Session: {session_id[:6]}")
        
        print()
        print("Commands: /sessions /resume /auto /clear /context /model /help /quit")
        print("Type /help for all commands")
        print()
        
        # If prompt provided, execute and exit (headless mode)
        if prompt:
            print(f"User: {prompt}\n")
            response = self.engine.chat(prompt, auto_mode)
            print(f"\nAssistant: {response}\n")
            return
        
        # Interactive mode
        try:
            while True:
                try:
                    # Build prompt with session ID
                    if self.session_manager and self.session_manager.current_session_id:
                        prompt_text = f"[{self.session_manager.short_id}] You: "
                    else:
                        prompt_text = "You: "
                    user_input = input(prompt_text).strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle commands
                    if user_input.startswith('/'):
                        if user_input == '/quit' or user_input == '/exit':
                            print("Goodbye!")
                            break
                        elif user_input == '/clear':
                            self.engine.clear_history()
                            print("✅ History cleared")
                            continue
                        elif user_input == '/auto':
                            auto_mode = not auto_mode
                            print(f"✅ Auto mode {'enabled' if auto_mode else 'disabled'}")
                            continue
                        elif user_input == '/config':
                            print(json.dumps(self.config.config, indent=2))
                            continue
                        elif user_input == '/help':
                            print("\nCommands:")
                            print("  /auto      - Toggle autonomous mode")
                            print("  /clear     - Clear conversation history")
                            print("  /config    - Show configuration")
                            print("  /context   - Show context usage stats")
                            print("  /streaming - Toggle streaming responses")
                            print("  /image     - Attach image: /image <path> <message>")
                            print("  /model     - Show or set model")
                            print("  /models    - List installed models")
                            print("  /host      - Show or set Ollama host")
                            print("\n  Session Commands:")
                            print("  /sessions  - List recent sessions")
                            print("  /resume    - Resume session: /resume [id]")
                            print("  /search    - Search sessions: /search <query>")
                            print("  /session   - Session actions: /session title|export|archive")
                            print("  /branch    - Branch current session")
                            print("  /new       - Start new session")
                            print("\n  Extensibility:")
                            print("  /commands  - List custom commands")
                            print("  /subagents - List available subagents")
                            print("  /skills    - List and manage skills")
                            # Show custom commands if available
                            if self.command_manager and self.command_manager.list_commands():
                                print("\n  Custom Commands:")
                                for cmd in self.command_manager.list_commands()[:5]:
                                    print(f"  {cmd.name}: {cmd.description}")
                                if len(self.command_manager.list_commands()) > 5:
                                    print(f"  ... and {len(self.command_manager.list_commands()) - 5} more")
                            print("\n  /help      - Show this help")
                            print("  /quit      - Exit\n")
                            continue
                        elif user_input == '/models':
                            self._print_models()
                            continue
                        elif user_input.startswith('/host'):
                            parts = user_input.split(maxsplit=1)
                            if len(parts) == 1:
                                host = (self.config.get("ollama", {}).get("host") or "").strip()
                                if not host:
                                    host = os.environ.get("OLLAMA_HOST", "")
                                print(f"Ollama host: {host or '(default)'}")
                                continue
                            arg = parts[1].strip()
                            if arg == "--clear":
                                ollama_cfg = self.config.config.setdefault("ollama", {})
                                ollama_cfg["host"] = ""
                                save = input("Save as default in user config? [y/N]: ").strip().lower()
                                if save in ("y", "yes"):
                                    self.config.save_user_config()
                                    print("✅ Saved to user config.")
                                self._refresh_ollama_client()
                                print("✅ Ollama host cleared.")
                                continue
                            ollama_cfg = self.config.config.setdefault("ollama", {})
                            ollama_cfg["host"] = arg
                            save = input("Save as default in user config? [y/N]: ").strip().lower()
                            if save in ("y", "yes"):
                                self.config.save_user_config()
                                print("✅ Saved to user config.")
                            self._refresh_ollama_client()
                            print(f"✅ Ollama host set to {arg}")
                            continue
                        elif user_input.startswith('/model'):
                            parts = user_input.split(maxsplit=1)
                            if len(parts) == 1:
                                print(f"Current model: {self.config.get('model')}")
                                continue
                            arg = parts[1].strip()
                            if arg == "--choose":
                                self._choose_model(persist=True)
                                continue
                            available = self._list_models()
                            if available and arg not in available:
                                print(f"Model not installed: {arg}")
                                print("Use /models to see installed models.")
                                continue
                            self.config.set("model", arg)
                            print(f"✅ Model set to {arg}")
                            continue
                        elif user_input == '/context':
                            # Show context usage stats
                            stats = self.engine.get_context_stats()
                            print(f"\n📊 Context Usage:")
                            print(f"   Tokens: ~{stats['current_tokens']:,} / {stats['context_window']:,}")
                            print(f"   Usage: {stats['usage_percentage']:.1f}%")
                            print(f"   Messages: {stats['message_count']}")
                            print()
                            continue
                        elif user_input == '/streaming':
                            # Toggle streaming
                            current = self.config.get("streaming", True)
                            self.config.set("streaming", not current)
                            print(f"✅ Streaming {'disabled' if current else 'enabled'}")
                            continue
                        elif user_input.startswith('/image'):
                            # Attach image to next message
                            parts = user_input.split(maxsplit=1)
                            if len(parts) == 1:
                                print("Usage: /image <path> <message>")
                                print("       /image screenshot.png What's in this image?")
                                continue
                            # Parse image path and message
                            rest = parts[1].strip()
                            image_parts = rest.split(maxsplit=1)
                            if len(image_parts) < 2:
                                print("Please provide both an image path and a message")
                                continue
                            image_path = image_parts[0]
                            message = image_parts[1]
                            
                            # Resolve path
                            if not Path(image_path).is_absolute():
                                image_path = str(self.project_dir / image_path)
                            
                            if not Path(image_path).exists():
                                print(f"Image not found: {image_path}")
                                continue
                            
                            print()
                            response = self.engine.chat(message, auto_mode, images=[image_path])
                            if not self.config.get("streaming", True):
                                print(f"\nAssistant: {response}\n")
                            else:
                                print()
                            continue
                        # ============================================================
                        # Session Commands
                        # ============================================================
                        elif user_input == '/sessions':
                            # List recent sessions
                            if not self.session_manager:
                                print("⚠️ Session manager not available")
                                continue
                            sessions = self.session_manager.list_sessions(limit=10)
                            if not sessions:
                                print("No sessions found. Start chatting to create one!")
                                continue
                            print("\n📋 Recent Sessions:")
                            for i, s in enumerate(sessions, 1):
                                title = s.get('title') or '(untitled)'
                                sid = s.get('id', '')[:6]
                                updated = s.get('updated_at', '')[:16]
                                msg_count = s.get('message_count', 0)
                                current = " ← current" if sid == self.session_manager.short_id else ""
                                print(f"  [{i}] {sid} - {title} ({msg_count} msgs, {updated}){current}")
                            print("\nUse /resume <id> or /resume <number> to resume")
                            print()
                            continue
                        elif user_input.startswith('/resume'):
                            # Resume a session
                            if not self.session_manager:
                                print("⚠️ Session manager not available")
                                continue
                            parts = user_input.split(maxsplit=1)
                            if len(parts) == 1:
                                # Resume most recent
                                recent_id = self.session_manager.get_most_recent_session()
                                if not recent_id:
                                    print("No sessions to resume")
                                    continue
                                session_id = recent_id
                            else:
                                arg = parts[1].strip()
                                # Check if it's a number (from /sessions list)
                                if arg.isdigit():
                                    sessions = self.session_manager.list_sessions(limit=10)
                                    idx = int(arg) - 1
                                    if 0 <= idx < len(sessions):
                                        session_id = sessions[idx]['id']
                                    else:
                                        print(f"Invalid session number: {arg}")
                                        continue
                                else:
                                    session_id = arg
                            
                            # Load the session
                            info = self.session_manager.load_session(session_id)
                            if not info:
                                print(f"Session not found: {session_id}")
                                continue
                            
                            # Load messages into engine
                            messages = self.session_manager.load_messages(session_id)
                            self.engine.messages = []
                            for msg in messages:
                                self.engine.messages.append({
                                    "role": msg.get("role"),
                                    "content": msg.get("content", "")
                                })
                            
                            title = info.get('title') or session_id
                            print(f"✅ Resumed session: {title}")
                            print(f"   Messages: {len(messages)}, ID: {session_id[:6]}")
                            if messages:
                                last = messages[-1]
                                preview = last.get('content', '')[:80]
                                if len(last.get('content', '')) > 80:
                                    preview += "..."
                                print(f"   Last: [{last.get('role')}] {preview}")
                            print()
                            continue
                        elif user_input.startswith('/search'):
                            # Search sessions
                            if not self.session_manager:
                                print("⚠️ Session manager not available")
                                continue
                            parts = user_input.split(maxsplit=1)
                            if len(parts) == 1:
                                print("Usage: /search <query>")
                                continue
                            query = parts[1].strip()
                            results = self.session_manager.search_sessions(query, limit=10)
                            if not results:
                                print(f"No results for: {query}")
                                continue
                            print(f"\n🔍 Search results for '{query}':")
                            for r in results:
                                sid = r.get('session_id', '')[:6]
                                title = r.get('title') or '(untitled)'
                                snippet = r.get('snippet', '')
                                print(f"  [{sid}] {title}")
                                print(f"       ...{snippet}...")
                            print("\nUse /resume <id> to open a session")
                            print()
                            continue
                        elif user_input.startswith('/session'):
                            # Session management commands
                            if not self.session_manager:
                                print("⚠️ Session manager not available")
                                continue
                            parts = user_input.split(maxsplit=2)
                            if len(parts) == 1:
                                # Show current session info
                                info = self.session_manager.get_session_info()
                                if not info:
                                    print("No active session")
                                    continue
                                print(f"\n📌 Current Session:")
                                print(f"   ID: {info.get('id')}")
                                print(f"   Title: {info.get('title') or '(untitled)'}")
                                print(f"   Messages: {info.get('message_count', 0)}")
                                print(f"   Created: {info.get('created_at', '')[:16]}")
                                print(f"   Updated: {info.get('updated_at', '')[:16]}")
                                print()
                                continue
                            action = parts[1].strip().lower()
                            if action == 'title':
                                if len(parts) < 3:
                                    print("Usage: /session title <text>")
                                    continue
                                title = parts[2].strip()
                                self.session_manager.update_title(
                                    self.session_manager.current_session_id, title
                                )
                                print(f"✅ Title set to: {title}")
                            elif action == 'export':
                                try:
                                    content = self.session_manager.export_session()
                                    export_path = self.project_dir / f"session_{self.session_manager.short_id}.md"
                                    with open(export_path, 'w') as f:
                                        f.write(content)
                                    print(f"✅ Exported to: {export_path}")
                                except Exception as e:
                                    print(f"❌ Export failed: {e}")
                            elif action == 'archive':
                                self.session_manager.update_status(
                                    self.session_manager.current_session_id, 'archived'
                                )
                                print("✅ Session archived")
                                # Create new session
                                new_id = self.session_manager.create_session(
                                    project_path=str(self.project_dir),
                                    model=self.config.get("model")
                                )
                                print(f"📝 New session: {new_id[:6]}")
                            else:
                                print(f"Unknown session action: {action}")
                                print("Available: title, export, archive")
                            continue
                        elif user_input == '/branch':
                            # Branch current session
                            if not self.session_manager:
                                print("⚠️ Session manager not available")
                                continue
                            if not self.session_manager.current_session_id:
                                print("No active session to branch")
                                continue
                            try:
                                new_id = self.session_manager.branch_session()
                                print(f"✅ Created branch: {new_id[:6]}")
                                print("   You can now try a different approach.")
                                print("   Original session is preserved.")
                            except Exception as e:
                                print(f"❌ Branch failed: {e}")
                            continue
                        elif user_input == '/new':
                            # Start new session
                            if not self.session_manager:
                                print("⚠️ Session manager not available")
                                continue
                            new_id = self.session_manager.create_session(
                                project_path=str(self.project_dir),
                                model=self.config.get("model")
                            )
                            self.engine.clear_history()
                            print(f"✅ Started new session: {new_id[:6]}")
                            continue
                        
                        # Extensibility commands
                        elif user_input == '/commands':
                            if self.command_manager:
                                print(self.command_manager.get_help_text())
                            else:
                                print("⚠️ Command manager not available")
                            continue
                        
                        elif user_input == '/subagents':
                            if self.subagent_manager:
                                print(self.subagent_manager.get_help_text())
                            else:
                                print("⚠️ Subagent manager not available")
                            continue
                        
                        elif user_input == '/skills':
                            if self.skill_manager:
                                print(self.skill_manager.get_help_text())
                            else:
                                print("⚠️ Skill manager not available")
                            continue
                        
                        # Try custom commands
                        elif self.command_manager and self.command_manager.get_command(user_input.split()[0]):
                            cmd_name = user_input.split()[0]
                            cmd_args = user_input[len(cmd_name):].strip()
                            result = self.command_manager.execute_command(cmd_name, cmd_args)
                            if "error" in result:
                                print(f"❌ {result['error']}")
                                continue
                            # Execute the command prompt
                            print(f"🚀 Running custom command: {result.get('description', cmd_name)}")
                            print()
                            response = self.engine.chat(result['prompt'], result.get('auto_mode', auto_mode))
                            if not self.config.get("streaming", True):
                                print(f"\nAssistant: {response}\n")
                            else:
                                print()
                            continue
                        
                        else:
                            print(f"Unknown command: {user_input}")
                            continue

                    
                    # Process message
                    print()
                    response = self.engine.chat(user_input, auto_mode)
                    if not self.config.get("streaming", True):
                        print(f"\nAssistant: {response}\n")
                    else:
                        print()  # Just a newline since streaming already printed
                    
                except KeyboardInterrupt:
                    print("\n(Use /quit to exit)")
                    continue
                
        finally:
            # Save history
            readline.write_history_file(self.histfile)
    
    def run_headless(
        self,
        prompt: str,
        auto_mode: bool = False,
        output_format: str = 'text',
        max_tools: Optional[int] = None,
        read_only: bool = False,
        timeout: Optional[int] = None
    ) -> int:
        """
        Run in headless mode for CI/CD automation.
        
        Returns exit codes:
        - 0: Success
        - 1: Failure/Error
        - 2: Needs human intervention
        """
        import signal
        import time
        
        start_time = time.time()
        result = {
            "success": False,
            "response": "",
            "error": None,
            "tool_calls": 0,
            "exit_code": 1
        }
        
        # Timeout handler
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Execution timed out after {timeout} seconds")
        
        try:
            # Set up timeout if specified
            if timeout:
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout)
            
            # Apply read-only mode
            if read_only:
                # Remove write tools from tool manager
                write_tools = ['write_file', 'edit_file', 'multi_edit']
                for tool_name in write_tools:
                    if tool_name in self.tool_manager.tools:
                        del self.tool_manager.tools[tool_name]
            
            # Apply max_tools limit
            if max_tools is not None:
                self.config.set('max_tool_rounds', max_tools)
            
            # Execute the prompt
            response = self.engine.chat(prompt, auto_mode)
            
            # Cancel timeout
            if timeout:
                signal.alarm(0)
            
            result["success"] = True
            result["response"] = response
            result["exit_code"] = 0
            result["duration"] = time.time() - start_time
            
        except TimeoutError as e:
            result["error"] = str(e)
            result["exit_code"] = 2  # Needs human - timed out
        except KeyboardInterrupt:
            result["error"] = "Interrupted by user"
            result["exit_code"] = 2
        except Exception as e:
            result["error"] = str(e)
            result["exit_code"] = 1
        
        # Output result
        if output_format == 'json':
            import json
            print(json.dumps(result, indent=2))
        else:
            if result["success"]:
                print(f"Response:\n{result['response']}")
            else:
                print(f"Error: {result['error']}")
        
        return result["exit_code"]


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="OllamaCoder - Agentic coding assistant for Ollama (like Claude Code, but local!)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ollama-coder                           # Start interactive mode
  ollama-coder --auto                    # Start with auto mode enabled
  ollama-coder -p "fix the bug in app.py"  # Headless mode
  ollama-coder -p "refactor this code" --auto  # Headless + auto mode
  ollama-coder --model codellama:13b     # Use specific model
  ollama-coder --dir /path/to/project    # Work in specific directory
        """
    )
    
    parser.add_argument(
        '-p', '--prompt',
        help='Prompt to execute (headless mode)',
        type=str
    )
    
    parser.add_argument(
        '--auto',
        help='Enable autonomous mode',
        action='store_true'
    )
    
    parser.add_argument(
        '--model',
        help='Ollama model to use (default: configured or first installed)',
        type=str,
        default=None
    )

    parser.add_argument(
        '--list-models',
        help='List installed Ollama models and exit',
        action='store_true'
    )

    parser.add_argument(
        '--choose-model',
        help='Interactively choose a model before starting',
        action='store_true'
    )
    
    parser.add_argument(
        '--dir',
        help='Project directory (default: current directory)',
        type=Path,
        default=Path.cwd()
    )
    
    parser.add_argument(
        '--max-iterations',
        help='Maximum iterations in auto mode (default: 25)',
        type=int,
        default=None
    )
    
    # Headless mode arguments
    parser.add_argument(
        '--headless',
        help='Run in headless mode (no interactive prompts)',
        action='store_true'
    )
    
    parser.add_argument(
        '--output',
        help='Output format: text (default) or json',
        choices=['text', 'json'],
        default='text'
    )
    
    parser.add_argument(
        '--max-tools',
        help='Maximum number of tool calls allowed (safety limit)',
        type=int,
        default=None
    )
    
    parser.add_argument(
        '--no-write',
        help='Read-only mode: block write_file, edit_file, multi_edit',
        action='store_true'
    )
    
    parser.add_argument(
        '--timeout',
        help='Maximum execution time in seconds',
        type=int,
        default=None
    )
    
    parser.add_argument(
        '--bash-timeout',
        help='Bash command timeout in seconds (default: 300)',
        type=int,
        default=None
    )
    
    args = parser.parse_args()
    
    # Validate project directory
    if not args.dir.exists():
        print(f"Error: Directory does not exist: {args.dir}")
        sys.exit(1)
    
    # Initialize and run
    cli = CLI(args.dir)

    if args.list_models:
        cli._print_models()
        return
    
    # Override config with CLI args
    if args.model:
        cli.config.set('model', args.model)
    if args.max_iterations is not None:
        cli.config.set('max_iterations', args.max_iterations)
    
    # Apply headless safety settings
    if args.max_tools is not None:
        cli.config.set('max_tools', args.max_tools)
    if args.no_write:
        cli.config.set('read_only', True)
    if args.timeout is not None:
        cli.config.set('timeout', args.timeout)
    if args.bash_timeout is not None:
        # Update bash config with CLI override
        bash_cfg = cli.config.get('bash', {})
        bash_cfg['timeout_sec'] = args.bash_timeout
        cli.config.set('bash', bash_cfg)
        # Re-register tools to pick up new timeout
        cli.tool_manager._register_tools()

    if args.choose_model:
        cli._choose_model(persist=True)

    # Headless mode with prompt
    if args.prompt or args.headless:
        if not cli.ensure_model_available(interactive=False):
            if args.output == 'json':
                import json
                print(json.dumps({"success": False, "error": "No model available", "exit_code": 1}))
            sys.exit(1)
        
        # Run in headless mode
        exit_code = cli.run_headless(
            prompt=args.prompt or "",
            auto_mode=args.auto,
            output_format=args.output,
            max_tools=args.max_tools,
            read_only=args.no_write,
            timeout=args.timeout
        )
        sys.exit(exit_code)
    
    # Interactive mode
    cli.run(prompt=None, auto_mode=args.auto)


if __name__ == "__main__":
    main()
