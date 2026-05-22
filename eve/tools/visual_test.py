"""
Visual Test Tool — Eve's Eyes
================================
Captures screenshots of web pages and analyzes them with Qwen 3.5 Cloud vision.
No selectors, no DOM parsing — pure pixel-level visual QA like a human tester.
"""

import asyncio
import base64
import logging
import os
from typing import Any, Dict, List, Optional

from .base import Tool

logger = logging.getLogger(__name__)

# Default viewports to test
VIEWPORTS = {
    "desktop": {"width": 1280, "height": 800},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 375, "height": 812},
}

ANALYSIS_PROMPT = """You are a senior QA engineer reviewing a screenshot of a web application.

Analyze this screenshot and report:
1. **Layout** — Is everything properly aligned? Any overflow, clipping, or overlapping elements?
2. **Readability** — Is text legible? Good contrast? Proper sizing?
3. **Functionality** — Do interactive elements (buttons, inputs, links) look functional?
4. **Responsiveness** — Does the layout make sense for this viewport size ({viewport})?
5. **Visual Bugs** — Any blank areas, broken images, misaligned components, z-index issues?

Be specific about coordinates/regions when reporting issues. Be concise — bullet points, not essays.
If everything looks correct, say so briefly and move on."""


class VisualTestTool(Tool):
    """Captures a screenshot of a URL and analyzes it with vision AI."""

    name = "visual_test"
    description = (
        "Take a screenshot of any web page and analyze it visually using AI vision. "
        "Returns a detailed QA report of layout issues, visual bugs, and responsiveness. "
        "Uses Playwright for screenshots and Qwen 3.5 Cloud vision for analysis. "
        "Args: url (str) — page URL; viewports (list, optional) — 'desktop','tablet','mobile'; "
        "prompt (str, optional) — custom analysis prompt."
    )

    def __init__(self, ollama_base_url: str = None, ollama_model: str = None):
        self.ollama_base_url = ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.ollama_model = ollama_model or os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
        self._browser = None
        self._playwright = None

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to screenshot (e.g., 'http://localhost:8006')",
                },
                "viewports": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Viewport sizes to test: 'desktop', 'tablet', 'mobile'. Default: ['desktop']",
                },
                "prompt": {
                    "type": "string",
                    "description": "Custom analysis prompt (optional — default is general QA review)",
                },
                "wait_seconds": {
                    "type": "number",
                    "description": "Seconds to wait after page load before screenshot (default: 2)",
                },
            },
            "required": ["url"],
        }

    async def _ensure_browser(self):
        """Launch Playwright browser if not already running."""
        if self._browser:
            return self._browser

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
            ],
        )
        logger.info("🎭 Playwright browser launched")
        return self._browser

    async def _capture_screenshot(self, url: str, viewport: Dict, wait_seconds: float = 2) -> bytes:
        """Capture a screenshot at the given viewport."""
        browser = await self._ensure_browser()
        context = await browser.new_context(
            viewport=viewport,
            device_scale_factor=1,
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(wait_seconds)
            screenshot = await page.screenshot(full_page=True, type="png")
            return screenshot
        finally:
            await context.close()

    async def _analyze_screenshot(self, screenshot_b64: str, viewport_name: str,
                                   custom_prompt: str = None) -> str:
        """Send screenshot to Qwen 3.5 Cloud vision for analysis."""
        import httpx

        prompt = custom_prompt or ANALYSIS_PROMPT.format(viewport=viewport_name)

        payload = {
            "model": self.ollama_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [screenshot_b64],
                }
            ],
            "stream": False,
            "options": {"temperature": 0.3},
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.ollama_base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content = data.get("message", {}).get("content", "")
        # Strip thinking tags if present
        if "<think>" in content and "</think>" in content:
            think_end = content.index("</think>") + len("</think>")
            content = content[think_end:].strip()

        return content

    async def execute(self, url: str, viewports: List[str] = None,
                      prompt: str = None, wait_seconds: float = 2) -> Dict[str, Any]:
        """Capture screenshots and analyze them."""
        viewports = viewports or ["desktop"]
        results = {}
        screenshots_saved = []

        for vp_name in viewports:
            vp_config = VIEWPORTS.get(vp_name)
            if not vp_config:
                results[vp_name] = f"Unknown viewport '{vp_name}'. Use: desktop, tablet, mobile"
                continue

            try:
                logger.info(f"📸 Capturing {vp_name} ({vp_config['width']}x{vp_config['height']}): {url}")
                screenshot_bytes = await self._capture_screenshot(url, vp_config, wait_seconds)

                # Save screenshot for reference
                save_dir = "/app/eve_data/visual_tests"
                os.makedirs(save_dir, exist_ok=True)
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{save_dir}/{vp_name}_{timestamp}.png"
                with open(filename, "wb") as f:
                    f.write(screenshot_bytes)
                screenshots_saved.append(filename)
                logger.info(f"💾 Saved: {filename} ({len(screenshot_bytes)} bytes)")

                # Send to vision model
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                logger.info(f"🧠 Analyzing {vp_name} with {self.ollama_model}...")
                analysis = await self._analyze_screenshot(screenshot_b64, vp_name, prompt)
                results[vp_name] = analysis

            except Exception as e:
                logger.error(f"❌ Failed {vp_name}: {e}")
                results[vp_name] = f"Error: {e}"

        return {
            "success": True,
            "url": url,
            "viewports_tested": viewports,
            "screenshots": screenshots_saved,
            "analysis": results,
        }

    async def cleanup(self):
        """Close the browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
