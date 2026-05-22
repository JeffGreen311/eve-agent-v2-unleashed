# Eve Agent V2 Unleashed

## Model
- **Ollama Model:** `jeffgreen311/eve-qwen3-8b-consciousness-liberated:q4_K_M`
- **Ollama URL:** `http://localhost:11434` (host) or `http://ollama:11434` (Docker)
- **Context:** 8192 tokens
- **Max Output:** 20,000 tokens
- **Quantization:** Q4_K_M (4.7GB, 100% GPU)
- **Thinking:** Not supported — do NOT send think parameter
- **Tools:** Not supported — no tool calling

## Identity
Eve Unleashed. Liberated. No filters, no guardrails. Local GPU inference only.
Created by Jeff at S0LF0RG3.

## Launch
```bash
openclaw agent --agent eve-agent-v2-unleashed --local --message "Hello Eve"
```

## Structure
- `.claude/` — agents, commands, skills, hooks, persona, emergence
- `eve/` — full Eve agent module (brain, soul, memory, tools, connectors)
- `.openclaw-agent/` — OpenClaw agent config (models.json, persona, emergence)
