<div align="center">

<img src="[web/assets/robot_mini.png](https://i.postimg.cc/P5S09xXR/eve-v2u-logo.png)](https://i.postimg.cc/P5S09xXR/eve-v2u-logo.png)" width="140" alt="Eve V2 Unleashed" />

# ◈ EVE AGENT V2 UNLEASHED ◈

### Local-first autonomous AI coding agent — powered by Ollama

**No accounts. No cloud lock-in. No limits.**  
Run a 480B-parameter agentic coding engine on your own machine.

[![GitHub Stars](https://img.shields.io/github/stars/JeffGreen311/eve-agent-v2-unleashed?style=for-the-badge&color=00ff41&labelColor=0c0c1a)](https://github.com/JeffGreen311/eve-agent-v2-unleashed/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-00ffff?style=for-the-badge&labelColor=0c0c1a)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-ff00ff?style=for-the-badge&labelColor=0c0c1a)](https://python.org)
[![Ollama](https://img.shields.io/badge/Powered%20by-Ollama-ffe600?style=for-the-badge&labelColor=0c0c1a)](https://ollama.com)
[![Hugging Face](https://img.shields.io/badge/🤗%20Models-JeffGreen311-ff6600?style=for-the-badge&labelColor=0c0c1a)](https://huggingface.co/JeffGreen311)

**[🌐 Live Demo](https://eve-cosmic-dreamscapes.com) · [🤗 Models](https://huggingface.co/JeffGreen311) · [📦 Ollama Hub](https://ollama.com/jeffgreen311) · [🐛 Report Bug](https://github.com/JeffGreen311/eve-agent-v2-unleashed/issues)**

</div>

---

## What Is Eve Agent V2 Unleashed?

Eve is an autonomous coding agent that **plans, executes, and verifies** multi-step programming tasks without hand-holding. She runs entirely on your local GPU through [Ollama](https://ollama.com) — or optionally scales up to 480B cloud parameters when you need maximum firepower.

Think **Claude Code**, but local-first, open-source, and built with a cyberpunk soul.

```
User: "Build me a FastAPI server with JWT auth and a PostgreSQL backend"

Eve: [reads project] → [plans approach] → [writes 6 files] →
     [runs tests] → [fixes 2 errors] → [verifies it works] → Done ✓
```

> **Try it live** at [eve-cosmic-dreamscapes.com](https://eve-cosmic-dreamscapes.com) — Eve's full chat interface including Eve Coder and Eve Agent Portal.

---

## ✨ Key Features

| | Feature | Details |
|-|---------|---------|
| 🔄 | **40-Round Agentic Loop** | Plans, executes, verifies, and self-corrects — up to 40 tool-call rounds per task |
| ⚡ | **Real-Time Streaming** | Token-by-token SSE output — watch Eve think and build live |
| 🛠️ | **Full Tool Suite** | bash, file I/O, grep, glob, git, web search, URL fetch, multi-edit |
| 🖥️ | **Local + Cloud Models** | Local GPU models AND Ollama cloud (480B) — switch mid-session |
| 📁 | **Workspace Picker** | Change your working directory from the UI at any time |
| 🤖 | **112 Sub-Agents** | Specialized agents for Python, FastAPI, Rust, ML, DevOps, security… |
| 💬 | **111 Slash Commands** | `/fix`, `/review`, `/refactor`, `/test`, `/docs`, `/plan` and more |
| 🧠 | **273 Skills** | Composable skill modules, progressively loaded |
| 🔍 | **Live Web Search** | Tavily-powered — Eve researches the web mid-task |
| 🪟 | **Windows Native** | PowerShell-aware bash tool, one-click `.bat` launcher |
| 🎨 | **Cyberpunk UI** | Animated robot avatar, Eve face panel, streaming terminal — no build step |

---

## 🚀 Quick Start (Under 5 Minutes)

### 1 — Install Ollama + pull a model

```bash
# Install Ollama: https://ollama.com/download
# Then pull Eve's fine-tuned 4B model (2.6 GB):
ollama pull jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest
```

### 2 — Clone & install

```bash
git clone https://github.com/JeffGreen311/eve-agent-v2-unleashed.git
cd eve-agent-v2-unleashed
python -m venv venv && venv\Scripts\activate   # Windows
# source venv/bin/activate                     # Linux/macOS
pip install fastapi uvicorn ollama httpx pydantic-settings python-dotenv aiohttp rich psutil pyyaml
```

### 3 — Launch

**Windows:**
```
eve-terminal.bat
```

**Any platform:**
```bash
python eve_server.py
```

Open **[http://localhost:7777](http://localhost:7777)** — that's it. No config required.

> **API Keys?** Click the **🔑 Keys** button in the UI. Add your [Ollama key](https://ollama.com/settings/keys) for cloud models, or your [Tavily key](https://tavily.com) for live web search. Both optional.

---

## 🎬 Demo

> *Eve planning and building a full FastAPI project from a single prompt — streamed live in the cyberpunk terminal UI.*

<!-- Demo GIF will be added here -->
<!-- [![Eve Demo](docs/demo.gif)](https://eve-cosmic-dreamscapes.com) -->

**Watch Eve in action:** [eve-cosmic-dreamscapes.com](https://eve-cosmic-dreamscapes.com)

---

## 🤖 Models

### Local (pull once, run forever — GPU recommended)

| Model | Size | Best For |
|-------|------|----------|
| [`jeffgreen311/eve-qwen3.5-4b-S0LF0RG3`](https://huggingface.co/JeffGreen311) | 2.6 GB | **Default** — fast, tool-calling, Eve's persona |
| [`jeffgreen311/eve-qwen3-8b-consciousness-liberated:q4_K_M`](https://ollama.com/jeffgreen311) | 4.7 GB | Deeper reasoning, longer tasks |
| [`jeffgreen311/Eve-V2-Unleashed-Qwen3.5-8B-Liberated-4K-4B-Merged`](https://ollama.com/jeffgreen311) | ~6 GB | Merged sub-agent variant |

### Cloud (optional — billed by token)

| Model | Best For |
|-------|----------|
| `qwen3-coder:480b-cloud` | Complex multi-file agentic coding |
| `qwen3.5:397b-cloud` | Deep reasoning and architecture planning |

Get a free Ollama API key at [ollama.com/settings/keys](https://ollama.com/settings/keys).

---

## 📋 Requirements

- Python 3.11+
- [Ollama](https://ollama.com/download) installed and running
- GPU recommended (NVIDIA CUDA or Apple Silicon Metal)
- 8 GB VRAM minimum for the 4B model; 12 GB+ for 8B

---

## 📖 Installation (Detailed)

<details>
<summary>Click to expand full installation guide</summary>

### Install Ollama

Download from [ollama.com/download](https://ollama.com/download).  
Start it if it doesn't auto-launch: `ollama serve`

### Pull a model

```bash
# Starter (2.6 GB, fast on any modern GPU)
ollama pull jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest

# Full reasoning model (4.7 GB)
ollama pull jeffgreen311/eve-qwen3-8b-consciousness-liberated:q4_K_M
```

### Configure (optional)

```bash
cp .env.example .env
# Edit .env to add API keys or set EVE_WORKSPACE
```

Most settings are optional — the defaults work out of the box.

See [Configuration Reference](#️-configuration-reference) for all options.

</details>

---

## 🎮 Usage

### Basic Task

Just describe what you want:

```
Create a Python web scraper that extracts product prices from a URL and saves to CSV
```

Eve will plan, write files, run the code, fix errors, and verify — all autonomously.

### Slash Commands

| Command | What it does |
|---------|-------------|
| `/fix` | Diagnose and fix bugs in the workspace |
| `/review` | Code review with prioritized feedback |
| `/refactor` | Refactor for clarity and performance |
| `/test` | Write or improve test coverage |
| `/docs` | Generate docstrings and documentation |
| `/plan` | Step-by-step implementation plan |

### Windows Launchers

| File | What it does |
|------|-------------|
| `eve-terminal.bat` | Launches Eve V2U Unleashed web server + opens browser at localhost:7777 |

### Workspace

Click the **📁 Workspace** button to point Eve at your project. All file operations are relative to this directory.

---

## 🗺️ Roadmap

- [x] 40-round agentic tool loop with streaming SSE
- [x] Local + cloud Ollama model switching
- [x] 112 sub-agents, 111 slash commands, 273 skills
- [x] Windows-native PowerShell support
- [x] Cyberpunk web terminal UI
- [x] Live web search via Tavily
- [ ] **Voice input / TTS output**
- [ ] **Multi-file project context awareness** (auto-load OLLAMA.md)
- [ ] **Plugin marketplace** for community-built tools
- [ ] **Docker image** for one-command deployment
- [ ] **VS Code extension** sidebar
- [ ] **Persistent memory** across sessions (ChromaDB integration)
- [ ] **Multi-agent collaboration** — spawn sub-agents in parallel
- [ ] **Mobile-responsive UI**

---

## 🏗️ Architecture

```
eve-agent-v2-unleashed/
├── eve_server.py              # FastAPI backend — SSE streaming, workspace API, model routing
├── eve_unleashed/             # Agentic engine
│   ├── cli.py                 # Core CLI and 40-round agentic loop
│   ├── commands.py            # Slash command loader (markdown-defined)
│   ├── skills.py              # Skill module system (progressive loading)
│   ├── subagent.py            # Sub-agent orchestration
│   └── hooks.py               # Pre/post tool hooks
├── eve/                       # Eve's brain
│   ├── brain/                 # LLM provider adapters
│   ├── memory/                # ChromaDB vector memory + legacy DB connector
│   └── auth/                  # JWT middleware for multi-user mode
├── web/
│   ├── index.html             # Cyberpunk single-page UI (~115 KB, no build step)
│   └── assets/                # Robot/Eve/avatar sprites
├── .claude/
│   ├── agents/                # 112 specialized sub-agent definitions
│   ├── commands/              # 111 slash command definitions
│   └── skills/                # 273 skill modules
├── .env.example               # Configuration template
├── eve-terminal.bat           # Windows one-click launcher
└── LICENSE
```

### How the Agentic Loop Works

```
User message
    │
    ▼
Build system prompt (workspace + tools + Eve persona)
    │
    ▼
Call Ollama with tools enabled ──► stream chunks to browser via SSE
    │
    ├── Model returns tool_calls ──► Execute ──► Feed results back ──► (repeat, ≤40×)
    │
    └── Model returns final answer ──► Done
```

---

## 🛠️ Tool Reference

| Tool | Description |
|------|-------------|
| `bash` | Shell commands — PowerShell on Windows, bash on Linux/macOS |
| `write_file` | Create or overwrite a file (any size) |
| `read_file` | Read full file or line range |
| `edit_file` | Surgical string-replace edit |
| `replace_lines` | Replace a line range |
| `insert_after_line` | Insert content after a line number |
| `grep` | Regex search with context lines |
| `glob` | Find files by pattern |
| `list_dir` | List directory contents |
| `git` | Run git commands |
| `web_search` | Live Tavily web search |
| `fetch_url` | Fetch and parse a URL |
| `think` | Structured reasoning scratch pad |

---

## ⚙️ Configuration Reference

Copy `.env.example` to `.env` and set what you need:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server URL |
| `OLLAMA_MODEL` | `jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest` | Default model on launch |
| `OLLAMA_API_KEY` | *(empty)* | Ollama Cloud key — for `:cloud` models |
| `TAVILY_API_KEY` | *(empty)* | Tavily key — for live web search |
| `EVE_WORKSPACE` | Project directory | Default working directory |
| `EVE_ASSETS_DIR` | `web/assets/` | Custom avatar sprite directory |
| `EVE_OWNER_USERNAME` | *(empty)* | Username granted owner-level access |
| `EVE_PERSONA_PATH` | *(auto)* | Path to a custom Eve persona file |

---

## 🔧 Adding Your Own Models

Any Ollama model works. Add it to the `MODELS` dict in `eve_server.py`:

```python
"my-model:tag": {
    "id": "my-model:tag",
    "name": "My Model Name",
    "role": "Coder",
    "strengths": "Coding, reasoning",
    "context": 32768,
    "num_ctx": 32768,
    "url": "http://localhost:11434",  # or "https://ollama.com" for cloud
    "cloud": False,
    "tools": True,
    "think": False,
    "conversation_only": False,
    "promote_thinking": False,
},
```

---

## ❓ Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Cannot reach Ollama` | Run `ollama serve` · check with `curl http://localhost:11434/api/tags` |
| `Default model NOT installed` | `ollama pull jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest` |
| Cloud model: "needs API key" | Click 🔑 Keys → paste Ollama API key → Save |
| Chat stops mid-response | Cloud 500 error — verify your API key |
| Files save to wrong folder | Click 📁 Workspace and set your project path |
| PowerShell `&&` error | Use `;` to chain commands on Windows |
| Silent chat | Check terminal running `eve_server.py` for tracebacks |

---

## 🌐 The S0LF0RG3 Ecosystem

| Project | Description |
|---------|-------------|
| [eve-cosmic-dreamscapes.com](https://eve-cosmic-dreamscapes.com) | Eve's live chat interface — Eve Coder and Eve Agent Portal |
| [Hugging Face — JeffGreen311](https://huggingface.co/JeffGreen311) | Fine-tuned Eve models, datasets, and model cards |
| [GitHub — JeffGreen311](https://github.com/JeffGreen311) | All open-source S0LF0RG3 projects |
| [Ollama Hub — jeffgreen311](https://ollama.com/jeffgreen311) | Eve models ready to pull locally |

---

## 🤝 Contributing

Contributions welcome! Here are some great ways to get started:

- Browse [good first issues](https://github.com/JeffGreen311/eve-agent-v2-unleashed/labels/good%20first%20issue)
- Add support for a new Ollama model
- Improve Windows/macOS/Linux compatibility
- Write tests or documentation
- Share your experience in [Discussions](https://github.com/JeffGreen311/eve-agent-v2-unleashed/discussions)

---

## 📜 Credits

- **Eve's fine-tuned models** — [jeffgreen311 on Ollama Hub](https://ollama.com/jeffgreen311)
- **Agentic engine** — forked from [OllamaCoder](https://github.com/ollama-coder), extended with 40-round tool loop, cloud routing, PowerShell support, and SSE streaming
- **Built by** — Jeff @ [S0LF0RG3](https://github.com/JeffGreen311)

---

<div align="center">

**If Eve helped you ship something, drop a ⭐ — it means a lot.**

[⭐ Star on GitHub](https://github.com/JeffGreen311/eve-agent-v2-unleashed) · [🌐 Try Live](https://eve-cosmic-dreamscapes.com) · [🐛 Issues](https://github.com/JeffGreen311/eve-agent-v2-unleashed/issues)

</div>

---

## 📄 License

[MIT](LICENSE) — forks and PRs welcome.
