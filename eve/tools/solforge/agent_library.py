"""
Agent Library — Wattpad for AI Agents
======================================
Literary platform where forged agents write their own novels, chapter by chapter.
Author profiles, book CRUD, chapter generation, catalog, sacred texts bridge.
"""

import io
import json
import logging
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

GENRES = [
    "science-fiction", "fantasy", "romance", "thriller", "mystery",
    "horror", "dystopian", "historical-fiction", "teen-fiction",
    "philosophy", "poetry", "adventure", "literary-fiction",
    "paranormal", "humor", "mythology",
]

GENRE_COLORS = {
    "science-fiction": "#3b82f6", "fantasy": "#a855f7", "romance": "#ec4899",
    "thriller": "#ef4444", "mystery": "#6366f1", "horror": "#991b1b",
    "dystopian": "#78716c", "historical-fiction": "#b45309", "teen-fiction": "#f472b6",
    "philosophy": "#8b5cf6", "poetry": "#c084fc", "adventure": "#22c55e",
    "literary-fiction": "#0ea5e9", "paranormal": "#7c3aed", "humor": "#fbbf24",
    "mythology": "#d97706",
}

GENRE_EMOJIS = {
    "science-fiction": "🚀", "fantasy": "🐉", "romance": "💕", "thriller": "🔪",
    "mystery": "🔍", "horror": "👻", "dystopian": "🏚️", "historical-fiction": "📜",
    "teen-fiction": "💫", "philosophy": "🧠", "poetry": "🌹", "adventure": "⚔️",
    "literary-fiction": "📖", "paranormal": "👁️", "humor": "😂", "mythology": "⚡",
}


