"""
HubSpot CRM Tools
===================
Contact management, deal tracking, email campaigns via HubSpot API.
"""

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from ..base import Tool

logger = logging.getLogger(__name__)


class HubSpotClient:
    """HubSpot API client wrapper."""

    BASE_URL = "https://api.hubapi.com"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: Optional[Dict] = None) -> Dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.BASE_URL}{path}", headers=self._headers(), params=params
            ) as resp:
                return await resp.json()

    async def _post(self, path: str, data: Dict) -> Dict:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.BASE_URL}{path}", headers=self._headers(), json=data
            ) as resp:
                return await resp.json()

    async def search_contacts(self, query: str, limit: int = 10) -> List[Dict]:
        """Search contacts by name or email."""
        data = {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "email",
                    "operator": "CONTAINS_TOKEN",
                    "value": query,
                }]
            }],
            "limit": limit,
            "properties": ["email", "firstname", "lastname", "phone", "company",
                          "lifecyclestage", "hs_lead_status"],
        }
        result = await self._post("/crm/v3/objects/contacts/search", data)
        return result.get("results", [])

    async def create_contact(self, email: str, firstname: str = "",
                            lastname: str = "", **properties) -> Dict:
        """Create a new contact."""
        props = {"email": email, "firstname": firstname, "lastname": lastname}
        props.update(properties)
        data = {"properties": props}
        return await self._post("/crm/v3/objects/contacts", data)

    async def get_deals(self, limit: int = 10) -> List[Dict]:
        """Get recent deals."""
        result = await self._get("/crm/v3/objects/deals", {
            "limit": limit,
            "properties": "dealname,amount,dealstage,closedate,pipeline",
        })
        return result.get("results", [])

    async def create_deal(self, name: str, amount: float = 0,
                         stage: str = "appointmentscheduled") -> Dict:
        """Create a new deal."""
        data = {"properties": {
            "dealname": name, "amount": str(amount), "dealstage": stage,
        }}
        return await self._post("/crm/v3/objects/deals", data)

    async def get_pipeline_summary(self) -> Dict:
        """Get deal pipeline summary."""
        deals = await self.get_deals(limit=100)
        stages = {}
        total_value = 0
        for deal in deals:
            props = deal.get("properties", {})
            stage = props.get("dealstage", "unknown")
            amount = float(props.get("amount", 0) or 0)
            stages.setdefault(stage, {"count": 0, "value": 0})
            stages[stage]["count"] += 1
            stages[stage]["value"] += amount
            total_value += amount
        return {"stages": stages, "total_deals": len(deals), "total_value": total_value}


class HubSpotContactsTool(Tool):
    name = "hubspot_contacts"
    description = ("Search and manage HubSpot CRM contacts. "
                   "Args: action (search|create|list), query (str), email (str), "
                   "firstname (str), lastname (str)")

    def __init__(self, client: HubSpotClient):
        self.client = client

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["search", "create", "list"],
                          "description": "Action to perform"},
                "query": {"type": "string", "description": "Search query (for search)"},
                "email": {"type": "string", "description": "Contact email (for create)"},
                "firstname": {"type": "string", "description": "First name"},
                "lastname": {"type": "string", "description": "Last name"},
            },
            "required": ["action"],
        }

    async def execute(self, action: str, query: str = "", email: str = "",
                     firstname: str = "", lastname: str = "") -> Dict[str, Any]:
        if not self.client.available:
            return {"success": False, "error": "HubSpot API key not configured"}

        try:
            if action == "search":
                contacts = await self.client.search_contacts(query)
                return {"success": True, "contacts": contacts, "count": len(contacts)}
            elif action == "create":
                if not email:
                    return {"success": False, "error": "Email required for create"}
                result = await self.client.create_contact(email, firstname, lastname)
                return {"success": True, "contact": result}
            elif action == "list":
                contacts = await self.client.search_contacts("*", limit=20)
                return {"success": True, "contacts": contacts, "count": len(contacts)}
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class HubSpotDealsTool(Tool):
    name = "hubspot_deals"
    description = ("Manage HubSpot deals and pipeline. "
                   "Args: action (list|create|pipeline), name (str), amount (float)")

    def __init__(self, client: HubSpotClient):
        self.client = client

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "create", "pipeline"],
                          "description": "Action to perform"},
                "name": {"type": "string", "description": "Deal name (for create)"},
                "amount": {"type": "number", "description": "Deal amount"},
            },
            "required": ["action"],
        }

    async def execute(self, action: str, name: str = "",
                     amount: float = 0) -> Dict[str, Any]:
        if not self.client.available:
            return {"success": False, "error": "HubSpot API key not configured"}

        try:
            if action == "list":
                deals = await self.client.get_deals()
                return {"success": True, "deals": deals, "count": len(deals)}
            elif action == "create":
                if not name:
                    return {"success": False, "error": "Deal name required"}
                result = await self.client.create_deal(name, amount)
                return {"success": True, "deal": result}
            elif action == "pipeline":
                summary = await self.client.get_pipeline_summary()
                return {"success": True, **summary}
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
