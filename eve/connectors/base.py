"""
Connector Base Class
=====================
Base class for all messaging platform connectors.
"""

from abc import ABC, abstractmethod
from typing import Optional

from eve.config import Settings
from eve.agent import EveAgent


class Connector(ABC):
    """Base class for messaging platform connectors."""

    def __init__(self, settings: Settings, agent: Optional[EveAgent] = None):
        self.settings = settings
        self.agent = agent or EveAgent(settings)

    @abstractmethod
    def run(self):
        """Start the connector (blocking)."""
        ...

    @abstractmethod
    async def send_message(self, channel_id: str, content: str):
        """Send a message to a channel."""
        ...
