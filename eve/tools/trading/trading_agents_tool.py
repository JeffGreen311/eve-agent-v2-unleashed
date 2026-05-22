"""
TradingAgents Tool — Multi-agent stock research pipeline
=========================================================
Wraps TauricResearch/TradingAgents with Ollama Cloud (qwen3.5:397b-cloud).

Pipeline:
  4 Analysts (technical, news, fundamentals, social)
  → Bull vs Bear researcher debate
  → Research Manager → Trader
  → Risk Debate (aggressive / conservative / neutral)
  → Risk Manager → BUY / SELL / HOLD

Data: Yahoo Finance (live, no API key required)
LLM: Ollama Cloud via OpenAI-compat endpoint
"""

import logging
import os
from datetime import date as _date
from typing import Any, Dict, List, Optional

from eve.tools.base import Tool

logger = logging.getLogger(__name__)

VALID_ANALYSTS = {"market", "news", "fundamentals", "social"}


def _fetch_live_snapshot(ticker: str, trade_date: str) -> str:
    """Pre-fetch live yfinance data as a grounded market snapshot header."""
    try:
        import yfinance as yf
        from datetime import datetime

        t = yf.Ticker(ticker)
        info = t.info

        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose", "N/A")
        prev_close = info.get("previousClose", "N/A")
        open_price = info.get("open", "N/A")
        day_high = info.get("dayHigh", "N/A")
        day_low = info.get("dayLow", "N/A")
        week52_high = info.get("fiftyTwoWeekHigh", "N/A")
        week52_low = info.get("fiftyTwoWeekLow", "N/A")
        volume = info.get("volume", info.get("regularMarketVolume", "N/A"))
        avg_vol = info.get("averageVolume", "N/A")
        market_cap = info.get("marketCap", "N/A")
        pe_ratio = info.get("trailingPE", "N/A")
        fwd_pe = info.get("forwardPE", "N/A")
        eps = info.get("trailingEps", "N/A")
        revenue = info.get("totalRevenue", "N/A")
        gross_margin = info.get("grossMargins", "N/A")
        short_name = info.get("shortName", ticker)
        sector = info.get("sector", "N/A")
        industry = info.get("industryDisp", info.get("industry", "N/A"))
        analyst_target = info.get("targetMeanPrice", "N/A")
        recommendation = info.get("recommendationKey", "N/A").upper()

        def fmt_num(n):
            if n == "N/A" or n is None:
                return "N/A"
            if isinstance(n, float) and n > 1e9:
                return f"${n/1e9:.2f}B"
            if isinstance(n, float) and n > 1e6:
                return f"${n/1e6:.1f}M"
            if isinstance(n, float):
                return f"{n:.2f}"
            return str(n)

        def fmt_pct(n):
            if n == "N/A" or n is None:
                return "N/A"
            return f"{float(n)*100:.1f}%"

        lines = [
            f"## LIVE MARKET SNAPSHOT — {ticker} ({short_name})",
            f"**Data retrieved: {trade_date} (live via yfinance)**",
            f"> This analysis uses real-time data as of {trade_date}. All price levels below are CURRENT.",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Current Price | ${fmt_num(price)} |",
            f"| Prev Close | ${fmt_num(prev_close)} |",
            f"| Today Open | ${fmt_num(open_price)} |",
            f"| Day Range | ${fmt_num(day_low)} – ${fmt_num(day_high)} |",
            f"| 52-Week Range | ${fmt_num(week52_low)} – ${fmt_num(week52_high)} |",
            f"| Volume | {fmt_num(volume)} (avg: {fmt_num(avg_vol)}) |",
            f"| Market Cap | {fmt_num(market_cap)} |",
            f"| Trailing P/E | {fmt_num(pe_ratio)} |",
            f"| Forward P/E | {fmt_num(fwd_pe)} |",
            f"| EPS (TTM) | ${fmt_num(eps)} |",
            f"| Revenue | {fmt_num(revenue)} |",
            f"| Gross Margin | {fmt_pct(gross_margin)} |",
            f"| Analyst Target | ${fmt_num(analyst_target)} |",
            f"| Analyst Rating | {recommendation} |",
            f"| Sector | {sector} |",
            f"| Industry | {industry} |",
            "",
        ]
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Live snapshot fetch failed for {ticker}: {e}")
        return f"## {ticker} — {trade_date}\n*Live snapshot unavailable: {e}*\n"


