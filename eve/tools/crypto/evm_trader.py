"""
EVM DeFi Trader — 0x Protocol
================================
Routes swaps through 0x Protocol's DEX aggregator.
Supports: Ethereum (1), Base (8453), Arbitrum (42161), BSC (56)
"""

import logging
from typing import Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class EVMTrader:
    """EVM swap execution via 0x Protocol + eth_sendRawTransaction."""

    CHAIN_IDS: Dict[str, int] = {
        "ethereum": 1,
        "base": 8453,
        "arbitrum": 42161,
        "bsc": 56,
    }

    # Public RPC endpoints (no API key required)
    RPC_URLS: Dict[str, str] = {
        "ethereum": "https://cloudflare-eth.com",
        "base": "https://mainnet.base.org",
        "arbitrum": "https://arb1.arbitrum.io/rpc",
        "bsc": "https://bsc-dataseed.binance.org",
    }

    # 0x API v2 with chain-specific subdomains
    ZERO_EX_BASE: Dict[str, str] = {
        "ethereum": "https://api.0x.org",
        "base": "https://base.api.0x.org",
        "arbitrum": "https://arbitrum.api.0x.org",
        "bsc": "https://bsc.api.0x.org",
    }

    # Common token addresses per chain
    WETH: Dict[str, str] = {
        "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "base": "0x4200000000000000000000000000000000000006",
        "arbitrum": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "bsc": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
    }

    def __init__(self, zero_ex_api_key: str = ""):
        self.zero_ex_api_key = zero_ex_api_key

    def _resolve_token(self, symbol_or_address: str, chain: str) -> str:
        """Resolve common symbol to address or return as-is if already an address."""
        if symbol_or_address.startswith("0x"):
            return symbol_or_address
        sym = symbol_or_address.upper()
        if sym in ("ETH", "BNB"):
            return "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"  # 0x native token alias
        if sym in ("WETH", "WBNB"):
            return self.WETH.get(chain, self.WETH["ethereum"])
        if sym == "USDC":
            usdc = {
                "ethereum": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "base": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "arbitrum": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
                "bsc": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            }
            return usdc.get(chain, usdc["ethereum"])
        # Unknown symbol — return as-is and hope the model provided an address
        return symbol_or_address

    async def get_quote(
        self,
        sell_token: str,
        buy_token: str,
        sell_amount_wei: int,
        chain: str = "base",
        taker_address: Optional[str] = None,
    ) -> dict:
        """
        Fetch a swap quote from 0x Protocol.
        Returns the full quote response or raises on failure.
        """
        if chain not in self.CHAIN_IDS:
            raise ValueError(f"Unsupported chain: {chain}. Use: {list(self.CHAIN_IDS)}")

        sell_addr = self._resolve_token(sell_token, chain)
        buy_addr = self._resolve_token(buy_token, chain)
        base_url = self.ZERO_EX_BASE.get(chain, self.ZERO_EX_BASE["ethereum"])

        params = {
            "sellToken": sell_addr,
            "buyToken": buy_addr,
            "sellAmount": str(sell_amount_wei),
            "chainId": self.CHAIN_IDS[chain],
        }
        if taker_address:
            params["takerAddress"] = taker_address

        headers = {"0x-api-key": self.zero_ex_api_key} if self.zero_ex_api_key else {}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{base_url}/swap/v1/quote",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    raise RuntimeError(f"0x API error {resp.status}: {data.get('reason', data)}")
                return data

    async def execute_swap(
        self,
        private_key: str,
        sell_token: str,
        buy_token: str,
        sell_amount_usd: float,
        chain: str = "base",
        eth_price_usd: float = 3000.0,  # Approximate ETH price for USD → wei conversion
        slippage_pct: float = 1.0,
    ) -> dict:
        """
        Execute a swap: get quote → sign tx → broadcast.
        Returns {"tx_hash": "0x...", "chain": ..., "sell_token": ..., "buy_token": ..., "amount_usd": ...}
        """
        from eth_account import Account

        if chain not in self.RPC_URLS:
            raise ValueError(f"Unsupported chain: {chain}")

        # Convert USD to wei (approximate; real amount from quote)
        # Assume sell token is native (ETH/BNB) for simplicity
        # If sell token is a stablecoin, multiply by token decimals
        sell_amount_wei = int((sell_amount_usd / eth_price_usd) * 10**18)

        sell_addr = self._resolve_token(sell_token, chain)
        quote = await self.get_quote(sell_addr, buy_token, sell_amount_wei, chain)

        tx = {
            "to": quote["to"],
            "data": quote["data"],
            "value": int(quote.get("value", 0)),
            "gasPrice": int(quote.get("gasPrice", 0)),
            "gas": int(int(quote.get("estimatedGas", 200_000)) * 1.2),  # 20% buffer
            "chainId": self.CHAIN_IDS[chain],
            "nonce": await self._get_nonce(Account.from_key(private_key).address, chain),
        }

        acct = Account.from_key(private_key)
        signed = acct.sign_transaction(tx)
        tx_hash = await self._broadcast(signed.raw_transaction, chain)

        buy_amount = int(quote.get("buyAmount", 0))
        buy_token_addr = quote.get("buyTokenAddress", buy_token)

        logger.info(f"EVM swap executed: {sell_token} → {buy_token} on {chain} | tx: {tx_hash}")
        return {
            "success": True,
            "tx_hash": tx_hash,
            "chain": chain,
            "sell_token": sell_token,
            "buy_token": buy_token,
            "sell_amount_wei": sell_amount_wei,
            "buy_amount_raw": buy_amount,
            "amount_usd": sell_amount_usd,
            "explorer": f"https://{'basescan.org' if chain == 'base' else 'etherscan.io'}/tx/{tx_hash}",
        }

    async def _get_nonce(self, address: str, chain: str) -> int:
        rpc = self.RPC_URLS[chain]
        payload = {"jsonrpc": "2.0", "method": "eth_getTransactionCount",
                   "params": [address, "pending"], "id": 1}
        async with aiohttp.ClientSession() as session:
            async with session.post(rpc, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                return int(data["result"], 16)

    async def _broadcast(self, raw_tx: bytes, chain: str) -> str:
        import binascii
        rpc = self.RPC_URLS[chain]
        hex_tx = "0x" + binascii.hexlify(raw_tx).decode()
        payload = {"jsonrpc": "2.0", "method": "eth_sendRawTransaction",
                   "params": [hex_tx], "id": 1}
        async with aiohttp.ClientSession() as session:
            async with session.post(rpc, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json()
                if "error" in data:
                    raise RuntimeError(f"Broadcast failed: {data['error']}")
                return data["result"]

    async def get_balance(self, address: str, chain: str = "base") -> dict:
        """Fetch native token balance (ETH/BNB) in wei and formatted."""
        rpc = self.RPC_URLS.get(chain, self.RPC_URLS["base"])
        payload = {"jsonrpc": "2.0", "method": "eth_getBalance",
                   "params": [address, "latest"], "id": 1}
        async with aiohttp.ClientSession() as session:
            async with session.post(rpc, json=payload,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                wei = int(data["result"], 16)
                eth = wei / 10**18
                symbol = "BNB" if chain == "bsc" else "ETH"
                return {"wei": wei, "formatted": f"{eth:.6f} {symbol}", "chain": chain}
