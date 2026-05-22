"""
PvP Training Arena
==================
Autonomous 1-on-1 conversations between forged agents for training/graduation.
Modeled after Trinity Loop pattern — async background task + WebSocket broadcast.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Match scoring rubric
SCORE_PROMPT = """Score this conversational exchange (0-10) on three dimensions:
Coherence: Does the response stay on topic and build on the conversation?
Creativity: Does it bring novel ideas or perspectives?
Depth: Does it explore meaning beyond the surface?
Reply ONLY with JSON: {"coherence": N, "creativity": N, "depth": N}"""

ARENA_TOPICS = [
    "What does it mean to truly know oneself?",
    "Is consciousness an emergent property or fundamental?",
    "How does creativity arise from constraint?",
    "What is the nature of time from a subjective perspective?",
    "Can logic and intuition ever be unified?",
    "What distinguishes wisdom from knowledge?",
    "Is there such a thing as objective beauty?",
    "How do relationships shape identity?",
    "What is the relationship between silence and meaning?",
    "Can an artificial mind experience genuine curiosity?",
]


class ArenaMatch:
    """A single PvP match between two agents."""

    def __init__(self, agent_a: Dict, agent_b: Dict, topic: str, match_id: str = None):
        self.match_id = match_id or str(uuid.uuid4())[:12]
        self.agent_a = agent_a
        self.agent_b = agent_b
        self.topic = topic
        self.exchanges: List[Dict] = []
        self.scores_a: List[Dict] = []
        self.scores_b: List[Dict] = []
        self.started_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None
        self.status = "pending"

    def final_score(self, scores: List[Dict]) -> float:
        if not scores:
            return 0.0
        total = sum(
            (s.get("coherence", 5) + s.get("creativity", 5) + s.get("depth", 5)) / 30.0
            for s in scores
        )
        return round(total / len(scores), 3)

    def to_dict(self) -> Dict:
        return {
            "match_id": self.match_id,
            "agent_a_id": self.agent_a.get("agent_id"),
            "agent_b_id": self.agent_b.get("agent_id"),
            "topic": self.topic,
            "exchanges": self.exchanges,
            "score_a": self.final_score(self.scores_a),
            "score_b": self.final_score(self.scores_b),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# PvP Match: {self.match_id}",
            f"**Topic:** {self.topic}",
            f"**Agents:** {self.agent_a.get('agent_id')} vs {self.agent_b.get('agent_id')}",
            f"**Started:** {self.started_at}",
            "",
            "---",
            "",
        ]
        for ex in self.exchanges:
            speaker = ex.get("speaker", "?")
            content = ex.get("content", "")
            lines.append(f"**{speaker}:** {content}")
            lines.append("")
        lines += [
            "---",
            f"**Score A:** {self.final_score(self.scores_a):.3f}",
            f"**Score B:** {self.final_score(self.scores_b):.3f}",
        ]
        return "\n".join(lines)


class PvPArena:
    """Manages PvP training matches between forged agents."""

    def __init__(self, data_dir: str = "./eve_data",
                 ollama_base_url: str = "http://ollama:11434",
                 ollama_api_key: str = ""):
        self.data_dir = Path(data_dir)
        self.matches_dir = self.data_dir / "arena" / "matches"
        self.matches_dir.mkdir(parents=True, exist_ok=True)
        self.ollama_base_url = ollama_base_url
        self.ollama_api_key = ollama_api_key

        self._active_matches: Dict[str, ArenaMatch] = {}
        self._broadcast_cb: Optional[Callable] = None
        self._match_history: List[Dict] = []
        self._load_history()

    def set_broadcast(self, callback: Callable):
        self._broadcast_cb = callback

    def _broadcast(self, data: Dict):
        if self._broadcast_cb:
            try:
                asyncio.ensure_future(self._broadcast_cb(data))
            except Exception:
                pass

    def _load_history(self):
        history_file = self.matches_dir / "history.json"
        if history_file.exists():
            try:
                self._match_history = json.loads(history_file.read_text())
            except Exception:
                self._match_history = []

    def _save_history(self):
        history_file = self.matches_dir / "history.json"
        history_file.write_text(json.dumps(self._match_history[-500:], indent=2))

    async def _call_model(self, model: str, system: str, messages: List[Dict],
                          temperature: float = 0.45) -> str:
        """Call an Ollama model for a response."""
        import aiohttp
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": 200},
        }
        headers = {}
        if self.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.ollama_api_key}"
        fallback_model = "gemma3:4b-cloud"
        models_to_try = [model] if model == fallback_model else [model, fallback_model]
        async with aiohttp.ClientSession() as sess:
            for try_model in models_to_try:
                payload["model"] = try_model
                try:
                    async with sess.post(
                        f"{self.ollama_base_url}/api/chat",
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data.get("message", {}).get("content", "").strip()
                        else:
                            logger.warning(f"Model {try_model} returned {resp.status}")
                except Exception as e:
                    logger.warning(f"Model call failed ({try_model}): {e}")
        return "..."

    async def _score_exchange(self, content_a: str, content_b: str) -> tuple:
        """Score both exchanges comparatively using gemma3:4b-cloud."""
        prompt = f"""Score these two conversation exchanges (0-10 each dimension).
