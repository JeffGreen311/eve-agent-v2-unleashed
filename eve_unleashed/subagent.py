#!/usr/bin/env python3
"""
Subagent System for EveUnleashed

Allows spawning specialized agents for focused tasks.
Agents are defined in YAML files:
- ~/.eve_unleashed/agents/ (global)
- .eve_unleashed/agents/ (project-specific)
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    import ollama


class AgentDefinition:
    """Definition of a subagent from YAML"""
    
    def __init__(
        self,
        name: str,
        model: str = "llama3:8b",
        system_prompt: str = "",
        allowed_tools: Optional[List[str]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        description: str = "",
        source: str = "global"
    ):
        self.name = name
        self.model = model
        self.system_prompt = system_prompt
        self.allowed_tools = allowed_tools or []
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.description = description
        self.source = source


class SubagentManager:
    """
    Manages subagent definitions and execution.
    
    Agent YAML format:
    ```yaml
    name: code-reviewer
    model: qwen3:latest
    description: Reviews code for issues
    system_prompt: |
      You are a code review specialist. Analyze code for:
      - Bugs and potential issues
      - Security vulnerabilities
      - Code style and best practices
    allowed_tools:
      - read_file
      - search_code
      - grep
    max_tokens: 4096
    temperature: 0.3
    ```
    """
    
    def __init__(self, project_dir: Optional[Path] = None):
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.global_agents_dir = Path.home() / ".eve_unleashed" / "agents"
        self.project_agents_dir = self.project_dir / ".eve_unleashed" / "agents"
        
        self._agents: Dict[str, AgentDefinition] = {}
        
        # Load agents
        self.reload_agents()
    
    def reload_agents(self) -> None:
        """Reload all agent definitions from disk"""
        self._agents = {}
        
        # Load global agents first
        if self.global_agents_dir.exists():
            self._load_agents_from_dir(self.global_agents_dir, source='global')
        
        # Load project agents (override global)
        if self.project_agents_dir.exists():
            self._load_agents_from_dir(self.project_agents_dir, source='project')
        
        # Add built-in agents
        self._add_builtin_agents()
    
    def _load_agents_from_dir(self, directory: Path, source: str) -> None:
        """Load all agent files from a directory"""
        for file_path in directory.glob("*.yaml"):
            try:
                agent = self._parse_agent_file(file_path, source)
                if agent:
                    self._agents[agent.name] = agent
            except Exception:
                pass
        
        for file_path in directory.glob("*.yml"):
            try:
                agent = self._parse_agent_file(file_path, source)
                if agent:
                    self._agents[agent.name] = agent
            except Exception:
                pass
    
    def _parse_agent_file(self, file_path: Path, source: str) -> Optional[AgentDefinition]:
        """Parse an agent YAML file"""
        content = file_path.read_text()
        data = yaml.safe_load(content)
        
        if not data or not isinstance(data, dict):
            return None
        
        return AgentDefinition(
            name=data.get('name', file_path.stem),
            model=data.get('model', 'llama3:8b'),
            system_prompt=data.get('system_prompt', ''),
            allowed_tools=data.get('allowed_tools', []),
            max_tokens=data.get('max_tokens', 4096),
            temperature=data.get('temperature', 0.7),
            description=data.get('description', ''),
            source=source
        )
    
    def _add_builtin_agents(self) -> None:
        """Add built-in agent definitions"""
        builtins = [
            AgentDefinition(
                name="code-reviewer",
                model="",  # Use current model
                description="Reviews code for bugs, security issues, and best practices",
                system_prompt="""You are a code review specialist. When given code or files to review:

1. Check for bugs and logical errors
2. Identify security vulnerabilities
3. Look for performance issues
4. Suggest improvements for readability
5. Check for proper error handling

Be constructive and specific in your feedback. Reference line numbers when possible.""",
                allowed_tools=["read_file", "search_code", "grep", "list_directory"],
                max_tokens=4096,
                temperature=0.3,
                source="builtin"
            ),
            AgentDefinition(
                name="test-writer",
                model="",
                description="Writes tests for code",
                system_prompt="""You are a test writing specialist. When given code to test:

1. Identify the testing framework used in the project
2. Write comprehensive unit tests
3. Include edge cases and error conditions
4. Follow the project's existing test patterns
5. Ensure tests are readable and maintainable

Write tests that actually verify behavior, not just code coverage.""",
                allowed_tools=["read_file", "write_file", "search_code", "grep", "bash", "list_directory"],
                max_tokens=4096,
                temperature=0.3,
                source="builtin"
            ),
            AgentDefinition(
                name="documenter",
                model="",
                description="Writes documentation for code",
                system_prompt="""You are a documentation specialist. When asked to document code:

