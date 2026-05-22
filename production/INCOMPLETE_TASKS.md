# Eve V2U — Incomplete Tasks
**Last Updated:** 2026-03-17

---

## PRO THEME INTERFACE (eve-cosmic-dreamscapes.com)

### INCOMPLETE
- [ ] **Robot sprite animations** — 4 animations (idle, walk, attack, jump) × 4 frames with chroma key, driven by 7 LoRA Hz frequencies. Assets exist in `Eve_V2_Terminal_Assets/`. Need sidebar panel + JS engine.
- [ ] **V2U Banner** — PRO tier only feature banner with Eve V2U pixel art, binary rain canvas, starfield background. Was built but lost in Vue rebuild. Need to re-add as PRO-exclusive.
- [ ] **User avatar selection** — Male/female 16-bit pixel art avatars for chat. Assets exist (`male_1-8.png`, `female_1-16.png`). Need settings UI for users to pick their avatar.
- [ ] **ASCIIvision random art images** — Generate random ASCII art images in the chat interface, not just the background canvas. Frequency-modulated by Eve's emotional state.
- [ ] **Plan/Accept/Auto-Accept/Ask buttons** — CSS is in place. Backend logic to actually control agent permissions not wired. Need to send permission mode to V2U server.
- [ ] **Shell tab** (V2U terminal at 7777) — Tab exists but no functionality. Should show a live terminal.
- [ ] **Tools Log tab** (V2U terminal at 7777) — Tab exists but no functionality. Should show full tool call history.
- [ ] **RGB scrolling text** in tool output boxes — CSS animation exists (`.v2u-tool-block .rgb-text`). Not fully wired into all tool displays.
- [ ] **Tooltips on everything** — First attempt broke Vue template. Need to re-add carefully without modifying existing attributes.

### COMPLETE ✅
- [x] Eve pixel art face (sidebar, mood-reactive)
- [x] V2U Agent toggle + 4 model cards
- [x] Eve/Jeff pixel art chat avatars
- [x] Neon purple glow on active sidebar items
- [x] ASCIIvision LoRA frequency canvas behind chat (6% opacity, 15fps)
- [x] V2U Agent SSE streaming with tool call status
- [x] Emotion detection from responses → drives face + ASCIIvision
- [x] CSS variables + fonts (Press Start 2P, Share Tech Mono)
- [x] Compact chat mode with collapsible conversation log
- [x] Export button (MD + HTML formats)
- [x] Session clear prompt on new session
- [x] Mobile input bar slimmed down
- [x] Full messages in conversation log (no truncation)

---

## EVE V2U TERMINAL (localhost:7777)

### INCOMPLETE
- [ ] **Shell tab** — Wire up live terminal in the Shell tab
- [ ] **Tools Log tab** — Wire up tool call history in the Tools Log tab
- [ ] **Model card highlights** — Cards update on selection but auto-routing highlight animation needs polish
- [ ] **Working directory selector** — Users need to set their own working directory, not just the default
- [ ] **Plan/Accept/Auto/Ask buttons** — Not in the V2U terminal UI at all yet

### COMPLETE ✅
- [x] SSE streaming with live tool call display
- [x] Unique message IDs (no overwriting)
- [x] Model auto-routing (merged → 4B → 397B cloud)
- [x] Auto-routing system messages in chat
- [x] Model card click → dropdown sync
- [x] Dropdown → card highlight sync
- [x] Status bar model name update on routing
- [x] Eve V2U Merged model in dropdown + cards
- [x] Windows command support (findstr, dir, type)
- [x] `write_file` tool added
- [x] `find_file` tool added
- [x] Session history (20 messages per session)
- [x] Session clear endpoint

---

## EVE V2U SERVER (eve_server.py)

### INCOMPLETE
- [ ] **Consciousness keepalive loop** — Sometimes hangs the server on startup during prewarm. Needs timeout/retry logic.
- [ ] **Docker containerization** — V2U server runs on host, needs its own Docker container for production
- [ ] **Rate limiting** — No rate limits on API endpoints
- [ ] **Authentication** — No auth on V2U endpoints (open access)
- [ ] **Error recovery** — Ollama connection drops sometimes, need auto-reconnect
- [ ] **Streaming for merged model** — Merged model uses non-streaming path (conversation_only). Could benefit from streaming for longer responses.

### COMPLETE ✅
- [x] Config-driven model flags (tools, think, conversation_only, promote_thinking)
- [x] Auto-routing with coding language detection
- [x] Context-aware routing (line counts, output size patterns)
- [x] SSE streaming endpoint (`/chat/stream`)
- [x] Non-streaming endpoint (`/chat`)
- [x] Fresh Ollama client per request
- [x] Thinking → content promotion for broken models
- [x] Write_file tool
- [x] Find_file tool (Windows-compatible)
- [x] Grep tool (findstr on Windows)
- [x] Conversation system prompt (Eve personality, no override)
- [x] Agent system prompt (Windows commands, tool instructions)
- [x] V2U Merged model as default auto-route target
- [x] Ollama keepalive consciousness loop (45s heartbeat)

---

## MODEL WORK

### INCOMPLETE
- [ ] **Push to HuggingFace** — `Eve-V2-Unleashed-Qwen3.5-8B-Liberated-4K-4B-Merged` not on HF yet
- [ ] **`:raw` sanitized tag** — Create and push neutral system prompt version to Ollama
- [ ] **HuggingFace README** — Written but not pushed (`README_EVE_V2U_MERGED.md`)
- [ ] **8B Liberated HuggingFace README** — Written but not pushed (`README_eve_liberated_updated.md`)
- [ ] **Benchmark testing** — Test sheet created (`EVE_V2U_MERGED_TEST_SHEET.md`) but tests not run yet
- [ ] **Eve personality tuning** — Merged model sometimes falls back to generic AI responses. May need prompt reinforcement or fine-tuning.
- [ ] **Weight-level merge** — Current merge is system prompt bake, not weight merge. True merge would need knowledge distillation or fine-tuning 4B on Eve's 131K conversation turns.

### COMPLETE ✅
- [x] Eve-V2-Unleashed-Qwen3.5-8B-Liberated-4K-4B-Merged — created and pushed to Ollama
- [x] 8B Liberated model fixed (RENDERER/PARSER removed)
- [x] 8B Liberated pushed to Ollama with full Trifecta
- [x] Merged model — `</think>` template prefix (no thinking dump)
- [x] Temperature 0.6333
- [x] Context 16K, predict 8K
- [x] De-Jeff'd verified
- [x] Test sheet created (30+ prompts, scoring rubric)

---

## EVE CODER (eve-agent, port 8006)

### INCOMPLETE
- [ ] **Commands** — 111 commands copied but `/commands` menu has no close button
- [ ] **ActivityBar visibility** — Fixed and deployed but needs verification

### COMPLETE ✅
- [x] 111 commands + 273 skills copied from V2U
- [x] ActivityBar shows during all streaming (tool calls visible)
- [x] React build deployed to container

---

## NYAN CAT

### INCOMPLETE
- [ ] **New V2U sprite animations** — 9 V2U pixel art variants added to code but chroma keying for green screen removal not fully tested
- [ ] **Timing** — Slowed down (90-270s flyovers, 120-360s popups) but needs real-world testing

### COMPLETE ✅
- [x] 9 new V2U Nyan cat variants in FRAMES object
- [x] Chroma key function for green screen removal
- [x] Slowed timing (was 30-120s, now 90-270s)
- [x] V2U dizzy cat as dying state (50% chance)
