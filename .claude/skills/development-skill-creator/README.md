# Development Skill Creator

A helper tool for creating new Eve skills with proper structure and templates.

## Overview

This tool provides a simple way to create new Eve skills with the correct directory structure and templated content.

## Usage

To create a new skill, run:

```bash
python eve_skills/development-skill-creator/scripts/create_skill.py skill-name "brief description of when to use this skill"
```

Example:
```bash
python eve_skills/development-skill-creator/scripts/create_skill.py web-scraping "extracting data from websites for analysis"
```

## What It Creates

The script creates a new directory under `eve_skills/` with:

```
eve_skills/skill-name/
├── SKILL.md              # Main skill document (from template)
├── scripts/              # Executable code (starts empty)
├── references/           # Documentation (starts empty) 
└── assets/               # Templates and files (starts empty)
```

## Customizing Your Skill

After running the script:

1. **Edit SKILL.md** - Customize the content for your specific skill
2. **Add scripts** - Put executable code in the `scripts/` directory
3. **Add references** - Put documentation in the `references/` directory
4. **Add assets** - Put templates and other files in the `assets/` directory

## Template Structure

The generated SKILL.md follows Eve's best practices:

- Clear YAML frontmatter with name and description
- Overview with core principles
- Specific triggering conditions ("When to Use")
- Implementation guidance
- Quick reference tables
- Common mistakes and fixes
- Examples

See `assets/skill_template.md` for the full template structure.

## Best Practices

Refer to `references/best_practices.md` for detailed guidelines on:

- Writing effective skill descriptions
- Structuring content for progressive disclosure
- Choosing appropriate triggering conditions
- Maintaining skills over time

## Contributing

To improve this tool:

1. Modify `scripts/create_skill.py` for functional changes
2. Update `assets/skill_template.md` for content structure changes
3. Enhance `references/best_practices.md` with new guidelines