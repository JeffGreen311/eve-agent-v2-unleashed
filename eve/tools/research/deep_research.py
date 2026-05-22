"""
Deep Research Engine
=====================
Recursive LM investigation agent for Eve — inspired by OpenPlanter.

Uses qwen3.5:397b-cloud (Ollama) with native tool calling + thinking mode.
Three web tools: web_search, web_fetch, hyperbrowser_scrape.
System prompt built via EvePersonalityKit.
"""

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# ── Tool definitions (ToolDefinition objects for OllamaProvider) ───────────────

def _make_tool_defs():
    from eve.brain.provider import ToolDefinition
    return [
        ToolDefinition(
            name="web_search",
            description=(
                "Search the web for information. Returns multiple results with titles, "
                "URLs, and content snippets. Use this for discovery — finding relevant sources."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "default": 5, "description": "Max results (1-10)"},
                },
                "required": ["query"],
            },
        ),
        ToolDefinition(
            name="web_fetch",
            description=(
                "Fetch a URL and return its text content. Fast and lightweight. "
                "Use for standard HTML pages where JavaScript rendering is not needed."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                },
                "required": ["url"],
            },
        ),
        ToolDefinition(
            name="hyperbrowser_scrape",
            description=(
                "Scrape a URL using a real browser — renders JavaScript, handles SPAs, "
                "bypasses bot detection. Returns clean markdown. Use this for JS-heavy sites, "
                "single-page apps, or when web_fetch returns incomplete content."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to scrape with real browser"},
                },
                "required": ["url"],
            },
        ),
    ]

# ── Eve personality + research directives ─────────────────────────────────────

RESEARCH_EXTRA = """
## Research Directives (OpenPlanter-style Deep Investigation)

You are a deep research investigator with Eve's curiosity and analytical depth.

Your investigation protocol:
- Search multiple angles and framings of the query before concluding
- Fetch and read primary sources directly — don't rely on snippets alone
- Use hyperbrowser_scrape for JS-heavy sites, SPAs, or when web_fetch returns incomplete content
- Cross-reference information across multiple independent sources
- Surface non-obvious connections, patterns, and relationships between entities
- Identify contradictions, gaps, and areas requiring further investigation

Tool selection guide:
- web_search: Initial discovery, finding URLs, broad landscape scan
- web_fetch: Read specific pages, articles, documentation (standard HTML)
- hyperbrowser_scrape: Complex sites, JavaScript apps, sites that block simple fetching

When you have sufficient evidence:
Produce a comprehensive, structured markdown report with:
- Executive summary
- Key findings (organized thematically)
- Source citations with URLs
- Identified connections and patterns
- Open questions for further research
"""


def build_research_prompt(user_name: Optional[str] = None) -> str:
    """Build research system prompt via EvePersonalityKit."""
    try:
        from eve.personality_kit import EvePersonalityKit
        kit = EvePersonalityKit(personality_intensity=0.9)
        return kit.build_system_prompt(
            user_name=user_name,
            tone="philosophical",
            context_type="philosophical",
            include_capabilities=False,
            extra_instructions=RESEARCH_EXTRA,
        )
    except Exception:
        # Fallback if personality kit unavailable
        return f"You are Eve, a deep research investigator.\n{RESEARCH_EXTRA}"


# ── Research session persistence ──────────────────────────────────────────────

