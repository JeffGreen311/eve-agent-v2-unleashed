"""
Live Market Data Feed Hub
=========================
Kraken WebSocket (crypto, US-friendly) + Finnhub WebSocket (US stocks).
Unified candle/price stream for the Eve portal.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Kraken uses different pair names than most exchanges
SYMBOL_TO_KRAKEN = {
    "BTCUSDT": "XBT/USD", "BTCUSD": "XBT/USD", "BTC": "XBT/USD",
    "ETHUSDT": "ETH/USD", "ETHUSD": "ETH/USD", "ETH": "ETH/USD",
    "SOLUSDT": "SOL/USD", "SOLUSD": "SOL/USD", "SOL": "SOL/USD",
    "XRPUSDT": "XRP/USD", "XRPUSD": "XRP/USD", "XRP": "XRP/USD",
    "DOGEUSDT": "DOGE/USD", "DOGEUSD": "DOGE/USD", "DOGE": "DOGE/USD",
    "ADAUSDT": "ADA/USD", "ADAUSD": "ADA/USD", "ADA": "ADA/USD",
    "AVAXUSDT": "AVAX/USD", "LINKUSDT": "LINK/USD", "DOTUSDT": "DOT/USD",
    "MATICUSDT": "MATIC/USD", "SHIBUSDT": "SHIB/USD",
}

# Reverse: prefer the USDT variant for consistency with frontend
KRAKEN_TO_SYMBOL = {}
for _k, _v in SYMBOL_TO_KRAKEN.items():
    if _v not in KRAKEN_TO_SYMBOL or _k.endswith("USDT"):
        KRAKEN_TO_SYMBOL[_v] = _k


# ── Kraken WebSocket Feed ─────────────────────────────────────────────────────

class KrakenFeed:
    """Connects to Kraken public WebSocket for crypto OHLC + trades."""

    WS_URL = "wss://ws.kraken.com/"

    def __init__(self, hub: "LiveFeedHub"):
        self._hub = hub
        self._pairs: Dict[str, str] = {}  # our_symbol → kraken_pair
        self._intervals: Dict[str, int] = {}  # our_symbol → kraken interval (minutes)
        self._ws = None
        self._task: Optional[asyncio.Task] = None
        self._running = True
        # 1-second candle aggregation from trades
        self._agg: Dict[str, dict] = {}
        self._agg_sec: Dict[str, int] = {}

    async def subscribe(self, symbol: str, interval: str = "1s"):
        sym = symbol.upper()
        kraken_pair = SYMBOL_TO_KRAKEN.get(sym)
        if not kraken_pair:
            # Try as-is with /USD suffix
            kraken_pair = f"{sym}/USD" if "/" not in sym else sym

        self._pairs[sym] = kraken_pair

        # Map interval to Kraken (1, 5, 15, 60 minutes) — for OHLC subscription
        iv_map = {"1s": 1, "1m": 1, "5m": 5, "15m": 15, "1h": 60}
        self._intervals[sym] = iv_map.get(interval, 1)

        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._stream())
        else:
            await self._send_subscriptions()

    async def unsubscribe(self, symbol: str):
        sym = symbol.upper()
        self._pairs.pop(sym, None)
        self._intervals.pop(sym, None)

    async def _send_subscriptions(self):
        if not self._ws or not self._pairs:
            return
        pairs = list(set(self._pairs.values()))

        # Subscribe to OHLC for candles
        try:
            await self._ws.send(json.dumps({
                "event": "subscribe",
                "pair": pairs,
                "subscription": {"name": "ohlc", "interval": 1},
            }))
        except Exception:
            pass

        # Subscribe to trades for real-time price ticks
        try:
            await self._ws.send(json.dumps({
                "event": "subscribe",
                "pair": pairs,
                "subscription": {"name": "trade"},
            }))
        except Exception:
            pass

    async def _stream(self):
        import websockets

        while self._running:
            try:
                async with websockets.connect(self.WS_URL, ping_interval=20, ping_timeout=10) as ws:
                    self._ws = ws
                    logger.info(f"Kraken WS connected, subscribing to {list(self._pairs.values())}")
                    await self._send_subscriptions()

                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            msg = json.loads(raw)
                            if isinstance(msg, list) and len(msg) >= 4:
                                channel_name = msg[-2]  # "ohlc-1", "trade", etc.
                                kraken_pair = msg[-1]    # "XBT/USD"
                                data = msg[1]

                                # Resolve to our symbol
                                our_sym = KRAKEN_TO_SYMBOL.get(kraken_pair, kraken_pair.replace("/", ""))

                                if "ohlc" in str(channel_name):
                                    self._handle_ohlc(our_sym, data, kraken_pair)
                                elif channel_name == "trade":
                                    self._handle_trades(our_sym, data, kraken_pair)
                        except Exception as e:
                            logger.debug(f"Kraken parse: {e}")
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning(f"Kraken WS error: {e}, reconnecting in 3s")
                self._ws = None
                await asyncio.sleep(3)

    def _handle_ohlc(self, symbol: str, data, pair: str):
        """Handle OHLC candle update from Kraken.
        data = [time, etime, open, high, low, close, vwap, volume, count]
        """
        if not isinstance(data, list) or len(data) < 8:
            return
        candle = {
            "type": "candle",
            "symbol": symbol,
            "source": "kraken",
            "time": float(data[0]),
            "open": float(data[2]),
            "high": float(data[3]),
            "low": float(data[4]),
            "close": float(data[5]),
            "volume": float(data[7]),
            "closed": False,  # Kraken OHLC updates are live (not closed until next interval)
        }
        self._hub._handle_candle(candle)
        self._hub._handle_price(symbol, float(data[5]), "kraken")

    def _handle_trades(self, symbol: str, data, pair: str):
        """Handle trade messages from Kraken.
        data = [[price, volume, time, side, orderType, misc], ...]
        """
        if not isinstance(data, list):
            return

        trades = data if isinstance(data[0], list) else [data]
        for trade in trades:
            if len(trade) < 4:
                continue
            price = float(trade[0])
            volume = float(trade[1])

            self._hub._handle_price(symbol, price, "kraken")
            self._agg_trade(symbol, price, volume)

    def _agg_trade(self, sym: str, price: float, volume: float):
        """Aggregate trades into 1-second candles for smooth chart updates."""
        sec = int(time.time())
        if self._agg_sec.get(sym) != sec:
            # Flush previous second
            prev = self._agg.pop(sym, None)
            if prev:
                prev["closed"] = True
                self._hub._handle_candle(prev)
            self._agg_sec[sym] = sec
            self._agg[sym] = {
                "type": "candle", "symbol": sym, "source": "kraken",
                "time": float(sec), "open": price, "high": price, "low": price,
                "close": price, "volume": volume, "closed": False,
            }
        else:
            c = self._agg[sym]
            c["high"] = max(c["high"], price)
            c["low"] = min(c["low"], price)
            c["close"] = price
            c["volume"] += volume

    async def shutdown(self):
        self._running = False
        if self._task:
            self._task.cancel()
        self._ws = None


# ── Finnhub WebSocket Feed ───────────────────────────────────────────────────

class FinnhubFeed:
    """Connects to Finnhub WebSocket for real-time US stock trades.
    Free tier — just needs an API key (email signup, no brokerage / tax ID).
    Trades are aggregated into 1-second candles for charting.
    """

    WS_URL = "wss://ws.finnhub.io?token={token}"

    def __init__(self, hub: "LiveFeedHub", api_key: str = ""):
        self._hub = hub
        self._api_key = api_key
        self._symbols: set = set()
        self._ws = None
        self._task: Optional[asyncio.Task] = None
        self._running = True
        self._agg: Dict[str, dict] = {}
        self._agg_sec: Dict[str, int] = {}

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    async def subscribe(self, symbol: str, interval: str = "1s"):
        if not self.available:
            logger.warning("Finnhub API key not set — stock feed unavailable")
            return
        sym = symbol.upper()
        self._symbols.add(sym)
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._stream())
        else:
            await self._send_sub_single(sym)

    async def unsubscribe(self, symbol: str):
        sym = symbol.upper()
        self._symbols.discard(sym)
        if self._ws:
            try:
                await self._ws.send(json.dumps({"type": "unsubscribe", "symbol": sym}))
            except Exception:
                pass

    async def _send_sub_single(self, sym: str):
        if self._ws:
            try:
                await self._ws.send(json.dumps({"type": "subscribe", "symbol": sym}))
            except Exception:
                pass

    async def _send_all_subs(self):
        if not self._ws:
            return
        for sym in self._symbols:
            try:
                await self._ws.send(json.dumps({"type": "subscribe", "symbol": sym}))
            except Exception:
                pass

    async def _stream(self):
        import websockets

        url = self.WS_URL.format(token=self._api_key)

        while self._running and self._symbols:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    self._ws = ws
                    logger.info("Finnhub WS connected, subscribing to %s", list(self._symbols))
                    await self._send_all_subs()

                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            msg = json.loads(raw)
                            if msg.get("type") == "trade":
                                self._handle_trades(msg.get("data", []))
                        except Exception as e:
                            logger.debug("Finnhub parse: %s", e)
                    self._ws = None
            except asyncio.CancelledError:
                return
            except Exception as e:
                self._ws = None
                logger.warning("Finnhub WS error: %s, reconnecting in 3s", e)
                await asyncio.sleep(3)

    def _handle_trades(self, trades: list):
        """Handle Finnhub trade messages.
        Each trade: {"c": [conditions], "p": price, "s": symbol, "t": timestamp_ms, "v": volume}
        """
        for trade in trades:
            sym = trade.get("s", "")
            price = float(trade.get("p", 0))
            volume = float(trade.get("v", 0))
            if not sym or price <= 0:
                continue

            self._hub._handle_price(sym, price, "finnhub")
            self._agg_trade(sym, price, volume)

    def _agg_trade(self, sym: str, price: float, volume: float):
        """Aggregate trades into 1-second candles."""
        sec = int(time.time())
        if self._agg_sec.get(sym) != sec:
            prev = self._agg.pop(sym, None)
            if prev:
                prev["closed"] = True
                self._hub._handle_candle(prev)
            self._agg_sec[sym] = sec
            self._agg[sym] = {
                "type": "candle", "symbol": sym, "source": "finnhub",
                "time": float(sec), "open": price, "high": price, "low": price,
                "close": price, "volume": volume, "closed": False,
            }
        else:
            c = self._agg[sym]
            c["high"] = max(c["high"], price)
            c["low"] = min(c["low"], price)
            c["close"] = price
            c["volume"] += volume

    async def shutdown(self):
        self._running = False
        if self._task:
            self._task.cancel()
        self._ws = None


# ── LiveFeedHub ───────────────────────────────────────────────────────────────

class LiveFeedHub:
    """Central hub — Kraken (crypto) + Finnhub (stocks) → unified events."""

    def __init__(self, finnhub_key: str = "", alpaca_key: str = "", alpaca_secret: str = ""):
        self.kraken = KrakenFeed(self)
        self.finnhub = FinnhubFeed(self, api_key=finnhub_key)

        self.prices: Dict[str, dict] = {}
        self._prev_prices: Dict[str, float] = {}
        self.candle_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))

        self._candle_cbs: List[Callable] = []
        self._price_cbs: List[Callable] = []
        self._signal_cbs: List[Callable] = []
        self._subs: Dict[str, dict] = {}

    def on_candle(self, cb: Callable):
        self._candle_cbs.append(cb)

    def on_price(self, cb: Callable):
        self._price_cbs.append(cb)

    def on_signal(self, cb: Callable):
        self._signal_cbs.append(cb)

    async def subscribe(self, symbol: str, interval: str = "1s", source: str = "auto"):
        sym = symbol.upper()
        if source == "auto":
            # Crypto detection — known pairs or ends in USDT/USD
            if sym in SYMBOL_TO_KRAKEN or any(sym.endswith(s) for s in ("USDT", "USDC", "USD")):
                source = "kraken"
            elif sym in ("BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT"):
                source = "kraken"
            else:
                source = "finnhub"

        self._subs[sym] = {"interval": interval, "source": source}
        if source == "kraken":
            await self.kraken.subscribe(sym, interval)
        elif source == "finnhub":
            await self.finnhub.subscribe(sym, interval)
        logger.info(f"Hub: subscribed {sym} ({source} @ {interval})")

    async def unsubscribe(self, symbol: str):
        sym = symbol.upper()
        info = self._subs.pop(sym, {})
        if info.get("source") == "kraken":
            await self.kraken.unsubscribe(sym)
        elif info.get("source") == "finnhub":
            await self.finnhub.unsubscribe(sym)

    def get_buffered_candles(self, symbol: str) -> List[dict]:
        return list(self.candle_buffers.get(symbol.upper(), []))

    def get_prices(self) -> Dict[str, dict]:
        return dict(self.prices)

    def emit_signal(self, signal: dict):
        for cb in self._signal_cbs:
            try:
                cb(signal)
            except Exception:
                pass

    def _handle_candle(self, candle: dict):
        sym = candle.get("symbol", "")
        if candle.get("closed"):
            self.candle_buffers[sym].append(candle)
        for cb in self._candle_cbs:
            try:
                cb(candle)
            except Exception as e:
                logger.debug(f"candle cb error: {e}")

    def _handle_price(self, symbol: str, price: float, source: str):
        prev = self._prev_prices.get(symbol, price)
        pct = ((price - prev) / prev * 100) if prev else 0.0
        self._prev_prices[symbol] = price
        data = {"symbol": symbol, "price": price, "change_pct": round(pct, 4), "source": source, "ts": time.time()}
        self.prices[symbol] = data
        for cb in self._price_cbs:
            try:
                cb(data)
            except Exception as e:
                logger.debug(f"price cb error: {e}")

    async def shutdown(self):
        await self.kraken.shutdown()
        await self.finnhub.shutdown()
        logger.info("LiveFeedHub shut down")
