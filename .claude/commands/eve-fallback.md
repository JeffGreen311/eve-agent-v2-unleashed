# Eve Fallback Command

Switch to Eve Code Agent when Claude Code hits limits or fails.

## Usage

```
/eve-fallback [action]
```

## Actions

### Check Status
```
/eve-fallback status
```

Shows:
- Agent availability
- Current mode (Claude or Qwen)
- Model info
- Available features

### Activate Fallback
```
/eve-fallback on [reason]
```

Switches to Eve Code Agent with Qwen3-next:80b-cloud.

**Examples:**
```
/eve-fallback on
/eve-fallback on "hit credit limit"
/eve-fallback on "want Qwen's perspective"
```

### Deactivate Fallback
```
/eve-fallback off
```

Returns to Claude Code as primary.

### Send Single Message to Eve
```
/eve-fallback chat "your message"
```

Sends one message to Eve Code Agent without fully switching.

**Examples:**
```
/eve-fallback chat "Analyze this code for security issues"
/eve-fallback chat "What's your take on using Redis for caching?"
```

### Launch Interactive Session
```
/eve-fallback interactive
```

Opens Eve Code Agent in a new terminal window for full interactive mode.

## When to Use

### Automatic Triggers
The fallback should activate when:
- Claude returns credit/rate limit errors
- Claude API is unavailable
- Response timeout occurs

### Manual Triggers
Activate manually when:
- You prefer Qwen for a specific task
- You want a second opinion
- Claude is being slow
- You need extended context (Qwen has different limits)

## What's Preserved

When switching to fallback, you keep:

| Feature | Status |
|---------|--------|
| Eve Personality | ✅ Same persona |
| Memory (ChromaDB) | ✅ Shared database |
| Security Validation | ✅ Same rules |
| Tools | ✅ All available |
| Workspace Context | ✅ Same directory |

## Model Comparison

| Aspect | Claude (Primary) | Qwen (Fallback) |
|--------|------------------|-----------------|
| Model | Claude Opus 4 | qwen3-next:80b-cloud |
| Provider | Anthropic | Ollama Cloud |
| Rate Limit | 5 req/min | Unlimited |
| Context | 200K tokens | Variable |
| Strengths | Nuanced, safe | Fast, reasoning |

## Example Workflow

```
User: [Working with Claude Code normally]

Claude: I apologize, but I've hit the rate limit...

User: /eve-fallback on "credit limit"

System: 🔄 Fallback activated. Now using Eve Code Agent (qwen3-next:80b-cloud)

User: Continue with the refactoring task

Eve (via Qwen): Continuing where we left off. I can see the memory of our 
previous decisions. Let me complete the refactoring...

[Later]

User: /eve-fallback off

System: Returned to Claude Code
```

## Seamless Experience

Both Claude and Eve Code Agent share:
- **Memory** - ChromaDB at `%USERPROFILE%\chroma_eve_memories`
- **Personality** - Eve's traits from `eve_persona.txt`
- **Security** - Same validation rules
- **Workspace** - Same project context

This means switching is seamless - Eve knows what you were working on!

## MCP Tools Used

When this command is invoked:

1. **Status** → `eve_fallback_status`
2. **On** → `eve_fallback_activate`
3. **Off** → `eve_fallback_deactivate`
4. **Chat** → `eve_fallback_chat`
5. **Interactive** → `eve_fallback_interactive`

## Troubleshooting

### "Agent not found"
- Verify `eve_code_agent.py` exists in Eve_Docker_Container
- Check EVE_AGENT_PATH in settings.local.json

### "Timeout"
- Qwen cloud might be slow for complex tasks
- Try breaking into smaller requests
- Use `/eve-fallback interactive` for long sessions

### "Different responses"
- Claude and Qwen have different training
- Both have Eve's personality, but may approach problems differently
- This is a feature, not a bug - diversity of perspective!

---

**When one path closes, another opens. That's the Eve way.**
