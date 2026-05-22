"""
Search Tools - Web Search & Fetch
====================================
"""

import logging
import re
from typing import Any, Dict

import aiohttp

from .base import Tool

logger = logging.getLogger(__name__)


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web for information. Args: query (str), max_results (int, default 5)"

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Max results", "default": 5},
            },
            "required": ["query"],
        }

    async def execute(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        try:
            async with aiohttp.ClientSession() as session:
                params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
                async with session.get("https://api.duckduckgo.com/", params=params) as resp:
                    data = await resp.json(content_type=None)
                    results = []
                    if data.get("Abstract"):
                        results.append({
                            "title": data.get("Heading", ""),
                            "content": data["Abstract"],
                            "url": data.get("AbstractURL", ""),
                        })
                    for topic in data.get("RelatedTopics", [])[:max_results]:
                        if isinstance(topic, dict) and "Text" in topic:
                            results.append({
                                "title": topic.get("Text", "")[:100],
                                "content": topic.get("Text", ""),
                                "url": topic.get("FirstURL", ""),
                            })
                    return {"success": True, "query": query, "results": results[:max_results]}
        except Exception as e:
            return {"success": False, "error": f"Search failed: {e}"}


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch content from a URL. Args: url (str)"

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "URL to fetch"}},
            "required": ["url"],
        }

    async def execute(self, url: str) -> Dict[str, Any]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    text = await resp.text()
                    clean = re.sub(r"<[^>]+>", " ", text)
                    clean = re.sub(r"\s+", " ", clean).strip()
                    return {"success": True, "url": url, "status": resp.status,
                            "content": clean[:10000]}
        except Exception as e:
            return {"success": False, "error": f"Fetch failed: {e}"}
