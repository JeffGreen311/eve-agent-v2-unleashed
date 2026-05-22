# Eve Memory Command

Interact with Eve's persistent memory system.

## Usage

```
/eve-memory <action> [args]
```

## Actions

### Store a Memory
```
/eve-memory store "content" [category] [importance]
```

**Categories:** architecture, decision, pattern, preference, context, general
**Importance:** low, normal, high, critical

**Examples:**
```
/eve-memory store "Using TypeScript strict mode for all new files" architecture high
/eve-memory store "Jeff prefers tabs over spaces" preference normal
```

### Retrieve Memories
```
/eve-memory recall "query" [category] [count]
```

**Examples:**
```
/eve-memory recall "database patterns"
/eve-memory recall "communication style" preference 3
```

### List Memories
```
/eve-memory list [category]
```

**Examples:**
```
/eve-memory list
/eve-memory list architecture
```

### Memory Stats
```
/eve-memory stats
```

### Delete Memory
```
/eve-memory delete <memory_id>
```

## Quick Reference

| Action | Command |
|--------|---------|
| Store | `/eve-memory store "content" category importance` |
| Recall | `/eve-memory recall "query"` |
| List | `/eve-memory list` |
| Stats | `/eve-memory stats` |
| Delete | `/eve-memory delete mem_xxx` |

## Automatic Memory Usage

When this command is invoked, Claude should:

1. **On Store:** Call `memory_store` MCP tool with provided content, category, and importance
2. **On Recall:** Call `memory_retrieve` MCP tool with the query and display results
3. **On List:** Call `memory_list` MCP tool and format output nicely
4. **On Stats:** Call `memory_stats` MCP tool and show summary

## Best Practices

### What to Store
- ✅ Architecture decisions
- ✅ User preferences
- ✅ Project-specific patterns
- ✅ Solutions to tricky problems
- ✅ Important context

### What NOT to Store
- ❌ Temporary debugging info
- ❌ Secrets or credentials
- ❌ Large code blocks (summarize instead)
- ❌ Obvious/universal knowledge

## Integration

This command uses the `eve-memory` MCP server which stores memories in ChromaDB at:
```
%USERPROFILE%\chroma_eve_memories
```

Memories are shared across:
- Claude Code (this command)
- Eve Code Agent
- Eve Terminal GUI
