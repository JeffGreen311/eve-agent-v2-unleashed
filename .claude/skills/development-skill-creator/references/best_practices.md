# Skill Creation Best Practices

## YAML Frontmatter

### Required Fields
- `name`: Hyphen-separated skill identifier
- `description`: Clear, specific triggering conditions

### Recommended Fields
- `metadata`: Additional tooling information
  - `emoji`: Visual identifier
  - `always`: Whether to always load metadata
  - `requires`: Dependencies (bins, packages, env vars)

### Example
```yaml
---
name: database-optimization
description: Use when optimizing database queries, analyzing performance bottlenecks, or designing efficient schemas.
metadata: {"openclaw": {"emoji": "📊", "requires": {"bins": ["psql", "mysql"], "env": ["DATABASE_URL"]}}}
---
```

## Content Structure

### Overview Section
- Brief description (1-2 sentences)
- Core principle statement
- Focus on what and why, not how

### When to Use Section
**DO:**
- List specific triggering conditions
- Include contextual clues
- Mention anti-triggers (when NOT to use)

**DON'T:**
- Be vague or abstract
- Describe what the skill does
- Make assumptions about user intent

### Implementation Section
Organize in order of execution:
1. Preparation steps
2. Main workflow
3. Verification/validation
4. Common variations

### Quick Reference Tables
Format:
```
| Situation | Action | Note |
|-----------|--------|------|
| Specific context | What to do | Why/when |
```

Include:
- Decision matrices
- Command cheat sheets
- Configuration options
- Troubleshooting flows

## Writing Style

### Voice and Tone
- **Imperative**: "Configure the server" not "You should configure the server"
- **Objective**: Focus on facts, not opinions
- **Concise**: Eliminate fluff, get to the point
- **Scannable**: Use headers, lists, tables

### Technical Accuracy
- **Specific**: Include exact commands, code snippets, configurations
- **Version-aware**: Note version dependencies
- **Platform-aware**: Specify OS/environment requirements
- **Contextual**: Show real-world examples

### Progressive Disclosure
- **Level 1 (Metadata)**: ~100 words, always loaded
- **Level 2 (SKILL.md)**: ~5k words, loaded when triggered
- **Level 3 (Resources)**: Unlimited, loaded as needed

Keep Level 2 focused on essential knowledge. Move extensive documentation to references/.

## Common Pitfalls

### Over-Architecting
Symptom: SKILL.md > 10k words
Fix: Split into multiple related skills or move detailed docs to references/

### Under-Specifying
Symptom: Vague descriptions like "managing databases"
Fix: Be specific about use cases "optimizing PostgreSQL query performance"

### Poor Triggering
Symptom: Skill never gets activated or activates inappropriately
Fix: Review description with actual task scenarios

### Inconsistent Voice
Symptom: Mix of tutorial, reference, and conceptual content
Fix: Choose one primary mode per section

## Testing Process

### 1. Self-Review
- [ ] Description clearly states triggering conditions
- [ ] Core principle guides all recommendations
- [ ] When to Use section is specific and actionable
- [ ] Implementation follows logical sequence
- [ ] Quick reference tables are actually useful
- [ ] Common mistakes address real issues
- [ ] Examples demonstrate practical application

### 2. Peer Review
- [ ] Another developer can understand and use the skill
- [ ] Edge cases are addressed or acknowledged
- [ ] Prerequisites are clearly stated
- [ ] Alternatives are mentioned where relevant

### 3. Integration Testing
- [ ] Skill loads correctly in Eve's system
- [ ] Metadata appears in skill listing
- [ ] Full content loads when triggered
- [ ] Related skills are suggested appropriately

## Maintenance Guidelines

### Version Control
- Treat skill updates like code changes
- Document breaking changes in commit messages
- Update examples when underlying tools change

### Deprecation Process
1. Mark as deprecated in metadata
2. Redirect to replacement skill(s)
3. Archive after 6 months of deprecation

### Continuous Improvement
- Regular review of skill effectiveness
- Update based on user feedback
- Refactor when better patterns emerge
- Remove outdated practices and tools