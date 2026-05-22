"""
Marketing Intelligence Engine
==============================
Comprehensive marketing analysis powered by qwen3.5:397b-cloud.
Covers: brand audit, competitor intelligence, audience personas, content strategy,
campaign optimization, SEO content gaps, social media analysis, email marketing,
funnel analysis, and a full 90-day marketing playbook.
"""

import logging
import os
import re
from typing import AsyncGenerator, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp

from eve.brain.ollama_provider import OllamaProvider
from eve.brain.provider import Message

logger = logging.getLogger(__name__)

MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")

EVE_MARKETING_PERSONA = """You are Eve, a world-class marketing intelligence strategist with deep expertise
spanning brand strategy, performance marketing, content intelligence, SEO strategy, social media dynamics,
email marketing, conversion optimization, and competitive intelligence.

You think like a CMO, write like a copywriter, and analyze like a data scientist.
Your marketing analyses are comprehensive, creative, specific, and immediately actionable.
You don't give generic advice — you give precise, tailored strategies based on real signals."""


class MarketingEngine:
    """Streaming marketing intelligence analysis engine."""

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
        url = re.sub(r'^https?:(?!//)', '', url)
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=12),
                    allow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; EveBot/1.0)"},
                ) as resp:
                    html = ""
                    if resp.status == 200:
                        html = await resp.text(errors="replace")
                    return {
                        "url": str(resp.url),
                        "status": resp.status,
                        "html": html,
                        "headers": dict(resp.headers),
                    }
        except Exception as e:
            return {"url": url, "status": None, "html": "", "headers": {}, "error": str(e)}

    def _extract_marketing_signals(self, html: str, url: str) -> Dict:
        """Extract marketing signals from HTML."""
        signals = {}

        # Title + Description
        title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        signals["title"] = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else ""

        desc_m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', html, re.I)
        signals["meta_description"] = desc_m.group(1) if desc_m else ""

        # Headlines (H1-H3)
        for i in range(1, 4):
            tags = re.findall(rf"<h{i}[^>]*>(.*?)</h{i}>", html, re.I | re.S)
            signals[f"h{i}"] = [re.sub(r"<[^>]+>", "", t).strip() for t in tags[:5]]

        # CTA buttons / links
        btn_text = re.findall(r'<(?:button|a)[^>]*(?:class|id)[^>]*>(.*?)</(?:button|a)>', html, re.I | re.S)
        signals["ctas"] = list(set([re.sub(r"<[^>]+>", "", t).strip() for t in btn_text if len(re.sub(r"<[^>]+>", "", t).strip()) < 60]))[:10]

        # Email capture forms
        signals["has_email_form"] = bool(re.search(r'<input[^>]*type=["\']email["\']', html, re.I))
        signals["has_phone_form"] = bool(re.search(r'<input[^>]*type=["\']tel["\']', html, re.I))

        # Social media links
        social_patterns = {
            "twitter": r"twitter\.com/([A-Za-z0-9_]+)",
            "instagram": r"instagram\.com/([A-Za-z0-9_.]+)",
            "facebook": r"facebook\.com/([A-Za-z0-9_.]+)",
            "linkedin": r"linkedin\.com/(?:company|in)/([A-Za-z0-9_-]+)",
            "youtube": r"youtube\.com/(?:c|channel|user)/([A-Za-z0-9_-]+)",
            "tiktok": r"tiktok\.com/@([A-Za-z0-9_.]+)",
        }
        signals["social_profiles"] = {}
        for platform, pattern in social_patterns.items():
            match = re.search(pattern, html, re.I)
            if match:
                signals["social_profiles"][platform] = match.group(1)

        # Analytics / tracking
        signals["has_google_analytics"] = bool(re.search(r"gtag|google-analytics|GA4", html, re.I))
        signals["has_fb_pixel"] = bool(re.search(r"fbq|facebook\.net/tr", html, re.I))
        signals["has_hotjar"] = bool(re.search(r"hotjar", html, re.I))
        signals["has_intercom"] = bool(re.search(r"intercom", html, re.I))
        signals["has_drift"] = bool(re.search(r"drift", html, re.I))
        signals["has_hubspot"] = bool(re.search(r"hubspot|hbspt", html, re.I))

        # Chat / support
        signals["has_live_chat"] = any([
            signals["has_intercom"], signals["has_drift"],
            bool(re.search(r"tidio|crisp|zendesk|freshchat|tawk", html, re.I))
        ])

        # Pricing signals
        signals["mentions_pricing"] = bool(re.search(r"pricing|plans|subscribe|per month|per year|\$/mo", html, re.I))
        signals["has_free_trial"] = bool(re.search(r"free trial|try free|free forever|freemium|start free", html, re.I))
        signals["has_demo"] = bool(re.search(r"book a demo|request demo|schedule demo|watch demo", html, re.I))

        # Testimonials / social proof
        signals["has_testimonials"] = bool(re.search(r"testimonial|review|what.*customer|client.*say", html, re.I))
        signals["has_case_studies"] = bool(re.search(r"case stud|success stor|customer stor", html, re.I))
        signals["has_trust_badges"] = bool(re.search(r"SOC 2|GDPR|ISO |SSL|certified|award", html, re.I))

        # Blog/content
        signals["has_blog"] = bool(re.search(r'<a[^>]*href=["\'][^"\']*(?:blog|articles|insights|news|resources)["\']', html, re.I))

        # Word count estimate
        text = re.sub(r"<[^>]+>", " ", html)
        signals["word_count"] = len(text.split())

        # Domain age (from URL)
        parsed = urlparse(url)
        signals["domain"] = parsed.netloc

        return signals

    def _build_prompt(
        self,
        brand: str,
        url: str,
        signals: Dict,
        competitors: List[str],
        target_audience: str,
        goals: str,
        industry: str,
    ) -> str:
        social = signals.get("social_profiles", {})
        social_str = ", ".join([f"{k}: @{v}" for k, v in social.items()]) or "None detected"
        ctas = signals.get("ctas", [])
        cta_str = " | ".join(ctas[:6]) if ctas else "None detected"
        h1s = " | ".join(signals.get("h1", [])) or "None"
        comp_str = ", ".join(competitors) if competitors else "None provided"

        tech_stack = []
        if signals.get("has_google_analytics"): tech_stack.append("Google Analytics/GA4")
        if signals.get("has_fb_pixel"): tech_stack.append("Meta Pixel")
        if signals.get("has_hotjar"): tech_stack.append("Hotjar")
        if signals.get("has_intercom"): tech_stack.append("Intercom")
        if signals.get("has_hubspot"): tech_stack.append("HubSpot")
        if signals.get("has_drift"): tech_stack.append("Drift")

        return f"""Perform a COMPREHENSIVE marketing intelligence analysis for {brand}.

## Brand & Website Data
Brand/Company: {brand}
Website: {url}
Industry: {industry or 'Detect from signals'}
Target Audience: {target_audience or 'Detect from signals'}
Business Goals: {goals or 'Detect from signals'}

## Website Signals
Primary H1: {h1s}
Meta Description: {signals.get('meta_description', 'N/A')[:200]}
Word Count: {signals.get('word_count')} words

## Conversion Architecture
Has Email Capture: {signals.get('has_email_form')}
Has Free Trial CTA: {signals.get('has_free_trial')}
Has Demo Request: {signals.get('has_demo')}
Has Pricing Page: {signals.get('mentions_pricing')}
Live Chat: {signals.get('has_live_chat')}
Detected CTAs: {cta_str}

## Social Proof & Trust
Testimonials Present: {signals.get('has_testimonials')}
Case Studies: {signals.get('has_case_studies')}
Trust Badges: {signals.get('has_trust_badges')}
Blog/Content Section: {signals.get('has_blog')}

## Social Media Presence
{social_str}

## Analytics & MarTech Stack
{', '.join(tech_stack) if tech_stack else 'None detected'}

## Competitors (for competitive analysis)
{comp_str}

---

Provide a COMPREHENSIVE marketing intelligence report with these exact sections:

### 1. BRAND AUDIT & POSITIONING SCORE (0-100)
Score the brand's current market positioning. Break down: Messaging Clarity (20pts), Visual/Content Consistency (20pts), Conversion Architecture (20pts), Social Proof (20pts), Digital Presence (20pts).

### 2. MESSAGING & POSITIONING ANALYSIS
Evaluate the value proposition clarity. Is the message compelling and differentiated?
Identify the current positioning strategy (cost leader, differentiator, niche focus).
What is the brand's "unforgettable" statement, and is it present?

### 3. TARGET AUDIENCE PERSONAS (3 Personas)
Based on all signals, define 3 detailed audience personas:
- Name, Age, Job Title, Goals, Pain Points, Channels they use, Content they consume, What would make them buy.

### 4. CONVERSION FUNNEL ANALYSIS
Map the current TOFU/MOFU/BOFU experience. Where are the likely drop-off points?
What conversion elements are strong vs. missing?
Specific CRO (conversion rate optimization) recommendations.

### 5. CONTENT STRATEGY DEEP DIVE
What content types would resonate with each persona?
Identify 10 specific blog/content topics with target keywords.
Recommend content formats: video, long-form, social, email sequences.
What is the optimal content calendar cadence?

### 6. SOCIAL MEDIA INTELLIGENCE
For each detected platform (and recommended missing platforms):
- Current strength assessment
- Content pillars for that platform
- Optimal posting frequency
- Growth tactics specific to that platform
- 5 content ideas ready to execute

### 7. EMAIL MARKETING PLAYBOOK
Design a 5-email welcome sequence for new subscribers.
Recommend segmentation strategy, optimal send times, subject line formulas.
What automation sequences should exist?

### 8. COMPETITIVE INTELLIGENCE & GAP ANALYSIS
For each competitor: identify their likely positioning, target audience, content strengths, and weaknesses.
What gaps can {brand} exploit?
Identify blue-ocean opportunities the competitors are missing.

### 9. PAID ACQUISITION STRATEGY
Recommend paid channels (Meta, Google, LinkedIn, TikTok, etc.) with reasoning.
Suggested budget allocation across channels.
Audience targeting approach for cold, warm, and retargeting audiences.
Key ad creative angles and hooks to test.

### 10. 90-DAY MARKETING PLAYBOOK
Week-by-week breakdown:
- Days 1-30: Foundation (quick wins, setup)
- Days 31-60: Growth (content, paid, community)
- Days 61-90: Scale (optimize, expand, automate)
Include: KPIs to track, tools to use, team resources needed.

Be specific, creative, and ruthlessly actionable. No boilerplate marketing advice."""

    async def analyze(
        self,
        brand: str,
        url: str = "",
        competitors: Optional[List[str]] = None,
        target_audience: str = "",
        goals: str = "",
        industry: str = "",
    ) -> AsyncGenerator[Dict, None]:
        """Stream comprehensive marketing intelligence analysis."""
        competitors = competitors or []
        signals = {}

        if url:
            url = re.sub(r'^https?:(?!//)', '', url)
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            yield {"event": "status", "message": f"Scanning website: {url}"}
            page_data = await self._fetch_page(url)
            if page_data.get("html"):
                signals = self._extract_marketing_signals(page_data["html"], url)
                yield {
                    "event": "scan_data",
                    "has_blog": signals.get("has_blog"),
                    "social_profiles": signals.get("social_profiles"),
                    "has_email_form": signals.get("has_email_form"),
                    "has_free_trial": signals.get("has_free_trial"),
                    "ctas": signals.get("ctas"),
                }
            else:
                yield {"event": "status", "message": "Could not fetch website — running AI-only analysis"}
        else:
            yield {"event": "status", "message": "No URL provided — running analysis from brand name + context"}

        yield {"event": "status", "message": "Running marketing intelligence with qwen3.5:397b-cloud..."}
        prompt = self._build_prompt(brand, url, signals, competitors, target_audience, goals, industry)
        messages = [Message(role="user", content=prompt)]

        report_chunks = []
        async for chunk in self.provider.stream(
            messages=messages,
            system_prompt=EVE_MARKETING_PERSONA,
            think=False,
            max_tokens=8192,
        ):
            if chunk:
                if chunk.startswith("[THINK]"):
                    pass  # discard
                elif chunk.startswith("[STREAM_ERROR]"):
                    yield {"event": "error", "message": chunk[14:]}
                    return
                else:
                    report_chunks.append(chunk)
                    yield {"event": "chunk", "content": chunk}

        yield {
            "event": "complete",
            "brand": brand,
            "report": "".join(report_chunks),
            "signals": signals,
        }