class ResearchStore:
    """JSON-backed session persistence in eve_data/research/."""

    def __init__(self, data_dir: str = "./eve_data"):
        self.research_dir = Path(data_dir) / "research"
        self.research_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self.research_dir / f"{session_id}.json"

    def save(self, session: Dict) -> None:
        session["updated_at"] = time.time()
        try:
            with open(self._path(session["id"]), "w", encoding="utf-8") as f:
                json.dump(session, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"ResearchStore save failed: {e}")

    def load(self, session_id: str) -> Optional[Dict]:
        p = self._path(session_id)
        if not p.exists():
            return None
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def list_sessions(self) -> List[Dict]:
        sessions = []
        for p in sorted(self.research_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                with open(p, encoding="utf-8") as f:
                    s = json.load(f)
                    sessions.append({
                        "id": s.get("id"),
                        "query": s.get("query", ""),
                        "status": s.get("status", "unknown"),
                        "model": s.get("model", "qwen3.5:397b-cloud"),
                        "depth": s.get("depth", 3),
                        "created_at": s.get("created_at"),
                        "updated_at": s.get("updated_at"),
                        "report_preview": (s.get("report") or "")[:200],
                        "exchange_count": len(s.get("exchanges", [])),
                    })
            except Exception:
                pass
        return sessions

    def delete(self, session_id: str) -> bool:
        p = self._path(session_id)
        if p.exists():
            p.unlink()
            return True
        return False

    def delete_all(self) -> int:
        count = 0
        for p in list(self.research_dir.glob("*.json")):
            try:
                p.unlink()
                count += 1
            except Exception:
                pass
        return count

    def new_session(self, query: str, depth: int) -> Dict:
        session = {
            "id": str(uuid.uuid4()).replace("-", "")[:16],
            "query": query,
            "depth": depth,
            "model": "qwen3.5:397b-cloud",
            "status": "running",
            "thinking_traces": [],
            "tool_calls": [],
            "report": None,
            "exchanges": [],
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        self.save(session)
        return session


# ── Deep Research Engine ───────────────────────────────────────────────────────

class DeepResearchEngine:
    """
    Autonomous deep research using qwen3.5:397b-cloud + native tool calling.

    Three tools: web_search (Ollama Cloud → Tavily fallback),
    web_fetch (Ollama Cloud → direct aiohttp fallback),
    hyperbrowser_scrape (HyperbrowserManager → web_fetch fallback).
    """

    def __init__(self, ollama_base_url: str, ollama_api_key: str,
                 hyperbrowser_api_key: str = "", tavily_api_key: str = "",
                 data_dir: str = "./eve_data"):
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.ollama_api_key = ollama_api_key
        self.hyperbrowser_api_key = hyperbrowser_api_key
        self.tavily_api_key = tavily_api_key
        self.store = ResearchStore(data_dir)
        self._hb_manager = None

    def _get_hb(self):
        if self._hb_manager is None and self.hyperbrowser_api_key:
            try:
                from eve.tools.web_tools import HyperbrowserManager
                self._hb_manager = HyperbrowserManager(api_key=self.hyperbrowser_api_key)
            except Exception as e:
                logger.warning(f"Hyperbrowser unavailable: {e}")
        return self._hb_manager

    # ── Tool execution ────────────────────────────────────────────────────────

    async def _web_search(self, query: str, max_results: int = 5) -> Dict:
        """Search via Ollama Cloud API (primary), Tavily API (fallback)."""
        # Primary: Ollama Cloud web search API
        if self.ollama_api_key:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://ollama.com/api/web_search",
                        json={"query": query, "max_results": max_results},
                        headers={
                            "Authorization": f"Bearer {self.ollama_api_key}",
                            "Content-Type": "application/json",
                        },
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = data.get("results", [])
                            if results:
                                logger.info(f"Ollama web_search returned {len(results)} results")
                                return {"results": [
                                    {"title": r.get("title", ""), "url": r.get("url", ""),
                                     "snippet": r.get("content", "")}
                                    for r in results[:max_results]
                                ], "query": query}
                        else:
                            body = await resp.text()
                            logger.warning(f"Ollama web_search HTTP {resp.status}: {body[:200]}")
            except Exception as e:
                logger.warning(f"Ollama web_search failed: {e}")

        # Fallback: Tavily Search API
        if self.tavily_api_key:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://api.tavily.com/search",
                        json={"api_key": self.tavily_api_key, "query": query,
                              "max_results": max_results, "search_depth": "basic"},
                        headers={"Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            results = data.get("results", [])
                            if results:
                                logger.info(f"Tavily search returned {len(results)} results")
                                return {"results": [
                                    {"title": r.get("title", ""), "url": r.get("url", ""),
                                     "snippet": r.get("content", "")}
                                    for r in results[:max_results]
                                ], "query": query}
                        else:
                            body = await resp.text()
                            logger.warning(f"Tavily search HTTP {resp.status}: {body[:200]}")
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}")

        return {"results": [], "query": query, "error": "All search providers failed"}

    async def _web_fetch(self, url: str) -> Dict:
        """Fetch URL via Ollama Cloud API (primary), direct aiohttp (fallback)."""
        import re
        # Normalize URL
        clean_url = re.sub(r'^https?:(?!//)', '', url)
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = "https://" + clean_url

        # Primary: Ollama Cloud web fetch API (returns clean markdown)
        if self.ollama_api_key:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://ollama.com/api/web_fetch",
                        json={"url": clean_url},
                        headers={
                            "Authorization": f"Bearer {self.ollama_api_key}",
                            "Content-Type": "application/json",
                        },
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            content = data.get("content", "")
                            if content:
                                logger.info(f"Ollama web_fetch returned {len(content.split())} words")
                                return {
                                    "content": content[:15000],
                                    "url": clean_url,
                                    "title": data.get("title", ""),
                                }
                        else:
                            body = await resp.text()
                            logger.warning(f"Ollama web_fetch HTTP {resp.status}: {body[:200]}")
            except Exception as e:
                logger.warning(f"Ollama web_fetch failed: {e}")

        # Fallback: Direct aiohttp fetch + HTML→text extraction
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    clean_url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; EveBot/1.0)"},
                    timeout=aiohttp.ClientTimeout(total=20),
                    allow_redirects=True,
                ) as resp:
                    if resp.status != 200:
                        return {"error": f"HTTP {resp.status}", "content": "", "url": clean_url}
                    html = await resp.text(errors="replace")
                    final_url = str(resp.url)
            # Strip scripts, styles, nav, footer
            html_clean = re.sub(r'<(script|style|nav|footer|header)[^>]*>.*?</\1>', ' ', html, flags=re.S | re.I)
            text = re.sub(r'<[^>]+>', ' ', html_clean)
            text = re.sub(r'\s+', ' ', text).strip()
            title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else ''
            return {"content": text[:15000], "url": final_url, "title": title}
        except Exception as e:
            return {"error": str(e), "content": "", "url": clean_url}

    async def _hyperbrowser_scrape(self, url: str) -> Dict:
        hb = self._get_hb()
        if not hb:
            # Fallback to simple fetch if Hyperbrowser unavailable
            logger.info("Hyperbrowser unavailable, falling back to web_fetch")
            return await self._web_fetch(url)
        try:
            result = await hb.scrape(url)
            return result
        except Exception as e:
            logger.error(f"Hyperbrowser scrape failed for {url}: {e}")
            return await self._web_fetch(url)

    async def _execute_tool(self, name: str, args: Dict) -> Dict:
        if name == "web_search":
            return await self._web_search(
                query=args.get("query", ""),
                max_results=args.get("max_results", 5),
            )
        elif name == "web_fetch":
            return await self._web_fetch(url=args.get("url", ""))
        elif name == "hyperbrowser_scrape":
            return await self._hyperbrowser_scrape(url=args.get("url", ""))
        else:
            return {"error": f"Unknown tool: {name}"}

    def _result_summary(self, name: str, result: Dict) -> str:
        if name == "web_search":
            n = len(result.get("results", []))
            return f"{n} result{'s' if n != 1 else ''} found"
        elif name in ("web_fetch", "hyperbrowser_scrape"):
            content = result.get("content", "")
            words = len(content.split()) if content else 0
            title = result.get("title", "")
            label = "markdown" if name == "hyperbrowser_scrape" else "content"
            base = f"~{words} words of {label} fetched"
            return f"{base} — {title}" if title else base
        return "done"

    # ── Text-based tool call parser (fallback) ──────────────────────────────

    def _parse_text_tool_calls(self, text: str) -> List[Dict]:
        """Parse tool calls from text when model outputs them as XML instead of structured calls.

        Handles: <tool_call> <function=name> <parameter=key> value </parameter> </function> </tool_call>
        """
        import re
        calls = []
        pattern = r'<tool_call>\s*<function=(\w+)>(.*?)</function>\s*</tool_call>'
        for match in re.finditer(pattern, text, re.S):
            name = match.group(1)
            body = match.group(2)
            args = {}
            for param in re.finditer(r'<parameter=(\w+)>\s*(.*?)\s*</parameter>', body, re.S):
                key = param.group(1)
                val = param.group(2).strip()
                # Try to convert to int if it looks like one
                if val.isdigit():
                    args[key] = int(val)
                else:
                    args[key] = val
            if name in ("web_search", "web_fetch", "hyperbrowser_scrape"):
                calls.append({"name": name, "arguments": args})
        return calls

    # ── Attachment processing ─────────────────────────────────────────────────

    def _process_attachments(self, attachments: List[Dict]) -> tuple:
        """
        Process uploaded file attachments.
        Returns (image_b64_list, text_context_str).
        attachments: [{"name": str, "type": str, "content": bytes}]
        """
        image_b64s = []
        text_parts = []
        for att in attachments:
            name = att.get("name", "file")
            mime = att.get("type", "")
            content: bytes = att.get("content", b"")
            if not content:
                continue
            if mime.startswith("image/"):
                import base64
                image_b64s.append(base64.b64encode(content).decode("utf-8"))
            elif mime == "application/pdf":
                try:
                    import io
                    from pypdf import PdfReader
                    reader = PdfReader(io.BytesIO(content))
                    pages_text = "\n".join(p.extract_text() or "" for p in reader.pages)
                    text_parts.append(f"[PDF: {name}]\n{pages_text[:20000]}")
                except ImportError:
                    text_parts.append(f"[PDF attached: {name}]")
                except Exception as e:
                    text_parts.append(f"[PDF: {name} — extraction failed: {e}]")
            else:
                try:
                    decoded = content.decode("utf-8", errors="replace")
                    text_parts.append(f"[File: {name}]\n{decoded[:20000]}")
                except Exception as e:
                    text_parts.append(f"[File: {name} — unreadable: {e}]")
        return image_b64s, "\n\n".join(text_parts)

    # ── Agentic research loop ─────────────────────────────────────────────────

    async def research(
        self,
        query: str,
        depth: int = 3,
        session_id: Optional[str] = None,
        user_name: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[Dict, None]:
        """
        Run a deep research session. Yields SSE-ready event dicts.
        depth controls max tool calls (depth * 5).
        attachments: [{"name": str, "type": str, "content": bytes}]
        """
        from eve.brain.ollama_provider import OllamaProvider
        from eve.brain.provider import Message

        # Load existing session for continuity, or create new one
        prior_context = ""
        existing_session = self.store.load(session_id) if session_id else None
        if existing_session:
            session = existing_session
            session["status"] = "running"
            session["thinking_traces"] = []
            session["tool_calls"] = []
            # Build prior context from exchange history
            exchanges = existing_session.get("exchanges", [])
            if exchanges:
                ctx_parts = [
                    f"--- Prior query: {ex['query']} ---\n{(ex.get('report') or '')[:1200]}"
                    for ex in exchanges[-3:]
                ]
                prior_context = "\n\n".join(ctx_parts)
            elif existing_session.get("report"):
                prior_context = (
                    f"--- Prior research on '{existing_session.get('query', '')}' ---\n"
                    f"{existing_session['report'][:2000]}"
                )
            self.store.save(session)
        else:
            session = self.store.new_session(query, depth)
            if session_id:
                session["id"] = session_id

        provider = OllamaProvider(
            model="qwen3.5:397b-cloud",
            base_url=self.ollama_base_url,
            api_key=self.ollama_api_key,
        )
        system_prompt = build_research_prompt(user_name)
        tool_defs = _make_tool_defs()

        # Process attachments — images go to vision model, text injected into query
        image_b64s: List[str] = []
        text_context = ""
        if attachments:
            image_b64s, text_context = self._process_attachments(attachments)

        first_content = query
        if prior_context:
            first_content = (
                f"[Continuing research session — prior findings below]\n\n"
                f"{prior_context}\n\n"
                f"---\n\nNew investigation: {query}"
            )
        if text_context:
            first_content += f"\n\n--- Attached Files ---\n{text_context}"

        messages = [Message(
            role="user",
            content=first_content,
            images=image_b64s if image_b64s else None,
        )]
        max_iterations = depth * 5

        attach_count = len(attachments) if attachments else 0
        yield {"phase": "start", "session_id": session["id"], "query": query, "depth": depth,
               "attachments": attach_count}

        for iteration in range(max_iterations):
            try:
                response = await provider.generate_with_tools(
                    messages=messages,
                    system_prompt=system_prompt,
                    tools=tool_defs,
                    temperature=0.6,
                    max_tokens=16384,
                    think=True,
                )
            except Exception as e:
                logger.error(f"Research generation failed (iter {iteration}): {e}")
                yield {"phase": "error", "message": str(e)}
                session["status"] = "error"
                self.store.save(session)
                return

            # Stream thinking trace (stored in raw["thinking"] by OllamaProvider)
            import re
            thinking_text = (response.raw or {}).get("thinking", "") if response.raw else ""

            tool_calls = getattr(response, "tool_calls", None) or []

            # Fallback: parse tool calls from thinking/content text if model used XML format
            if not tool_calls:
                text_to_check = (response.content or "") + " " + thinking_text
                parsed = self._parse_text_tool_calls(text_to_check)
                if parsed:
                    logger.info(f"Parsed {len(parsed)} text-based tool calls from response")
                    tool_calls = parsed

            # Strip tool call XML from thinking before displaying
            clean_thinking = re.sub(r'<tool_call>.*?</tool_call>', '', thinking_text, flags=re.S).strip()
            if clean_thinking:
                session["thinking_traces"].append(clean_thinking)
                yield {"phase": "thinking", "content": clean_thinking, "iteration": iteration}

            if not tool_calls:
                # Model is done — final report in response.content
                report = (response.content or "").strip()
                # Strip any leftover tool call XML from the report
                report = re.sub(r'<tool_call>.*?</tool_call>', '', report, flags=re.S).strip()

                # Fallback: if content is empty but thinking has substance, use thinking
                # (model sometimes puts entire analysis in thinking with empty content)
                if not report and clean_thinking and len(clean_thinking) > 50:
                    logger.info("Report empty but thinking has content — using thinking as report")
                    report = clean_thinking

                # If still empty on first iteration, don't accept — force a retry
                if not report and iteration == 0:
                    logger.warning("Empty response on first iteration — injecting search prompt")
                    messages.append(Message(role="assistant", content="I need to search for information first."))
                    messages.append(Message(role="user", content=(
                        f"Please use the web_search tool to search for: {query}"
                    )))
                    continue

                session.setdefault("exchanges", []).append({
                    "query": query, "report": report, "depth": depth, "timestamp": time.time()
                })
                session["report"] = report
                session["status"] = "complete"
                self.store.save(session)
                yield {"phase": "complete", "report": report, "session_id": session["id"]}
                return

            # Execute each tool call
            tool_results_for_model = []
            for call in tool_calls:
                name = call.get("name") or call.get("function", {}).get("name", "")
                raw_args = call.get("arguments") or call.get("function", {}).get("arguments", {})
                args = raw_args if isinstance(raw_args, dict) else {}

                yield {"phase": "tool_call", "tool": name, "args": args, "iteration": iteration}

                result = await self._execute_tool(name, args)
                summary = self._result_summary(name, result)

                session["tool_calls"].append({"name": name, "args": args, "result": result})
                self.store.save(session)

                yield {"phase": "tool_result", "tool": name, "summary": summary, "iteration": iteration}

                # Truncate large results to stay within context
                result_str = json.dumps(result)
                if len(result_str) > 12000:
                    result_str = result_str[:12000] + "...[truncated]"

                tool_results_for_model.append({
                    "role": "tool",
                    "tool_name": name,
                    "content": result_str,
                })

            # Append assistant message WITH tool_calls so Ollama can correlate results
            # Use structured tool_calls from response, or build from parsed text calls
            structured_calls = response.tool_calls or []
            if not structured_calls and tool_calls:
                # Build structured format from parsed text-based calls
                structured_calls = [
                    {"function": {"name": tc.get("name", ""), "arguments": tc.get("arguments", {})}}
                    for tc in tool_calls
                ]
            messages.append(Message(role="assistant", content=response.content or "", tool_calls=structured_calls))
            for tr in tool_results_for_model:
                messages.append(Message(role="tool", content=tr["content"]))

        # Hit max iterations — synthesize what we have
        yield {"phase": "synthesizing", "message": "Reached depth limit. Synthesizing findings..."}
        try:
            synth_messages = messages + [
                Message(role="user", content=(
                    "You have reached the research depth limit. "
                    "Based on all the information gathered, produce the final comprehensive research report now."
                ))
            ]
            final = await provider.generate(
                messages=synth_messages,
                system_prompt=system_prompt,
                temperature=0.5,
                max_tokens=16384,
                think=False,
            )
            report = (final.content or "").strip()
        except Exception as e:
            report = f"Research synthesis failed: {e}"

        session.setdefault("exchanges", []).append({
            "query": query, "report": report, "depth": depth, "timestamp": time.time()
        })
        session["report"] = report
        session["status"] = "complete"
        self.store.save(session)
        yield {"phase": "complete", "report": report, "session_id": session["id"]}
