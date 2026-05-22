"""
Solana DeFi Trader — Jupiter v6 Aggregator
===========================================
Routes swaps through Jupiter's DEX aggregator on Solana mainnet.
Handles quote → swap transaction → sign → broadcast.
"""

import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# Common Solana token mint addresses
COMMON_MINTS = {
    "SOL": "So11111111111111111111111111111111111111112",      # Wrapped SOL
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",   # dogwifhat
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",   # Jupiter
    "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",  # Pyth
    "RNDR": "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",   # Render
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",   # Raydium
    "ORCA": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",   # Orca
}

LAMPORTS_PER_SOL = 1_000_000_000


class SolanaTrader:
    """Solana swap execution via Jupiter v6 aggregator."""

    JUPITER_QUOTE = "https://quote-api.jup.ag/v6/quote"
    JUPITER_SWAP = "https://quote-api.jup.ag/v6/swap"
    SOLANA_RPC = "https://api.mainnet-beta.solana.com"

    def _resolve_mint(self, symbol_or_mint: str) -> str:
        """Resolve common symbol to mint address or return as-is."""
        if len(symbol_or_mint) > 20:
            return symbol_or_mint  # Already a mint address
        upper = symbol_or_mint.upper()
        return COMMON_MINTS.get(upper, symbol_or_mint)

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount_lamports: int,
        slippage_bps: int = 50,
    ) -> dict:
        """
        Fetch a swap quote from Jupiter v6.
        slippage_bps: basis points (50 = 0.5%)
        Returns the full quote response or raises on failure.
        """
        in_mint = self._resolve_mint(input_mint)
        out_mint = self._resolve_mint(output_mint)

        params = {
            "inputMint": in_mint,
            "outputMint": out_mint,
            "amount": str(amount_lamports),
            "slippageBps": slippage_bps,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.JUPITER_QUOTE,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    raise RuntimeError(f"Jupiter quote error {resp.status}: {data}")
                return data

    async def get_swap_transaction(
        self,
        quote: dict,
        user_public_key: str,
        priority_fee_lamports: int = 5000,
    ) -> str:
        """
        Convert a Jupiter quote into a base64-encoded transaction.
        Returns the transaction ready for signing.
        """
        payload = {
            "quoteResponse": quote,
            "userPublicKey": user_public_key,
            "wrapAndUnwrapSol": True,
            "prioritizationFeeLamports": priority_fee_lamports,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.JUPITER_SWAP,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    raise RuntimeError(f"Jupiter swap error {resp.status}: {data}")
                return data["swapTransaction"]  # base64 encoded

    async def execute_swap(
        self,
        keypair_bytes: bytes,
        input_token: str,
        output_token: str,
        amount_usd: float,
        sol_price_usd: float = 200.0,
        slippage_bps: int = 50,
    ) -> dict:
        """
        Execute a full Solana swap: quote → get tx → sign → broadcast.
        Returns {tx_signature, input_token, output_token, amount_usd, ...}
        """
        from solders.keypair import Keypair  # type: ignore
        from solders.transaction import VersionedTransaction  # type: ignore
        import base64

        keypair = Keypair.from_bytes(keypair_bytes)
        public_key = str(keypair.pubkey())

        in_mint = self._resolve_mint(input_token)
        out_mint = self._resolve_mint(output_token)

        # Convert USD to lamports (assuming input is SOL)
        # If input is a stablecoin, use 1e6 decimals instead
        is_sol_input = input_token.upper() in ("SOL", "WSOL")
        if is_sol_input:
            amount_lamports = int((amount_usd / sol_price_usd) * LAMPORTS_PER_SOL)
        else:
            # Assume USDC/USDT with 6 decimals
            amount_lamports = int(amount_usd * 1_000_000)

        quote = await self.get_quote(in_mint, out_mint, amount_lamports, slippage_bps)
        swap_tx_b64 = await self.get_swap_transaction(quote, public_key)

        # Decode → deserialize → sign → re-serialize
        raw_bytes = base64.b64decode(swap_tx_b64)
        tx = VersionedTransaction.from_bytes(raw_bytes)
        signed_tx = keypair.sign_message(bytes(tx.message))

        # Rebuild with signature
        signed_bytes = bytes(VersionedTransaction([signed_tx], tx.message))
        tx_b64 = base64.b64encode(signed_bytes).decode("utf-8")

        # Broadcast
        signature = await self._broadcast(tx_b64)

        out_amount = int(quote.get("outAmount", 0))
        price_impact = float(quote.get("priceImpactPct", 0))

        logger.info(f"Solana swap: {input_token} → {output_token} | sig: {signature}")
        return {
            "success": True,
            "tx_signature": signature,
            "explorer": f"https://solscan.io/tx/{signature}",
            "input_token": input_token,
            "output_token": output_token,
            "amount_usd": amount_usd,
            "amount_lamports": amount_lamports,
            "out_amount_raw": out_amount,
            "price_impact_pct": price_impact,
            "slippage_bps": slippage_bps,
        }

    async def _broadcast(self, tx_b64: str) -> str:
        """Send signed base64 transaction to Solana RPC."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                tx_b64,
                {
                    "encoding": "base64",
                    "skipPreflight": False,
                    "preflightCommitment": "confirmed",
                    "maxRetries": 3,
                },
            ],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.SOLANA_RPC,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                data = await resp.json()
                if "error" in data:
                    raise RuntimeError(f"Solana broadcast failed: {data['error']}")
                return data["result"]

    async def get_balance(self, public_key: str) -> dict:
        """Fetch SOL balance for an address."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [public_key, {"commitment": "confirmed"}],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.SOLANA_RPC,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                lamports = data.get("result", {}).get("value", 0)
                sol = lamports / LAMPORTS_PER_SOL
                return {
                    "lamports": lamports,
                    "formatted": f"{sol:.6f} SOL",
                    "chain": "solana",
                }

    async def get_token_balances(self, public_key: str) -> list:
        """Fetch SPL token balances for an address."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                public_key,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"},
            ],
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.SOLANA_RPC,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                accounts = data.get("result", {}).get("value", [])
                balances = []
                for acc in accounts:
                    info = acc.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                    mint = info.get("mint", "")
                    ui_amount = info.get("tokenAmount", {}).get("uiAmountString", "0")
                    if float(ui_amount) > 0:
                        symbol = next(
                            (k for k, v in COMMON_MINTS.items() if v == mint), mint[:8] + "..."
                        )
                        balances.append({"symbol": symbol, "mint": mint, "amount": ui_amount})
                return balances
