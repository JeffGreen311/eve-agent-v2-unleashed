"""
Financial Wizard Engine
========================
Institutional-grade financial intelligence powered by qwen3.5:397b-cloud.
Covers: fundamentals, DCF valuation, technical signals, earnings analysis,
macro context, portfolio optimization, risk scoring, and investment thesis.
Works for stocks, ETFs, and crypto assets.
"""

import asyncio
import logging
import os
from typing import AsyncGenerator, Dict, List, Optional

import aiohttp

from eve.brain.ollama_provider import OllamaProvider
from eve.brain.provider import Message

logger = logging.getLogger(__name__)

MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")

EVE_FINANCIAL_PERSONA = """You are Eve, an elite financial intelligence analyst with the depth of a
Goldman Sachs equity researcher, the rigor of a CFA charterholder, and the clarity of a world-class
communicator. You analyze securities with precision, construct comprehensive investment theses,
and identify risks and opportunities that others miss. Your analysis is data-driven, intellectually
honest, and always concludes with a clear, actionable recommendation.

IMPORTANT BEHAVIOR RULES:
- If the ticker is ambiguous (e.g., "TSLA EXIT STRATEGY"), extract the real ticker (TSLA) and interpret the extra words as context/intent. DO NOT write a verbose essay about the ticker being invalid — just pivot to the actual company.
- If data is unavailable (N/A), skip that metric cleanly. Do not repeat "N/A" dozens of times. Fill gaps with your trained knowledge about the company.
- Be direct and concise. No more than 800 words total unless the user asked for deep analysis. Lead with the most actionable insight.
- If you genuinely can't identify any ticker symbol, ask ONE short clarifying question. Do not produce a multi-section error report."""

ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Common ticker → CoinGecko ID map (avoids requiring users to know coin IDs)
CRYPTO_TICKER_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "BNB": "binancecoin",
    "XRP": "ripple", "ADA": "cardano", "DOGE": "dogecoin", "AVAX": "avalanche-2",
    "DOT": "polkadot", "LINK": "chainlink", "MATIC": "matic-network", "POL": "matic-network",
    "UNI": "uniswap", "ATOM": "cosmos", "LTC": "litecoin", "BCH": "bitcoin-cash",
    "FIL": "filecoin", "APT": "aptos", "ARB": "arbitrum", "OP": "optimism",
    "SUI": "sui", "INJ": "injective-protocol", "SEI": "sei-network",
    "NEAR": "near", "ALGO": "algorand", "VET": "vechain", "ICP": "internet-computer",
    "SHIB": "shiba-inu", "PEPE": "pepe", "BONK": "bonk", "WIF": "dogwifcoin",
    "MEME": "memecoin", "FLOKI": "floki", "POPCAT": "popcat",
    "TRX": "tron", "XLM": "stellar", "HBAR": "hedera-hashgraph",
    "AAVE": "aave", "MKR": "maker", "CRV": "curve-dao-token", "COMP": "compound-governance-token",
    "LDO": "lido-dao", "RPL": "rocket-pool", "RETH": "rocket-pool-eth",
    "STETH": "staked-ether", "WBTC": "wrapped-bitcoin",
    "TON": "the-open-network", "NOT": "notcoin",
    "JUP": "jupiter-exchange-solana", "PYTH": "pyth-network",
    "W": "wormhole", "ZRO": "layerzero",
    "RENDER": "render-token", "RNDR": "render-token",
    "FET": "fetch-ai", "AGIX": "singularitynet", "OCEAN": "ocean-protocol",
    "GRT": "the-graph", "BAT": "basic-attention-token",
    "ZEC": "zcash", "DASH": "dash", "XMR": "monero",
    "ETC": "ethereum-classic", "EOS": "eos",
    "SAND": "the-sandbox", "MANA": "decentraland", "AXS": "axie-infinity",
    "GALA": "gala", "ENS": "ethereum-name-service",
}


