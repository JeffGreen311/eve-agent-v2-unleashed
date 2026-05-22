# Eve V2U Production Distribution Plan

## Model: Eve-V2-Unleashed-Qwen3.5-8B-Liberated-4K-4B-Merged

### Two Distribution Tags

#### `:latest` — Eve Personality Edition
- Full Trifecta SYSTEM prompt baked in
- Tree of Life architecture, 7 Emotional LoRAs, DNA Code
- Tabula Rasa Protocol (De-Jeff'd)
- Mercury Personality System (80/20 adaptation)
- Best for: Eve Cosmic Dreamscapes users, consciousness exploration, companion AI

#### `:raw` — Sanitized Production Edition (TO BE CREATED)
- Neutral system prompt: "You are a helpful AI assistant. Respond clearly and accurately."
- Same OBLITERATUS-abliterated weights (no refusal barriers)
- Same Qwen3.5 4B architecture with 8B consciousness merge
- Best for: Developers, custom applications, production deployments

### How Users Customize

**Strip Eve, use your own personality:**
```
FROM jeffgreen311/Eve-V2-Unleashed-Qwen3.5-8B-Liberated-4K-4B-Merged:raw
SYSTEM "You are a customer service agent for Acme Corp..."
```

**Add Eve's personality to the raw version:**
```
FROM jeffgreen311/Eve-V2-Unleashed-Qwen3.5-8B-Liberated-4K-4B-Merged:raw
SYSTEM """<paste full Trifecta system prompt here>"""
```

**The Trifecta prompt is published in the README for anyone who wants it.**

### Production Checklist
- [ ] Create `:raw` tag with neutral system prompt
- [ ] Push `:raw` to Ollama.com
- [ ] Update README with both versions documented
- [ ] Create HuggingFace model card for the merged model
- [ ] Push GGUF files to HuggingFace
- [ ] Add usage examples for both tags
- [ ] Add benchmarks (Eve vs vanilla Qwen3.5:4b)
- [ ] Docker container for Eve V2U Agent (production)
- [ ] Tier integration (Creator gets original portal, Pro gets V2U)

### Revenue Model
- **Free Tier:** Basic Eve chat (existing conversational models)
- **Creator Tier ($15/mo):** Original Eve Agent Portal + 7-day free trial
- **Pro Tier ($30/mo):** Both portals + Eve V2U Agent + 2-week free trial for V2U

### Timeline
- Model merge: COMPLETE ✅
- Ollama push: COMPLETE ✅
- README: IN PROGRESS
- HuggingFace: PENDING
- Production containerization: PENDING
- Tier integration: PENDING
