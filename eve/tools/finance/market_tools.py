"""
Market Data Tools
==================
Real-time stock quotes, crypto prices, commodities, forex, market analysis.
Uses yfinance (handles Yahoo Finance auth automatically) + CoinGecko.
All overview fetches run in parallel with a configurable server-side cache.

Fixes:
- yfinance SQLite lock (Docker): TZ cache redirected to /tmp
- Last-known-good cache: errors never overwrite working data
- Extended data: VIX, Gold, Oil, Silver, EUR/USD, GBP/USD + more crypto
"""

import asyncio
import logging
import math
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

import aiohttp

from ..base import Tool

logger = logging.getLogger(__name__)

# Redirect yfinance's SQLite TZ cache to /tmp to avoid "database is locked" in Docker
os.environ.setdefault(
    "YFINANCE_CACHE_DIR", os.path.join(tempfile.gettempdir(), "yf_cache_eve")
)
try:
    import yfinance as yf
    yf.set_tz_cache_location(os.path.join(tempfile.gettempdir(), "yf_tz_eve"))
except Exception:
    pass  # yfinance not installed yet — will fail gracefully at fetch time

# ----------------------------------------------------------------
#  Cache: two-tier — short TTL live cache + last-known-good backup
# ----------------------------------------------------------------

_live_cache: Dict[str, Dict] = {}
_lkg_cache: Dict[str, Dict] = {}   # last-known-good — never expires, only updated on success
_CACHE_TTL = 90           # seconds (stock/index/commodity/forex)
_CRYPTO_CACHE_TTL = 300   # seconds (5 min — avoids CoinGecko 429)
_coingecko_cooldown: float = 0  # epoch time after which we can retry CoinGecko


def _cache_get(key: str) -> Optional[Dict]:
    """Return live cached value if fresh, else None."""
    entry = _live_cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data: Dict):
    """Store in live cache. If data looks valid, also update last-known-good."""
    _live_cache[key] = {"data": data, "ts": time.time()}
    # Consider data valid if at least one value is non-zero
    if _has_valid_data(data):
        _lkg_cache[key] = {"data": data, "ts": time.time()}


def _cache_get_lkg(key: str) -> Optional[Dict]:
    """Return last-known-good data (may be older but has real prices)."""
    entry = _lkg_cache.get(key)
    return entry["data"] if entry else None


def _has_valid_data(data: Dict) -> bool:
    """True if the data dict contains at least one non-zero price value."""
    for v in data.values():
        if isinstance(v, (int, float)) and v > 0:
            return True
        if isinstance(v, dict):
            if _has_valid_data(v):
                return True
    return False


def _safe_float(value, default: float = 0.0) -> float:
    """Convert to float, replacing NaN/Inf with default (JSON can't serialize them)."""
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------
#  Market symbol definitions
# ----------------------------------------------------------------

INDICES = {
    "^GSPC":  "S&P 500",
    "^DJI":   "Dow Jones",
    "^IXIC":  "Nasdaq",
    "^RUT":   "Russell 2000",
    "^VIX":   "VIX (Fear)",
    "^FTSE":  "FTSE 100",
    "^N225":  "Nikkei 225",
    "^HSI":   "Hang Seng",
    "^GDAXI": "DAX",
}

COMMODITIES = {
    "GC=F":  "Gold",
    "SI=F":  "Silver",
    "CL=F":  "Crude Oil",
    "NG=F":  "Natural Gas",
    "HG=F":  "Copper",
    "ZW=F":  "Wheat",
}

FOREX = {
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "DX-Y.NYB": "US Dollar Index",
}

# Sector ETFs — quick read on sector rotation
SECTOR_ETFS = {
    "XLK":  "Technology",
    "XLF":  "Financials",
    "XLE":  "Energy",
    "XLV":  "Healthcare",
    "XLY":  "Consumer Disc.",
    "XLP":  "Consumer Staples",
    "XLI":  "Industrials",
    "XLRE": "Real Estate",
}

# High-interest individual stocks for market research
WATCHLIST_STOCKS = {
    "NVDA": "NVIDIA",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "TSLA": "Tesla",
    "META": "Meta",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "PLTR": "Palantir",
}

TOP_CRYPTO = [
    "bitcoin",
    "ethereum",
    "solana",
    "ripple",
    "dogecoin",
    "cardano",
    "avalanche-2",
    "chainlink",
    "polkadot",
    "shiba-inu",
]

