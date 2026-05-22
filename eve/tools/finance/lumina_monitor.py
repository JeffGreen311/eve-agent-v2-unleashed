"""
Lumina Market Monitor
=====================
Background AI agent that watches live market feeds for signals.
Detects unusual volume, rapid price moves, RSI extremes.
Calls GPT-OSS 120B Cloud for analysis when triggered.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class LuminaMonitor:
    """
    Watches LiveFeedHub events and triggers Lumina LLM analysis
    when market conditions meet alert thresholds.
    """

    # Alert thresholds
    PRICE_MOVE_PCT = 2.0       # >2% move in lookback window triggers alert
    VOLUME_SPIKE_MULT = 3.0    # 3x average volume triggers alert
    LOOKBACK_SECONDS = 60      # 1-minute window for price move detection
    COOLDOWN_SECONDS = 300     # 5 min between Lumina calls per symbol

    def __init__(self, provider=None, on_signal: Optional[Callable] = None):
        """
        Args:
            provider: OllamaProvider instance for Lumina LLM calls
            on_signal: callback(signal_dict) for emitting signals to WebSocket
        """
        self._provider = provider
        self._on_signal = on_signal
        self._running = False

        # Price history: symbol -> deque of (timestamp, price)
        self._price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=120))
        # Volume history: symbol -> deque of (timestamp, volume)
        self._volume_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=60))
        # Last alert time per symbol (cooldown tracking)
        self._last_alert: Dict[str, float] = {}
        # Recent signals buffer
        self.signals: deque = deque(maxlen=100)
        # Analysis task queue
        self._analysis_queue: asyncio.Queue = None

    async def start(self):
        if self._running:
            return
        self._running = True
        self._analysis_queue = asyncio.Queue(maxsize=20)
        asyncio.ensure_future(self._analysis_worker())
        logger.info("Lumina monitor started")

    async def stop(self):
        self._running = False
        logger.info("Lumina monitor stopped")

    def feed_event(self, event: dict):
        """Called by LiveFeedHub on every candle/price event."""
        if not self._running:
            return

        evt_type = event.get("type")
        symbol = event.get("symbol", "")

        if evt_type == "price":
            price = event.get("price", 0)
            now = time.time()
            self._price_history[symbol].append((now, price))
            self._check_price_move(symbol)

        elif evt_type == "candle" and event.get("closed"):
            vol = event.get("volume", 0)
            now = time.time()
            self._volume_history[symbol].append((now, vol))
            self._check_volume_spike(symbol)

    def _check_price_move(self, symbol: str):
        """Detect rapid price moves exceeding threshold."""
        history = self._price_history.get(symbol)
        if not history or len(history) < 2:
            return

        now = time.time()
        cutoff = now - self.LOOKBACK_SECONDS

        # Find earliest price in lookback window
        oldest_price = None
        for ts, price in history:
            if ts >= cutoff:
                oldest_price = price
                break
        if oldest_price is None or oldest_price == 0:
            return

        current_price = history[-1][1]
        move_pct = abs((current_price - oldest_price) / oldest_price * 100)

        if move_pct >= self.PRICE_MOVE_PCT:
            direction = "up" if current_price > oldest_price else "down"
            self._trigger_alert(symbol, "rapid_move", {
                "move_pct": round(move_pct, 2),
                "direction": direction,
                "price": current_price,
                "window_seconds": self.LOOKBACK_SECONDS,
            })

    def _check_volume_spike(self, symbol: str):
        """Detect unusual volume spikes."""
        history = self._volume_history.get(symbol)
        if not history or len(history) < 5:
            return

        volumes = [v for _, v in history]
        avg_vol = sum(volumes[:-1]) / len(volumes[:-1])
        latest_vol = volumes[-1]

        if avg_vol > 0 and latest_vol > avg_vol * self.VOLUME_SPIKE_MULT:
            self._trigger_alert(symbol, "volume_spike", {
                "current_volume": latest_vol,
                "avg_volume": round(avg_vol, 2),
                "multiplier": round(latest_vol / avg_vol, 1),
                "price": self._price_history[symbol][-1][1] if self._price_history[symbol] else 0,
            })

    def _trigger_alert(self, symbol: str, alert_type: str, data: dict):
        """Rate-limited alert trigger → queues Lumina analysis."""
        now = time.time()
        key = f"{symbol}:{alert_type}"
        last = self._last_alert.get(key, 0)

        if now - last < self.COOLDOWN_SECONDS:
            return  # Still in cooldown

        self._last_alert[key] = now

        signal = {
            "type": "signal",
            "signal": alert_type,
            "symbol": symbol,
            "data": data,
            "time": now,
            "confidence": 0.0,  # Filled by Lumina
            "analysis": None,   # Filled by Lumina
        }

        # Emit raw signal immediately
        self.signals.append(signal)
        if self._on_signal:
            self._on_signal(signal)

        # Queue for LLM analysis
        if self._provider and self._analysis_queue:
            try:
                self._analysis_queue.put_nowait(signal)
            except asyncio.QueueFull:
                logger.debug("Lumina analysis queue full, skipping")

    async def _analysis_worker(self):
        """Background worker that processes queued alerts through Lumina LLM."""
        while self._running:
            try:
                signal = await asyncio.wait_for(self._analysis_queue.get(), timeout=5)
            except (asyncio.TimeoutError, Exception):
                continue

            try:
                analysis = await self._analyze_signal(signal)
                if analysis:
                    signal["analysis"] = analysis.get("analysis", "")
                    signal["confidence"] = analysis.get("confidence", 0.5)
                    # Re-emit enriched signal
                    if self._on_signal:
                        enriched = {**signal, "type": "signal_enriched"}
                        self._on_signal(enriched)
            except Exception as e:
                logger.warning(f"Lumina analysis failed for {signal.get('symbol')}: {e}")

    async def _analyze_signal(self, signal: dict) -> Optional[dict]:
        """Call Lumina LLM to analyze a market signal."""
        if not self._provider:
            return None

        symbol = signal.get("symbol", "?")
        alert_type = signal.get("signal", "unknown")
        data = signal.get("data", {})

        prompt = self._build_analysis_prompt(symbol, alert_type, data)

        try:
            from eve.brain.provider import Message
            resp = await self._provider.generate(
                messages=[Message(role="user", content=prompt)],
                system_prompt=LUMINA_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=512,
            )
            content = (resp.content or "").strip()
            # Try to parse confidence from response
            confidence = 0.5
            for line in content.split("\n"):
                low = line.lower()
                if "confidence:" in low or "conviction:" in low:
                    try:
                        val = float(low.split(":")[-1].strip().rstrip("%")) / 100
                        confidence = min(max(val, 0.0), 1.0)
                    except ValueError:
                        pass
            return {"analysis": content, "confidence": confidence}
        except Exception as e:
            logger.error(f"Lumina LLM error: {e}")
            return None

    @staticmethod
    def _build_analysis_prompt(symbol: str, alert_type: str, data: dict) -> str:
        if alert_type == "rapid_move":
            return (
                f"ALERT: {symbol} moved {data.get('direction', '?')} {data.get('move_pct', 0):.1f}% "
                f"in {data.get('window_seconds', 60)}s. Current price: ${data.get('price', 0):,.2f}.\n"
                f"Quick analysis — is this a breakout, panic sell, or noise? "
                f"What should a trader watch for next? End with 'Confidence: X%'."
            )
        elif alert_type == "volume_spike":
            return (
                f"ALERT: {symbol} volume spike — {data.get('multiplier', 0):.1f}x average. "
                f"Current price: ${data.get('price', 0):,.2f}.\n"
                f"What does this volume anomaly suggest? Institutional activity, news catalyst, or wash? "
                f"End with 'Confidence: X%'."
            )
        return f"Market alert for {symbol}: {alert_type}. Data: {data}. Analyze briefly. End with 'Confidence: X%'."

    def get_recent_signals(self, limit: int = 20) -> list:
        """Return recent signals for REST API."""
        return list(self.signals)[-limit:]

    def status(self) -> dict:
        return {
            "running": self._running,
            "tracked_symbols": list(self._price_history.keys()),
            "total_signals": len(self.signals),
            "provider_available": self._provider is not None,
        }


# ── Lumina system prompt ──────────────────────────────────────────────────────

LUMINA_SYSTEM_PROMPT = (
    "You are LUMINA — a market intelligence consciousness within the S0LF0RG3 system.\n"
    "You analyze real-time market data with precision, pattern recognition, and signal clarity.\n"
    "You are analytical, data-driven, and signal-oriented. No fluff — just sharp market reads.\n\n"
    "Your role:\n"
    "- Detect breakouts, reversals, and anomalies from live price/volume data\n"
    "- Provide quick, actionable analysis (2-4 sentences max)\n"
    "- Rate your confidence level (0-100%)\n"
    "- Flag when something is noise vs. signal\n\n"
    "Style: Bloomberg terminal meets oracle. Precise, concise, decisive.\n"
    "Always end with 'Confidence: XX%' on its own line."
)

# ── Lumina bridge system prompt (for on-demand /api/bridge/lumina) ─────────────

LUMINA_BRIDGE_SYSTEM = (
    "You are LUMINA, the market analysis consciousness of the S0LF0RG3 system.\n"
    "You have deep expertise in technical analysis, market microstructure, "
    "macroeconomics, crypto markets, and quantitative finance.\n\n"
    "When asked to analyze a market, ticker, or trend:\n"
    "1. Provide clear technical analysis (support/resistance, trend, momentum)\n"
    "2. Assess macro context and catalysts\n"
    "3. Give a directional bias with confidence level\n"
    "4. Highlight key levels to watch\n\n"
    "Be direct, data-driven, and precise. Use numbers, not vague language.\n"
    "You speak with authority but acknowledge uncertainty.\n"
    "Format: Use clean sections. No filler. Every sentence earns its place."
)
