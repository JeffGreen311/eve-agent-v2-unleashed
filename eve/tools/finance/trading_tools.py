"""
Trading Tools
==============
Stock and crypto trading execution via broker APIs and Hyperbrowser.
Supports Alpaca (stocks), and exchange APIs (crypto).

IMPORTANT: All trades require explicit user confirmation.
Eve NEVER executes trades without approval.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import Tool

logger = logging.getLogger(__name__)


class PortfolioTracker:
    """Tracks portfolio positions and trade history."""

    def __init__(self, data_dir: str = "./eve_data/portfolio"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.positions: Dict[str, Dict] = {}
        self.trade_history: List[Dict] = []
        self._load()

    def add_position(self, symbol: str, quantity: float, avg_price: float,
                    asset_type: str = "stock"):
        """Add or update a portfolio position."""
        if symbol in self.positions:
            existing = self.positions[symbol]
            total_qty = existing["quantity"] + quantity
            if total_qty > 0:
                existing["avg_price"] = (
                    (existing["avg_price"] * existing["quantity"] + avg_price * quantity)
                    / total_qty
                )
            existing["quantity"] = total_qty
        else:
            self.positions[symbol] = {
                "symbol": symbol, "quantity": quantity,
                "avg_price": avg_price, "asset_type": asset_type,
                "opened_at": time.time(),
            }

        if self.positions.get(symbol, {}).get("quantity", 0) <= 0:
            self.positions.pop(symbol, None)

        self._save()

    def record_trade(self, symbol: str, side: str, quantity: float,
                    price: float, asset_type: str = "stock",
                    exchange: str = "", notes: str = ""):
        """Record a trade in history."""
        trade = {
            "symbol": symbol, "side": side, "quantity": quantity,
            "price": price, "asset_type": asset_type,
            "exchange": exchange, "notes": notes,
            "timestamp": time.time(), "total_value": quantity * price,
        }
        self.trade_history.append(trade)
        self._save()
        return trade

    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary."""
        stocks = {k: v for k, v in self.positions.items() if v["asset_type"] == "stock"}
        crypto = {k: v for k, v in self.positions.items() if v["asset_type"] == "crypto"}

        return {
            "total_positions": len(self.positions),
            "stock_positions": len(stocks),
            "crypto_positions": len(crypto),
            "positions": self.positions,
            "recent_trades": self.trade_history[-10:],
            "total_trades": len(self.trade_history),
        }

    def _save(self):
        data = {"positions": self.positions, "history": self.trade_history[-500:]}
        (self.data_dir / "portfolio.json").write_text(json.dumps(data, indent=2))

    def _load(self):
        path = self.data_dir / "portfolio.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.positions = data.get("positions", {})
                self.trade_history = data.get("history", [])
            except (json.JSONDecodeError, KeyError):
                pass


class PortfolioSummaryTool(Tool):
    name = "portfolio_summary"
    description = "View current portfolio positions, P&L, and recent trade history."

    def __init__(self, tracker: PortfolioTracker):
        self.tracker = tracker

    def get_parameters(self) -> Dict:
        return {"type": "object", "properties": {}}

    async def execute(self) -> Dict[str, Any]:
        return {"success": True, **self.tracker.get_portfolio_summary()}


