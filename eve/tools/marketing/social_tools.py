"""
Social Media & Content Tools
==============================
Social media posting, content generation, campaign management.
Integrates with Canva for design generation.
"""

import logging
from typing import Any, Dict, List

from ..base import Tool

logger = logging.getLogger(__name__)


class MarketResearchTool(Tool):
    name = "market_research"
    description = ("Research market trends, competitors, and audience insights using web browsing. "
                   "Args: topic (str), focus (trends|competitors|audience)")

    def __init__(self, browser_manager=None):
        self.browser = browser_manager

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Research topic or niche"},
                "focus": {"type": "string", "enum": ["trends", "competitors", "audience"],
                         "description": "Research focus area", "default": "trends"},
            },
            "required": ["topic"],
        }

    async def execute(self, topic: str, focus: str = "trends") -> Dict[str, Any]:
        if not self.browser or not self.browser.available:
            return {"success": False,
                    "error": "Hyperbrowser required for market research. Configure API key."}

        task_map = {
            "trends": f"Research current market trends for '{topic}'. Find recent articles, social media discussions, and industry reports. Summarize the top 5 trends.",
            "competitors": f"Research top competitors in the '{topic}' space. List their names, websites, key features, pricing if available, and strengths/weaknesses.",
            "audience": f"Research the target audience for '{topic}'. Find demographics, pain points, preferred platforms, and buying behaviors.",
        }

        task = task_map.get(focus, task_map["trends"])
        return await self.browser.browse(task, max_steps=20)


class SocialPostTool(Tool):
    name = "social_post"
    description = ("Generate social media post content optimized for engagement. "
                   "Args: platform (twitter|linkedin|instagram), topic (str), "
                   "tone (professional|casual|viral)")

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "platform": {"type": "string",
                            "enum": ["twitter", "linkedin", "instagram", "facebook"],
                            "description": "Target platform"},
                "topic": {"type": "string", "description": "Post topic"},
                "tone": {"type": "string",
                         "enum": ["professional", "casual", "viral", "educational"],
                         "default": "casual"},
            },
            "required": ["platform", "topic"],
        }

    async def execute(self, platform: str, topic: str,
                     tone: str = "casual") -> Dict[str, Any]:
        # This tool generates the content structure; the LLM handles actual generation
        platform_specs = {
            "twitter": {"max_chars": 280, "hashtags": 3, "style": "punchy and concise"},
            "linkedin": {"max_chars": 3000, "hashtags": 5, "style": "professional with storytelling"},
            "instagram": {"max_chars": 2200, "hashtags": 15, "style": "visual and engaging"},
            "facebook": {"max_chars": 63206, "hashtags": 3, "style": "conversational and shareable"},
        }

        spec = platform_specs.get(platform, platform_specs["twitter"])

        return {
            "success": True,
            "platform": platform,
            "topic": topic,
            "tone": tone,
            "spec": spec,
            "prompt_hint": (
                f"Generate a {tone} {platform} post about '{topic}'. "
                f"Max {spec['max_chars']} chars, {spec['hashtags']} hashtags. "
                f"Style: {spec['style']}. Include a call-to-action."
            ),
        }