1. Write clear, concise docstrings
2. Add inline comments for complex logic
3. Create README sections if needed
4. Document function parameters and return values
5. Include usage examples

Follow the documentation style used in the project.""",
                allowed_tools=["read_file", "write_file", "edit_file", "search_code", "list_directory"],
                max_tokens=4096,
                temperature=0.5,
                source="builtin"
            ),
        ]
        
        for agent in builtins:
            if agent.name not in self._agents:
                self._agents[agent.name] = agent
    
    def get_agent(self, name: str) -> Optional[AgentDefinition]:
        """Get an agent by name"""
        return self._agents.get(name)
    
    def list_agents(self) -> List[AgentDefinition]:
        """List all available agents"""
        return list(self._agents.values())
    
    def get_help_text(self) -> str:
        """Get help text listing all agents"""
        if not self._agents:
            return "No agents defined."
        
        lines = ["Available Subagents:"]
        for name, agent in sorted(self._agents.items()):
            source_tag = f"[{agent.source}]" if agent.source != 'builtin' else ""
            desc = agent.description or "No description"
            lines.append(f"  {name}: {desc} {source_tag}")
        
        return "\n".join(lines)
    
    def create_example_agents(self) -> None:
        """Create example agent files if none exist"""
        if self.global_agents_dir.exists() and list(self.global_agents_dir.glob("*.yaml")):
            return
        
        self.global_agents_dir.mkdir(parents=True, exist_ok=True)
        
        example = """# Example subagent definition
name: security-auditor
model: ""  # Uses current model if empty
description: Audits code for security vulnerabilities

system_prompt: |
  You are a security auditor. Analyze code for:
  - SQL injection vulnerabilities
  - XSS vulnerabilities
  - Authentication/authorization issues
  - Sensitive data exposure
  - Insecure dependencies
  
  Be thorough and provide specific recommendations.

allowed_tools:
  - read_file
  - search_code
  - grep
  - bash

max_tokens: 4096
temperature: 0.2
"""
        
        (self.global_agents_dir / "security-auditor.yaml").write_text(example)


class SubagentExecutor:
    """
    Executes subagents with sandboxed permissions.
    
    Each subagent runs with:
    - Its own system prompt
    - Limited tool access (only allowed_tools)
    - Separate conversation context
    """
    
    def __init__(
        self,
        agent: AgentDefinition,
        client: "ollama.Client",
        tool_manager: Any,
        working_dir: Path
    ):
        self.agent = agent
        self.client = client
        self.tool_manager = tool_manager
        self.working_dir = working_dir
        self.messages: List[Dict[str, Any]] = []
        
        # Initialize with system prompt
        if agent.system_prompt:
            self.messages.append({
                "role": "system",
                "content": agent.system_prompt
            })
    
    def _get_allowed_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas only for allowed tools"""
        if not self.agent.allowed_tools:
            # No restrictions
            return self.tool_manager.get_tool_schemas()
        
        schemas = []
        for tool_name in self.agent.allowed_tools:
            if tool_name in self.tool_manager.tools:
                schemas.append(self.tool_manager.tools[tool_name].get_schema())
        return schemas
    
    def execute(self, task: str, max_rounds: int = 5) -> str:
        """
        Execute the subagent on a task.
        
        Returns the final response from the agent.
        """
        # Add the task
        self.messages.append({
            "role": "user",
            "content": task
        })
        
        model = self.agent.model or "llama3:8b"
        tools = self._get_allowed_tool_schemas()
        
        rounds = 0
        final_content = ""
        
        while rounds < max_rounds:
            try:
                response = self.client.chat(
                    model=model,
                    messages=self.messages,
                    tools=tools if tools else None,
                    options={
                        "temperature": self.agent.temperature,
                        "num_predict": self.agent.max_tokens
                    }
                )
                
                message = response.get("message", {})
                self.messages.append(message)
                
                if message.get("content"):
                    final_content = message["content"]
                
                # Handle tool calls
                tool_calls = message.get("tool_calls", [])
                if not tool_calls:
                    break
                
                # Execute allowed tools
                for tool_call in tool_calls:
                    func = tool_call.get("function", {})
                    name = func.get("name", "")
                    args = func.get("arguments", {})
                    
                    # Check if tool is allowed
                    if self.agent.allowed_tools and name not in self.agent.allowed_tools:
                        result = {"error": f"Tool '{name}' not allowed for this agent"}
                    else:
                        result = self.tool_manager.execute_tool(name, **args)
                        result = result.to_dict()
                    
                    self.messages.append({
                        "role": "tool",
                        "name": name,
                        "content": str(result)
                    })
                
                rounds += 1
                
            except Exception as e:
                return f"Subagent error: {str(e)}"
        
        return final_content or "Subagent completed without response"
