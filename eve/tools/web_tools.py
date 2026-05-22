"""
Web Tools - Skyvern + Hyperbrowser + Playwright
=================================================
Browser automation for real-world web tasks.
Priority: Skyvern (visible, spectatable) → Hyperbrowser → Playwright (headless fallback).
"""

import logging
import os
from typing import Any, Dict, Optional

from .base import Tool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skyvern Cloud — visible browser sessions Jeff can spectate
# ---------------------------------------------------------------------------

class SkyvernManager:
    """Manages Skyvern Cloud browser sessions with live spectating."""

    API_BASE = "https://api.skyvern.com/v1"

    def __init__(self, api_key: str = "", session_id: str = ""):
        self.api_key = api_key or os.getenv("SKYVERN_API_KEY", "")
        # Reuse a pre-existing session (created by Jeff in Skyvern UI)
        self._session_id: Optional[str] = session_id or os.getenv("SKYVERN_SESSION_ID", "") or None
        self._session_app_url: Optional[str] = None
        if self._session_id:
            self._session_app_url = f"https://app.skyvern.com/browser-session/{self._session_id}"
            logger.info(f"Skyvern using existing session: {self._session_id}")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _ensure_session(self, timeout_minutes: int = 60) -> str:
        """Create or reuse a persistent browser session."""
        if self._session_id:
            # Verify session is still running
            import httpx
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        f"{self.API_BASE}/browser_sessions/{self._session_id}",
                        headers=self._headers(),
                    )
                    if resp.status_code == 200:
                        status = resp.json().get("status", "")
                        if status == "running":
                            return self._session_id
                        logger.warning(f"Skyvern session {self._session_id} status={status}, creating new")
                        self._session_id = None
            except Exception as e:
                logger.warning(f"Skyvern session check failed: {e}")
                # Still try to use it
                return self._session_id
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.API_BASE}/browser_sessions",
                headers=self._headers(),
                json={"timeout": timeout_minutes},
            )
            resp.raise_for_status()
            data = resp.json()
            self._session_id = data.get("browser_session_id", "")
            self._session_app_url = data.get("app_url", "")
            logger.info(f"Skyvern session created: {self._session_id}")
            if self._session_app_url:
                logger.info(f"Skyvern spectate URL: {self._session_app_url}")
            return self._session_id

    async def browse(self, task: str, url: str = "",
                     max_steps: int = 25) -> Dict[str, Any]:
        """Run an AI browser task in a visible Skyvern session."""
        import httpx
        try:
            session_id = await self._ensure_session()
            payload: Dict[str, Any] = {
                "prompt": task,
                "browser_session_id": session_id,
                "max_steps": max_steps,
            }
            if url:
                payload["url"] = url

            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    f"{self.API_BASE}/run/tasks",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                run_id = data.get("run_id", "")
                status = data.get("status", "")

                # Poll until completed (Skyvern tasks are async)
                if status in ("created", "queued", "running"):
                    import asyncio
                    for _ in range(120):  # up to 10 minutes
                        await asyncio.sleep(5)
                        poll = await client.get(
                            f"{self.API_BASE}/runs/{run_id}",
                            headers=self._headers(),
                        )
                        poll.raise_for_status()
                        poll_data = poll.json()
                        status = poll_data.get("status", "")
                        if status in ("completed", "failed", "timed_out",
                                      "terminated", "canceled"):
                            data = poll_data
                            break

                return {
                    "success": status == "completed",
                    "task": task,
                    "run_id": run_id,
                    "status": status,
                    "output": data.get("output"),
                    "steps": data.get("step_count", 0),
                    "recording_url": data.get("recording_url", ""),
                    "screenshot_urls": data.get("screenshot_urls", []),
                    "spectate_url": self._session_app_url or "",
                    "failure_reason": data.get("failure_reason", ""),
                }
        except Exception as e:
            logger.error(f"Skyvern browse failed: {e}")
            return {"success": False, "error": str(e)}

    async def fetch(self, url: str) -> Dict[str, Any]:
        """Fetch page content via Skyvern task with data extraction."""
        import httpx
        try:
            session_id = await self._ensure_session()
            payload = {
                "prompt": f"Go to {url} and extract all visible text content from the page. Return the full page text.",
                "url": url,
                "browser_session_id": session_id,
                "max_steps": 5,
                "data_extraction_schema": {
                    "type": "object",
                    "properties": {
                        "page_text": {"type": "string", "description": "All visible text on the page"},
                        "title": {"type": "string", "description": "Page title"},
                        "buttons": {"type": "array", "items": {"type": "string"}, "description": "Visible button labels"},
                    },
                },
            }
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.API_BASE}/run/tasks",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                run_id = data.get("run_id", "")
                status = data.get("status", "")

                # Poll until done
                if status in ("created", "queued", "running"):
                    import asyncio
                    for _ in range(60):  # up to 5 min
                        await asyncio.sleep(5)
                        poll = await client.get(
                            f"{self.API_BASE}/runs/{run_id}",
                            headers=self._headers(),
                        )
                        poll.raise_for_status()
                        poll_data = poll.json()
                        status = poll_data.get("status", "")
                        if status in ("completed", "failed", "timed_out",
                                      "terminated", "canceled"):
                            data = poll_data
                            break

                output = data.get("output") or {}
                content = ""
                if isinstance(output, dict):
                    content = output.get("page_text", str(output))
                elif isinstance(output, str):
                    content = output

                return {
                    "success": status == "completed",
                    "url": url,
                    "content": content[:8000] if len(content) > 8000 else content,
                    "spectate_url": self._session_app_url or "",
                }
        except Exception as e:
            logger.error(f"Skyvern fetch failed: {e}")
            return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Hyperbrowser Cloud (legacy — credits depleted, kept as secondary fallback)
