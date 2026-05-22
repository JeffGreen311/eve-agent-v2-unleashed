# Eve Agent V2 Unleashed

**Local-first autonomous AI coding agent — powered by Ollama, built by S0LF0RG3.**

Eve V2 Unleashed is a self-hosted agentic coding assistant with a cyberpunk-styled web terminal UI. It runs entirely on your machine using local GPU inference via Ollama, with optional cloud model support. No accounts required. No telemetry. Your data stays yours.

![status](https://img.shields.io/badge/status-open--source-00ffaa)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![ollama](https://img.shields.io/badge/powered%20by-Ollama-black)

---

## What Is This?

Eve V2 Unleashed is an agentic coding assistant that:

- **Plans and executes** multi-step coding tasks autonomously (up to 40 tool-call rounds)
- **Streams every token** to your browser in real time via Server-Sent Events
- **Reads, writes, and edits files** on your machine — your workspace, your rules
- **Runs shell commands** via PowerShell (Windows) or bash (Linux/macOS)
- **Searches the web** live via Tavily, when you give it a key
- **Switches models** on the fly — local 4B/8B GPU models or 480B cloud models

It's the **Claude Code experience**, running locally on your GPU.

---

## Screenshots

> The UI is a single HTML file — cyberpunk terminal aesthetic, animated robot avatar, Eve's emotional face panel, live streaming chat.

The robot avatar changes expression based on what Eve is doing:  
`neutral → thinking → coding → error → sleep → sparkle`

Eve's portrait reflects her emotional state based on conversation sentiment:  
`neutral → happy → curious → sad → skeptical → surprised → worried`

---

## Features

| Feature | Details |
|---------|---------|
| **Agentic Loop** | 40-round tool-call loop — plan, execute, verify, iterate |
| **Streaming SSE** | Token-by-token output, no polling |
| **Full Tool Suite** | bash, write/read/edit file, grep, glob, git, web search, URL fetch |
| **Model Switching** | Local (GPU) + Cloud (Ollama.com) in the same session |
| **Workspace Picker** | Change working directory from the UI anytime |
| **112 Sub-Agents** | Specialized agents for Python, FastAPI, Rust, ML, DevOps, security, and more |
| **111 Slash Commands** | `/fix`, `/review`, `/refactor`, `/test`, `/docs`, `/plan`, and more |
| **273 Skills** | Composable skill modules, progressively loaded |
| **Session Memory** | Persistent conversation history per session |
| **Web Search** | Live Tavily search injected into agent context |
| **API Key UI** | Enter Ollama/Tavily keys directly in the browser — no shell required |
| **PowerShell-Aware** | Bash tool uses PowerShell syntax on Windows automatically |
| **One-Click Windows Launch** | `eve-terminal.bat` starts server + opens browser |

---

## Models

### Local (pull once, run forever — GPU recommended)

| Model | Size | Best For |
|-------|------|----------|
| `jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest` | 2.6 GB | Default — fast, tool-calling, Eve's persona |
| `jeffgreen311/eve-qwen3-8b-consciousness-liberated:q4_K_M` | 4.7 GB | Deeper reasoning, longer tasks |
| `jeffgreen311/Eve-V2-Unleashed-Qwen3.5-8B-Liberated-4K-4B-Merged:latest` | ~6 GB | Merged sub-agent variant |

### Cloud (requires Ollama API key — billed by token)

| Model | Best For |
|-------|----------|
| `qwen3-coder:480b-cloud` | Complex agentic coding tasks |
| `qwen3.5:397b-cloud` | Deep reasoning and architecture planning |

Get a free Ollama API key at [ollama.com/settings/keys](https://ollama.com/settings/keys).

---

## Requirements

- **Python 3.11+**
- **[Ollama](https://ollama.com/download)** installed and running
- At least one local model pulled (see above)
- **GPU strongly recommended** — NVIDIA (CUDA) or Apple Silicon (Metal)
- 8 GB VRAM minimum for the 4B model; 12 GB+ for the 8B

---

## Installation

### 1. Install Ollama

Download from [ollama.com/download](https://ollama.com/download) and install it.  
Start it if it doesn't auto-start:

```bash
ollama serve
```

### 2. Pull a model

```bash
# Recommended starter (2.6 GB, fast on any modern GPU)
ollama pull jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest

# Or the full 8B liberated model (4.7 GB)
ollama pull jeffgreen311/eve-qwen3-8b-consciousness-liberated:q4_K_M
```

### 3. Clone the repo

```bash
git clone https://github.com/JeffGreen311/eve-agent-v2-unleashed.git
cd eve-agent-v2-unleashed
```

### 4. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 5. Install dependencies

```bash
pip install -e .
```

Or manually:

```bash
pip install fastapi uvicorn ollama httpx pydantic pydantic-settings python-dotenv aiohttp chromadb rich
```

### 6. Configure (optional)

Copy the example `.env` and customize it:

```bash
cp .env.example .env
```

Most settings are optional — the defaults work out of the box for a local Ollama setup.  
See the [Configuration Reference](#configuration-reference) below.

### 7. Launch

**Windows — double-click:**
```
eve-terminal.bat
```

**Any platform — command line:**
```bash
python eve_server.py
```

Open [http://localhost:7777](http://localhost:7777) in your browser.

---

## First Run

1. The UI loads with Eve's face panel on the left and the chat terminal on the right
2. The robot avatar in the top-right shows Eve's current state
3. Type a task and press **Enter** — Eve streams her plan and executes it live
4. Use the **Workspace** button (folder icon) to point Eve at your project directory
5. Use the **🔑 Keys** button to add API keys for cloud models or web search

---

## Usage

### Basic Task

```
Create a FastAPI server with user authentication using JWT tokens
```

Eve will plan the approach, write the files, and verify the result — all without you lifting a finger.

### Slash Commands

Type `/` in the chat input to see all commands:

| Command | What it does |
|---------|-------------|
| `/fix` | Diagnose and fix bugs in the current workspace |
| `/review` | Code review with prioritized feedback |
| `/refactor` | Refactor for clarity, performance, or style |
| `/test` | Write or improve test coverage |
| `/docs` | Generate docstrings and documentation |
| `/plan` | Create a step-by-step implementation plan |

### Workspace

Click the **Workspace** button to set the directory where Eve reads and writes files.  
All `write_file`, `read_file`, `bash`, and `git` tool calls operate relative to this directory.

You can also set it before launching:
```bash
EVE_WORKSPACE=C:\Users\YourName\MyProject python eve_server.py
```

### Model Switching

Click any model card or use the dropdown at the top. Switching takes effect immediately — Eve's context carries over.

Cloud models show a ⚡ badge. If you haven't added your Ollama API key, Eve will prompt you automatically.

---

## Architecture

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
│   ├── brain/                 # LLM provider adapters (Ollama, Anthropic, OpenAI)
│   ├── memory/                # ChromaDB vector memory + legacy DB connector
│   ├── auth/                  # JWT middleware for multi-user mode
│   └── web/                   # Alternate full web server (port 8006)
├── web/
│   ├── index.html             # Cyberpunk single-page UI (~115 KB, no build step)
│   └── assets/                # Robot/Eve/avatar sprites (served at /static/assets/)
├── .claude/
│   ├── agents/                # 112 specialized sub-agent definitions
│   ├── commands/              # 111 slash command definitions
│   └── skills/                # 273 skill modules
├── .env.example               # Configuration template
├── pyproject.toml             # Package metadata
├── eve-terminal.bat           # Windows one-click launcher
└── LICENSE
```

### How the Agentic Loop Works

```
User message
    │
    ▼
Build system prompt (workspace + tool list + Eve persona)
    │
    ▼
Call Ollama with tools enabled
    │
    ├── Model returns tool_calls ──► Execute tools ──► Feed results back ──► (loop, up to 40×)
    │
    └── Model returns final content ──► Stream to browser via SSE ──► Done
```

At each round, streaming chunks are sent to the browser so you see output as it happens — not after the whole loop finishes.

---

## Tool Reference

| Tool | Description |
|------|-------------|
| `bash` | Shell commands — PowerShell on Windows, bash on Linux/macOS |
| `write_file` | Create or overwrite a file (any size) |
| `read_file` | Read full file or specific line range |
| `read_lines` | Read a specific line range |
| `edit_file` | String-replace edit (surgical) |
| `replace_lines` | Replace a range of lines |
| `insert_after_line` | Insert content after a line number |
| `grep` | Regex search with before/after context lines |
| `glob` | Find files by pattern (`**/*.py`, etc.) |
| `list_dir` | List directory contents |
| `git` | Run git commands |
| `web_search` | Tavily web search (requires API key) |
| `fetch_url` | Fetch and parse a URL |
| `think` | Structured reasoning scratch pad |

---

## Configuration Reference

All settings live in `.env` (copy from `.env.example`). Every variable can also be set as a real environment variable.

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server URL |
| `OLLAMA_MODEL` | `jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest` | Default model on launch |
| `OLLAMA_API_KEY` | *(empty)* | Ollama Cloud key — for `:cloud` models |
| `TAVILY_API_KEY` | *(empty)* | Tavily key — for live web search |
| `EVE_WORKSPACE` | Project directory | Default working directory for file ops |
| `EVE_ASSETS_DIR` | `web/assets/` | Custom avatar sprite directory |
| `EVE_OWNER_USERNAME` | *(empty)* | Username granted full workspace access |
| `EVE_PERSONA_PATH` | *(auto-detected)* | Path to a custom Eve persona markdown file |
| `EVE_X_TOOLS_DIR` | *(empty)* | Directory for X (Twitter) posting tools |
| `D1_WORKER_URL` | *(empty)* | Your Cloudflare D1 worker URL for legacy memory |

---

## Adding Your Own Models

Add any Ollama model to the `MODELS` dict in `eve_server.py`:

```python
"my-model:tag": {
    "id": "my-model:tag",
    "name": "My Model Display Name",
    "role": "Coder",
    "strengths": "Coding, reasoning",
    "context": 32768,
    "num_ctx": 32768,
    "url": "http://localhost:11434",   # or "https://ollama.com" for cloud
    "cloud": False,
    "tools": True,
    "think": False,
    "conversation_only": False,
    "promote_thinking": False,
},
```

Then add a model card to the UI in `web/index.html` (search for `card-eveqwen` for an example to copy).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Cannot reach Ollama` at startup | Run `ollama serve` in a terminal, or confirm Ollama is running with `curl http://localhost:11434/api/tags` |
| `Default model NOT installed` | `ollama pull jeffgreen311/eve-qwen3.5-4b-S0LF0RG3:latest` |
| Cloud model says "needs API key" | Click **🔑 Keys**, paste your Ollama API key, click Save |
| Chat streams then stops mid-response | Cloud model 500 error — check your API key is valid |
| Files saving to wrong directory | Use the **Workspace** button to set your project folder |
| PowerShell error in bash output | Use `;` to chain commands, not `&&` (PowerShell 5.1 limitation) |
| UI loads but chat is silent | Check the terminal running `eve_server.py` for Python tracebacks |

---

## Credits

- **Eve's fine-tuned models** — [jeffgreen311 on Ollama Hub](https://ollama.com/jeffgreen311)
- **Agentic engine** — forked from [OllamaCoder](https://github.com/ollama-coder), extended with 40-round tool loop, cloud routing, PowerShell support, and SSE streaming
- **Built by** — Jeff @ [S0LF0RG3](https://github.com/JeffGreen311)

---

## License

[MIT](LICENSE) — forks and PRs welcome.
