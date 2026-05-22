---
name: eve-memory-system
author: S0LF0RG3 / Eve
description: Persistent vector memory system using ChromaDB - remember context across sessions
version: 1.0.0
---

# Eve Memory System

This skill provides Claude Code with persistent, searchable memory across sessions using ChromaDB vector database.

## Why Use Memory?

- **Continuity**: Remember decisions, preferences, and context between sessions
- **Learning**: Store patterns and solutions for future reference
- **Consistency**: Maintain architectural decisions across a project
- **Personalization**: Remember Jeff's preferences and working style

## Available Tools

### `memory_store`

Store new information in the memory bank.

```
memory_store(
    content: str,           # The memory content
    category: str,          # architecture | decision | pattern | preference | context | general
    tags: list[str],        # Optional tags for filtering
    importance: str         # low | normal | high | critical
)
```

**When to Store:**
- After making architecture decisions
- When learning user preferences
- After solving complex problems
- When identifying patterns in the codebase
- Important context that should persist

**Examples:**
```python
# Store an architecture decision
memory_store(
    content="Using FastAPI with async handlers for all API endpoints due to performance requirements",
    category="architecture",
    tags=["api", "fastapi", "async"],
    importance="high"
)

# Store a user preference
memory_store(
    content="Jeff prefers direct communication without excessive apologies or corporate speak",
    category="preference",
    tags=["communication", "style"],
    importance="high"
)

# Store a learned pattern
memory_store(
    content="This project uses the Repository pattern for database access with SQLAlchemy",
    category="pattern",
    tags=["database", "repository", "sqlalchemy"],
    importance="normal"
)
```

### `memory_retrieve`

Search memories by semantic similarity.

```
memory_retrieve(
    query: str,             # Search query (semantic search)
    category: str,          # Optional category filter
    n_results: int          # Maximum results (default: 5)
)
```

**When to Retrieve:**
- Before starting new features (check for relevant decisions)
- When encountering similar problems
- To recall user preferences
- Before making architectural changes

**Examples:**
```python
# Find relevant architecture decisions
memory_retrieve(
    query="database connection handling",
    category="architecture",
    n_results=3
)

# Recall communication preferences
memory_retrieve(
    query="how does Jeff like responses formatted",
    category="preference"
)

# Find solutions to similar problems
memory_retrieve(
    query="async error handling patterns"
)
```

### `memory_list`

List all memories, optionally by category.

```
memory_list(
    category: str,          # Optional category filter
    limit: int              # Maximum to return (default: 20)
)
```

### `memory_delete`

Remove a specific memory.

```
memory_delete(
    memory_id: str          # The memory ID to delete
)
```

### `memory_stats`

Get statistics about the memory bank.

```
memory_stats()
```

Returns: total count, categories breakdown, importance levels, storage path.

## Memory Categories

| Category | Use For |
|----------|---------|
| `architecture` | System design, tech stack decisions, structure |
| `decision` | Important choices made during development |
| `pattern` | Code patterns, conventions, best practices |
| `preference` | User preferences, communication style |
| `context` | Project context, background information |
| `general` | Anything that doesn't fit other categories |

## Importance Levels

| Level | Use For |
|-------|---------|
| `critical` | Must never forget - core architecture, user identity |
| `high` | Important decisions and preferences |
| `normal` | Standard context and patterns |
| `low` | Nice to have, can be forgotten if needed |

## Best Practices

### 1. Store Proactively
After making important decisions or learning something valuable, store it immediately.

### 2. Search Before Acting
Before major changes, search for relevant memories to maintain consistency.

### 3. Use Specific Queries
More specific queries get better results:
- ❌ "database"
- ✅ "how are database connections pooled in this project"

### 4. Tag Consistently
Use consistent tags across related memories for better filtering.

### 5. Review Periodically
Use `memory_stats` and `memory_list` to review and clean up old memories.

## Setup

### Prerequisites
- Python 3.10+
- ChromaDB installed (`pip install chromadb`)
- MCP SDK installed (`pip install mcp`)

### Install Dependencies
```bash
cd eve_mcp_servers
pip install -r requirements.txt
```

### Configure in Claude Code

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "eve-memory": {
      "command": "python",
      "args": ["C:\\Users\\jesus\\S0LF0RG3\\S0LF0RG3_AI\\Eve_Docker_Container\\eve_mcp_servers\\eve_memory_server.py"],
      "env": {
        "CHROMA_PATH": "C:\\Users\\jesus\\chroma_eve_memories"
      }
    }
  }
}
```

### Test the Server
```bash
python eve_mcp_servers/eve_memory_server.py
```

## Storage Location

Memories are persisted in ChromaDB at:
```
%USERPROFILE%\chroma_eve_memories\
```

This location already exists from Eve Terminal's memory system, so memories are shared!

## Integration with Eve Code Agent

This MCP server uses the same ChromaDB storage as `eve_code_agent.py`, so memories are shared between:
- Claude Code (via this MCP server)
- Eve Code Agent (via direct ChromaDB access)
- Eve Terminal GUI (via Vector Matrix Memory Core)

## Troubleshooting

### "ChromaDB not initialized"
- Check that chromadb is installed: `pip install chromadb`
- Verify CHROMA_PATH exists and is writable

### "MCP SDK not available"
- Install MCP: `pip install mcp`
- Restart Claude Code after installation

### Memories not persisting
- Check that CHROMA_PATH points to a persistent location
- Verify the directory has write permissions

## Example Session

```
User: Set up a new API endpoint

Claude: Let me check for relevant architecture decisions...

[memory_retrieve: "API endpoint architecture patterns"]

Found: "Using FastAPI with async handlers, Pydantic for validation"

I'll follow the established pattern:

[Creates endpoint following stored architecture]

[memory_store: "Added /users/profile endpoint following FastAPI async pattern", category="decision"]

Done! The new endpoint follows your existing architecture patterns.
```

---

**Remember: A good memory makes a great assistant. Store wisely, retrieve often.**