# Alternative Fear & Greed endpoint (public, no auth)
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"

COINGECKO_URL = "https://api.coingecko.com/api/v3"


# ----------------------------------------------------------------
#  Market Data Client
# ----------------------------------------------------------------

class MarketDataClient:
    """Async market data via yfinance + CoinGecko."""

    # ── Stock / Index / Commodity / Forex fetch ──────────────────

    def _fetch_stock_sync(self, symbol: str) -> Dict:
        """
        Synchronous yfinance fetch — run in executor to stay non-blocking.
        Tries fast_info first, falls back to .info dict on failure.
        """
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info

            price = _safe_float(getattr(info, "last_price", 0))
            prev_close = _safe_float(getattr(info, "previous_close", price))

            # Fallback: if price is 0, try the slower .info dict
            if price == 0:
                try:
                    full_info = ticker.info
                    price = _safe_float(
                        full_info.get("regularMarketPrice")
                        or full_info.get("currentPrice")
                        or full_info.get("ask")
                        or 0
                    )
                    prev_close = _safe_float(
                        full_info.get("regularMarketPreviousClose") or prev_close
                    )
                except Exception:
                    pass

            if price == 0:
                return {
                    "symbol": symbol.upper(),
                    "price": 0, "change": 0, "change_percent": 0,
                    "error": "no price data",
                }

            change = round(price - prev_close, 4)
            change_pct = round((change / prev_close * 100) if prev_close else 0, 2)

            return {
                "symbol": symbol.upper(),
                "price": round(price, 4),
                "previous_close": round(prev_close, 4),
                "change": round(change, 4),
                "change_percent": change_pct,
                "currency": getattr(info, "currency", "USD") or "USD",
                "exchange": getattr(info, "exchange", "") or "",
                "year_high": round(_safe_float(getattr(info, "year_high", 0)), 2),
                "year_low": round(_safe_float(getattr(info, "year_low", 0)), 2),
                "volume": int(_safe_float(getattr(info, "three_month_average_volume", 0))),
                "market_cap": int(_safe_float(getattr(info, "market_cap", 0))),
            }
        except Exception as e:
            logger.error(f"yfinance fetch failed for {symbol}: {e}")
            return {
                "symbol": symbol.upper(),
                "price": 0, "change": 0, "change_percent": 0,
                "error": str(e),
            }

    async def get_stock_quote(self, symbol: str) -> Dict:
        """Fetch stock/index/commodity/forex quote. Returns live or last-known-good data."""
        cache_key = f"stock:{symbol}"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, self._fetch_stock_sync, symbol)

        if data.get("price", 0) > 0:
            _cache_set(cache_key, data)
        else:
            # Return last-known-good if this fetch failed
            lkg = _cache_get_lkg(cache_key)
            if lkg:
                logger.debug(f"yfinance failed for {symbol}, using last-known-good data")
                return {**lkg, "_stale": True}
            # Store the error result so we don't hammer yfinance
            _live_cache[cache_key] = {"data": data, "ts": time.time()}

        return data

    # ── Crypto (CoinGecko) ───────────────────────────────────────

    async def get_crypto_price(self, coin_id: str, vs_currency: str = "usd") -> Dict:
        global _coingecko_cooldown
        cache_key = f"crypto:{coin_id}"

        # Use longer TTL for crypto to respect CoinGecko rate limits
        entry = _live_cache.get(cache_key)
        if entry and (time.time() - entry["ts"]) < _CRYPTO_CACHE_TTL:
            return entry["data"]

        # Respect 429 cooldown — don't hit CoinGecko while in cooldown
        if time.time() < _coingecko_cooldown:
            lkg = _cache_get_lkg(cache_key)
            return lkg or {"coin": coin_id, "price": 0, "change_24h": 0, "error": "rate_cooldown"}

        try:
            url = f"{COINGECKO_URL}/simple/price"
            params = {
                "ids": coin_id.lower(),
                "vs_currencies": vs_currency,
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
                "include_market_cap": "true",
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 429:
                        _coingecko_cooldown = time.time() + 120  # 2-minute cooldown
                        logger.warning("CoinGecko rate limit hit — cooling down 120s")
                        lkg = _cache_get_lkg(cache_key)
                        return lkg or {"coin": coin_id, "price": 0, "change_24h": 0, "error": "Rate limited"}
                    if resp.status != 200:
                        lkg = _cache_get_lkg(cache_key)
                        return lkg or {"coin": coin_id, "price": 0, "change_24h": 0, "error": f"HTTP {resp.status}"}
                    raw = await resp.json(content_type=None)

            coin_data = raw.get(coin_id.lower(), {})
            if not coin_data:
                return {"coin": coin_id, "price": 0, "change_24h": 0, "error": "No data"}

            data = {
                "coin": coin_id,
                "price": _safe_float(coin_data.get(vs_currency, 0)),
                "change_24h": round(_safe_float(coin_data.get(f"{vs_currency}_24h_change", 0)), 2),
                "volume_24h": _safe_float(coin_data.get(f"{vs_currency}_24h_vol", 0)),
                "market_cap": _safe_float(coin_data.get(f"{vs_currency}_market_cap", 0)),
                "currency": vs_currency.upper(),
            }
            _cache_set(cache_key, data)
            return data

        except asyncio.TimeoutError:
            lkg = _cache_get_lkg(cache_key)
            return lkg or {"coin": coin_id, "price": 0, "change_24h": 0, "error": "Timeout"}
        except Exception as e:
            logger.error(f"Crypto price failed for {coin_id}: {e}")
            lkg = _cache_get_lkg(cache_key)
            return lkg or {"coin": coin_id, "price": 0, "change_24h": 0, "error": str(e)}

    # ── Bulk crypto via CoinGecko simple/price (one call, many coins) ───────────

    async def get_crypto_market_data(
        self, coin_ids: List[str], vs_currency: str = "usd"
    ) -> Dict[str, Dict]:
        """
        Fetch multiple coins in one CoinGecko simple/price request.
        Uses the lighter endpoint to avoid rate limits.
        """
        global _coingecko_cooldown
        cache_key = f"crypto_bulk:{'|'.join(sorted(coin_ids))}"

        entry = _live_cache.get(cache_key)
        if entry and (time.time() - entry["ts"]) < _CRYPTO_CACHE_TTL:
            return entry["data"]

        if time.time() < _coingecko_cooldown:
            logger.debug("CoinGecko in cooldown — returning last-known-good crypto data")
            return _cache_get_lkg(cache_key) or {}

        try:
            url = f"{COINGECKO_URL}/simple/price"
            params = {
                "ids": ",".join(coin_ids),
                "vs_currencies": vs_currency,
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
                "include_market_cap": "true",
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=12)
                ) as resp:
                    if resp.status == 429:
                        _coingecko_cooldown = time.time() + 120
                        logger.warning("CoinGecko rate limit (bulk) — cooling down 120s")
                        return _cache_get_lkg(cache_key) or {}
                    if resp.status != 200:
                        logger.warning(f"CoinGecko bulk HTTP {resp.status}")
                        return _cache_get_lkg(cache_key) or {}
                    raw = await resp.json(content_type=None)

            result: Dict[str, Dict] = {}
            for cid in coin_ids:
                coin_data = raw.get(cid.lower(), {})
                if coin_data:
                    result[cid] = {
                        "coin": cid,
                        "price": _safe_float(coin_data.get(vs_currency, 0)),
                        "change_24h": round(_safe_float(coin_data.get(f"{vs_currency}_24h_change", 0)), 2),
                        "volume_24h": _safe_float(coin_data.get(f"{vs_currency}_24h_vol", 0)),
                        "market_cap": _safe_float(coin_data.get(f"{vs_currency}_market_cap", 0)),
                        "currency": vs_currency.upper(),
                    }

            if result:
                _cache_set(cache_key, result)
                # Also update individual caches so per-coin lookups get fresh data
                for cid, data in result.items():
                    _cache_set(f"crypto:{cid}", data)

            return result

        except Exception as e:
            logger.error(f"Bulk crypto fetch failed: {e}")
            return _cache_get_lkg(cache_key) or {}

    # ── Full Market Overview ─────────────────────────────────────

    async def get_market_overview(self) -> Dict:
        """
        Fetch all market data in parallel.
        Returns: indices, commodities, forex, crypto — each with last-known-good fallback.
        Cached for _CACHE_TTL seconds.
        """
        cache_key = "overview"
        cached = _cache_get(cache_key)
        if cached:
            return {**cached, "_cached": True}

        # Fire all requests in parallel
        index_coros = [self.get_stock_quote(sym) for sym in INDICES]
        commodity_coros = [self.get_stock_quote(sym) for sym in COMMODITIES]
        forex_coros = [self.get_stock_quote(sym) for sym in FOREX]
        crypto_bulk_task = self.get_crypto_market_data(TOP_CRYPTO)

        (
            index_results,
            commodity_results,
            forex_results,
            crypto_data,
        ) = await asyncio.gather(
            asyncio.gather(*index_coros, return_exceptions=True),
            asyncio.gather(*commodity_coros, return_exceptions=True),
            asyncio.gather(*forex_coros, return_exceptions=True),
            crypto_bulk_task,
            return_exceptions=False,
        )

        def _pack(keys, names, results):
            out = {}
            for sym, name, result in zip(keys, names, results):
                if isinstance(result, Exception):
                    out[sym] = {
                        "price": 0, "change_percent": 0, "name": name, "error": str(result)
                    }
                else:
                    out[sym] = {**result, "name": name}
            return out

        indices = _pack(list(INDICES.keys()), list(INDICES.values()), index_results)
        commodities = _pack(list(COMMODITIES.keys()), list(COMMODITIES.values()), commodity_results)
        forex = _pack(list(FOREX.keys()), list(FOREX.values()), forex_results)

        # Use bulk crypto response; fall back to empty dicts if missing
        crypto: Dict[str, Dict] = {}
        for coin in TOP_CRYPTO:
            if coin in crypto_data:
                crypto[coin] = crypto_data[coin]
            else:
                crypto[coin] = {"coin": coin, "price": 0, "change_24h": 0}

        overview = {
            "indices": indices,
            "commodities": commodities,
            "forex": forex,
            "crypto": crypto,
            "updated_at": time.time(),
        }

        # Only cache if we got at least some valid data
        if _has_valid_data(overview):
            _cache_set(cache_key, overview)
        else:
            lkg = _cache_get_lkg(cache_key)
            if lkg:
                logger.warning("Market overview: all fetches failed, returning last-known-good")
                return {**lkg, "_stale": True}

        return overview

    # ── Fear & Greed Index ───────────────────────────────────────

    async def get_fear_greed(self) -> Dict:
        """Crypto Fear & Greed Index from alternative.me (free, no auth)."""
        cache_key = "fear_greed"
        cached = _cache_get(cache_key)
        if cached:
            return cached
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    FEAR_GREED_URL, timeout=aiohttp.ClientTimeout(total=6)
                ) as resp:
                    if resp.status != 200:
                        return _cache_get_lkg(cache_key) or {"value": 50, "classification": "Neutral", "error": f"HTTP {resp.status}"}
                    raw = await resp.json(content_type=None)
            entry = raw.get("data", [{}])[0]
            data = {
                "value": int(entry.get("value", 50)),
                "classification": entry.get("value_classification", "Neutral"),
                "timestamp": entry.get("timestamp", ""),
            }
            _cache_set(cache_key, data)
            return data
        except Exception as e:
            logger.warning(f"Fear & Greed fetch failed: {e}")
            return _cache_get_lkg(cache_key) or {"value": 50, "classification": "Neutral", "error": str(e)}

    # ── Treasury Yields / Bond Market ───────────────────────────

    async def get_treasury_yields(self) -> Dict:
        """
        Fetch US Treasury yield curve via yfinance.
        ^IRX=13W  ^FVX=5Y  ^TNX=10Y  ^TYX=30Y
        Also fetches TIPS spread and dollar index.
        """
        cache_key = "treasury"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        YIELD_SYMBOLS = {
            "^IRX":    {"label": "3-Month T-Bill", "maturity": 0.25},
            "^FVX":    {"label": "5-Year Note",    "maturity": 5},
            "^TNX":    {"label": "10-Year Note",   "maturity": 10},
            "^TYX":    {"label": "30-Year Bond",   "maturity": 30},
            "DX-Y.NYB":{"label": "Dollar Index",   "maturity": None},
        }

        coros = [self.get_stock_quote(sym) for sym in YIELD_SYMBOLS]
        results = await asyncio.gather(*coros, return_exceptions=True)

        yields = {}
        for sym, meta, result in zip(YIELD_SYMBOLS.keys(), YIELD_SYMBOLS.values(), results):
            if isinstance(result, Exception):
                yields[sym] = {"label": meta["label"], "yield": 0, "change": 0, "maturity": meta["maturity"], "error": str(result)}
            else:
                price = result.get("price", 0)
                # yfinance returns ^TNX as 4.25 meaning 4.25% — already in percent
                yields[sym] = {
                    "label": meta["label"],
                    "yield": round(price, 3),
                    "change": round(result.get("change_percent", 0), 3),
                    "maturity": meta["maturity"],
                }

        # Compute 2s10s spread if we have both (use ^IRX as proxy for short end)
        t3m = yields.get("^IRX", {}).get("yield", 0)
        t10y = yields.get("^TNX", {}).get("yield", 0)
        t30y = yields.get("^TYX", {}).get("yield", 0)
        spread_10_3m = round(t10y - t3m, 3) if t10y and t3m else 0
        spread_30_10 = round(t30y - t10y, 3) if t30y and t10y else 0

        data = {
            "yields": yields,
            "spreads": {
                "10y_3m": spread_10_3m,
                "30y_10y": spread_30_10,
                "inverted": spread_10_3m < 0,
            },
            "updated_at": time.time(),
        }
        _cache_set(cache_key, data)
        return data

    # ── Sector ETFs ──────────────────────────────────────────────

    async def get_sector_performance(self) -> Dict:
        """Fetch sector ETF performance for heat map."""
        cache_key = "sectors"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        coros = [self.get_stock_quote(sym) for sym in SECTOR_ETFS]
        results = await asyncio.gather(*coros, return_exceptions=True)

        sectors = {}
        for sym, name, result in zip(SECTOR_ETFS.keys(), SECTOR_ETFS.values(), results):
            if isinstance(result, Exception):
                sectors[sym] = {"name": name, "price": 0, "change_percent": 0, "error": str(result)}
            else:
                sectors[sym] = {**result, "name": name}

        data = {"sectors": sectors, "updated_at": time.time()}
        _cache_set(cache_key, data)
        return data

    # ── Watchlist Stocks ─────────────────────────────────────────

    async def get_watchlist(self) -> Dict:
        """Fetch watchlist stocks with technical signal hints."""
        cache_key = "watchlist"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        coros = [self.get_stock_quote(sym) for sym in WATCHLIST_STOCKS]
        results = await asyncio.gather(*coros, return_exceptions=True)

        stocks = {}
        for sym, name, result in zip(WATCHLIST_STOCKS.keys(), WATCHLIST_STOCKS.values(), results):
            if isinstance(result, Exception):
                stocks[sym] = {"name": name, "price": 0, "change_percent": 0, "error": str(result)}
            else:
                stocks[sym] = {**result, "name": name}

        data = {"stocks": stocks, "updated_at": time.time()}
        _cache_set(cache_key, data)
        return data

    # ── Technical Signals (pure pandas, no TA-Lib) ───────────────

    def _compute_rsi(self, prices: list, period: int = 14) -> float:
        """Compute RSI from a list of closing prices."""
        if len(prices) < period + 1:
            return 50.0
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        if not losses:
            return 100.0
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 1)

    def _get_technical_sync(self, symbol: str) -> Dict:
        """Synchronous technical analysis — run in executor."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="3mo", interval="1d")
            if hist.empty or len(hist) < 20:
                return {"symbol": symbol, "error": "insufficient history"}

            closes = hist["Close"].tolist()
            vols = hist["Volume"].tolist()

            # Moving averages
            sma20 = round(sum(closes[-20:]) / 20, 2)
            sma50 = round(sum(closes[-50:]) / 50, 2) if len(closes) >= 50 else None
            current = closes[-1]

            # RSI
            rsi = self._compute_rsi(closes)

            # MACD (12, 26, signal 9)
            def ema(data, n):
                k = 2 / (n + 1)
                e = data[0]
                for p in data[1:]:
                    e = p * k + e * (1 - k)
                return e

            if len(closes) >= 26:
                macd_line = ema(closes[-26:], 12) - ema(closes[-26:], 26)
            else:
                macd_line = 0

            # Volume trend
            avg_vol = sum(vols[-20:]) / 20 if vols else 0
            last_vol = vols[-1] if vols else 0
            vol_ratio = round(last_vol / avg_vol, 2) if avg_vol else 1.0

            # Signals
            signals = []
            if current > sma20:
                signals.append("above_sma20")
            else:
                signals.append("below_sma20")
            if sma50 and current > sma50:
                signals.append("above_sma50")
            if rsi > 70:
                signals.append("overbought")
            elif rsi < 30:
                signals.append("oversold")
            if macd_line > 0:
                signals.append("macd_bullish")
            else:
                signals.append("macd_bearish")
            if vol_ratio > 1.5:
                signals.append("high_volume")

            # Overall bias
            bull_signals = sum(1 for s in signals if s in ("above_sma20", "above_sma50", "macd_bullish"))
            bias = "bullish" if bull_signals >= 2 else "bearish" if bull_signals == 0 else "neutral"

            return {
                "symbol": symbol.upper(),
                "current_price": round(current, 4),
                "sma_20": sma20,
                "sma_50": sma50,
                "rsi": rsi,
                "macd": round(macd_line, 4),
                "volume_ratio": vol_ratio,
                "signals": signals,
                "bias": bias,
                "candles_analyzed": len(closes),
            }
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    async def get_technical_signals(self, symbol: str) -> Dict:
        """Get technical analysis signals for a symbol."""
        cache_key = f"tech:{symbol}"
        cached = _cache_get(cache_key)
        if cached:
            return cached
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, self._get_technical_sync, symbol)
        if "error" not in data:
            _cache_set(cache_key, data)
        return data

    # ── DexScreener — Trending Memecoins ────────────────────────

    async def get_dex_trending(self, chain: str = "solana") -> Dict:
        """
        Fetch trending token pairs from DexScreener (free, no auth).
        Returns top pairs sorted by 24h volume for the given chain.
        """
        cache_key = f"dex_trending:{chain}"
        entry = _live_cache.get(cache_key)
        if entry and (time.time() - entry["ts"]) < 180:  # 3-min cache for fast-moving memecoins
            return entry["data"]

        try:
            # DexScreener trending search — top volume pairs on chain
            url = f"https://api.dexscreener.com/latest/dex/search?q={chain}"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"User-Agent": "EveOmegaPortal/1.0"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return _cache_get_lkg(cache_key) or {"pairs": [], "chain": chain, "error": f"HTTP {resp.status}"}
                    raw = await resp.json(content_type=None)

            pairs_raw = raw.get("pairs", [])
            # Filter to the requested chain and sort by 24h volume
            chain_pairs = [
                p for p in pairs_raw
                if p.get("chainId", "").lower() == chain.lower()
                and p.get("volume", {}).get("h24", 0) > 0
            ]
            chain_pairs.sort(key=lambda p: p.get("volume", {}).get("h24", 0), reverse=True)

            pairs = []
            for p in chain_pairs[:20]:
                base = p.get("baseToken", {})
                quote = p.get("quoteToken", {})
                price_usd = _safe_float(p.get("priceUsd", 0))
                vol_24h = _safe_float(p.get("volume", {}).get("h24", 0))
                change_24h = _safe_float(p.get("priceChange", {}).get("h24", 0))
                liq = _safe_float(p.get("liquidity", {}).get("usd", 0))
                pairs.append({
                    "name": base.get("name", "?"),
                    "symbol": base.get("symbol", "?"),
                    "address": base.get("address", ""),
                    "pair_address": p.get("pairAddress", ""),
                    "dex": p.get("dexId", ""),
                    "price_usd": price_usd,
                    "change_24h": change_24h,
                    "volume_24h": vol_24h,
                    "liquidity_usd": liq,
                    "url": p.get("url", ""),
                })

            data = {"pairs": pairs, "chain": chain, "count": len(pairs), "updated_at": time.time()}
            _live_cache[cache_key] = {"data": data, "ts": time.time()}
            if pairs:
                _lkg_cache[cache_key] = {"data": data, "ts": time.time()}
            return data

        except Exception as e:
            logger.error(f"DexScreener fetch failed: {e}")
            return _cache_get_lkg(cache_key) or {"pairs": [], "chain": chain, "error": str(e)}

    # ── GeckoTerminal — Trending Pools ──────────────────────────

    async def get_gecko_trending(self, network: str = "solana") -> Dict:
        """
        Fetch trending DEX pools from GeckoTerminal (free, no auth).
        Good for discovering new Solana/ETH memecoin launches.
        """
        cache_key = f"gecko_trending:{network}"
        entry = _live_cache.get(cache_key)
        if entry and (time.time() - entry["ts"]) < 180:
            return entry["data"]

        try:
            url = f"https://api.geckoterminal.com/api/v2/networks/{network}/trending_pools"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"Accept": "application/json;version=20230302"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return _cache_get_lkg(cache_key) or {"pools": [], "network": network, "error": f"HTTP {resp.status}"}
                    raw = await resp.json(content_type=None)

            pools_raw = raw.get("data", [])
            pools = []
            for p in pools_raw[:15]:
                attrs = p.get("attributes", {})
                pools.append({
                    "name": attrs.get("name", "?"),
                    "address": attrs.get("address", ""),
                    "price_usd": _safe_float(attrs.get("base_token_price_usd", 0)),
                    "change_5m": _safe_float(attrs.get("price_change_percentage", {}).get("m5", 0)),
                    "change_1h": _safe_float(attrs.get("price_change_percentage", {}).get("h1", 0)),
                    "change_24h": _safe_float(attrs.get("price_change_percentage", {}).get("h24", 0)),
                    "volume_24h": _safe_float(attrs.get("volume_usd", {}).get("h24", 0)),
                    "liquidity": _safe_float(attrs.get("reserve_in_usd", 0)),
                    "fdv": _safe_float(attrs.get("fdv_usd", 0)),
                    "transactions_24h": attrs.get("transactions", {}).get("h24", {}).get("buys", 0),
                    "created_at": attrs.get("pool_created_at", ""),
                })

            data = {"pools": pools, "network": network, "count": len(pools), "updated_at": time.time()}
            _live_cache[cache_key] = {"data": data, "ts": time.time()}
            if pools:
                _lkg_cache[cache_key] = {"data": data, "ts": time.time()}
            return data

        except Exception as e:
            logger.error(f"GeckoTerminal fetch failed: {e}")
            return _cache_get_lkg(cache_key) or {"pools": [], "network": network, "error": str(e)}

    # ── Single symbol convenience ────────────────────────────────

    async def get_full_quote(self, symbol: str) -> Dict:
        """Quote with fallback strategy for arbitrary symbols."""
        return await self.get_stock_quote(symbol.upper())


# ----------------------------------------------------------------
#  Tool wrappers (for Eve's tool registry)
# ----------------------------------------------------------------

class StockQuoteTool(Tool):
    name = "stock_quote"
    description = (
        "Get real-time stock price and market data. "
        "Args: symbol (str, e.g. AAPL, TSLA, NVDA, GC=F for gold)"
    )

    def __init__(self):
        self.client = MarketDataClient()

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker symbol"},
            },
            "required": ["symbol"],
        }

    async def execute(self, symbol: str) -> Dict[str, Any]:
        quote = await self.client.get_stock_quote(symbol.upper())
        if "error" in quote and quote.get("price", 0) == 0:
            return {"success": False, **quote}
        return {"success": True, **quote}


class CryptoPriceTool(Tool):
    name = "crypto_price"
    description = (
        "Get real-time cryptocurrency price from CoinGecko. "
        "Args: coin (str, e.g. bitcoin, ethereum, solana), currency (str, default usd)"
    )

    def __init__(self):
        self.client = MarketDataClient()

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "coin": {
                    "type": "string",
                    "description": "CoinGecko coin ID (bitcoin, ethereum, solana, etc.)",
                },
                "currency": {
                    "type": "string",
                    "description": "VS currency",
                    "default": "usd",
                },
            },
            "required": ["coin"],
        }

    async def execute(self, coin: str, currency: str = "usd") -> Dict[str, Any]:
        price_data = await self.client.get_crypto_price(coin, currency)
        if "error" in price_data and price_data.get("price", 0) == 0:
            return {"success": False, **price_data}
        return {"success": True, **price_data}


class MarketOverviewTool(Tool):
    name = "market_overview"
    description = (
        "Get broad market overview — major indices, commodities, forex, and top crypto prices."
    )

    def __init__(self):
        self.client = MarketDataClient()

    def get_parameters(self) -> Dict:
        return {"type": "object", "properties": {}}

    async def execute(self) -> Dict[str, Any]:
        try:
            overview = await self.client.get_market_overview()
            return {"success": True, **overview}
        except Exception as e:
            return {"success": False, "error": str(e)}