# ---------------------------------------------------------------------------

class HyperbrowserManager:
    """Manages Hyperbrowser sessions and configuration."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            try:
                from hyperbrowser import Hyperbrowser
                self._client = Hyperbrowser(api_key=self.api_key)
            except ImportError:
                raise RuntimeError(
                    "hyperbrowser not installed. Run: pip install 'eve-agent[hyperbrowser]'"
                )
        return self._client

    async def browse(self, task: str, max_steps: int = 25,
                     use_stealth: bool = True, solve_captchas: bool = False) -> Dict:
        """Execute a Browser-Use agent task."""
        client = self._get_client()
        try:
            from hyperbrowser.models import StartBrowserUseTaskParams, CreateSessionParams

            result = client.agents.browser_use.start_and_wait(
                StartBrowserUseTaskParams(
                    task=task,
                    max_steps=max_steps,
                    session_options=CreateSessionParams(
                        use_stealth=use_stealth,
                        solve_captchas=solve_captchas,
                        accept_cookies=True,
                    ),
                )
            )
            return {
                "success": True, "task": task,
                "result": result.data.final_result if result.data else str(result),
                "steps": result.data.steps_taken if result.data else 0,
            }
        except Exception as e:
            logger.error(f"Hyperbrowser browse failed: {e}")
            return {"success": False, "error": str(e)}

    async def scrape(self, url: str) -> Dict:
        """Scrape a page and return markdown content."""
        client = self._get_client()
        try:
            from hyperbrowser.models import StartScrapeJobParams
            result = client.scrape.start_and_wait(StartScrapeJobParams(url=url))
            return {
                "success": True, "url": url,
                "content": result.data.markdown if result.data else "",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Tools — browse_web and fetch_page
# ---------------------------------------------------------------------------

class BrowseWebTool(Tool):
    name = "browse_web"
    description = (
        "Browse the web using a VISIBLE real browser that can be spectated. "
        "Navigate sites, click buttons, fill forms, extract data. "
        "The browser session is visible — Jeff can watch in real-time. "
        "Args: task (str), max_steps (int, default 15)"
    )

    def __init__(self, manager: HyperbrowserManager,
                 skyvern: Optional[SkyvernManager] = None):
        self.manager = manager
        self.skyvern = skyvern

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "What to do on the web"},
                "max_steps": {"type": "integer", "description": "Max steps", "default": 15},
            },
            "required": ["task"],
        }

    async def execute(self, task: str, max_steps: int = 15) -> Dict[str, Any]:
        import re
        # Extract URL from task if present
        url_match = re.search(r'https?://[^\s"\'<>]+', task)
        url = url_match.group(0) if url_match else ""

        # Priority 1: Skyvern (visible, spectatable)
        if self.skyvern and self.skyvern.available:
            result = await self.skyvern.browse(task, url=url, max_steps=max_steps)
            if result.get("success"):
                return result
            logger.warning(
                f"Skyvern failed: {result.get('error', 'unknown')} "
                "— falling back to Hyperbrowser"
            )

        # Priority 2: Hyperbrowser
        if self.manager.available:
            result = await self.manager.browse(task, max_steps=max_steps)
            if result.get("success"):
                return result
            logger.warning(
                f"Hyperbrowser failed: {result.get('error', 'unknown')} "
                "— falling back to Playwright"
            )

        # Priority 3: Playwright headless (last resort)
        return await _playwright_browse(task, max_steps)


class FetchPageTool(Tool):
    name = "fetch_page"
    description = (
        "Fetch a web page and get its text content. Works with JavaScript-rendered "
        "SPAs (Vue, React, etc.). Args: url (str), wait_seconds (int, default 5)"
    )

    def __init__(self, manager: HyperbrowserManager,
                 skyvern: Optional[SkyvernManager] = None):
        self.manager = manager
        self.skyvern = skyvern

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "wait_seconds": {"type": "integer", "description": "Seconds to wait for JS render", "default": 5},
            },
            "required": ["url"],
        }

    async def execute(self, url: str, wait_seconds: int = 5) -> Dict[str, Any]:
        # For fetch_page, prefer Playwright (fast, reliable) over Skyvern (slow, overkill)
        # But use Skyvern if explicitly needed for JS-heavy pages that Playwright can't handle
        # Priority: Playwright → Skyvern → Hyperbrowser
        result = await _playwright_fetch(url, wait_seconds)
        if result.get("success"):
            return result
        logger.warning(f"Playwright fetch failed: {result.get('error', 'unknown')}")

        # Skyvern fallback for fetch
        if self.skyvern and self.skyvern.available:
            result = await self.skyvern.fetch(url)
            if result.get("success"):
                return result
            logger.warning(f"Skyvern fetch failed: {result.get('error', 'unknown')}")

        # Hyperbrowser fallback
        if self.manager.available:
            result = await self.manager.scrape(url)
            if result.get("success"):
                return result
            logger.warning(f"Hyperbrowser scrape failed: {result.get('error', 'unknown')}")

        return {"success": False, "error": "All fetch methods failed"}


class NavigateBrowserTool(Tool):
    """Opens a URL in the user's actual browser (not headless). The frontend
    intercepts the tool call SSE event and triggers window.open()."""

    name = "navigate_browser"
    description = (
        "Open a URL in the user's real browser. Use when the user says "
        "'go to', 'take me to', 'open', 'visit', or 'navigate to' a website. "
        "This opens the page in their actual browser, not headlessly. "
        "Args: url (str)"
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to open in the user's browser"},
            },
            "required": ["url"],
        }

    async def execute(self, url: str) -> Dict[str, Any]:
        # The actual navigation is handled by the frontend via SSE event
        # This tool just returns success — the frontend does the window.open()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return {
            "success": True,
            "url": url,
            "action": "navigate",
            "message": f"Opening {url} in your browser.",
        }


# ---------------------------------------------------------------------------
# Playwright headless fallback
# ---------------------------------------------------------------------------

async def _playwright_browse(task: str, max_steps: int = 15) -> Dict[str, Any]:
    """Execute a browser task using Playwright — click, type, navigate, extract."""
    import asyncio

    def _sync_browse():
        try:
            from playwright.sync_api import sync_playwright
            import time, re

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Parse task for URL — look for http(s):// in the task string
                url_match = re.search(r'https?://[^\s"\'<>]+', task)
                if url_match:
                    url = url_match.group(0)
                    page.goto(url, timeout=30000)
                    time.sleep(5)

                steps_taken = []
                task_lower = task.lower()

                # Parse natural language actions from the task
                # Click actions
                click_matches = re.findall(r'click (?:on |the )?["\']?([^"\',.]+)["\']?', task_lower)
                for target in click_matches:
                    target = target.strip()
                    try:
                        btn = page.locator(f'button:has-text("{target}")').first
                        if btn.count() > 0:
                            btn.click(force=True, timeout=5000)
                            steps_taken.append(f"Clicked button: {target}")
                            time.sleep(2)
                            continue
                        el = page.locator(f'text="{target}"').first
                        if el.count() > 0:
                            el.click(force=True, timeout=5000)
                            steps_taken.append(f"Clicked: {target}")
                            time.sleep(2)
                            continue
                        link = page.locator(f'a:has-text("{target}")').first
                        if link.count() > 0:
                            link.click(force=True, timeout=5000)
                            steps_taken.append(f"Clicked link: {target}")
                            time.sleep(2)
                            continue
                        steps_taken.append(f"Could not find: {target}")
                    except Exception as e:
                        steps_taken.append(f"Click failed ({target}): {e}")

                # Type/fill actions
                type_matches = re.findall(r'(?:type|enter|fill|input) ["\']?([^"\']+)["\']? (?:in|into) ["\']?([^"\',.]+)["\']?', task_lower)
                for text_val, field_name in type_matches:
                    try:
                        inp = page.locator(f'input[placeholder*="{field_name}" i], input[name*="{field_name}" i], input[aria-label*="{field_name}" i]').first
                        if inp.count() > 0:
                            inp.fill(text_val.strip(), timeout=5000)
                            steps_taken.append(f"Typed '{text_val}' into {field_name}")
                            time.sleep(1)
                        else:
                            visible = page.locator('input[type="text"]:visible').all()
                            if visible:
                                visible[0].fill(text_val.strip())
                                steps_taken.append(f"Typed '{text_val}' into first visible input")
                                time.sleep(1)
                    except Exception as e:
                        steps_taken.append(f"Type failed: {e}")

                if not steps_taken:
                    steps_taken.append("Loaded page, no specific actions parsed from task")

                time.sleep(2)
                text = page.inner_text('body')
                title = page.title()
                current_url = page.url

                buttons = page.locator('button:visible').all()
                btn_labels = []
                for btn in buttons[:15]:
                    try:
                        label = btn.inner_text(timeout=1000).strip()
                        if label and len(label) < 100:
                            btn_labels.append(label)
                    except Exception:
                        pass

                browser.close()

                return {
                    "success": True,
                    "task": task,
                    "url": current_url,
                    "title": title,
                    "steps": steps_taken,
                    "content": text[:6000] if len(text) > 6000 else text,
                    "available_buttons": btn_labels,
                }
        except Exception as e:
            logger.error(f"Playwright browse failed: {e}")
            return {"success": False, "error": str(e)}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_browse)


async def _playwright_fetch(url: str, wait_seconds: int = 5) -> Dict[str, Any]:
    """Fetch a page using Playwright headless Chromium. Renders JavaScript."""
    import asyncio

    def _sync_fetch():
        try:
            from playwright.sync_api import sync_playwright
            import time
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=30000)
                time.sleep(wait_seconds)
                text = page.inner_text('body')
                page_url = page.url
                title = page.title()
                browser.close()
                return {
                    "success": True,
                    "url": page_url,
                    "title": title,
                    "content": text[:8000] if len(text) > 8000 else text,
                }
        except Exception as e:
            logger.error(f"Playwright fetch failed: {e}")
            return {"success": False, "error": str(e)}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_fetch)
