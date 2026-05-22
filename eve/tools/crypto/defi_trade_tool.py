"""
DeFi Trade Tool — Agent-callable wrapper
=========================================
Wraps EVMTrader + SolanaTrader into an Eve Tool subclass.
Enforces permission checks, daily limits, and quote confirmation flow.
"""

import logging
from typing import Any, Dict, Optional

from eve.tools.base import Tool
from .wallet_manager import WalletManager
from .evm_trader import EVMTrader
from .solana_trader import SolanaTrader

logger = logging.getLogger(__name__)

EVM_CHAINS = {"ethereum", "base", "arbitrum", "bsc"}
SOLANA_CHAINS = {"solana"}


class DeFiTradeTool(Tool):
    name = "defi_trade"
    description = (
        "Execute a DeFi or meme coin token swap on behalf of the user using their connected "
        "crypto wallet. Requires agent_trading_enabled = True in user settings. "
        "First call returns a quote for confirmation. Call again with confirmed=True to execute.\n\n"
        "Parameters:\n"
        "  chain: ethereum | base | arbitrum | bsc | solana\n"
        "  sell_token: token symbol (ETH, SOL, USDC) or contract/mint address\n"
        "  buy_token: token symbol or contract/mint address\n"
        "  amount_usd: USD value to sell (subject to per-trade and daily limits)\n"
        "  confirmed: set True to execute after reviewing the quote (default False)"
    )

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "chain": {
                    "type": "string",
                    "enum": ["ethereum", "base", "arbitrum", "bsc", "solana"],
                    "description": "Blockchain network for the swap",
                },
                "sell_token": {
                    "type": "string",
                    "description": "Token to sell (symbol or address/mint)",
                },
                "buy_token": {
                    "type": "string",
                    "description": "Token to buy (symbol or address/mint)",
                },
                "amount_usd": {
                    "type": "number",
                    "description": "USD value to sell",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "Set True after reviewing the quote to execute the trade",
                },
                "wallet_password": {
                    "type": "string",
                    "description": "Wallet decryption password (required to execute)",
                },
            },
            "required": ["chain", "sell_token", "buy_token", "amount_usd"],
        }

    def __init__(self, wallet_manager: WalletManager, settings_manager: Any):
        self._wallet = wallet_manager
        self._settings = settings_manager
        self._evm = EVMTrader()
        self._sol = SolanaTrader()

    async def execute(self, **kwargs) -> Dict[str, Any]:
        chain: str = kwargs.get("chain", "base").lower()
        sell_token: str = kwargs.get("sell_token", "")
        buy_token: str = kwargs.get("buy_token", "")
        amount_usd: float = float(kwargs.get("amount_usd", 0))
        confirmed: bool = kwargs.get("confirmed", False)
        password: Optional[str] = kwargs.get("wallet_password")

        if not sell_token or not buy_token or amount_usd <= 0:
            return {"success": False, "output": "Missing required fields: chain, sell_token, buy_token, amount_usd"}

        settings = self._settings.get()

        # Permission gate
        try:
            self._wallet.check_trade_permission(amount_usd, settings)
        except PermissionError as e:
            return {"success": False, "output": str(e)}

        # Chain routing
        if chain in EVM_CHAINS:
            return await self._handle_evm(
                chain, sell_token, buy_token, amount_usd, confirmed, password, settings
            )
        elif chain in SOLANA_CHAINS:
            return await self._handle_solana(
                sell_token, buy_token, amount_usd, confirmed, password, settings
            )
        else:
            return {"success": False, "output": f"Unsupported chain: {chain}. Choose from: ethereum, base, arbitrum, bsc, solana"}

    # ──────────────────────────────────────────────────────────────────────────
    # EVM path
    # ──────────────────────────────────────────────────────────────────────────

    async def _handle_evm(
        self, chain, sell_token, buy_token, amount_usd, confirmed, password, settings
    ) -> Dict[str, Any]:
        wallet_cfg = settings.get("wallet", {})

        if not wallet_cfg.get("evm_connected"):
            return {"success": False, "output": "No EVM wallet connected. Ask the user to connect a wallet in the Wallet tab."}

        if chain not in wallet_cfg.get("allowed_chains", ["base"]):
            return {"success": False, "output": f"Chain '{chain}' is not in the user's allowed chains: {wallet_cfg.get('allowed_chains')}"}

        # Quote-only (first call)
        if not confirmed:
            try:
                sell_addr = self._evm._resolve_token(sell_token, chain)
                eth_price = 3000.0
                sell_wei = int((amount_usd / eth_price) * 10**18)
                quote = await self._evm.get_quote(sell_addr, buy_token, sell_wei, chain)
                buy_amount_raw = int(quote.get("buyAmount", 0))
                price = quote.get("price", "N/A")
                return {
                    "success": True,
                    "requires_confirmation": True,
                    "output": (
                        f"**Trade Quote — {chain.upper()}**\n"
                        f"Selling ~${amount_usd:.2f} of {sell_token}\n"
                        f"Buying {buy_token} at price: {price}\n"
                        f"Estimated output: {buy_amount_raw} (raw units)\n\n"
                        f"To confirm execution, call `defi_trade` again with `confirmed=True` and your `wallet_password`."
                    ),
                }
            except Exception as e:
                return {"success": False, "output": f"Quote failed: {e}"}

        # Execute
        if not password:
            return {"success": False, "output": "wallet_password is required to execute a trade."}

        try:
            private_key = self._wallet.decrypt_evm_key(password)
        except Exception as e:
            return {"success": False, "output": f"Wallet decryption failed: {e}"}

        try:
            result = await self._evm.execute_swap(
                private_key=private_key,
                sell_token=sell_token,
                buy_token=buy_token,
                sell_amount_usd=amount_usd,
                chain=chain,
            )
            self._wallet.record_trade(amount_usd, self._settings)
            return {
                "success": True,
                "output": (
                    f"**Swap Executed on {chain.upper()}**\n"
                    f"{sell_token} → {buy_token} | ${amount_usd:.2f}\n"
                    f"TX Hash: `{result['tx_hash']}`\n"
                    f"Explorer: {result['explorer']}"
                ),
            }
        except Exception as e:
            logger.error(f"EVM swap failed: {e}")
            return {"success": False, "output": f"Swap failed: {e}"}

    # ──────────────────────────────────────────────────────────────────────────
    # Solana path
    # ──────────────────────────────────────────────────────────────────────────

    async def _handle_solana(
        self, sell_token, buy_token, amount_usd, confirmed, password, settings
    ) -> Dict[str, Any]:
        wallet_cfg = settings.get("wallet", {})

        if not wallet_cfg.get("solana_connected"):
            return {"success": False, "output": "No Solana wallet connected. Ask the user to connect a wallet in the Wallet tab."}

        if "solana" not in wallet_cfg.get("allowed_chains", ["solana"]):
            return {"success": False, "output": "Solana chain is not in the user's allowed chains."}

        in_mint = self._sol._resolve_mint(sell_token)
        out_mint = self._sol._resolve_mint(buy_token)

        # Quote only
        if not confirmed:
            try:
                sol_price = 200.0
                is_sol = sell_token.upper() in ("SOL", "WSOL")
                lamports = (
                    int((amount_usd / sol_price) * 1_000_000_000)
                    if is_sol
                    else int(amount_usd * 1_000_000)
                )
                quote = await self._sol.get_quote(in_mint, out_mint, lamports)
                out_amount = int(quote.get("outAmount", 0))
                impact = float(quote.get("priceImpactPct", 0))
                return {
                    "success": True,
                    "requires_confirmation": True,
                    "output": (
                        f"**Trade Quote — SOLANA**\n"
                        f"Selling ~${amount_usd:.2f} of {sell_token}\n"
                        f"Buying {buy_token}\n"
                        f"Estimated output: {out_amount} (raw units)\n"
                        f"Price impact: {impact:.4f}%\n\n"
                        f"To confirm execution, call `defi_trade` again with `confirmed=True` and your `wallet_password`."
                    ),
                }
            except Exception as e:
                return {"success": False, "output": f"Quote failed: {e}"}

        # Execute
        if not password:
            return {"success": False, "output": "wallet_password is required to execute a trade."}

        try:
            keypair_bytes = self._wallet.decrypt_solana_keypair(password)
        except Exception as e:
            return {"success": False, "output": f"Wallet decryption failed: {e}"}

        try:
            kp_bytes = bytes(keypair_bytes)
            result = await self._sol.execute_swap(
                keypair_bytes=kp_bytes,
                input_token=sell_token,
                output_token=buy_token,
                amount_usd=amount_usd,
            )
            self._wallet.record_trade(amount_usd, self._settings)
            return {
                "success": True,
                "output": (
                    f"**Swap Executed on SOLANA**\n"
                    f"{sell_token} → {buy_token} | ${amount_usd:.2f}\n"
                    f"Signature: `{result['tx_signature']}`\n"
                    f"Explorer: {result['explorer']}"
                ),
            }
        except Exception as e:
            logger.error(f"Solana swap failed: {e}")
            return {"success": False, "output": f"Swap failed: {e}"}