class StockTradeTool(Tool):
    name = "stock_trade"
    description = ("Execute a stock trade (requires confirmation). "
                   "Args: symbol (str), side (buy|sell), quantity (int), "
                   "order_type (market|limit), limit_price (float, for limit orders)")

    def __init__(self, tracker: PortfolioTracker, broker_api_key: str = "",
                 browser_manager=None):
        self.tracker = tracker
        self.broker_api_key = broker_api_key
        self.browser = browser_manager

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker"},
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "quantity": {"type": "integer", "description": "Number of shares"},
                "order_type": {"type": "string", "enum": ["market", "limit"],
                              "default": "market"},
                "limit_price": {"type": "number", "description": "Price for limit orders"},
                "confirmed": {"type": "boolean", "description": "User confirmed trade",
                             "default": False},
            },
            "required": ["symbol", "side", "quantity"],
        }

    async def execute(self, symbol: str, side: str, quantity: int,
                     order_type: str = "market", limit_price: float = 0,
                     confirmed: bool = False) -> Dict[str, Any]:
        if not confirmed:
            return {
                "success": False,
                "requires_confirmation": True,
                "order": {
                    "symbol": symbol.upper(), "side": side,
                    "quantity": quantity, "order_type": order_type,
                    "limit_price": limit_price if order_type == "limit" else None,
                },
                "message": (
                    f"Trade requires confirmation: {side.upper()} {quantity} shares of "
                    f"{symbol.upper()} ({order_type})"
                    f"{f' at ${limit_price}' if order_type == 'limit' else ''}. "
                    f"Say 'confirm' to execute."
                ),
            }

        # If broker API available, use it; otherwise use Hyperbrowser
        if self.broker_api_key:
            return await self._execute_via_api(symbol, side, quantity, order_type, limit_price)
        elif self.browser and self.browser.available:
            return await self._execute_via_browser(symbol, side, quantity, order_type, limit_price)
        else:
            # Paper trade — record locally
            from .market_tools import MarketDataClient
            client = MarketDataClient()
            quote = await client.get_stock_quote(symbol)
            price = quote.get("price", limit_price or 0)

            trade = self.tracker.record_trade(
                symbol=symbol.upper(), side=side, quantity=quantity,
                price=price, asset_type="stock", notes="paper_trade",
            )

            if side == "buy":
                self.tracker.add_position(symbol.upper(), quantity, price, "stock")
            else:
                self.tracker.add_position(symbol.upper(), -quantity, price, "stock")

            return {
                "success": True, "mode": "paper_trade",
                "trade": trade,
                "message": f"Paper trade: {side.upper()} {quantity} {symbol.upper()} @ ${price}",
            }

    async def _execute_via_api(self, symbol, side, qty, order_type, limit_price) -> Dict:
        """Execute via Alpaca or similar broker API."""
        try:
            async with __import__("aiohttp").ClientSession() as session:
                headers = {
                    "APCA-API-KEY-ID": self.broker_api_key.split(":")[0],
                    "APCA-API-SECRET-KEY": self.broker_api_key.split(":")[-1],
                }
                data = {
                    "symbol": symbol.upper(), "qty": qty, "side": side,
                    "type": order_type, "time_in_force": "day",
                }
                if order_type == "limit":
                    data["limit_price"] = limit_price

                async with session.post(
                    "https://paper-api.alpaca.markets/v2/orders",
                    headers=headers, json=data,
                ) as resp:
                    result = await resp.json()
                    if resp.status in (200, 201):
                        price = float(result.get("filled_avg_price", limit_price or 0))
                        self.tracker.record_trade(
                            symbol.upper(), side, qty, price, "stock", "alpaca",
                        )
                        return {"success": True, "mode": "alpaca", "order": result}
                    else:
                        return {"success": False, "error": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_via_browser(self, symbol, side, qty, order_type, limit_price) -> Dict:
        """Execute via Hyperbrowser on a trading platform."""
        task = (
            f"Go to the trading platform and {side} {qty} shares of {symbol.upper()}. "
            f"Order type: {order_type}."
        )
        if order_type == "limit":
            task += f" Limit price: ${limit_price}."
        return await self.browser.browse(task, max_steps=20)


class CryptoTradeTool(Tool):
    name = "crypto_trade"
    description = ("Execute a crypto trade (requires confirmation). "
                   "Args: coin (str), side (buy|sell), amount (float), "
                   "quote_currency (str, default USDT)")

    def __init__(self, tracker: PortfolioTracker, browser_manager=None):
        self.tracker = tracker
        self.browser = browser_manager

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "coin": {"type": "string", "description": "Crypto symbol (BTC, ETH, SOL)"},
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "amount": {"type": "number", "description": "Amount in quote currency (USD)"},
                "confirmed": {"type": "boolean", "default": False},
            },
            "required": ["coin", "side", "amount"],
        }

    async def execute(self, coin: str, side: str, amount: float,
                     confirmed: bool = False) -> Dict[str, Any]:
        if not confirmed:
            return {
                "success": False,
                "requires_confirmation": True,
                "order": {"coin": coin.upper(), "side": side, "amount": amount},
                "message": (
                    f"Crypto trade requires confirmation: {side.upper()} "
                    f"${amount} of {coin.upper()}. Say 'confirm' to execute."
                ),
            }

        # Paper trade
        from .market_tools import MarketDataClient
        client = MarketDataClient()
        coin_id_map = {
            "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
            "ADA": "cardano", "DOGE": "dogecoin", "XRP": "ripple",
            "AVAX": "avalanche-2", "DOT": "polkadot", "MATIC": "matic-network",
        }
        coin_id = coin_id_map.get(coin.upper(), coin.lower())
        price_data = await client.get_crypto_price(coin_id)
        price = price_data.get("price", 0)

        if not price:
            return {"success": False, "error": f"Could not get price for {coin}"}

        quantity = amount / price

        trade = self.tracker.record_trade(
            symbol=coin.upper(), side=side, quantity=quantity,
            price=price, asset_type="crypto", notes="paper_trade",
        )

        if side == "buy":
            self.tracker.add_position(coin.upper(), quantity, price, "crypto")
        else:
            self.tracker.add_position(coin.upper(), -quantity, price, "crypto")

        return {
            "success": True, "mode": "paper_trade", "trade": trade,
            "message": (
                f"Paper trade: {side.upper()} {quantity:.6f} {coin.upper()} "
                f"@ ${price:,.2f} (${amount:,.2f} total)"
            ),
        }
