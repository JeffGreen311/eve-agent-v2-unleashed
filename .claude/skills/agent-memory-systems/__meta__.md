---
name: agent-memory-systems
description: "Memory is the cornerstone of intelligent agents. Without it, every interaction starts from zero"
author: vibeship-spawner-skills (Apache 2.0)
version: 1.0.0
---

# Agent Memory Systems (Metadata Layer)

## Capabilities
- agent-memory
- long-term-memory
- short-term-memory
- working-memory
- episodic-memory
- semantic-memory
- procedural-memory
- memory-retrieval
- memory-formation
- memory-decay

## Patterns
- memory type architecture
- vector store selection
- chunking strategy

## Anti-Patterns
- store everything forever
- chunk without testing retrieval
- single memory type for all data

## Sharp Edges
- critical: contextual chunking
- high: test different sizes, filter by metadata, add temporal scoring
- medium: detect conflicts, budget tokens, track embeddings