def _get_trading_config() -> Dict[str, Any]:
    from tradingagents.default_config import DEFAULT_CONFIG

    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    deep_model = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
    # quick_think_llm runs all analyst steps — use a fast cloud model to avoid local bottleneck
    quick_model = os.getenv("OLLAMA_QUICK_MODEL", "gpt-oss:20b-cloud")

    return {
        **DEFAULT_CONFIG,
        "llm_provider": "openai",          # OpenAI-compat mode → uses backend_url
        "deep_think_llm": deep_model,      # cloud model for final synthesis/decision
        "quick_think_llm": quick_model,    # fast local model for analyst steps
        "backend_url": f"{ollama_base}/v1",
        "max_debate_rounds": 1,
        "max_risk_discuss_rounds": 1,
        "max_recur_limit": 100,
        "data_vendors": {
            "core_stock_apis": "yfinance",
            "technical_indicators": "yfinance",
            "fundamental_data": "yfinance",
            "news_data": "yfinance",
        },
    }


def _run_analysis_sync(ticker: str, trade_date: str, analysts: List[str]) -> Dict[str, Any]:
    """Synchronous execution — run in thread pool from async context."""
    # langchain_openai needs OPENAI_API_KEY set; "ollama" is the dummy value
    os.environ.setdefault("OPENAI_API_KEY", "ollama")

    # Pre-fetch live data FIRST — anchors the report to today's real prices
    live_snapshot = _fetch_live_snapshot(ticker, trade_date)

    from tradingagents.graph.trading_graph import TradingAgentsGraph

    config = _get_trading_config()
    ta = TradingAgentsGraph(selected_analysts=analysts, debug=False, config=config)
    state, decision = ta.propagate(ticker, trade_date)

    market_report       = state.get("market_report", "") or ""
    sentiment_report    = state.get("sentiment_report", "") or ""
    news_report         = state.get("news_report", "") or ""
    fundamentals_report = state.get("fundamentals_report", "") or ""
    final_decision      = state.get("final_trade_decision", "") or ""

    # Live snapshot always leads — prevents stale training-data hallucinations
    lines = [live_snapshot, f"**Multi-Agent Signal: {decision}**", ""]
    if market_report:
        lines += ["### Technical Analysis", market_report[:1000], ""]
    if news_report:
        lines += ["### News Analysis", news_report[:800], ""]
    if sentiment_report:
        lines += ["### Sentiment", sentiment_report[:600], ""]
    if fundamentals_report:
        lines += ["### Fundamentals", fundamentals_report[:800], ""]
    if final_decision:
        lines += ["### Trading Decision", final_decision[:800], ""]

    return {
        "success": True,
        "signal": decision,
        "ticker": ticker,
        "date": trade_date,
        "output": "\n".join(lines),
        "reports": {
            "market": market_report,
            "news": news_report,
            "sentiment": sentiment_report,
            "fundamentals": fundamentals_report,
            "decision": final_decision,
        },
    }


class StockAnalysisTool(Tool):
    name = "stock_analysis"
    description = (
        "Run a deep multi-agent stock research pipeline on any publicly traded ticker. "
        "Four specialist analysts (technical, news, fundamentals, social sentiment) feed "
        "into a bull vs. bear debate, then a risk management review, producing a final "
        "BUY / SELL / HOLD signal with full supporting analysis. "
        "Live market data (current price, P/E, 52-week range, etc.) is fetched first "
        "and anchors the entire analysis to today's real figures.\n\n"
        "Parameters:\n"
        "  ticker: Stock symbol (e.g. NVDA, AAPL, TSLA, SPY)\n"
        "  date: Analysis date YYYY-MM-DD (defaults to today)\n"
        "  analysts: Subset of analysts to run — market, news, fundamentals, social "
        "(defaults to all four)\n\n"
        "Note: This runs multiple LLM calls and takes 1-3 minutes. Returns the signal "
        "immediately when done."
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g. NVDA, AAPL, TSLA)",
                },
                "date": {
                    "type": "string",
                    "description": "Analysis date YYYY-MM-DD. Defaults to today.",
                },
                "analysts": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["market", "news", "fundamentals", "social"]},
                    "description": "Which analysts to include. Default: all four.",
                },
            },
            "required": ["ticker"],
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        import asyncio

        ticker: str = kwargs.get("ticker", "").upper().strip()
        trade_date: str = kwargs.get("date") or _date.today().isoformat()
        analysts_raw = kwargs.get("analysts") or ["market", "news", "fundamentals", "social"]
        analysts = [a for a in analysts_raw if a in VALID_ANALYSTS] or ["market", "news", "fundamentals", "social"]

        if not ticker:
            return {"success": False, "output": "ticker is required"}

        logger.info(f"StockAnalysisTool: running {ticker} on {trade_date} with {analysts}")

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _run_analysis_sync, ticker, trade_date, analysts)
            logger.info(f"StockAnalysisTool: {ticker} → {result.get('signal')}")
            return result
        except Exception as e:
            logger.error(f"StockAnalysisTool failed [{ticker}]: {e}")
            return {"success": False, "output": f"Analysis failed: {e}"}
