#!/usr/bin/env python3
"""
Skills System for EveUnleashed

Progressive expertise loading - skills are loaded on demand when keywords match.
Skills are folders with:
- SKILL.md: Context injected into the prompt
- skill.yaml: Metadata and keywords
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass


@dataclass
class Skill:
    """Represents a skill definition"""
    name: str
    description: str
    keywords: List[str]
    content: str  # SKILL.md content
    source: str
    path: Path
    
    # Optional
    tools: List[str] = None
    auto_load: bool = False
    
    def __post_init__(self):
        if self.tools is None:
            self.tools = []


class SkillManager:
    """
    Manages progressive skill loading.
    
    Skills are folders in:
    - ~/.eve_unleashed/skills/{skill-name}/
    - .eve_unleashed/skills/{skill-name}/
    
    Each skill folder contains:
    - SKILL.md: The expertise content (injected into context)
    - skill.yaml: Metadata including keywords
    
    Example skill.yaml:
    ```yaml
    name: python-testing
    description: Expertise in Python testing with pytest
    keywords:
      - pytest
      - unittest
      - test
      - testing
    tools:
      - bash
      - read_file
    ```
    """
    
    def __init__(self, project_dir: Optional[Path] = None):
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.global_skills_dir = Path.home() / ".eve_unleashed" / "skills"
        self.project_skills_dir = self.project_dir / ".eve_unleashed" / "skills"
        
        self._skills: Dict[str, Skill] = {}
        self._loaded_skills: Set[str] = set()  # Currently active skills
        
        # Load skill definitions
        self.reload_skills()
    
    def reload_skills(self) -> None:
        """Reload all skill definitions from disk"""
        self._skills = {}
        
        # Load global skills first
        if self.global_skills_dir.exists():
            self._load_skills_from_dir(self.global_skills_dir, source='global')
        
        # Load project skills (override global)
        if self.project_skills_dir.exists():
            self._load_skills_from_dir(self.project_skills_dir, source='project')
    
    def _load_skills_from_dir(self, directory: Path, source: str) -> None:
        """Load all skill folders from a directory"""
        for skill_dir in directory.iterdir():
            if skill_dir.is_dir():
                try:
                    skill = self._parse_skill(skill_dir, source)
                    if skill:
                        self._skills[skill.name] = skill
                except Exception:
                    pass
    
    def _parse_skill(self, skill_dir: Path, source: str) -> Optional[Skill]:
        """Parse a skill folder"""
        skill_yaml = skill_dir / "skill.yaml"
        skill_yml = skill_dir / "skill.yml"
        skill_md = skill_dir / "SKILL.md"
        
        # Load metadata
        metadata = {}
        if skill_yaml.exists():
            metadata = yaml.safe_load(skill_yaml.read_text()) or {}
        elif skill_yml.exists():
            metadata = yaml.safe_load(skill_yml.read_text()) or {}
        
        # Load content
        content = ""
        if skill_md.exists():
            content = skill_md.read_text()
        
        if not content:
            return None
        
        return Skill(
            name=metadata.get('name', skill_dir.name),
            description=metadata.get('description', f'{skill_dir.name} skill'),
            keywords=metadata.get('keywords', [skill_dir.name]),
            content=content,
            source=source,
            path=skill_dir,
            tools=metadata.get('tools', []),
            auto_load=metadata.get('auto_load', False)
        )
    
    def find_matching_skills(self, query: str) -> List[Skill]:
        """Find skills that match keywords in the query"""
        query_lower = query.lower()
        matching = []
        
        for skill in self._skills.values():
            for keyword in skill.keywords:
                if keyword.lower() in query_lower:
                    matching.append(skill)
                    break
        
        return matching
    
    def load_skill(self, name: str) -> Optional[str]:
        """
        Load a skill and return its content.
        Marks the skill as loaded.
        """
        skill = self._skills.get(name)
        if skill:
            self._loaded_skills.add(name)
            return skill.content
        return None
    
    def unload_skill(self, name: str) -> None:
        """Unload a skill from active context"""
        self._loaded_skills.discard(name)
    
    def get_loaded_skills(self) -> List[Skill]:
        """Get currently loaded skills"""
        return [self._skills[name] for name in self._loaded_skills if name in self._skills]
    
    def get_loaded_content(self) -> str:
        """Get combined content of all loaded skills"""
        contents = []
        for skill in self.get_loaded_skills():
            contents.append(f"## Skill: {skill.name}\n\n{skill.content}")
        return "\n\n---\n\n".join(contents)
    
    def list_skills(self) -> List[Skill]:
        """List all available skills"""
        return list(self._skills.values())
    
    def get_help_text(self) -> str:
        """Get help text listing all skills"""
        if not self._skills:
            return "No skills defined. Create folders in ~/.eve_unleashed/skills/"
        
        lines = ["Available Skills:"]
        for name, skill in sorted(self._skills.items()):
            loaded = "✓" if name in self._loaded_skills else " "
            source_tag = f"[{skill.source}]" if skill.source != 'global' else ""
            keywords = ", ".join(skill.keywords[:3])
            lines.append(f"  [{loaded}] {name}: {skill.description} (keywords: {keywords}) {source_tag}")
        
        return "\n".join(lines)
    
    def create_example_skills(self) -> None:
        """Create example skill if none exist"""
        if self.global_skills_dir.exists() and list(self.global_skills_dir.iterdir()):
            return
        
        # Create python-testing skill
        skill_dir = self.global_skills_dir / "python-testing"
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        (skill_dir / "skill.yaml").write_text("""name: python-testing
description: Python testing expertise with pytest
keywords:
  - pytest
  - unittest
  - test
  - testing
  - coverage
tools:
  - bash
  - read_file
  - write_file
""")
        
        (skill_dir / "SKILL.md").write_text("""# Python Testing Expertise

When writing or running Python tests:

## Frameworks
- **pytest** is the preferred framework
- Use fixtures for setup/teardown
- Use parametrize for data-driven tests

## Best Practices
- Test one thing per test function
- Use descriptive test names: `test_user_can_login_with_valid_credentials`
- Group related tests in classes
- Use conftest.py for shared fixtures

## Common Commands
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_user.py

# Run tests matching pattern
pytest -k "test_login"

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

## Assertions
```python
# Basic assertions
assert result == expected
assert item in collection
assert error_msg in str(exception)

# Pytest assertions
import pytest
pytest.raises(ValueError)
pytest.approx(0.1 + 0.2, 0.3)
```
""")


def progressive_load(skill_manager: SkillManager, query: str) -> str:
    """
    Utility function to progressively load skills based on query.
    
    Returns additional context to inject into the prompt.
    """
    matching_skills = skill_manager.find_matching_skills(query)
    
    context_parts = []
    for skill in matching_skills:
        if skill.name not in skill_manager._loaded_skills:
            skill_manager.load_skill(skill.name)
            context_parts.append(f"[Loading skill: {skill.name}]")
    
    if context_parts:
        return "\n".join(context_parts) + "\n\n" + skill_manager.get_loaded_content()
    
    return ""
