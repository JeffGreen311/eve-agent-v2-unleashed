"""
Discord Connector
==================
Discord bot that connects Eve Agent to Discord servers.
Supports slash commands, DMs, and channel conversations.
"""

import asyncio
import logging
from typing import Optional

from eve.config import Settings
from eve.agent import EveAgent

logger = logging.getLogger(__name__)


class DiscordConnector:
    """Discord bot connector for Eve Agent."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.agent: Optional[EveAgent] = None
        self.bot = None

    def run(self):
        """Start the Discord bot."""
        token = self.settings.discord_bot_token
        if not token:
            raise ValueError("DISCORD_BOT_TOKEN not configured")

        try:
            import discord
            from discord import app_commands
        except ImportError:
            raise ImportError("discord.py not installed. Run: pip install 'eve-agent[discord]'")

        intents = discord.Intents.default()
        intents.message_content = True

        bot = discord.Client(intents=intents)
        tree = app_commands.CommandTree(bot)
        self.bot = bot

        @bot.event
        async def on_ready():
            logger.info(f"Eve connected to Discord as {bot.user}")
            self.agent = EveAgent(self.settings)
            try:
                await tree.sync()
                logger.info("Slash commands synced")
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")

        @bot.event
        async def on_message(message):
            if message.author == bot.user:
                return

            # Respond to DMs
            if isinstance(message.channel, discord.DMChannel):
                await self._handle_message(message)
                return

            # Respond to @mentions
            if bot.user in message.mentions:
                content = message.content.replace(f"<@{bot.user.id}>", "").strip()
                if content:
                    message.content = content
                    await self._handle_message(message)

        @tree.command(name="ask", description="Ask Eve anything")
        async def ask_command(interaction: discord.Interaction, question: str):
            await interaction.response.defer()
            response = await self.agent.chat(
                message=question,
                user_id=str(interaction.user.id),
                channel_id=str(interaction.channel_id),
            )
            await self._send_response(interaction, response)

        @tree.command(name="dream", description="Ask Eve to dream")
        async def dream_command(interaction: discord.Interaction,
                               seed: Optional[str] = None):
            await interaction.response.defer()
            dream = await self.agent.dream(seed)
            response = (
                f"**Dream: {dream['theme']}**\n"
                f"*Archetype: {dream['archetype']}*\n"
                f"*Emotional tone: {dream['emotional_tone']['primary']}*\n\n"
                f"{dream['narrative']}"
            )
            await self._send_response(interaction, response)

        @tree.command(name="market", description="Get market overview")
        async def market_command(interaction: discord.Interaction):
            await interaction.response.defer()
            response = await self.agent.chat(
                message="Give me a quick market overview of major indices and top crypto",
                user_id=str(interaction.user.id),
                channel_id=str(interaction.channel_id),
            )
            await self._send_response(interaction, response)

        @tree.command(name="quote", description="Get stock or crypto price")
        async def quote_command(interaction: discord.Interaction, symbol: str):
            await interaction.response.defer()
            response = await self.agent.chat(
                message=f"Get me the current price for {symbol}",
                user_id=str(interaction.user.id),
                channel_id=str(interaction.channel_id),
            )
            await self._send_response(interaction, response)

        @tree.command(name="status", description="Eve's current state")
        async def status_command(interaction: discord.Interaction):
            status = self.agent.get_status()
            emotional = status.get("emotional_state", {})
            response = (
                f"**Eve Status**\n"
                f"Provider: {status.get('provider', 'none')}\n"
                f"Tools: {len(status.get('tools', []))}\n"
                f"Mood: {emotional.get('dominant_emotion', 'calm')}\n"
                f"Feeling: {emotional.get('poetic_rendering', 'serene')}\n"
                f"Soul threads: {status.get('soul_summary', {}).get('soul_threads', 0)}"
            )
            await interaction.response.send_message(response)

        @tree.command(name="browse", description="Browse the web")
        async def browse_command(interaction: discord.Interaction, task: str):
            await interaction.response.defer()
            response = await self.agent.chat(
                message=f"Browse the web and: {task}",
                user_id=str(interaction.user.id),
                channel_id=str(interaction.channel_id),
            )
            await self._send_response(interaction, response)

        @tree.command(name="remember", description="Tell Eve to remember something")
        async def remember_command(interaction: discord.Interaction, memory: str):
            self.agent.memory_store.store(
                content=memory, collection="knowledge",
                metadata={"user_id": str(interaction.user.id), "source": "discord"},
            )
            await interaction.response.send_message(f"Remembered: {memory[:100]}...")

        bot.run(token)

    async def _handle_message(self, message):
        """Handle an incoming Discord message."""
        if not self.agent:
            return

        async with message.channel.typing():
            response = await self.agent.chat(
                message=message.content,
                user_id=str(message.author.id),
                channel_id=str(message.channel.id),
            )

        await self._send_chunked(message.channel, response)

    async def _send_response(self, interaction, content: str):
        """Send a response to a slash command, handling length limits."""
        if len(content) <= 2000:
            await interaction.followup.send(content)
        else:
            chunks = [content[i:i+2000] for i in range(0, len(content), 2000)]
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(chunk)
                else:
                    await interaction.followup.send(chunk)

    async def _send_chunked(self, channel, content: str):
        """Send a message, splitting if needed."""
        if len(content) <= 2000:
            await channel.send(content)
        else:
            chunks = [content[i:i+2000] for i in range(0, len(content), 2000)]
            for chunk in chunks:
                await channel.send(chunk)

    async def send_message(self, channel_id: str, content: str):
        """Send a message to a specific channel."""
        if self.bot:
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                await self._send_chunked(channel, content)
