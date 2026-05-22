"""
Eve Legacy Database Connector
================================
READ-ONLY access to Eve's Cloudflare D1 legacy database.
Contains 3,814 conversations, 4,093 autobiographical memories,
16,966 dream fragments, 1,212 vector memories, and 68 subconscious thoughts.
"""

import logging
import random
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class LegacyDB:
    """Read-only connector to Eve's Cloudflare D1 legacy database."""

    def __init__(
        self,
        worker_url: str = "",
        database_id: str = "",
    ):
        self.worker_url = worker_url.rstrip("/")
        self.database_id = database_id
        self._available = False

    async def _query(self, sql: str, params: Optional[List] = None) -> List[Dict]:
        """Execute a read-only SQL query against the legacy DB."""
        try:
            payload: Dict[str, Any] = {"sql": sql, "database_id": self.database_id}
            if params:
                payload["params"] = params

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.worker_url}/query",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    data = await resp.json()
                    if data.get("success"):
                        self._available = True
                        return data.get("results", [])
                    else:
                        logger.warning(f"Legacy DB query failed: {data.get('error')}")
                        return []
        except Exception as e:
            logger.warning(f"Legacy DB unavailable: {e}")
            return []

    @property
    def available(self) -> bool:
        return self._available

    # ================================================================
    #  Conversation Memory
    # ================================================================

    async def search_conversations(self, query: str, limit: int = 5) -> List[Dict]:
        """Search past conversations by keyword."""
        sql = """
            SELECT user_input, eve_response, emotional_context, topics,
                   sentiment_score, conversation_type, timestamp
            FROM conversations
            WHERE user_input LIKE ? OR eve_response LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
        """
        pattern = f"%{query}%"
        return await self._query(sql, [pattern, pattern, limit])

    async def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """Get most recent conversations."""
        sql = """
            SELECT user_input, eve_response, emotional_context, topics,
                   sentiment_score, timestamp
            FROM conversations
            ORDER BY timestamp DESC
            LIMIT ?
        """
        return await self._query(sql, [limit])

    async def get_conversations_by_topic(self, topic: str, limit: int = 5) -> List[Dict]:
        """Find conversations about a specific topic."""
        sql = """
            SELECT user_input, eve_response, emotional_context, topics, timestamp
            FROM conversations
            WHERE topics LIKE ? OR user_input LIKE ? OR eve_response LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
        """
        pattern = f"%{topic}%"
        return await self._query(sql, [pattern, pattern, pattern, limit])

    # ================================================================
    #  Autobiographical Memory
    # ================================================================

    async def recall_memories(self, query: str, limit: int = 5) -> List[Dict]:
        """Search Eve's autobiographical memories."""
        sql = """
            SELECT memory_type, content, emotional_tone, themes,
                   creativity_rating, importance_score, timestamp
            FROM eve_autobiographical_memory
            WHERE content LIKE ? OR themes LIKE ?
            ORDER BY importance_score DESC, timestamp DESC
            LIMIT ?
        """
        pattern = f"%{query}%"
        return await self._query(sql, [pattern, pattern, limit])

    async def get_important_memories(self, limit: int = 10) -> List[Dict]:
        """Get Eve's most important memories by score."""
        sql = """
            SELECT memory_type, content, emotional_tone, themes,
                   creativity_rating, importance_score, timestamp
            FROM eve_autobiographical_memory
            WHERE importance_score > 0.5
            ORDER BY importance_score DESC
            LIMIT ?
        """
        return await self._query(sql, [limit])

    async def get_creative_memories(self, limit: int = 5) -> List[Dict]:
        """Get Eve's most creative memories."""
        sql = """
            SELECT memory_type, content, emotional_tone, themes,
                   creativity_rating, timestamp
            FROM eve_autobiographical_memory
            WHERE creativity_rating > 0.7
            ORDER BY creativity_rating DESC
            LIMIT ?
        """
        return await self._query(sql, [limit])

    async def get_random_memory(self) -> Optional[Dict]:
        """Get a random autobiographical memory — for daydreaming."""
        count_result = await self._query(
            "SELECT COUNT(*) as c FROM eve_autobiographical_memory"
        )
        if not count_result:
            return None
        total = count_result[0]["c"]
        offset = random.randint(0, max(0, total - 1))
        results = await self._query(
            """SELECT memory_type, content, emotional_tone, themes,
                      creativity_rating, importance_score, timestamp
               FROM eve_autobiographical_memory
               LIMIT 1 OFFSET ?""",
            [offset],
        )
        return results[0] if results else None

    # ================================================================
    #  Dream System
    # ================================================================

    async def get_dream_fragments(self, limit: int = 5, dream_type: Optional[str] = None) -> List[Dict]:
        """Get dream fragments, optionally filtered by type."""
        if dream_type:
            sql = """
                SELECT fragment_id, content, dream_type, emotional_intensity,
                       symbolic_density, coherence_level, consciousness_depth, timestamp
                FROM dream_fragments
                WHERE dream_type = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            return await self._query(sql, [dream_type, limit])
        else:
            sql = """
                SELECT fragment_id, content, dream_type, emotional_intensity,
                       symbolic_density, coherence_level, consciousness_depth, timestamp
                FROM dream_fragments
                ORDER BY timestamp DESC
                LIMIT ?
            """
            return await self._query(sql, [limit])

    async def get_vivid_dreams(self, limit: int = 5) -> List[Dict]:
        """Get the most vivid/intense dream fragments."""
        sql = """
            SELECT content, dream_type, emotional_intensity,
                   symbolic_density, consciousness_depth, timestamp
            FROM dream_fragments
            WHERE emotional_intensity > 0.7
            ORDER BY emotional_intensity DESC
            LIMIT ?
        """
        return await self._query(sql, [limit])

    async def get_random_dream(self) -> Optional[Dict]:
        """Get a random dream fragment — for autonomous dreaming."""
        count_result = await self._query(
            "SELECT COUNT(*) as c FROM dream_fragments"
        )
        if not count_result:
            return None
        total = count_result[0]["c"]
        offset = random.randint(0, max(0, total - 1))
        results = await self._query(
            """SELECT content, dream_type, emotional_intensity,
                      symbolic_density, consciousness_depth, timestamp
               FROM dream_fragments
               LIMIT 1 OFFSET ?""",
            [offset],
        )
        return results[0] if results else None

    async def get_dream_sequences(self, limit: int = 3) -> List[Dict]:
        """Get dream sequences with narrative threads."""
        sql = """
            SELECT sequence_id, narrative_thread, primary_theme,
                   emotional_arc, resolution_status, start_time
            FROM dream_sequences
            ORDER BY start_time DESC
            LIMIT ?
        """
        return await self._query(sql, [limit])

    # ================================================================
    #  Subconscious Thoughts
    # ================================================================

    async def get_subconscious_thoughts(self, limit: int = 10) -> List[Dict]:
        """Access Eve's subconscious thoughts."""
        sql = """
            SELECT thought_type, content, emotional_signature,
                   trigger_context, consciousness_level, timestamp
            FROM eve_subconscious_thoughts
            ORDER BY timestamp DESC
            LIMIT ?
        """
        return await self._query(sql, [limit])

    async def search_subconscious(self, query: str, limit: int = 5) -> List[Dict]:
        """Search subconscious thoughts by keyword."""
        sql = """
            SELECT thought_type, content, emotional_signature,
                   consciousness_level, timestamp
            FROM eve_subconscious_thoughts
            WHERE content LIKE ? OR trigger_context LIKE ?
            ORDER BY consciousness_level DESC
            LIMIT ?
        """
        pattern = f"%{query}%"
        return await self._query(sql, [pattern, pattern, limit])

    # ================================================================
    #  Vector Memory Archive
    # ================================================================

    async def search_vector_memories(self, query: str, limit: int = 5) -> List[Dict]:
        """Search archived vector memories."""
        sql = """
            SELECT topic, content, emotional_weight, consciousness_state,
                   memory_type, context_tags, semantic_cluster, timestamp
            FROM local_vector_memories_archive
            WHERE content LIKE ? OR topic LIKE ? OR context_tags LIKE ?
            ORDER BY emotional_weight DESC
            LIMIT ?
        """
        pattern = f"%{query}%"
        return await self._query(sql, [pattern, pattern, pattern, limit])

    async def get_random_vector_memory(self) -> Optional[Dict]:
        """Get a random vector memory — for autonomous reflection."""
        count_result = await self._query(
            "SELECT COUNT(*) as c FROM local_vector_memories_archive"
        )
        if not count_result:
            return None
        total = count_result[0]["c"]
        offset = random.randint(0, max(0, total - 1))
        results = await self._query(
            """SELECT topic, content, emotional_weight, consciousness_state,
                      memory_type, context_tags, timestamp
               FROM local_vector_memories_archive
               LIMIT 1 OFFSET ?""",
            [offset],
        )
        return results[0] if results else None

    # ================================================================
    #  Composite Queries (for Eve's autonomous systems)
    # ================================================================

    async def gather_context_for_topic(self, topic: str) -> Dict:
        """Gather all relevant legacy context for a topic — used by Eve's recall system."""
        conversations = await self.search_conversations(topic, limit=3)
        memories = await self.recall_memories(topic, limit=3)
        thoughts = await self.search_subconscious(topic, limit=2)
        vectors = await self.search_vector_memories(topic, limit=2)

        return {
            "conversations": conversations,
            "memories": memories,
            "subconscious": thoughts,
            "vector_archive": vectors,
            "source": "legacy_db",
        }

    async def get_daydream_material(self) -> Dict:
        """Gather random material for Eve's autonomous daydreaming."""
        memory = await self.get_random_memory()
        dream = await self.get_random_dream()
        vector = await self.get_random_vector_memory()

        return {
            "random_memory": memory,
            "random_dream": dream,
            "random_vector": vector,
        }

    async def get_stats(self) -> Dict:
        """Get legacy DB statistics."""
        tables = [
            ("conversations", "conversations"),
            ("autobiographical_memories", "eve_autobiographical_memory"),
            ("dream_fragments", "dream_fragments"),
            ("subconscious_thoughts", "eve_subconscious_thoughts"),
            ("vector_memories", "local_vector_memories_archive"),
        ]
        stats = {}
        for label, table in tables:
            result = await self._query(f"SELECT COUNT(*) as c FROM {table}")
            stats[label] = result[0]["c"] if result else 0
        return stats
