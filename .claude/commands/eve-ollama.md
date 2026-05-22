# Eve Ollama Command

Chat with Qwen models through Ollama as an alternative perspective.

## Usage

```
/eve-ollama <action> [args]
```

## Actions

### Chat
```
/eve-ollama chat "message"
```

Send a message to Qwen and get a response with Eve's persona.

**Examples:**
```
/eve-ollama chat "What's the best way to handle errors in async Python?"
/eve-ollama chat "Give me a creative solution for caching"
```

### Analyze Code
```
/eve-ollama analyze <type> "content"
```

Get AI analysis on code or text.

**Types:**
- `code_review` - Bugs, performance, security, style
- `architecture` - Design patterns, scalability
- `security` - Vulnerabilities, OWASP, hardening
- `general` - Overall feedback

**Examples:**
```
/eve-ollama analyze code_review "def process(data): return eval(data)"
/eve-ollama analyze security "user_input = request.args.get('q')"
```

### Get Second Opinion
```
/eve-ollama opinion "question or decision"
```

Get an alternative perspective on a technical decision.

**Examples:**
```
/eve-ollama opinion "Should I use PostgreSQL or MongoDB for this project?"
/eve-ollama opinion "Is microservices the right choice for a team of 3?"
```

## Why Use This?

### Different Perspective
Claude and Qwen have different training and approaches. Getting both perspectives can:
- Catch blind spots
- Offer creative alternatives
- Validate decisions

### Specific Strengths
Qwen3-Next 80B excels at:
- Complex reasoning with visible thinking
- Code generation and analysis
- Mathematical and logical problems

### Fallback
If Claude is rate-limited or unavailable, Ollama continues working.

## Models Available

| Model | Use Case |
|-------|----------|
| `qwen3-next:80b-cloud` | Primary - complex tasks, reasoning |
| `qwen3-coder:280b-cloud` | Fallback - coding specialist |

## MCP Tools Used

When this command is invoked, Claude should use:

1. **ollama_chat** - For general chat/questions
2. **ollama_analyze** - For code/architecture analysis
3. **ollama_generate** - For text completion

## Example Workflow

```
User: /eve-ollama opinion "React vs Vue for a dashboard project"

Claude: Let me get Qwen's perspective on this...

[ollama_chat: "What are the tradeoffs between React and Vue for building a data dashboard?"]

Qwen says:
🤔 Thinking: [reasoning process]

💬 Response:
For a dashboard specifically:
- React: Better for complex state, larger ecosystem of chart libraries
- Vue: Faster setup, gentler learning curve, great for rapid prototyping

Consider: Team experience, timeline, and specific visualization needs...

Claude: That aligns with my assessment. I'd add that React's concurrent features
could help with heavy data rendering. Want me to prototype in both?
```

## Configuration

The Ollama MCP server uses:
- API Key: Set in settings.local.json
- Base URL: https://ollama.com (cloud) or localhost:11434 (local)
- Eve's persona from eve_persona.txt

## Troubleshooting

### "Ollama client not initialized"
- Check OLLAMA_API_KEY is set
- Verify network connectivity to ollama.com

### Slow responses
- qwen3-next:80b is large, responses take 10-30 seconds
- Consider using local models for simple questions

### "All models failed"
- Check API key validity
- Verify Ollama cloud service status
- Try local Ollama if installed
