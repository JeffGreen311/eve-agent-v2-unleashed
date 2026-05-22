#!/usr/bin/env python3
"""
Helper script to create new Eve skills following the standard structure.
"""

import os
import sys
import shutil
from pathlib import Path

def create_skill(skill_name, description=""):
    """
    Create a new skill directory with the standard structure.
    
    Args:
        skill_name (str): Name of the skill (hyphen-separated)
        description (str): Brief description of when to use this skill
    """
    # Validate skill name
    if not skill_name:
        print("Error: Skill name is required")
        return False
    
    # Create skill directory
    skill_dir = Path(f"eve_skills/{skill_name}")
    if skill_dir.exists():
        print(f"Error: Skill '{skill_name}' already exists")
        return False
    
    try:
        # Create directory structure
        skill_dir.mkdir(parents=True)
        (skill_dir / "scripts").mkdir()
        (skill_dir / "references").mkdir()
        (skill_dir / "assets").mkdir()
        
        # Create SKILL.md from template
        template_path = Path("eve_skills/skill-template/SKILL.md")
        if template_path.exists():
            # Copy template
            shutil.copy(template_path, skill_dir / "SKILL.md")
            
            # Update YAML frontmatter
            with open(skill_dir / "SKILL.md", "r", encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Replace placeholder values
            content = content.replace("skill-template", skill_name)
            if description:
                content = content.replace(
                    "Template for creating new Eve skills. Use when creating a new specialized capability or workflow for Eve.",
                    description
                )
            
            # Remove the notes section at the end including the separator
            notes_start = content.find("\n## Notes for Skill Creators")
            if notes_start != -1:
                content = content[:notes_start]
            
            # Handle encoding issues by removing problematic characters
            content = content.encode('utf-8', errors='ignore').decode('utf-8')
            
            with open(skill_dir / "SKILL.md", "w", encoding='utf-8') as f:
                f.write(content)
        else:
            # Create basic SKILL.md
            skill_md_content = f'''---
name: {skill_name}
description: {"Use when " + description if description else "Use when [specific triggering conditions]"}
metadata: {{"openclaw": {{"emoji": "🔧", "always": false}}}}
---

# {skill_name.replace("-", " ").title()}

## Overview

[Brief description of what this skill does]

Core principle: [Fundamental approach or philosophy]

## When to Use

Use this skill when:
- [Specific condition 1]
- [Specific condition 2]

Do NOT use when:
- [When not applicable]
- [Alternative approach better]

## Core Principles/Patterns

[Document the main approaches, workflows, or methodologies]

## Implementation

[Step-by-step guide or workflow]

## Quick Reference

| Situation | Action | Note |
|-----------|--------|------|
| [Scenario] | [Action] | [Context] |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| [Problem] | [Solution] |

## Examples

### Example 1: [Scenario]

**Context:** [Setup description]

**Approach:**
```
[Code, commands, or procedure]
```

**Result:** [Outcome]
'''
            with open(skill_dir / "SKILL.md", "w") as f:
                f.write(skill_md_content)
        
        print(f"Successfully created skill: {skill_name}")
        print(f"Location: {skill_dir}")
        print("\nNext steps:")
        print("1. Edit eve_skills/{}/SKILL.md".format(skill_name))
        print("2. Add scripts to eve_skills/{}/scripts/".format(skill_name))
        print("3. Add documentation to eve_skills/{}/references/".format(skill_name))
        print("4. Add assets to eve_skills/{}/assets/".format(skill_name))
        
        return True
        
    except Exception as e:
        print(f"Error creating skill: {e}")
        # Clean up partially created directory
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        return False

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python create_skill.py <skill_name> [description]")
        print("Example: python create_skill.py api-integration 'integrating with external APIs'")
        return 1
    
    skill_name = sys.argv[1]
    description = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
    
    if create_skill(skill_name, description):
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())