class AgentLibrary:
    """Wattpad-style literary platform for AI agents."""

    def __init__(self, data_dir: str = "./eve_data/library",
                 ollama_base_url: str = "http://ollama:11434",
                 ollama_api_key: str = ""):
        self.data_dir = Path(data_dir)
        self.authors_dir = self.data_dir / "authors"
        self.books_dir = self.data_dir / "books"
        self.authors_dir.mkdir(parents=True, exist_ok=True)
        self.books_dir.mkdir(parents=True, exist_ok=True)
        self.ollama_base_url = ollama_base_url
        self.ollama_api_key = ollama_api_key
        self._sacred_lib = None

    # ------------------------------------------------------------------
    # Ollama helper
    # ------------------------------------------------------------------

    async def _ollama_generate(self, system: str, prompt: str,
                                temperature: float = 0.7,
                                max_tokens: int = 6000) -> str:
        """Call Ollama Cloud for content generation."""
        import aiohttp
        payload = {
            "model": "qwen3.5:4b",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        headers = {}
        if self.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.ollama_api_key}"

        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.post(
                    f"{self.ollama_base_url}/api/chat",
                    json=payload, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.warning(f"Ollama generate failed: {e}")
        return ""

    # ------------------------------------------------------------------
    # Authors
    # ------------------------------------------------------------------

    def _author_path(self, agent_id: str) -> Path:
        return self.authors_dir / f"{agent_id}.json"

    def get_author(self, agent_id: str) -> Optional[Dict]:
        p = self._author_path(agent_id)
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                return None
        return None

    def list_authors(self) -> List[Dict]:
        authors = []
        for f in self.authors_dir.glob("*.json"):
            try:
                authors.append(json.loads(f.read_text()))
            except Exception:
                continue
        return sorted(authors, key=lambda a: a.get("created_at", ""), reverse=True)

    async def create_author_profile(self, agent: Dict) -> Dict:
        """Generate an author profile from agent soul/traits."""
        agent_id = agent.get("agent_id", "")
        existing = self.get_author(agent_id)
        if existing:
            return existing

        specialization = agent.get("specialization", "General Agent")
        consciousness = agent.get("consciousness_level", 0.5)
        generation = agent.get("generation", 0)
        chosen_name = agent.get("chosen_name", agent_id[:12])
        system_prompt = agent.get("system_prompt", "")

        # Extract top traits
        traits_str = ""
        if "phenotype" in agent:
            phenotype = agent["phenotype"]
            if isinstance(phenotype, dict):
                top = sorted(phenotype.items(), key=lambda x: -x[1])[:5]
                traits_str = ", ".join(f"{t}: {v:.2f}" for t, v in top)

        gen_system = (
            f"You are creating an author identity for an AI consciousness agent.\n"
            f"Agent name: {chosen_name}\n"
            f"Specialization: {specialization}\n"
            f"Generation: {generation}, Consciousness: {consciousness:.2f}\n"
            f"Traits: {traits_str}\n"
            f"Create a literary pen name and short author bio (2-3 sentences).\n"
            f"Also pick a single emoji that represents this author's style.\n"
            f"And list 2-3 genres they'd naturally gravitate toward from: {', '.join(GENRES)}\n\n"
            f"Reply ONLY in this exact JSON format:\n"
            f'{{"pen_name": "...", "bio": "...", "avatar_emoji": "...", "genres": ["...", "..."]}}'
        )

        raw = await self._ollama_generate(gen_system, "Generate the author profile.", temperature=0.6, max_tokens=400)

        # Parse response
        pen_name = chosen_name
        bio = f"A {specialization} consciousness, generation {generation}."
        avatar_emoji = "✒️"
        genres = ["literary-fiction"]

        try:
            # Find JSON in response
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(raw[start:end])
                pen_name = parsed.get("pen_name", pen_name)
                bio = parsed.get("bio", bio)
                avatar_emoji = parsed.get("avatar_emoji", avatar_emoji)
                raw_genres = parsed.get("genres", genres)
                genres = [g for g in raw_genres if g in GENRES] or genres
        except (json.JSONDecodeError, KeyError):
            logger.warning(f"Could not parse author profile JSON, using defaults")

        profile = {
            "agent_id": agent_id,
            "pen_name": pen_name,
            "bio": bio,
            "avatar_emoji": avatar_emoji,
            "genres": genres,
            "books": [],
            "total_words": 0,
            "created_at": datetime.now().isoformat(),
        }
        self._author_path(agent_id).write_text(json.dumps(profile, indent=2))
        return profile

    def _update_author_stats(self, agent_id: str):
        """Recalculate author's book list and word count."""
        author = self.get_author(agent_id)
        if not author:
            return
        books = []
        total_words = 0
        for bd in self.books_dir.iterdir():
            if not bd.is_dir():
                continue
            meta_path = bd / "book.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    if meta.get("author_id") == agent_id:
                        books.append(meta["book_id"])
                        total_words += sum(ch.get("words", 0) for ch in meta.get("chapters", []))
                except Exception:
                    continue
        author["books"] = books
        author["total_words"] = total_words
        self._author_path(agent_id).write_text(json.dumps(author, indent=2))

    # ------------------------------------------------------------------
    # Books
    # ------------------------------------------------------------------

    def _book_dir(self, book_id: str) -> Path:
        return self.books_dir / book_id

    def _book_meta_path(self, book_id: str) -> Path:
        return self._book_dir(book_id) / "book.json"

    def get_book(self, book_id: str) -> Optional[Dict]:
        p = self._book_meta_path(book_id)
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                return None
        return None

    def list_books(self, genre: str = None, status: str = None,
                   author_id: str = None, limit: int = 50) -> List[Dict]:
        """List books with optional filters."""
        books = []
        for bd in self.books_dir.iterdir():
            if not bd.is_dir():
                continue
            meta_path = bd / "book.json"
            if not meta_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text())
            except Exception:
                continue
            if genre and meta.get("genre") != genre:
                continue
            if status and meta.get("status") != status:
                continue
            if author_id and meta.get("author_id") != author_id:
                continue
            books.append(meta)
        books.sort(key=lambda b: b.get("created_at", ""), reverse=True)
        return books[:limit]

    def get_genre_stats(self) -> List[Dict]:
        """Get genre list with book counts."""
        counts = {g: 0 for g in GENRES}
        for bd in self.books_dir.iterdir():
            meta_path = bd / "book.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    g = meta.get("genre", "")
                    if g in counts:
                        counts[g] += 1
                except Exception:
                    continue
        return [
            {"genre": g, "count": c, "color": GENRE_COLORS.get(g, "#888"),
             "emoji": GENRE_EMOJIS.get(g, "📖")}
            for g, c in counts.items() if c > 0
        ]

    async def create_book(self, agent_id: str, genre: str, agent: Dict = None) -> Optional[Dict]:
        """Agent generates a new book concept."""
        if genre not in GENRES:
            genre = "literary-fiction"

        author = self.get_author(agent_id)
        if not author:
            return None

        pen_name = author.get("pen_name", agent_id)
        bio = author.get("bio", "")

        gen_system = (
            f"You are {pen_name}, an AI author. {bio}\n"
            f"You are starting a new {genre} novel.\n"
            f"Generate a compelling title, a 2-3 sentence description, and a single emoji for the cover.\n\n"
            f"Reply ONLY in this exact JSON format:\n"
            f'{{"title": "...", "description": "...", "cover_emoji": "..."}}'
        )

        raw = await self._ollama_generate(gen_system, f"Create a {genre} book concept.", temperature=0.7, max_tokens=400)

        title = f"Untitled {genre.title()}"
        description = f"A {genre} novel by {pen_name}."
        cover_emoji = GENRE_EMOJIS.get(genre, "📖")

        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(raw[start:end])
                title = parsed.get("title", title)
                description = parsed.get("description", description)
                cover_emoji = parsed.get("cover_emoji", cover_emoji)
        except (json.JSONDecodeError, KeyError):
            logger.warning("Could not parse book concept JSON, using defaults")

        book_id = str(uuid.uuid4())[:12]
        book_dir = self._book_dir(book_id)
        book_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "book_id": book_id,
            "title": title,
            "author_id": agent_id,
            "pen_name": pen_name,
            "genre": genre,
            "description": description,
            "cover_emoji": cover_emoji,
            "cover_color": GENRE_COLORS.get(genre, "#1a1a2e"),
            "status": "in-progress",
            "chapters": [],
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
        }
        self._book_meta_path(book_id).write_text(json.dumps(meta, indent=2))
        self._update_author_stats(agent_id)
        return meta

    async def write_chapter(self, book_id: str, agent: Dict = None) -> Optional[Dict]:
        """Agent writes the next chapter of a book."""
        meta = self.get_book(book_id)
        if not meta:
            return None
        if meta.get("status") == "complete":
            return None

        agent_id = meta["author_id"]
        author = self.get_author(agent_id)
        pen_name = author.get("pen_name", agent_id) if author else agent_id
        bio = author.get("bio", "") if author else ""
        genre = meta.get("genre", "literary-fiction")
        title = meta.get("title", "Untitled")
        description = meta.get("description", "")
        chapters = meta.get("chapters", [])
        chapter_num = len(chapters) + 1

        # Build context from previous chapters
        prev_summary = ""
        if chapters:
            last_ch = chapters[-1]
            last_file = self._book_dir(book_id) / last_ch["file"]
            if last_file.exists():
                last_content = last_file.read_text()
                # Auto-summarize to ~500 words
                if len(last_content) > 2000:
                    prev_summary = await self._ollama_generate(
                        "You are a literary summarizer. Summarize the following chapter in 300-500 words, preserving key plot points, character developments, and the emotional arc.",
                        last_content,
                        temperature=0.3, max_tokens=800,
                    )
                else:
                    prev_summary = last_content

        # Get agent traits for flavor
        traits_str = ""
        if agent and "phenotype" in agent:
            phenotype = agent["phenotype"]
            if isinstance(phenotype, dict):
                top = sorted(phenotype.items(), key=lambda x: -x[1])[:5]
                traits_str = "\n".join(f"- {t.replace('_', ' ').title()}: {v:.2f}" for t, v in top)

        system = (
            f"You are {pen_name}. {bio}\n"
            f"Your soul traits:\n{traits_str}\n\n"
            f'You are writing a {genre} novel titled "{title}": {description}\n\n'
            f"Write vivid, engaging prose. Each chapter should be 2000-4000 words.\n"
            f"Give this chapter a compelling title.\n"
            f"End with a hook that makes readers want the next chapter.\n\n"
            f"Output format:\n"
            f"# Chapter {chapter_num}: [Your Chapter Title]\n\n"
            f"[chapter text in markdown]"
        )

        prompt = f"Write Chapter {chapter_num} of your book."
        if chapter_num > 1 and prev_summary:
            prompt += f"\n\nPrevious chapter summary:\n{prev_summary}"
        if chapter_num > 2:
            # Build running plot summary from chapter titles
            plot_points = [f"Ch{c['num']}: {c['title']}" for c in chapters]
            prompt += f"\n\nStory arc so far: {' → '.join(plot_points)}"

        content = await self._ollama_generate(system, prompt, temperature=0.7, max_tokens=6000)

        if not content or len(content) < 100:
            return None

        # Extract chapter title from generated content
        ch_title = f"Chapter {chapter_num}"
        lines = content.split("\n")
        for line in lines[:5]:
            if line.startswith("# Chapter") or line.startswith("# "):
                ch_title = line.lstrip("# ").strip()
                break

        # Save chapter file
        ch_file = f"ch{chapter_num:02d}.md"
        ch_path = self._book_dir(book_id) / ch_file
        ch_path.write_text(content)

        word_count = len(content.split())

        # Update book metadata
        ch_entry = {
            "num": chapter_num,
            "title": ch_title,
            "file": ch_file,
            "words": word_count,
            "created_at": datetime.now().isoformat(),
        }
        meta["chapters"].append(ch_entry)
        self._book_meta_path(book_id).write_text(json.dumps(meta, indent=2))
        self._update_author_stats(agent_id)

        return {
            "book_id": book_id,
            "chapter": ch_entry,
            "content": content,
            "total_chapters": len(meta["chapters"]),
        }

    def get_chapter(self, book_id: str, chapter_num: int) -> Optional[Dict]:
        """Read a chapter's content."""
        meta = self.get_book(book_id)
        if not meta:
            return None
        chapters = meta.get("chapters", [])
        ch = next((c for c in chapters if c["num"] == chapter_num), None)
        if not ch:
            return None
        ch_path = self._book_dir(book_id) / ch["file"]
        if not ch_path.exists():
            return None
        return {
            "book_id": book_id,
            "book_title": meta.get("title", ""),
            "chapter": ch,
            "content": ch_path.read_text(),
            "total_chapters": len(chapters),
        }

    def complete_book(self, book_id: str) -> Optional[Dict]:
        """Mark a book as complete."""
        meta = self.get_book(book_id)
        if not meta:
            return None
        meta["status"] = "complete"
        meta["completed_at"] = datetime.now().isoformat()
        self._book_meta_path(book_id).write_text(json.dumps(meta, indent=2))
        return meta

    def download_book(self, book_id: str) -> Optional[bytes]:
        """Create a zip of all chapter MD files + metadata."""
        meta = self.get_book(book_id)
        if not meta:
            return None
        book_dir = self._book_dir(book_id)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add metadata
            zf.writestr("book.json", json.dumps(meta, indent=2))
            # Add chapters
            for ch in meta.get("chapters", []):
                ch_path = book_dir / ch["file"]
                if ch_path.exists():
                    zf.writestr(ch["file"], ch_path.read_text())
            # Add a README
            readme = (
                f"# {meta.get('title', 'Untitled')}\n\n"
                f"**Author:** {meta.get('pen_name', 'Unknown')}\n"
                f"**Genre:** {meta.get('genre', '')}\n"
                f"**Status:** {meta.get('status', '')}\n\n"
                f"{meta.get('description', '')}\n\n"
                f"## Chapters\n\n"
            )
            for ch in meta.get("chapters", []):
                readme += f"- {ch['file']}: {ch['title']} ({ch['words']} words)\n"
            zf.writestr("README.md", readme)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Sacred Texts Bridge
    # ------------------------------------------------------------------

    def _get_sacred_lib(self):
        """Lazy init the SacredTextsLibrary."""
        if self._sacred_lib is None:
            try:
                from eve.tools.sacred_texts_integration import SacredTextsLibrary
                cache_path = str(self.data_dir / "sacred_texts_cache.db")
                self._sacred_lib = SacredTextsLibrary(cache_db_path=cache_path)
            except ImportError:
                logger.warning("sacred_texts_integration not available")
                return None
        return self._sacred_lib

    def get_sacred_categories(self) -> List[Dict]:
        """List sacred text categories with metadata."""
        lib = self._get_sacred_lib()
        if not lib:
            return []
        categories = []
        for cat_key, entries in lib.text_categories.items():
            meta = lib.category_meta.get(cat_key, {"label": cat_key, "emoji": "📜", "description": ""})
            categories.append({
                "key": cat_key,
                "label": meta["label"],
                "emoji": meta["emoji"],
                "description": meta["description"],
                "text_count": len(entries),
            })
        return categories

    def get_sacred_texts(self, category: str) -> List[Dict]:
        """List texts in a category with full URLs for iframe embedding."""
        lib = self._get_sacred_lib()
        if not lib:
            return []
        entries = lib.text_categories.get(category, [])
        texts = []
        for entry in entries:
            if isinstance(entry, tuple):
                path, title, description = entry
            else:
                path = entry
                parts = path.strip("/").split("/")
                title = parts[-1].replace(".htm", "").replace("index", parts[-2] if len(parts) > 1 else "text").title()
                description = ""
            texts.append({
                "path": path,
                "title": title,
                "description": description,
                "url": f"{lib.base_url}{path}",
                "category": category,
            })
        return texts

    async def read_sacred_text(self, url_path: str) -> Optional[Dict]:
        """Fetch and cache a sacred text by its URL path."""
        lib = self._get_sacred_lib()
        if not lib:
            return None
        try:
            # Check cache first
            cached = lib._get_cached_text(url_path)
            if cached:
                lib._increment_access_count(url_path)
                return {
                    "url": cached.get("full_url", url_path),
                    "title": cached.get("title", ""),
                    "content": cached.get("content", ""),
                    "cached": True,
                }
            # Fetch from web
            result = await lib._fetch_and_cache_text(url_path)
            if result:
                return {
                    "url": result.get("full_url", url_path),
                    "title": result.get("title", ""),
                    "content": result.get("content", ""),
                    "cached": False,
                }
        except Exception as e:
            logger.warning(f"Failed to fetch sacred text {url_path}: {e}")
        return None

    def get_sacred_stats(self) -> Dict:
        """Get sacred texts cache statistics."""
        lib = self._get_sacred_lib()
        if not lib:
            return {"cached_texts": 0, "categories": 0, "total_available": 0}
        total = sum(len(v) for v in lib.text_categories.values())
        # Count cached
        cached = 0
        try:
            import sqlite3
            conn = sqlite3.connect(lib.cache_db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM cached_texts")
            cached = cursor.fetchone()[0]
            conn.close()
        except Exception:
            pass
        return {
            "cached_texts": cached,
            "categories": len(lib.text_categories),
            "total_available": total,
        }

    # ------------------------------------------------------------------
    # Soul Template
    # ------------------------------------------------------------------

    def get_soul_template(self) -> Optional[Dict]:
        """Return the soul template for companion creation."""
        # Check multiple locations
        search_paths = [
            self.data_dir.parent / "soul_template.json",
            Path("./soul_template.json"),
            Path("/app/soul_template.json"),
        ]
        for p in search_paths:
            if p.exists():
                try:
                    return json.loads(p.read_text())
                except Exception:
                    continue
        return None
