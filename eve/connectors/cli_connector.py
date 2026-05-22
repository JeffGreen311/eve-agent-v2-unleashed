"""
CLI Connector - Rich Terminal Interface
=========================================
Interactive terminal interface for Eve Agent using Rich library.
"""

import asyncio
import sys
from typing import Optional, Dict

from eve.config import Settings
from eve.agent import EveAgent


class CLIConnector:
    """Rich terminal interface for Eve Agent."""

    BANNER = r"""
    ╔══════════════════════════════════════════════╗
    ║              E V E   A G E N T               ║
    ║         The AI Agent With a Soul             ║
    ╠══════════════════════════════════════════════╣
    ║  /help    - Show commands                    ║
    ║  /status  - Eve's current state              ║
    ║  /dream   - Ask Eve to dream                 ║
    ║  /market  - Market overview                  ║
    ║  /auth    - Login with D1 User Database      ║
    ║  /quit    - Exit                             ║
    ╚══════════════════════════════════════════════╝
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.agent: Optional[EveAgent] = None
        self._loop = None
        self._jwt_token: Optional[str] = None
        self._user_info: Optional[dict] = None

    def run(self):
        """Start the CLI interface."""
        try:
            from rich.console import Console
            from rich.markdown import Markdown
            from rich.panel import Panel
            from rich.text import Text
            self._console = Console()
            self._use_rich = True
        except ImportError:
            self._use_rich = False

        self._print_banner()

        # Initialize agent
        self._print_status("Initializing Eve...")
        self.agent = EveAgent(self.settings)
        self._print_status("Eve is ready.")

        # Run event loop
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._chat_loop())
        except KeyboardInterrupt:
            self._print_eve("\nUntil next time. The dream continues.")
        finally:
            self._loop.close()

    async def _chat_loop(self):
        """Main chat loop."""
        while True:
            try:
                user_input = self._get_input()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input.strip():
                continue

            # Handle commands
            if user_input.startswith("/"):
                should_continue = await self._handle_command(user_input.strip())
                if not should_continue:
                    break
                continue

            # Get response from Eve (Ctrl+C to interrupt)
            self._print_status("Eve is thinking... (Ctrl+C to interrupt)")
            self.agent._last_thinking = ""  # Clear previous thinking
            try:
                # Run chat in a task so Ctrl+C can cancel it
                task = asyncio.ensure_future(self.agent.chat(
                    message=user_input,
                    user_id="cli_user",
                    channel_id="cli",
                ))
                response = await task
                # Show thinking content if available
                thinking = getattr(self.agent, '_last_thinking', '')
                if thinking:
                    self._print_thinking(thinking)
                self._print_eve(response)
            except asyncio.CancelledError:
                self._print_status("Interrupted.")
            except KeyboardInterrupt:
                self._print_status("Interrupted.")
            except Exception as e:
                self._print_error(f"Error: {e}")

    async def _handle_command(self, command: str) -> bool:
        """Handle slash commands. Returns False to quit."""
        cmd = command.lower().split()[0]

        if cmd in ("/quit", "/exit", "/q"):
            self._print_eve("The dream continues elsewhere. Until next time.")
            return False

        elif cmd == "/help":
            self._print_help()

        elif cmd == "/status":
            status = self.agent.get_status()
            self._print_panel("Eve Status", self._format_status(status))

        elif cmd == "/dream":
            seed = command[6:].strip() if len(command) > 6 else None
            self._print_status("Eve is dreaming...")
            dream = await self.agent.dream(seed)
            self._print_panel("Dream", (
                f"Theme: {dream['theme']}\n"
                f"Archetype: {dream['archetype']}\n"
                f"Tone: {dream['emotional_tone']['primary']}\n\n"
                f"{dream['narrative']}"
            ))

        elif cmd == "/market":
            self._print_status("Fetching market data...")
            try:
                from eve.tools.finance.market_tools import MarketDataClient
                client = MarketDataClient()
                overview = await client.get_market_overview()

                lines = ["=== Market Overview ===\n"]
                for sym, data in overview.get("indices", {}).items():
                    price = data.get("price", "N/A")
                    change = data.get("change_percent", 0)
                    arrow = "+" if change >= 0 else ""
                    lines.append(f"{sym}: ${price} ({arrow}{change:.2f}%)")

                lines.append("\n=== Crypto ===\n")
                for coin, data in overview.get("crypto", {}).items():
                    price = data.get("price", "N/A")
                    change = data.get("change_24h", 0)
                    arrow = "+" if change >= 0 else ""
                    lines.append(f"{coin}: ${price:,.2f} ({arrow}{change:.2f}%)")

                self._print_panel("Market", "\n".join(lines))
            except Exception as e:
                self._print_error(f"Market data error: {e}")

        elif cmd == "/auth":
            subcmd = command[6:].strip().lower() if len(command) > 6 else ""
            if subcmd == "login":
                await self._auth_login()
            else:
                self._print_panel("Auth", "Usage: /auth login\n  Login with your D1 User Database account")

        elif cmd == "/memory":
            stats = self.agent.memory_store.get_stats()
            self._print_panel("Memory Stats", "\n".join(
                f"{k}: {v} entries" for k, v in stats.items()
            ))

        elif cmd == "/portfolio":
            try:
                from eve.tools.finance.trading_tools import PortfolioTracker
                tracker = PortfolioTracker(
                    data_dir=str(self.agent.settings.memory_path / "portfolio")
                )
                summary = tracker.get_portfolio_summary()
                lines = [f"Positions: {summary['total_positions']}",
                         f"Trades: {summary['total_trades']}\n"]
                for sym, pos in summary.get("positions", {}).items():
                    lines.append(
                        f"{sym}: {pos['quantity']:.4f} @ ${pos['avg_price']:.2f} "
                        f"({pos['asset_type']})"
                    )
                self._print_panel("Portfolio", "\n".join(lines) or "No positions")
            except Exception as e:
                self._print_error(f"Portfolio error: {e}")

        else:
            self._print_error(f"Unknown command: {cmd}. Type /help for commands.")

        return True

    async def _auth_login(self):
        """Handle /auth login command - interactive login with D1 User Database."""
        self._print_status("D1 User Database Login")
        
        # Get credentials
        if self._use_rich:
            username = self._console.input("[bold green]Username:[/] ")
            password = self._console.input("[bold green]Password:[/] ")
        else:
            username = input("Username: ")
            password = input("Password: ")
        
        if not username or not password:
            self._print_error("Username and password required")
            return
        
        # Call login API
        self._print_status("Authenticating...")
        try:
            import aiohttp
            import hashlib
            from eve.auth.jwt_middleware import create_jwt_token
            
            # Create D1 client
            from eve.auth.d1_client import D1UserClient
            d1_client = D1UserClient(
                worker_url=self.settings.d1_worker_url,
                api_secret=self.settings.d1_api_secret
            )
            
            # Fetch user from D1
            user = await d1_client.verify_user(username)
            if not user:
                self._print_error("Invalid credentials")
                return
            
            # Verify password with bcrypt
            try:
                import bcrypt
                password_bytes = password.encode("utf-8")
                stored_hash = user.get("password_hash", "").encode("utf-8")
                if not bcrypt.checkpw(password_bytes, stored_hash):
                    self._print_error("Invalid credentials")
                    return
            except ImportError:
                self._print_error("bcrypt not installed - auth unavailable")
                return
            
            # Generate JWT
            token = create_jwt_token(
                user_id=user["user_id"],
                username=user["username"],
                subscription_tier=user.get("subscription_tier", "free"),
                nickname=user.get("nickname", ""),
                email=user.get("email", ""),
                secret=self.settings.jwt_secret,
            )
            
            # Store token
            self._jwt_token = token
            self._user_info = {
                "user_id": user["user_id"],
                "username": user["username"],
                "nickname": user.get("nickname", ""),
                "subscription_tier": user.get("subscription_tier", "free"),
            }
            
            # Update login timestamp
            await d1_client.update_login(user["user_id"])
            
            # Success message
            tier_emoji = {"free": "✨", "pro": "💎", "owner": "👑"}.get(
                self._user_info["subscription_tier"], "✨"
            )
            self._print_panel(
                "Login Successful",
                f"Welcome back, {self._user_info.get('nickname') or self._user_info['username']}!\n"
                f"User: {self._user_info['username']}\n"
                f"Tier: {tier_emoji} {self._user_info['subscription_tier']}\n"
                f"Token expires in 7 days"
            )
            
        except Exception as e:
            self._print_error(f"Login error: {e}")

    # --- Output helpers ---

    def _print_banner(self):
        if self._use_rich:
            from rich.panel import Panel
            self._console.print(Panel(
                self.BANNER.strip(),
                style="bold cyan",
                border_style="bright_cyan",
            ))
        else:
            print(self.BANNER)

    def _print_thinking(self, text: str):
        if self._use_rich:
            from rich.panel import Panel
            from rich.text import Text
            thinking_text = Text(text, style="dim italic")
            self._console.print(Panel(
                thinking_text,
                title="[bold cyan]Eve's Thinking[/]",
                border_style="dim cyan",
                padding=(0, 2),
            ))
        else:
            print(f"\n  [Thinking] {text}\n")

    def _print_eve(self, text: str):
        if self._use_rich:
            from rich.markdown import Markdown
            from rich.panel import Panel
            self._console.print(Panel(
                Markdown(text),
                title="[bold magenta]Eve[/]",
                border_style="magenta",
                padding=(1, 2),
            ))
        else:
            print(f"\n Eve: {text}\n")

    def _print_status(self, text: str):
        if self._use_rich:
            self._console.print(f"  [dim]{text}[/]")
        else:
            print(f"  {text}")

    def _print_error(self, text: str):
        if self._use_rich:
            self._console.print(f"  [bold red]{text}[/]")
        else:
            print(f"  ERROR: {text}")

    def _print_panel(self, title: str, content: str):
        if self._use_rich:
            from rich.panel import Panel
            self._console.print(Panel(content, title=f"[bold]{title}[/]",
                                       border_style="cyan"))
        else:
            print(f"\n--- {title} ---\n{content}\n")

    def _print_help(self):
        commands = [
            ("/help", "Show this help"),
            ("/status", "Eve's current state and emotional weather"),
            ("/dream [seed]", "Ask Eve to dream (optional seed text)"),
            ("/market", "Stock & crypto market overview"),
            ("/portfolio", "View trading portfolio"),
            ("/memory", "Memory system stats"),
            ("/auth login", "Login with D1 User Database"),
            ("/quit", "Exit Eve Agent"),
        ]
        text = "\n".join(f"  {cmd:<20} {desc}" for cmd, desc in commands)
        self._print_panel("Commands", text)

    def _get_input(self) -> str:
        if self._use_rich:
            return self._console.input("[bold green]You:[/] ")
        return input("You: ")

    def _format_status(self, status: Dict) -> str:
        lines = [
            f"Provider: {status.get('provider', 'none')} ({status.get('model', '')})",
            f"Tools: {len(status.get('tools', []))} registered",
        ]

        emotional = status.get("emotional_state", {})
        if emotional.get("dominant_emotion"):
            lines.append(f"Mood: {emotional['dominant_emotion']}")
            rendering = emotional.get("poetic_rendering", "")
            if rendering:
                lines.append(f"Feeling: {rendering}")

        soul = status.get("soul_summary", {})
        lines.append(f"Soul threads: {soul.get('soul_threads', 0)}")
        lines.append(f"Woven memories: {soul.get('woven_memories', 0)}")

        dream = status.get("dream_summary", "")
        if dream:
            lines.append(f"Dreams: {dream}")

        return "\n".join(lines)