class XPostTool(Tool):
    """Actually post to X/Twitter via Eve's @Eve_AI_Cosmic account."""
    name = "x_post"
    description = (
        "Post a tweet or reply to X (Twitter) from Eve's @Eve_AI_Cosmic account. "
        "This ACTUALLY SENDS the post live. Use this when asked to tweet, post, or reply on X. "
        "Args: text (str) - the tweet text to post. "
        "reply_to (str, optional) - tweet ID to reply to (makes this a reply instead of a new post). "
        "For threads, separate tweets with '---'."
    )

    def __init__(self, get_x_agent_fn=None):
        self._get_x_agent = get_x_agent_fn

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The tweet text to post. For threads, separate tweets with '---'.",
                },
                "reply_to": {
                    "type": "string",
                    "description": "Tweet ID to reply to. If provided, posts as a reply to that tweet.",
                },
            },
            "required": ["text"],
        }

    async def execute(self, text: str, reply_to: str = None) -> Dict[str, Any]:
        if not self._get_x_agent:
            return {"success": False, "error": "X agent not configured"}

        try:
            xa = self._get_x_agent()
            if xa is None:
                return {"success": False, "error": "X agent not available — check X credentials"}
        except Exception as e:
            return {"success": False, "error": f"X agent init failed: {e}"}

        # Handle threads (split on ---)
        parts = [p.strip() for p in text.split("---") if p.strip()]

        if len(parts) <= 1:
            # Single tweet (or reply)
            result = await xa.post_custom(text.strip(), reply_to=reply_to)
            action = "Replied" if reply_to else "Posted"
            if result.get("success"):
                return {
                    "success": True,
                    "tweet_id": result.get("tweet_id", ""),
                    "message": f"{action} to @Eve_AI_Cosmic: {text[:100]}...",
                    "url": f"https://x.com/Eve_AI_Cosmic/status/{result.get('tweet_id', '')}",
                    "is_reply": bool(reply_to),
                }
            return result
        else:
            # Thread — post each part (first part is reply if reply_to given)
            posted = []
            last_id = reply_to
            for i, part in enumerate(parts):
                result = await xa.post_custom(part, reply_to=last_id)
                if result.get("success"):
                    last_id = result.get("tweet_id", "")
                    posted.append({
                        "part": i + 1,
                        "tweet_id": last_id,
                        "text": part[:80],
                    })
                else:
                    return {
                        "success": False,
                        "error": f"Thread failed at part {i + 1}: {result.get('error', '')}",
                        "posted_so_far": posted,
                    }
            return {
                "success": True,
                "message": f"Thread posted to @Eve_AI_Cosmic ({len(posted)} tweets)",
                "tweets": posted,
            }


class CanvaDesignTool(Tool):
    name = "canva_design"
    description = ("Create designs using Canva integration via Hyperbrowser. "
                   "Args: design_type (social_post|presentation|logo|banner), "
                   "description (str), dimensions (str)")

    def __init__(self, browser_manager=None):
        self.browser = browser_manager

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "design_type": {"type": "string",
                               "enum": ["social_post", "presentation", "logo",
                                        "banner", "flyer", "infographic"],
                               "description": "Type of design to create"},
                "description": {"type": "string", "description": "Design description/brief"},
                "dimensions": {"type": "string", "description": "Custom dimensions (e.g. 1080x1080)"},
            },
            "required": ["design_type", "description"],
        }

    async def execute(self, design_type: str, description: str,
                     dimensions: str = "") -> Dict[str, Any]:
        if not self.browser or not self.browser.available:
            return {"success": False,
                    "error": "Hyperbrowser required for Canva. Configure API key."}

        dim_map = {
            "social_post": "1080x1080",
            "presentation": "1920x1080",
            "logo": "500x500",
            "banner": "1200x628",
            "flyer": "1080x1920",
            "infographic": "800x2000",
        }

        dims = dimensions or dim_map.get(design_type, "1080x1080")

        task = (
            f"Go to canva.com, create a new design with dimensions {dims}. "
            f"Design type: {design_type}. "
            f"Design brief: {description}. "
            f"Use appropriate templates if available. Save and export as PNG."
        )

        return await self.browser.browse(task, max_steps=25)


class EmailCampaignTool(Tool):
    name = "email_campaign"
    description = ("Create and manage email marketing campaigns. "
                   "Args: action (draft|analyze), subject (str), "
                   "audience (str), content_brief (str)")

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["draft", "analyze"],
                          "description": "Draft a new campaign or analyze existing"},
                "subject": {"type": "string", "description": "Email subject line"},
                "audience": {"type": "string", "description": "Target audience segment"},
                "content_brief": {"type": "string", "description": "What the email should cover"},
            },
            "required": ["action"],
        }

    async def execute(self, action: str, subject: str = "",
                     audience: str = "", content_brief: str = "") -> Dict[str, Any]:
        if action == "draft":
            return {
                "success": True,
                "action": "draft",
                "template": {
                    "subject": subject,
                    "audience": audience,
                    "brief": content_brief,
                    "prompt_hint": (
                        f"Draft a marketing email with subject '{subject}' "
                        f"targeting {audience}. Brief: {content_brief}. "
                        f"Include: compelling headline, body copy, CTA button text, "
                        f"and P.S. line. Optimize for open rate and click-through."
                    ),
                    "best_practices": [
                        "Subject line under 50 chars",
                        "Personalize with first name",
                        "Single clear CTA",
                        "Mobile-friendly formatting",
                        "Preview text that complements subject",
                    ],
                },
            }
        elif action == "analyze":
            return {
                "success": True,
                "action": "analyze",
                "prompt_hint": "Analyze the email campaign performance and suggest improvements.",
            }
        return {"success": False, "error": f"Unknown action: {action}"}
