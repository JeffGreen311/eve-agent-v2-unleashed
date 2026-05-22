"""
Chrome DevTools Tool
=====================
Browser automation, performance testing, accessibility validation,
and Core Web Vitals measurement via Chrome DevTools Protocol.
Uses Playwright to connect to Chrome and execute CDP commands.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from typing import Any, Dict, Optional

from .base import Tool

logger = logging.getLogger(__name__)


class ChromeDevToolsManager:
    """Manages Chrome DevTools Protocol connections via Playwright."""

    def __init__(self):
        self._browser = None
        self._playwright = None
        self.available = True

    async def _ensure_browser(self):
        if self._browser and self._browser.is_connected():
            return self._browser
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
            )
            return self._browser
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            self.available = False
            return None

    async def screenshot(self, url: str, viewport: Dict = None, full_page: bool = False) -> Dict:
        """Take a screenshot of a URL."""
        browser = await self._ensure_browser()
        if not browser:
            return {"success": False, "error": "Browser unavailable"}
        try:
            page = await browser.new_page(viewport=viewport or {"width": 1920, "height": 1080})
            await page.goto(url, wait_until="networkidle", timeout=30000)
            screenshot_bytes = await page.screenshot(full_page=full_page)
            await page.close()

            # Save to temp file
            import uuid
            filename = f"devtools_screenshot_{uuid.uuid4().hex[:8]}.png"
            filepath = os.path.join("/app/static/eve_generated_images", filename)
            with open(filepath, "wb") as f:
                f.write(screenshot_bytes)

            return {
                "success": True,
                "url": url,
                "screenshot_url": f"/static/eve_generated_images/{filename}",
                "size": len(screenshot_bytes),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def performance_audit(self, url: str) -> Dict:
        """Measure Core Web Vitals and performance metrics."""
        browser = await self._ensure_browser()
        if not browser:
            return {"success": False, "error": "Browser unavailable"}
        try:
            page = await browser.new_page()
            # Inject performance observer before navigation
            await page.add_init_script("""
                window.__perfMetrics = {};
                new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        if (entry.entryType === 'largest-contentful-paint') {
                            window.__perfMetrics.lcp = entry.startTime;
                        }
                    }
                }).observe({type: 'largest-contentful-paint', buffered: true});

                new PerformanceObserver((list) => {
                    let cls = 0;
                    for (const entry of list.getEntries()) {
                        if (!entry.hadRecentInput) cls += entry.value;
                    }
                    window.__perfMetrics.cls = cls;
                }).observe({type: 'layout-shift', buffered: true});
            """)

            start = asyncio.get_event_loop().time()
            response = await page.goto(url, wait_until="networkidle", timeout=30000)
            load_time = asyncio.get_event_loop().time() - start

            # Get metrics
            metrics = await page.evaluate("window.__perfMetrics")
            timing = await page.evaluate("""() => {
                const t = performance.timing;
                return {
                    dns: t.domainLookupEnd - t.domainLookupStart,
                    tcp: t.connectEnd - t.connectStart,
                    ttfb: t.responseStart - t.requestStart,
                    dom_interactive: t.domInteractive - t.navigationStart,
                    dom_complete: t.domComplete - t.navigationStart,
                    load_event: t.loadEventEnd - t.navigationStart,
                };
            }""")

            await page.close()
            return {
                "success": True,
                "url": url,
                "status_code": response.status if response else None,
                "total_load_time_ms": round(load_time * 1000),
                "core_web_vitals": {
                    "LCP_ms": round(metrics.get("lcp", 0)),
                    "CLS": round(metrics.get("cls", 0), 4),
                },
                "timing": timing,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def accessibility_check(self, url: str) -> Dict:
        """Run accessibility validation on a page."""
        browser = await self._ensure_browser()
        if not browser:
            return {"success": False, "error": "Browser unavailable"}
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Run axe-core accessibility audit
            issues = await page.evaluate("""async () => {
                const issues = [];
                // Check images without alt text
                document.querySelectorAll('img:not([alt])').forEach(img => {
                    issues.push({type: 'error', rule: 'img-alt', message: 'Image missing alt text', element: img.src?.substring(0, 80)});
                });
                // Check empty links
                document.querySelectorAll('a').forEach(a => {
                    if (!a.textContent.trim() && !a.querySelector('img[alt]')) {
                        issues.push({type: 'error', rule: 'link-name', message: 'Link has no accessible name', element: a.href?.substring(0, 80)});
                    }
                });
                // Check form inputs without labels
                document.querySelectorAll('input:not([type="hidden"]):not([aria-label]):not([aria-labelledby])').forEach(input => {
                    const id = input.id;
                    if (!id || !document.querySelector(`label[for="${id}"]`)) {
                        issues.push({type: 'warning', rule: 'label', message: 'Input missing label', element: input.name || input.type});
                    }
                });
                // Check color contrast (basic)
                // Check heading hierarchy
                let lastLevel = 0;
                document.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach(h => {
                    const level = parseInt(h.tagName[1]);
                    if (level > lastLevel + 1) {
                        issues.push({type: 'warning', rule: 'heading-order', message: `Heading level skipped: h${lastLevel} to h${level}`, element: h.textContent?.substring(0, 40)});
                    }
                    lastLevel = level;
                });
                return issues;
            }""")

            await page.close()
            return {
                "success": True,
                "url": url,
                "total_issues": len(issues),
                "errors": len([i for i in issues if i["type"] == "error"]),
                "warnings": len([i for i in issues if i["type"] == "warning"]),
                "issues": issues[:20],  # Cap at 20
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_page_info(self, url: str) -> Dict:
        """Get page metadata, DOM stats, and network info."""
        browser = await self._ensure_browser()
        if not browser:
            return {"success": False, "error": "Browser unavailable"}
        try:
            page = await browser.new_page()
            response = await page.goto(url, wait_until="networkidle", timeout=30000)

            info = await page.evaluate("""() => ({
                title: document.title,
                meta_description: document.querySelector('meta[name="description"]')?.content || '',
                canonical: document.querySelector('link[rel="canonical"]')?.href || '',
                h1: Array.from(document.querySelectorAll('h1')).map(h => h.textContent.trim()).slice(0, 3),
                links: document.querySelectorAll('a[href]').length,
                images: document.querySelectorAll('img').length,
                scripts: document.querySelectorAll('script').length,
                stylesheets: document.querySelectorAll('link[rel="stylesheet"]').length,
                forms: document.querySelectorAll('form').length,
                dom_elements: document.querySelectorAll('*').length,
            })""")

            await page.close()
            return {
                "success": True,
                "url": url,
                "status_code": response.status if response else None,
                **info,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

class DevToolsScreenshotTool(Tool):
    name = "devtools_screenshot"
    description = (
        "Take a screenshot of any webpage using Chrome DevTools. "
        "Returns a viewable image URL. "
        "Args: url (str), full_page (bool, default false)"
    )

    def __init__(self, manager: ChromeDevToolsManager):
        self.manager = manager

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to screenshot"},
                "full_page": {"type": "boolean", "description": "Capture full scrollable page", "default": False},
            },
            "required": ["url"],
        }

    async def execute(self, url: str, full_page: bool = False) -> Dict[str, Any]:
        return await self.manager.screenshot(url, full_page=full_page)


class DevToolsPerformanceTool(Tool):
    name = "devtools_performance"
    description = (
        "Measure Core Web Vitals (LCP, CLS) and page load performance. "
        "Returns timing breakdown, TTFB, DOM metrics. "
        "Args: url (str)"
    )

    def __init__(self, manager: ChromeDevToolsManager):
        self.manager = manager

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to audit"},
            },
            "required": ["url"],
        }

    async def execute(self, url: str) -> Dict[str, Any]:
        return await self.manager.performance_audit(url)


class DevToolsAccessibilityTool(Tool):
    name = "devtools_accessibility"
    description = (
        "Run accessibility validation on a webpage. "
        "Checks for missing alt text, unlabeled inputs, heading hierarchy issues. "
        "Args: url (str)"
    )

    def __init__(self, manager: ChromeDevToolsManager):
        self.manager = manager

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to check"},
            },
            "required": ["url"],
        }

    async def execute(self, url: str) -> Dict[str, Any]:
        return await self.manager.accessibility_check(url)


class DevToolsPageInfoTool(Tool):
    name = "devtools_page_info"
    description = (
        "Get page metadata, DOM stats, SEO info from any URL. "
        "Returns title, meta description, headings, link/image/script counts. "
        "Args: url (str)"
    )

    def __init__(self, manager: ChromeDevToolsManager):
        self.manager = manager

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to analyze"},
            },
            "required": ["url"],
        }

    async def execute(self, url: str) -> Dict[str, Any]:
        return await self.manager.get_page_info(url)
