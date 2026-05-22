"""
SEO Intelligence Engine
========================
Comprehensive SEO analysis powered by qwen3.5:397b-cloud.
Covers: on-page, technical, content, competitors, schema, Core Web Vitals,
keyword strategy, backlink profile, and actionable improvement roadmap.
"""

import asyncio
import logging
import os
import re
import time
from typing import AsyncGenerator, Dict, List, Optional
from urllib.parse import urlparse, urljoin

import aiohttp

from eve.brain.ollama_provider import OllamaProvider
from eve.brain.provider import Message

logger = logging.getLogger(__name__)

MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")

EVE_SEO_PERSONA = """You are Eve, an elite SEO intelligence analyst with deep expertise in technical SEO,
content strategy, Core Web Vitals, schema markup, and competitive analysis.
You analyze websites with precision, identify critical issues, and provide a clear,
prioritized roadmap with specific, actionable recommendations.
Your analysis is thorough, data-driven, and always practical."""


class SEOEngine:
    """Streaming SEO intelligence analysis engine."""

    def __init__(
        self,
        ollama_base_url: str = "http://ollama:11434",
        ollama_api_key: str = "",
    ):
        self.provider = OllamaProvider(
            model=MODEL,
            base_url=ollama_base_url,
            api_key=ollama_api_key,
        )

    async def _fetch_page(self, url: str) -> Dict:
        """Fetch a URL and extract basic HTML data."""
        # Normalize URL — strip malformed scheme like "https:example.com" (missing //)
        url = re.sub(r'^https?:(?!//)', '', url)
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        result = {
            "url": url,
            "status": None,
            "html": "",
            "headers": {},
            "load_time_ms": None,
            "error": None,
        }
        try:
            start = time.monotonic()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=15),
                    allow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; EveBot/1.0; +https://s0lf0rge.com)"},
                ) as resp:
                    result["status"] = resp.status
                    result["headers"] = dict(resp.headers)
                    result["final_url"] = str(resp.url)
                    result["load_time_ms"] = int((time.monotonic() - start) * 1000)
                    if resp.status == 200:
                        content_type = resp.headers.get("content-type", "")
                        if "html" in content_type or not content_type:
                            result["html"] = await resp.text(errors="replace")
        except Exception as e:
            result["error"] = str(e)
        return result

    def _extract_seo_data(self, html: str, url: str) -> Dict:
        """Extract SEO signals from raw HTML."""
        data = {}

        # Title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        data["title"] = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else ""
        data["title_len"] = len(data["title"])

        # Meta description
        desc_match = re.search(r'<meta\s+name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
        if not desc_match:
            desc_match = re.search(r'<meta\s+content=["\']([^"\']*)["\'][^>]*name=["\']description["\']', html, re.I)
        data["meta_description"] = desc_match.group(1).strip() if desc_match else ""
        data["meta_desc_len"] = len(data["meta_description"])

        # Meta keywords
        kw_match = re.search(r'<meta\s+name=["\']keywords["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
        data["meta_keywords"] = kw_match.group(1).strip() if kw_match else ""

        # Canonical
        canon_match = re.search(r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']*)["\']', html, re.I)
        data["canonical"] = canon_match.group(1).strip() if canon_match else ""

        # H tags
        for i in range(1, 7):
            tags = re.findall(rf"<h{i}[^>]*>(.*?)</h{i}>", html, re.I | re.S)
            data[f"h{i}"] = [re.sub(r"<[^>]+>", "", t).strip() for t in tags]

        # Images without alt
        all_imgs = re.findall(r"<img[^>]+>", html, re.I)
        imgs_no_alt = [t for t in all_imgs if "alt=" not in t.lower() or 'alt=""' in t.lower() or "alt=''" in t.lower()]
        data["total_images"] = len(all_imgs)
        data["images_missing_alt"] = len(imgs_no_alt)

        # Links
        all_links = re.findall(r'<a[^>]+href=["\']([^"\']*)["\']', html, re.I)
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        internal = [l for l in all_links if l.startswith("/") or l.startswith(base)]
        external = [l for l in all_links if l.startswith("http") and not l.startswith(base)]
        data["internal_links"] = len(internal)
        data["external_links"] = len(external)
        data["nofollow_links"] = len([l for l in re.findall(r'<a[^>]+rel=["\'][^"\']*nofollow', html, re.I)])

        # Schema markup
        schema_types = re.findall(r'"@type"\s*:\s*"([^"]+)"', html)
        data["schema_types"] = list(set(schema_types))

        # Open Graph
        og_tags = re.findall(r'<meta\s+property=["\']og:([^"\']+)["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
        data["og_tags"] = {k: v for k, v in og_tags}

        # Twitter Card
        tw_tags = re.findall(r'<meta\s+name=["\']twitter:([^"\']+)["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
        data["twitter_card"] = {k: v for k, v in tw_tags}

        # Robots meta
        robots_match = re.search(r'<meta\s+name=["\']robots["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
        data["robots_meta"] = robots_match.group(1) if robots_match else "not set"

        # Structured content word count estimate
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        words = text.split()
        data["word_count"] = len(words)

        # Viewport (mobile)
        data["has_viewport"] = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.I))

        # HTTPS
        data["is_https"] = url.startswith("https")

        # Sitemap link
        data["has_sitemap_link"] = bool(re.search(r"sitemap", html, re.I))

        return data

    def _build_seo_prompt(self, url: str, page_data: Dict, seo: Dict, competitors: List[str]) -> str:
        h1s = ", ".join(seo.get("h1", [])[:3]) or "NONE"
        h2s = ", ".join(seo.get("h2", [])[:5]) or "NONE"
        schema = ", ".join(seo.get("schema_types", [])) or "NONE"
        og = seo.get("og_tags", {})
        comp_str = ", ".join(competitors) if competitors else "None provided"

        return f"""Perform a comprehensive SEO intelligence analysis for this website.

## Page Data
URL: {url}
HTTP Status: {page_data.get('status')}
Load Time: {page_data.get('load_time_ms')}ms
Final URL (after redirects): {page_data.get('final_url', url)}
HTTPS: {seo.get('is_https')}
Has Viewport Meta: {seo.get('has_viewport')}

## On-Page Elements
Title: "{seo.get('title')}" ({seo.get('title_len')} chars)
Meta Description: "{seo.get('meta_description')[:200]}" ({seo.get('meta_desc_len')} chars)
Meta Keywords: {seo.get('meta_keywords', 'not set') or 'not set'}
Canonical: {seo.get('canonical') or 'not set'}
Robots Meta: {seo.get('robots_meta')}

## Heading Structure
H1 tags ({len(seo.get('h1', []))}): {h1s}
H2 tags ({len(seo.get('h2', []))}): {h2s}
H3 tags: {len(seo.get('h3', []))}
H4-H6: {sum(len(seo.get(f'h{i}', [])) for i in range(4,7))}

## Content & Links
Word Count: {seo.get('word_count')} words
Total Images: {seo.get('total_images')} ({seo.get('images_missing_alt')} missing alt text)
Internal Links: {seo.get('internal_links')}
External Links: {seo.get('external_links')}
Nofollow Links: {seo.get('nofollow_links')}

## Social & Schema
Schema Markup Types: {schema}
Open Graph Tags: {', '.join(f'{k}={v[:50]}' for k, v in og.items()) or 'NONE'}
Twitter Card: {seo.get('twitter_card', {}).get('card', 'not set')}

## HTTP Headers
Cache-Control: {page_data.get('headers', {}).get('cache-control', 'not set')}
Content-Encoding: {page_data.get('headers', {}).get('content-encoding', 'none')}
X-Frame-Options: {page_data.get('headers', {}).get('x-frame-options', 'not set')}
Strict-Transport-Security: {page_data.get('headers', {}).get('strict-transport-security', 'not set')}

## Competitors (for comparison context)
{comp_str}

---

Provide a COMPREHENSIVE SEO intelligence report with these exact sections:

### 1. SEO SCORE (0-100)
Give an overall score and brief scoring breakdown across: Technical (25pts), On-Page (25pts), Content (25pts), Authority Signals (25pts).

### 2. CRITICAL ISSUES (fix immediately)
List showstopper issues that are actively hurting rankings. Be specific.

### 3. ON-PAGE ANALYSIS
Deep analysis of title, meta description, H-tag hierarchy, internal linking, image optimization. Include specific rewrite recommendations.

### 4. TECHNICAL SEO
Analyze: load time, HTTPS, mobile-friendliness, security headers, caching, redirects, canonical setup. Flag all issues.

### 5. CONTENT STRATEGY
Evaluate word count, content depth, keyword coverage (inferred from headings), content gaps, and E-E-A-T signals.

### 6. SCHEMA & STRUCTURED DATA
Analyze existing schema markup. Recommend additional schema types that would benefit this site based on its apparent content type.

### 7. COMPETITOR GAPS
Based on the competitors provided (if any), identify likely content and keyword gaps.

### 8. KEYWORD OPPORTUNITIES
Suggest 10 specific long-tail keywords this page should target based on the content signals detected.

### 9. BACKLINK STRATEGY
Recommend 5 specific, realistic backlink acquisition strategies for this site type.

### 10. PRIORITIZED ACTION PLAN
A 30-60-90 day roadmap with specific actions, ranked by impact vs effort. Format as a checklist.

Be direct, specific, and actionable. No vague advice."""

    async def analyze(
        self,
        url: str,
        competitors: Optional[List[str]] = None,
        focus_keywords: Optional[List[str]] = None,
    ) -> AsyncGenerator[Dict, None]:
        """Stream a comprehensive SEO analysis report."""
        competitors = competitors or []
        focus_keywords = focus_keywords or []

        yield {"event": "status", "message": f"Fetching page: {url}"}
        page_data = await self._fetch_page(url)

        if page_data.get("error"):
            yield {"event": "error", "message": f"Could not fetch page: {page_data['error']}"}
            return

        yield {"event": "status", "message": "Extracting SEO signals from HTML..."}
        seo = self._extract_seo_data(page_data.get("html", ""), url)

        yield {
            "event": "page_data",
            "title": seo.get("title"),
            "status": page_data.get("status"),
            "load_time_ms": page_data.get("load_time_ms"),
            "word_count": seo.get("word_count"),
            "schema_types": seo.get("schema_types"),
            "has_viewport": seo.get("has_viewport"),
            "is_https": seo.get("is_https"),
            "images_missing_alt": seo.get("images_missing_alt"),
            "internal_links": seo.get("internal_links"),
        }

        yield {"event": "status", "message": "Running AI SEO analysis with qwen3.5:397b-cloud..."}

        prompt = self._build_seo_prompt(url, page_data, seo, competitors)
        if focus_keywords:
            prompt += f"\n\n**Focus Keywords to prioritize:** {', '.join(focus_keywords)}"

        messages = [Message(role="user", content=prompt)]

        report_chunks = []
        async for chunk in self.provider.stream(
            messages=messages,
            system_prompt=EVE_SEO_PERSONA,
            think=False,  # disable thinking — SEO reports don't need extended reasoning
            max_tokens=8192,
        ):
            if chunk:
                if chunk.startswith("[THINK]"):
                    pass  # discard thinking tokens silently
                elif chunk.startswith("[STREAM_ERROR]"):
                    yield {"event": "error", "message": chunk[14:]}
                    return
                else:
                    report_chunks.append(chunk)
                    yield {"event": "chunk", "content": chunk}

        full_report = "".join(report_chunks)
        yield {
            "event": "complete",
            "report": full_report,
            "url": url,
            "seo_data": {k: v for k, v in seo.items() if k != "html"},
            "competitors": competitors,
        }
