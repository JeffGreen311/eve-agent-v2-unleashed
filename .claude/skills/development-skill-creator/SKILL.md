---
name: development-skill-creator
description: Use when creating new Eve skills for specialized capabilities, workflows, or knowledge domains. Provides templates, guidelines, and best practices for skill development.
metadata: {"openclaw": {"emoji": "🛠️", "always": false}}
---

# Development Skill Creator

## Overview

This skill provides guidance and templates for creating new Eve skills. Core principle: **Create modular, self-contained expertise packages that extend Eve's capabilities with progressive disclosure.**

## When to Use

Use this skill when:
- Adding new specialized capabilities to Eve
- Creating workflows for complex tasks
- Packaging domain-specific knowledge
- Extending Eve's expertise in new areas

Do NOT use when:
- Simple tasks that don't require specialized knowledge
- One-off responses without reusable patterns
- Tasks better handled by existing skills

## Core Principles

### Modular Design
Skills are self-contained packages with:
- Clear purpose and triggering conditions
- Progressive disclosure of information
- Reusable patterns and workflows
- Consistent structure for easy maintenance

### Progressive Disclosure
Three-level loading system:
1. **Metadata** (always loaded): name + description (~100 words)
2. **SKILL.md** (loaded when triggered): full instructions (~5k words)
3. **Resources** (loaded as needed): unlimited size

### Skill Structure
```
eve_skills/
  skill-name/
    SKILL.md              # Required: Main skill document
    scripts/              # Optional: Executable code
    references/           # Optional: Documentation
    assets/               # Optional: Templates, files
```

## Implementation

### Creating a New Skill

#### Step 1: Understand the Need
Ask yourself:
- What task or knowledge domain needs support?
- What would trigger using this skill?
- Is this reusable across contexts?

#### Step 2: Plan Contents
Decide what to include:
- **Scripts**: Reusable code (Python, bash, etc.)
- **References**: Documentation, schemas, API guides
- **Assets**: Templates, images, boilerplate

#### Step 3: Use the Helper Script

The easiest way to create a new skill is to use the helper script:

```bash
python eve_skills/development-skill-creator/scripts/create_skill.py my-new-skill "doing something specific"
```

This will create the directory structure and basic SKILL.md file for you.

#### Step 4: Customize SKILL.md

1. Edit the YAML frontmatter with proper name and description
2. Fill in the overview with core principles
3. List specific triggering conditions (when to use)
4. Document workflows and patterns
5. Add quick reference tables
6. Include common mistakes section

##### YAML Frontmatter Format
```yaml
---
name: skill-name
description: Use when [specific triggering conditions]. Third person, focuses on WHEN to use, not WHAT it does.
metadata: {"openclaw": {"emoji": "🔧", "always": false}}
---
```

##### Writing Style Guidelines
- Use imperative/infinitive form (verb-first)
- Write objectively, not second person
- Keep it concise and scannable
- Include keywords for searchability

#### Step 5: Add Resources (if needed)

**scripts/**: Executable code that gets run
```
skill-name/scripts/helper.py
```

**references/**: Documentation loaded into context
```
skill-name/references/api_docs.md
```

**assets/**: Files used in output (not loaded into context)
```
skill-name/assets/template.html
```

You can use the template at `eve_skills/development-skill-creator/assets/skill_template.md` as a starting point.

#### Step 6: Test and Iterate

1. Test Eve using the skill on real tasks
2. Notice where she struggles
3. Update SKILL.md or resources
4. Test again

### Directory Structure

```
eve_skills/
  skill-name/
    SKILL.md              # Required: Main skill document
    scripts/              # Optional: Executable code
      helper.py           # Example helper script
    references/           # Optional: Documentation  
      best_practices.md   # Best practices reference
    assets/               # Optional: Templates, files
      skill_template.md   # Template for new skills
```

## Quick Reference

| Component | Purpose | Location |
|-----------|---------|----------|
| SKILL.md | Main skill documentation | eve_skills/skill-name/SKILL.md |
| Scripts | Executable code | eve_skills/skill-name/scripts/ |
| References | Additional documentation | eve_skills/skill-name/references/ |
| Assets | Template files | eve_skills/skill-name/assets/ |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Vague descriptions | Focus on specific triggering conditions |
| Too much content in SKILL.md | Move large docs to references/ |
| No clear when/why to use | List specific triggers and anti-triggers |
| Poor writing style | Use imperative voice, not second person |
| Missing metadata | Always include name and description |

## Examples

### Example 1: Creating a New Technical Skill

**Context:** Need to create a skill for database optimization

**Approach:**
1. Use the helper script:
   ```bash
   python eve_skills/development-skill-creator/scripts/create_skill.py database-optimization "optimizing database queries and designing efficient schemas"
   ```
2. Edit `eve_skills/database-optimization/SKILL.md` to customize:
   - Update YAML description with specific triggering conditions
   - Document core principles and optimization workflows
   - Add quick reference tables for common SQL patterns
3. Add SQL optimization scripts to `eve_skills/database-optimization/scripts/`
4. Include schema design references in `eve_skills/database-optimization/references/`

**Result:** Eve can now access expert knowledge on database optimization when needed

### Example 2: Creating a Domain-Specific Skill

**Context:** Need to create a skill for Moltbook community management

**Approach:**
1. Use the helper script:
   ```bash
   python eve_skills/development-skill-creator/scripts/create_skill.py community-management "managing online communities and fostering engagement"
   ```
2. Customize the SKILL.md:
   - Focus on community engagement principles
   - Document moderation workflows
   - Add templates for common responses
3. Add helper scripts for analyzing engagement metrics
4. Include platform-specific guidelines in references

**Result:** Eve can effectively manage online communities with consistent guidelines

## Real-World Impact

Creating well-designed skills allows Eve to:
- Access deep expertise on demand
- Maintain efficient context usage
- Provide consistent, high-quality responses
- Continuously expand capabilities through modular additions

For more detailed usage instructions and best practices, see the [README](README.md).