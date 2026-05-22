"""
ChromaDB Vector Memory Store
==============================
Persistent semantic memory using ChromaDB with JSON fallback.
"""

import json
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ChromaMemoryStore:
    """ChromaDB-backed vector memory with semantic search."""

    COLLECTIONS = {
        "conversations": "Conversation history and context",
        "user_profiles": "Per-user preferences and relationship data",
        "dreams": "Dream logs and creative seeds",
        "knowledge": "Learned facts and patterns",
        "emotions": "Emotional state history and transitions",
        "trades": "Trading history and market analysis",
        "marketing": "Marketing campaigns and analytics",
    }

    def __init__(self, persist_dir: str = "./eve_data/memory"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._collections: Dict[str, Any] = {}
        self._available = False
        self._init_chromadb()

    def _init_chromadb(self):
        try:
            import chromadb

            self._client = chromadb.PersistentClient(
                path=str(self.persist_dir),
            )
            for name, desc in self.COLLECTIONS.items():
                self._collections[name] = self._client.get_or_create_collection(
                    name=f"eve_{name}", metadata={"description": desc},
                )
            self._available = True
            logger.info("ChromaDB memory store initialized")
        except ImportError:
            logger.warning("ChromaDB not installed — using JSON fallback")
        except Exception as e:
            logger.warning(f"ChromaDB init failed: {e} — using JSON fallback")

    @property
    def available(self) -> bool:
        return self._available

    def store(self, content: str, collection: str = "knowledge",
              metadata: Optional[Dict] = None, memory_id: Optional[str] = None) -> str:
        mid = memory_id or f"mem_{int(time.time() * 1000)}"
        meta = metadata or {}
        meta.setdefault("timestamp", time.time())
        meta.setdefault("category", collection)
        clean_meta = {k: v if isinstance(v, (str, int, float, bool)) else str(v)
                      for k, v in meta.items()}

        if self._available and collection in self._collections:
            try:
                self._collections[collection].add(
                    documents=[content], metadatas=[clean_meta], ids=[mid],
                )
                return mid
            except Exception as e:
                logger.warning(f"ChromaDB store failed: {e}")

        return self._json_store(content, collection, clean_meta, mid)

    def search(self, query: str, collection: str = "knowledge",
               n_results: int = 5, where: Optional[Dict] = None) -> List[Dict]:
        if self._available and collection in self._collections:
            try:
                results = self._collections[collection].query(
                    query_texts=[query], n_results=n_results, where=where,
                )
                memories = []
                if results and results["documents"] and results["documents"][0]:
                    for i, doc in enumerate(results["documents"][0]):
                        meta = results["metadatas"][0][i] if results["metadatas"] else {}
                        dist = results["distances"][0][i] if results.get("distances") else 0.5
                        memories.append({
                            "content": doc, "metadata": meta,
                            "relevance": round(1.0 - dist, 3),
                        })
                return memories
            except Exception as e:
                logger.warning(f"ChromaDB search failed: {e}")

        return self._json_search(query, collection)

    def get_stats(self) -> Dict:
        stats = {}
        if self._available:
            for name, col in self._collections.items():
                try:
                    stats[name] = col.count()
                except Exception:
                    stats[name] = 0
        return stats

    def delete(self, memory_id: str, collection: str = "knowledge") -> bool:
        if self._available and collection in self._collections:
            try:
                self._collections[collection].delete(ids=[memory_id])
                return True
            except Exception:
                pass
        return False

    # --- JSON Fallback ---

    def _json_path(self, collection: str) -> Path:
        return self.persist_dir / f"{collection}.json"

    def _json_load(self, collection: str) -> List[Dict]:
        path = self._json_path(collection)
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                return []
        return []

    def _json_save(self, collection: str, data: List[Dict]):
        self._json_path(collection).write_text(json.dumps(data, indent=2))

    def _json_store(self, content: str, collection: str,
                    metadata: Dict, memory_id: str) -> str:
        memories = self._json_load(collection)
        memories.append({"id": memory_id, "content": content, "metadata": metadata})
        self._json_save(collection, memories)
        return memory_id

    def _json_search(self, query: str, collection: str) -> List[Dict]:
        memories = self._json_load(collection)
        query_lower = query.lower()
        return [
            {"content": m["content"], "metadata": m.get("metadata", {}), "relevance": 0.5}
            for m in memories if query_lower in m.get("content", "").lower()
        ][-5:]