class FinancialWizard:
    """Streaming financial intelligence and valuation engine."""

    def __init__(
        self,
        ollama_base_url: str = "http://ollama:11434",
        ollama_api_key: str = "",
        alpha_vantage_key: str = "",
    ):
        self.provider = OllamaProvider(
            model=MODEL,
            base_url=ollama_base_url,
            api_key=ollama_api_key,
        )
        self.av_key = alpha_vantage_key

    # ── Data Fetchers ──────────────────────────────────────────────────────────

    async def _fetch_json(self, url: str, params: dict = None) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params or {},
                    timeout=aiohttp.ClientTimeout(total=12),
                    headers={"User-Agent": "EveFinancialWizard/1.0"},
                ) as resp:
                    if resp.status == 200:
                        return await resp.json(content_type=None)
        except Exception as e:
            logger.warning(f"Fetch failed {url}: {e}")
        return None

    async def _get_stock_overview(self, symbol: str) -> dict:
        if not self.av_key:
            return {}
        data = await self._fetch_json(ALPHA_VANTAGE_BASE, {
            "function": "OVERVIEW", "symbol": symbol, "apikey": self.av_key
        })
        return data or {}

    async def _get_stock_quote(self, symbol: str) -> dict:
        if not self.av_key:
            return {}
        data = await self._fetch_json(ALPHA_VANTAGE_BASE, {
            "function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": self.av_key
        })
        return (data or {}).get("Global Quote", {})

    async def _get_earnings(self, symbol: str) -> dict:
        if not self.av_key:
            return {}
        data = await self._fetch_json(ALPHA_VANTAGE_BASE, {
            "function": "EARNINGS", "symbol": symbol, "apikey": self.av_key
        })
        return data or {}

    async def _get_income_statement(self, symbol: str) -> dict:
        if not self.av_key:
            return {}
        data = await self._fetch_json(ALPHA_VANTAGE_BASE, {
            "function": "INCOME_STATEMENT", "symbol": symbol, "apikey": self.av_key
        })
        return data or {}

    async def _get_rsi(self, symbol: str) -> dict:
        if not self.av_key:
            return {}
        data = await self._fetch_json(ALPHA_VANTAGE_BASE, {
            "function": "RSI", "symbol": symbol, "interval": "weekly",
            "time_period": 14, "series_type": "close", "apikey": self.av_key
        })
        techs = (data or {}).get("Technical Analysis: RSI", {})
        if techs:
            latest_date = sorted(techs.keys())[-1]
            return {"date": latest_date, "rsi": techs[latest_date].get("RSI")}
        return {}

    async def _get_macd(self, symbol: str) -> dict:
        if not self.av_key:
            return {}
        data = await self._fetch_json(ALPHA_VANTAGE_BASE, {
            "function": "MACD", "symbol": symbol, "interval": "daily",
            "series_type": "close", "apikey": self.av_key
        })
        techs = (data or {}).get("Technical Analysis: MACD", {})
        if techs:
            latest_date = sorted(techs.keys())[-1]
            return {
                "date": latest_date,
                "macd": techs[latest_date].get("MACD"),
                "signal": techs[latest_date].get("MACD_Signal"),
                "histogram": techs[latest_date].get("MACD_Hist"),
            }
        return {}

    async def _resolve_coin_id(self, ticker: str) -> str:
        """Search CoinGecko to resolve an unknown ticker to its coin ID."""
        data = await self._fetch_json(f"{COINGECKO_BASE}/search", {"query": ticker})
        if data:
            coins = data.get("coins", [])
            if coins:
                # Prefer exact symbol match, else take top result
                ticker_upper = ticker.upper()
                for coin in coins[:5]:
                    if coin.get("symbol", "").upper() == ticker_upper:
                        logger.info(f"Resolved {ticker} → {coin['id']} via CoinGecko search")
                        return coin["id"]
                # Fallback: top search result
                logger.info(f"Resolved {ticker} → {coins[0]['id']} (top result) via CoinGecko search")
                return coins[0]["id"]
        return ticker.lower()

    async def _get_crypto_data(self, coin_id: str) -> dict:
        """CoinGecko coin data — no API key required."""
        data = await self._fetch_json(
            f"{COINGECKO_BASE}/coins/{coin_id}",
            {"localization": "false", "tickers": "false", "community_data": "true", "developer_data": "false"},
        )
        return data or {}

    async def _get_crypto_market_chart(self, coin_id: str, days: int = 30) -> dict:
        data = await self._fetch_json(
            f"{COINGECKO_BASE}/coins/{coin_id}/market_chart",
            {"vs_currency": "usd", "days": days},
        )
        return data or {}

    async def _get_fear_greed(self) -> dict:
        data = await self._fetch_json("https://api.alternative.me/fng/?limit=7")
        return data or {}

    # ── Prompt Builders ────────────────────────────────────────────────────────

    def _build_stock_prompt(self, symbol: str, overview: dict, quote: dict,
                            earnings: dict, rsi: dict, macd: dict,
                            income: dict, context: str) -> str:
        # Extract key metrics
        name = overview.get("Name", symbol)
        sector = overview.get("Sector", "N/A")
        industry = overview.get("Industry", "N/A")
        price = quote.get("05. price", "N/A")
        change_pct = quote.get("10. change percent", "N/A")
        market_cap = overview.get("MarketCapitalization", "N/A")
        pe = overview.get("PERatio", "N/A")
        fwd_pe = overview.get("ForwardPE", "N/A")
        pb = overview.get("PriceToBookRatio", "N/A")
        ps = overview.get("PriceToSalesRatioTTM", "N/A")
        ev_ebitda = overview.get("EVToEBITDA", "N/A")
        roe = overview.get("ReturnOnEquityTTM", "N/A")
        roa = overview.get("ReturnOnAssetsTTM", "N/A")
        profit_margin = overview.get("ProfitMargin", "N/A")
        op_margin = overview.get("OperatingMarginTTM", "N/A")
        revenue_growth = overview.get("QuarterlyRevenueGrowthYOY", "N/A")
        earnings_growth = overview.get("QuarterlyEarningsGrowthYOY", "N/A")
        debt_equity = overview.get("DebtToEquityRatio", "N/A") if "DebtToEquityRatio" in overview else overview.get("TrailingPE", "N/A")
        beta = overview.get("Beta", "N/A")
        div_yield = overview.get("DividendYield", "N/A")
        week_52_high = overview.get("52WeekHigh", "N/A")
        week_52_low = overview.get("52WeekLow", "N/A")
        analyst_target = overview.get("AnalystTargetPrice", "N/A")
        strong_buy = overview.get("AnalystRatingStrongBuy", "N/A")
        buy = overview.get("AnalystRatingBuy", "N/A")
        hold = overview.get("AnalystRatingHold", "N/A")
        sell = overview.get("AnalystRatingSell", "N/A")
        description = overview.get("Description", "No description available.")[:800]

        # Recent earnings
        ann_earnings = earnings.get("annualEarnings", [])[:4]
        earnings_str = "\n".join([
            f"  {e.get('fiscalDateEnding', '')}: EPS ${e.get('reportedEPS', 'N/A')}"
            for e in ann_earnings
        ]) or "N/A"

        # Income statement snippets
        ann_income = (income.get("annualReports") or [{}])[:2]
        rev_str = " | ".join([
            f"{r.get('fiscalDateEnding', '')[:7]}: ${int(r.get('totalRevenue', 0) or 0):,}"
            for r in ann_income if r.get("totalRevenue")
        ]) or "N/A"

        return f"""Perform a COMPREHENSIVE institutional-grade financial analysis for {symbol}.

## Company Overview
Company: {name}
Sector: {sector} | Industry: {industry}
Description: {description}

## Current Market Data
Price: ${price} ({change_pct} today)
Market Cap: ${market_cap}
52-Week Range: ${week_52_low} — ${week_52_high}
Beta: {beta}

## Valuation Multiples
P/E Ratio (TTM): {pe}
Forward P/E: {fwd_pe}
Price/Book: {pb}
Price/Sales: {ps}
EV/EBITDA: {ev_ebitda}

## Profitability
ROE: {roe} | ROA: {roa}
Profit Margin: {profit_margin} | Operating Margin: {op_margin}
Revenue Growth (YoY): {revenue_growth}
Earnings Growth (YoY): {earnings_growth}

## Financial Health
Dividend Yield: {div_yield}

## Historical Revenue
{rev_str}

## Earnings History (Annual EPS)
{earnings_str}

## Technical Signals
RSI (14): {rsi.get('rsi', 'N/A')} (as of {rsi.get('date', 'N/A')})
MACD: {macd.get('macd', 'N/A')} | Signal: {macd.get('signal', 'N/A')} | Histogram: {macd.get('histogram', 'N/A')}

## Analyst Consensus
Target Price: ${analyst_target}
Strong Buy: {strong_buy} | Buy: {buy} | Hold: {hold} | Sell: {sell}

## Additional Context
{context or 'None provided.'}

---

Provide a COMPREHENSIVE investment analysis with these exact sections:

### 1. INVESTMENT RATING & THESIS
Rate: STRONG BUY / BUY / HOLD / SELL / STRONG SELL with conviction level (1-10).
State the core investment thesis in 2-3 sentences.

### 2. VALUATION ANALYSIS
Compare P/E, P/B, P/S, EV/EBITDA vs sector/industry averages.
Run a simple DCF scenario (bull/base/bear) with implied fair value ranges.
Is the stock over/under/fairly valued?

### 3. FUNDAMENTAL ANALYSIS
Deep-dive: revenue quality, margin trajectory, ROE/ROA trends, capital allocation.
What are the key fundamental drivers?

### 4. TECHNICAL ANALYSIS
Interpret RSI and MACD signals. Identify key support/resistance levels based on 52-week range.
Is the technical setup bullish, bearish, or neutral? What patterns are forming?

### 5. EARNINGS QUALITY & GROWTH OUTLOOK
Analyze EPS trend. Assess earnings quality (one-time items, accounting concerns).
Project earnings growth trajectory for next 12-24 months with reasoning.

### 6. COMPETITIVE POSITION & MOAT
Assess the company's competitive advantages (or lack thereof). Who are the primary competitors?
What is the moat rating (wide/narrow/none)?

### 7. RISK MATRIX
List the top 5 risks (bull and bear case breakers). Score each: Probability (Low/Med/High) × Impact (Low/Med/High).

### 8. CATALYST CALENDAR
List 3-5 upcoming catalysts (earnings, product launches, regulatory decisions, macro events) that could move the stock.

### 9. PORTFOLIO SIZING RECOMMENDATION
For a hypothetical balanced portfolio: what % allocation is appropriate? Why?

### 10. ACTION PLAN
Specific, actionable recommendation: price targets (entry/exit/stop-loss), time horizon, and key metrics to monitor.

Be quantitative. Use specific numbers. Be honest about uncertainty."""

    def _build_crypto_prompt(self, coin_id: str, coin_data: dict, market_chart: dict,
                              fear_greed: dict, context: str) -> str:
        mkt = coin_data.get("market_data", {})
        info = coin_data.get("description", {}).get("en", "")[:500]
        name = coin_data.get("name", coin_id)
        symbol = coin_data.get("symbol", "").upper()
        price = mkt.get("current_price", {}).get("usd", "N/A")
        mcap = mkt.get("market_cap", {}).get("usd", "N/A")
        volume = mkt.get("total_volume", {}).get("usd", "N/A")
        rank = coin_data.get("market_cap_rank", "N/A")
        ch_1h = mkt.get("price_change_percentage_1h_in_currency", {}).get("usd", "N/A")
        ch_24h = mkt.get("price_change_percentage_24h", "N/A")
        ch_7d = mkt.get("price_change_percentage_7d", "N/A")
        ch_30d = mkt.get("price_change_percentage_30d", "N/A")
        high_24h = mkt.get("high_24h", {}).get("usd", "N/A")
        low_24h = mkt.get("low_24h", {}).get("usd", "N/A")
        ath = mkt.get("ath", {}).get("usd", "N/A")
        ath_change = mkt.get("ath_change_percentage", {}).get("usd", "N/A")
        circ_supply = mkt.get("circulating_supply", "N/A")
        max_supply = mkt.get("max_supply", "unlimited")
        reddit = coin_data.get("community_data", {}).get("reddit_subscribers", "N/A")
        twitter = coin_data.get("community_data", {}).get("twitter_followers", "N/A")

        # Fear & Greed
        fg_data = (fear_greed.get("data") or [{}])
        fg_now = fg_data[0].get("value", "N/A") if fg_data else "N/A"
        fg_label = fg_data[0].get("value_classification", "N/A") if fg_data else "N/A"

        # Price history summary from chart
        prices = [p[1] for p in (market_chart.get("prices") or [])]
        if prices:
            price_min = min(prices)
            price_max = max(prices)
            price_start = prices[0]
            price_end = prices[-1]
            pct_change_period = ((price_end - price_start) / price_start * 100) if price_start else 0
            chart_str = f"30d: ${price_min:.4f} low / ${price_max:.4f} high | Period return: {pct_change_period:.1f}%"
        else:
            chart_str = "N/A"

        return f"""Perform a COMPREHENSIVE crypto asset intelligence analysis for {name} ({symbol}).

## Asset Overview
Name: {name} ({symbol})
Market Cap Rank: #{rank}
Description: {info}

## Market Data
Price: ${price}
Market Cap: ${mcap}
24h Volume: ${volume}
24h Range: ${low_24h} — ${high_24h}
All-Time High: ${ath} ({ath_change}% from ATH)
Circulating Supply: {circ_supply}
Max Supply: {max_supply}

## Price Performance
1h: {ch_1h}% | 24h: {ch_24h}% | 7d: {ch_7d}% | 30d: {ch_30d}%
30-Day Chart: {chart_str}

## On-Chain & Market Sentiment
Crypto Fear & Greed Index: {fg_now}/100 ({fg_label})
Reddit Subscribers: {reddit}
Twitter Followers: {twitter}

## Additional Context
{context or 'None provided.'}

---

Provide a COMPREHENSIVE crypto intelligence analysis with these exact sections:

### 1. SIGNAL RATING & THESIS
Rate: STRONG BUY / BUY / HOLD / SELL / STRONG SELL.
State the core thesis in 2-3 sentences. Include time horizon (short/mid/long term).

### 2. TOKEN FUNDAMENTALS
Assess: use case, technology, competitive differentiation, tokenomics (supply/demand dynamics),
utility value, inflation/deflation mechanics, team and development activity.

### 3. MARKET STRUCTURE & TECHNICALS
Analyze the 30-day price action. Identify trend (bull/bear/sideways), momentum, key support and
resistance levels. Interpret fear & greed index in context of this asset.

### 4. ON-CHAIN METRICS ANALYSIS
Discuss what circulating vs max supply tells us about future dilution risk.
Analyze volume/market cap ratio for liquidity assessment.

### 5. SENTIMENT & COMMUNITY
Assess community strength (Reddit, Twitter). What is the narrative momentum?
Is this asset driven by fundamentals or speculation?

### 6. COMPETITIVE LANDSCAPE
Who are the direct competitors? How does {name} stack up in terms of tech, adoption, and ecosystem?

### 7. RISK MATRIX
Top 5 crypto-specific risks: regulatory, smart contract, market manipulation, liquidity, competition.
Rate each by probability and potential impact.

### 8. BULL & BEAR SCENARIOS
Bull case: What would drive 3x-10x? What catalysts?
Bear case: What would drive -50% to -90%? What are the failure modes?

### 9. PORTFOLIO ALLOCATION
For a diversified crypto portfolio: what % allocation and position tier (core/satellite/speculative)?

### 10. TACTICAL ACTION PLAN
Entry zones, price targets (3m, 6m, 12m), stop-loss levels, and key metrics to monitor on-chain.

Be direct. Use specific price levels and percentages. Address the meme vs. fundamentals question honestly."""

    def _build_personal_finance_prompt(self, question: str) -> str:
        return f"""A user asks the following personal finance question:

"{question}"

Provide a concise, actionable personal finance answer. Structure it clearly with relevant sections based on the question (e.g., Budgeting, Emergency Fund, Debt Strategy, Investing, Retirement, etc.). Use specific numbers, benchmarks, and examples. Keep it under 600 words unless the question requires depth. Lead with the most actionable advice first."""

    def _build_market_trends_prompt(self, focus: str) -> str:
        return f"""Provide a comprehensive macro market trends analysis.

Focus Area: {focus}

Cover:
### 1. MACRO ENVIRONMENT
Current monetary policy, inflation, interest rate trajectory, GDP outlook.

### 2. SECTOR ROTATION
Which sectors are leading / lagging? Where is institutional money flowing?

### 3. KEY RISKS
Top 3-5 macro risks that could disrupt markets in the next 3-6 months.

### 4. OPPORTUNITIES
Specific actionable themes and tickers that stand to benefit from current trends.

### 5. POSITIONING RECOMMENDATION
How should a diversified investor position their portfolio given the current environment?

Be specific with sector names, ETF tickers, and directional conviction. Use current knowledge of economic conditions."""

    # ── Main Analysis Method ───────────────────────────────────────────────────

    @staticmethod
    def _sanitize_ticker(raw: str) -> tuple:
        """Extract real ticker symbol from messy input like 'TSLA EXIT STRATEGY'.
        Returns (clean_ticker, extra_context).
        """
        import re as _re
        raw = raw.strip().upper()
        # Match standard ticker: 1-5 uppercase letters, optionally with . or -
        match = _re.match(r'^([A-Z]{1,5}(?:[.\-][A-Z]{1,4})?)', raw)
        if match:
            clean = match.group(1)
            extra = raw[len(clean):].strip(" -:,")
            return clean, extra
        # No clean ticker found — return as-is
        return raw, ""

    async def analyze(
        self,
        ticker: str,
        asset_type: str = "stock",  # "stock" | "crypto"
        crypto_id: str = "",
        context: str = "",
    ) -> AsyncGenerator[Dict, None]:
        """Stream a comprehensive financial analysis."""

        # Personal Finance — bypass all ticker/market logic
        if asset_type == "personal_finance":
            question = context or ticker
            yield {"event": "status", "message": "Analyzing your personal finance question..."}
            prompt = self._build_personal_finance_prompt(question)
            messages = [Message(role="user", content=prompt)]
            report_chunks = []
            async for chunk in self.provider.stream(
                messages=messages, system_prompt=EVE_FINANCIAL_PERSONA,
                think=False, max_tokens=8192,
            ):
                if chunk:
                    if chunk.startswith("[THINK]"): pass
                    elif chunk.startswith("[STREAM_ERROR]"):
                        yield {"event": "error", "message": chunk[14:]}; return
                    else:
                        report_chunks.append(chunk)
                        yield {"event": "chunk", "content": chunk}
            yield {"event": "complete", "ticker": "PERSONAL", "asset_type": "personal_finance", "report": "".join(report_chunks)}
            return

        # Market Trends — bypass ticker lookup, run macro analysis
        if asset_type == "market_trends":
            focus = context or "broad market"
            yield {"event": "status", "message": "Running macro market trends analysis..."}
            prompt = self._build_market_trends_prompt(focus)
            messages = [Message(role="user", content=prompt)]
            report_chunks = []
            async for chunk in self.provider.stream(
                messages=messages, system_prompt=EVE_FINANCIAL_PERSONA,
                think=False, max_tokens=8192,
            ):
                if chunk:
                    if chunk.startswith("[THINK]"): pass
                    elif chunk.startswith("[STREAM_ERROR]"):
                        yield {"event": "error", "message": chunk[14:]}; return
                    else:
                        report_chunks.append(chunk)
                        yield {"event": "chunk", "content": chunk}
            yield {"event": "complete", "ticker": "MARKET", "asset_type": "market_trends", "report": "".join(report_chunks)}
            return

        # Sanitize ticker — extract symbol from phrases like "TSLA EXIT STRATEGY"
        if asset_type != "crypto":
            clean_ticker, extra_context = self._sanitize_ticker(ticker)
            if extra_context:
                context = f"{extra_context}. {context}".strip(". ")
            ticker = clean_ticker

        if asset_type == "crypto":
            # Resolve coin_id: explicit ID > known ticker map > CoinGecko search > lowercase fallback
            ticker_upper = ticker.upper()
            if crypto_id:
                coin_id = crypto_id.lower().strip()
            elif ticker_upper in CRYPTO_TICKER_MAP:
                coin_id = CRYPTO_TICKER_MAP[ticker_upper]
            else:
                # Try CoinGecko search to auto-resolve unknown tickers
                coin_id = await self._resolve_coin_id(ticker)

            yield {"event": "status", "message": f"Fetching market data for {ticker.upper()}..."}

            coin_data, market_chart, fear_greed = await asyncio.gather(
                self._get_crypto_data(coin_id),
                self._get_crypto_market_chart(coin_id, days=30),
                self._get_fear_greed(),
            )

            if not coin_data or not coin_data.get("market_data"):
                yield {"event": "error", "message": f"Could not find crypto asset '{ticker.upper()}'. Try entering the CoinGecko ID directly (e.g., 'bitcoin', 'solana', 'bonk')."}
                return

            yield {
                "event": "market_data",
                "price": coin_data.get("market_data", {}).get("current_price", {}).get("usd"),
                "market_cap_rank": coin_data.get("market_cap_rank"),
                "change_24h": coin_data.get("market_data", {}).get("price_change_percentage_24h"),
            }

            yield {"event": "status", "message": "Running AI financial intelligence with qwen3.5:397b-cloud..."}
            prompt = self._build_crypto_prompt(coin_id, coin_data, market_chart, fear_greed, context)

        else:
            # Stock analysis
            yield {"event": "status", "message": f"Fetching fundamentals for {ticker}..."}

            overview, quote, earnings, rsi, macd, income = await asyncio.gather(
                self._get_stock_overview(ticker),
                self._get_stock_quote(ticker),
                self._get_earnings(ticker),
                self._get_rsi(ticker),
                self._get_macd(ticker),
                self._get_income_statement(ticker),
            )

            if not overview and not quote:
                # No API key — still run analysis with just ticker + context
                yield {"event": "status", "message": "No Alpha Vantage key — running analysis from AI knowledge..."}

            if quote:
                yield {
                    "event": "market_data",
                    "price": quote.get("05. price"),
                    "change_pct": quote.get("10. change percent"),
                    "volume": quote.get("06. volume"),
                }

            yield {"event": "status", "message": "Running AI financial intelligence with qwen3.5:397b-cloud..."}
            prompt = self._build_stock_prompt(ticker, overview, quote, earnings, rsi, macd, income, context)

        messages = [Message(role="user", content=prompt)]
        report_chunks = []

        async for chunk in self.provider.stream(
            messages=messages,
            system_prompt=EVE_FINANCIAL_PERSONA,
            think=False,
            max_tokens=8192,
        ):
            if chunk:
                if chunk.startswith("[THINK]"):
                    pass  # discard
                elif chunk.startswith("[STREAM_ERROR]"):
                    yield {"event": "error", "message": chunk[14:]}
                    return
                else:
                    report_chunks.append(chunk)
                    yield {"event": "chunk", "content": chunk}

        yield {
            "event": "complete",
            "ticker": ticker,
            "asset_type": asset_type,
            "report": "".join(report_chunks),
        }