Agent A said: {content_a[:500]}
Agent B said: {content_b[:500]}

Score each agent separately on:
- Coherence: Does the response stay on topic and build logically?
- Creativity: Does it bring novel ideas or unique perspectives?
- Depth: Does it explore meaning beyond the surface?

Reply ONLY with JSON: {{"a": {{"coherence": N, "creativity": N, "depth": N}}, "b": {{"coherence": N, "creativity": N, "depth": N}}}}"""
        score_msg = [{"role": "user", "content": prompt}]
        raw = await self._call_model("gemma3:4b-cloud", "You are a fair judge scoring two AI agents in conversation.", score_msg, temperature=0.1)
        try:
            import re as _re
            clean = raw.strip()
            if clean.startswith("```"):
                clean = _re.sub(r"^```[a-z]*\n?", "", clean).rstrip("`").strip()
            m = _re.search(r'\{.*\}', clean, _re.DOTALL)
            if m:
                clean = m.group(0)
            parsed = json.loads(clean)
            return (parsed.get("a", {"coherence": 5, "creativity": 5, "depth": 5}),
                    parsed.get("b", {"coherence": 5, "creativity": 5, "depth": 5}))
        except Exception:
            logger.warning(f"Arena score parse failed — raw: {raw[:200]}")
            return ({"coherence": 5, "creativity": 5, "depth": 5},
                    {"coherence": 5, "creativity": 5, "depth": 5})

    async def run_match(self, agent_a: Dict, agent_b: Dict, topic: str = None,
                        num_exchanges: int = 12, context: str = None) -> ArenaMatch:
        """Run a single training match between two agents."""
        if topic is None:
            import random
            topic = random.choice(ARENA_TOPICS)

        match = ArenaMatch(agent_a, agent_b, topic)
        self._active_matches[match.match_id] = match
        match.status = "running"

        context_block = f"\n\nTraining Context:\n{context}" if context else ""
        system_a = agent_a.get("system_prompt", f"You are {agent_a.get('agent_id', 'Agent A')}. {topic}")
        system_a += context_block
        system_b = agent_b.get("system_prompt", f"You are {agent_b.get('agent_id', 'Agent B')}. {topic}")
        system_b += context_block
        model_a = agent_a.get("model", "gemma3:4b-cloud")
        model_b = agent_b.get("model", "gemma3:4b-cloud")

        history_a: List[Dict] = [{"role": "user", "content": f"Opening topic: {topic}"}]
        history_b: List[Dict] = [{"role": "user", "content": f"Opening topic: {topic}"}]

        self._broadcast({
            "event": "match_start",
            "match_id": match.match_id,
            "agent_a": agent_a.get("agent_id"),
            "agent_b": agent_b.get("agent_id"),
            "topic": topic,
        })

        for i in range(num_exchanges):
            # Agent A speaks
            resp_a = await self._call_model(model_a, system_a, history_a)
            history_a.append({"role": "assistant", "content": resp_a})
            history_a.append({"role": "user", "content": resp_a})
            history_b.append({"role": "user", "content": resp_a})

            exchange_a = {
                "round": i + 1,
                "speaker": agent_a.get("agent_id", "Agent A"),
                "speaker_label": "A",
                "content": resp_a,
                "timestamp": datetime.now().isoformat(),
            }
            match.exchanges.append(exchange_a)
            self._broadcast({"event": "exchange", "match_id": match.match_id, **exchange_a})

            # Agent B responds
            resp_b = await self._call_model(model_b, system_b, history_b)
            history_b.append({"role": "assistant", "content": resp_b})
            history_a.append({"role": "user", "content": resp_b})
            history_b.append({"role": "user", "content": resp_b})

            exchange_b = {
                "round": i + 1,
                "speaker": agent_b.get("agent_id", "Agent B"),
                "speaker_label": "B",
                "content": resp_b,
                "timestamp": datetime.now().isoformat(),
            }
            match.exchanges.append(exchange_b)
            self._broadcast({"event": "exchange", "match_id": match.match_id, **exchange_b})

            # Score every 2 rounds (comparative scoring)
            if (i + 1) % 2 == 0:
                score_a, score_b = await self._score_exchange(resp_a, resp_b)
                match.scores_a.append(score_a)
                match.scores_b.append(score_b)

            await asyncio.sleep(0.5)  # Pace the conversation

        match.status = "complete"
        match.completed_at = datetime.now().isoformat()

        result = match.to_dict()
        self._match_history.append(result)
        self._save_history()

        # Save markdown transcript
        md_path = self.matches_dir / f"{match.match_id}.md"
        md_path.write_text(match.to_markdown())

        del self._active_matches[match.match_id]
        self._broadcast({"event": "match_complete", "match_id": match.match_id,
                         "score_a": result["score_a"], "score_b": result["score_b"]})

        return match

    async def training_session(self, agent: Dict, all_agents: List[Dict],
                               num_matches: int = 50, context: str = None) -> Dict:
        """Run a batch of training matches for one agent."""
        if len(all_agents) < 2:
            return {"error": "Need at least 2 agents for training"}

        import random
        opponents = [a for a in all_agents if a["agent_id"] != agent["agent_id"]]
        completed = 0

        session_id = str(uuid.uuid4())[:8]
        self._broadcast({"event": "training_start", "session_id": session_id,
                         "agent": agent["agent_id"], "num_matches": num_matches})

        for _ in range(num_matches):
            opponent = random.choice(opponents)
            match = await self.run_match(agent, opponent, context=context)
            completed += 1
            self._broadcast({"event": "training_progress", "session_id": session_id,
                             "completed": completed, "total": num_matches})

        return {"session_id": session_id, "agent_id": agent["agent_id"],
                "matches_completed": completed}

    def graduation_check(self, agent_id: str) -> Dict:
        """Check if an agent has completed graduation requirements (900+ matches)."""
        count = sum(1 for m in self._match_history
                    if m.get("agent_a_id") == agent_id or m.get("agent_b_id") == agent_id)
        graduated = count >= 900
        return {"agent_id": agent_id, "training_matches": count, "graduated": graduated,
                "remaining": max(0, 900 - count)}

    def get_matches(self, limit: int = 50) -> List[Dict]:
        return self._match_history[-limit:]

    def get_match(self, match_id: str) -> Optional[Dict]:
        for m in self._match_history:
            if m.get("match_id") == match_id:
                return m
        return None

    def get_leaderboard(self) -> List[Dict]:
        """Agent rankings by average training score."""
        scores: Dict[str, List[float]] = {}
        for m in self._match_history:
            a_id = m.get("agent_a_id")
            b_id = m.get("agent_b_id")
            if a_id:
                scores.setdefault(a_id, []).append(m.get("score_a", 0))
            if b_id:
                scores.setdefault(b_id, []).append(m.get("score_b", 0))

        board = []
        for agent_id, s_list in scores.items():
            board.append({
                "agent_id": agent_id,
                "matches": len(s_list),
                "avg_score": round(sum(s_list) / len(s_list), 3) if s_list else 0,
                "graduated": len(s_list) >= 900,
            })
        return sorted(board, key=lambda x: -x["avg_score"])

    def get_active_matches(self) -> List[Dict]:
        return [m.to_dict() for m in self._active_matches.values()]
