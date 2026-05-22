# Agent Memory Systems - Instructions Layer

## Overview

Memory is the cornerstone of intelligent agents. Without it, every interaction starts from zero. This skill covers the architecture of agent memory: short-term (context window), long-term (vector stores), and the cognitive architectures that organize them.  Key insight: Memory isn't just storage - it's retrieval. A million stored facts mean nothing if you can't find the right one. Chunking, embedding, and retrieval strategies determine whether your agent remembers or forgets.  The field is fragm

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

### Memory Type Architecture

Choosing the right memory type for different information

### Vector Store Selection Pattern

Choosing the right vector database for your use case

### Chunking Strategy Pattern

Breaking documents into retrievable chunks

## Anti-Patterns

### ❌ Store Everything Forever

### ❌ Chunk Without Testing Retrieval

### ❌ Single Memory Type for All Data

## ⚠️ Sharp Edges

| Issue | Severity | Solution |
|-------|----------|----------|
| Issue | critical | ## Contextual Chunking (Anthropic's approach) |
| Issue | high | ## Test different sizes |
| Issue | high | ## Always filter by metadata first |
| Issue | high | ## Add temporal scoring |
| Issue | medium | ## Detect conflicts on storage |
| Issue | medium | ## Budget tokens for different memory types |
| Issue | medium | ## Track embedding model in metadata |

## Related Skills

Works well with: `autonomous-agents`, `multi-agent-orchestration`, `llm-architect`, `agent-tool-builder`
