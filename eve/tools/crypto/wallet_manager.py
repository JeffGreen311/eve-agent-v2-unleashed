"""
DeFi Wallet Manager
====================
AES-256-GCM encrypted key vault for EVM and Solana wallets.
Private keys are NEVER written to disk unencrypted.
Keys exist in memory only during active trade execution.
"""

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class WalletError(Exception):
    """Raised for wallet operation failures."""


class WalletManager:
    """
    Encrypted wallet vault + agent trading permission guard.

    Encryption: PBKDF2-HMAC-SHA256 (100k iterations) → 32-byte AES key → AES-256-GCM.
    Storage: eve_data/wallets/{evm|sol}.enc  (JSON: {salt, nonce, tag, ciphertext} as hex)
    """

    def __init__(self, data_dir: str = "./eve_data"):
        self.wallet_dir = Path(data_dir) / "wallets"
        self.wallet_dir.mkdir(parents=True, exist_ok=True)
        self._evm_file = self.wallet_dir / "evm.enc"
        self._sol_file = self.wallet_dir / "sol.enc"
        self._settings_ref = None  # Set by server after init

    # ── Encryption helpers ────────────────────────────────────────────────────

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """PBKDF2 key derivation → 32-byte AES key."""
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        return kdf.derive(password.encode("utf-8"))

    @staticmethod
    def _encrypt(plaintext: bytes, password: str) -> dict:
        """AES-256-GCM encrypt. Returns dict with hex-encoded salt/nonce/tag/ciphertext."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        salt = os.urandom(32)
        nonce = os.urandom(12)
        key = WalletManager._derive_key(password, salt)
        aes = AESGCM(key)
        ct = aes.encrypt(nonce, plaintext, None)
        return {
            "salt": salt.hex(),
            "nonce": nonce.hex(),
            "ciphertext": ct.hex(),
        }

    @staticmethod
    def _decrypt(enc_dict: dict, password: str) -> bytes:
        """AES-256-GCM decrypt. Raises WalletError on wrong password."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.exceptions import InvalidTag
        salt = bytes.fromhex(enc_dict["salt"])
        nonce = bytes.fromhex(enc_dict["nonce"])
        ct = bytes.fromhex(enc_dict["ciphertext"])
        key = WalletManager._derive_key(password, salt)
        aes = AESGCM(key)
        try:
            return aes.decrypt(nonce, ct, None)
        except InvalidTag:
            raise WalletError("Wrong password — decryption failed.")

    # ── EVM wallet ────────────────────────────────────────────────────────────

    def setup_evm_wallet(self, private_key: str, password: str) -> dict:
        """
        Validate EVM private key, encrypt, and store.
        Returns {"address": "0x...", "connected": True}
        """
        from eth_account import Account
        key = private_key.strip()
        if not key.startswith("0x"):
            key = "0x" + key
        try:
            acct = Account.from_key(key)
        except Exception as e:
            raise WalletError(f"Invalid EVM private key: {e}")

        enc = self._encrypt(key.encode("utf-8"), password)
        enc["address"] = acct.address
        self._evm_file.write_text(json.dumps(enc))
        logger.info(f"EVM wallet connected: {acct.address}")
        return {"address": acct.address, "connected": True}

    def decrypt_evm_key(self, password: str) -> str:
        """Decrypt and return raw EVM private key (hex string with 0x prefix)."""
        if not self._evm_file.exists():
            raise WalletError("No EVM wallet configured.")
        enc = json.loads(self._evm_file.read_text())
        raw = self._decrypt(enc, password)
        return raw.decode("utf-8")

    def get_evm_address(self) -> Optional[str]:
        if not self._evm_file.exists():
            return None
        try:
            return json.loads(self._evm_file.read_text()).get("address")
        except Exception:
            return None

    def remove_evm_wallet(self):
        if self._evm_file.exists():
            self._evm_file.unlink()
        logger.info("EVM wallet removed")

    # ── Solana wallet ─────────────────────────────────────────────────────────

    def setup_solana_wallet(self, private_key_b58: str, password: str) -> dict:
        """
        Validate Solana private key (base58 secret key), encrypt, and store.
        Returns {"address": "...", "connected": True}
        """
        from solders.keypair import Keypair
        key = private_key_b58.strip()
        try:
            if len(key) == 88 or len(key) == 87:
                # base58-encoded 64-byte secret key
                import base58
                secret_bytes = base58.b58decode(key)
                keypair = Keypair.from_bytes(secret_bytes)
            elif key.startswith("["):
                # JSON byte array format
                byte_list = json.loads(key)
                keypair = Keypair.from_bytes(bytes(byte_list))
            else:
                raise WalletError("Unknown Solana key format. Use base58 or JSON byte array.")
        except WalletError:
            raise
        except Exception as e:
            raise WalletError(f"Invalid Solana private key: {e}")

        address = str(keypair.pubkey())
        enc = self._encrypt(key.encode("utf-8"), password)
        enc["address"] = address
        self._sol_file.write_text(json.dumps(enc))
        logger.info(f"Solana wallet connected: {address}")
        return {"address": address, "connected": True}

    def decrypt_solana_keypair(self, password: str):
        """Decrypt and return a Solana Keypair object (in-memory only)."""
        if not self._sol_file.exists():
            raise WalletError("No Solana wallet configured.")
        from solders.keypair import Keypair
        enc = json.loads(self._sol_file.read_text())
        raw = self._decrypt(enc, password).decode("utf-8").strip()
        try:
            import base58
            secret_bytes = base58.b58decode(raw) if len(raw) in (87, 88) else bytes(json.loads(raw))
            return Keypair.from_bytes(secret_bytes)
        except Exception as e:
            raise WalletError(f"Failed to reconstruct Solana keypair: {e}")

    def get_solana_address(self) -> Optional[str]:
        if not self._sol_file.exists():
            return None
        try:
            return json.loads(self._sol_file.read_text()).get("address")
        except Exception:
            return None

    def remove_solana_wallet(self):
        if self._sol_file.exists():
            self._sol_file.unlink()
        logger.info("Solana wallet removed")

    # ── Permission guard ──────────────────────────────────────────────────────

    def check_trade_permission(self, usd_amount: float, settings: dict) -> None:
        """
        Validate agent has permission to execute a trade.
        Raises PermissionError with reason if not allowed.
        """
        wallet_cfg = settings.get("wallet", {})

        if not wallet_cfg.get("agent_trading_enabled", False):
            raise PermissionError("Agent trading is not enabled. Enable it in Wallet settings.")

        max_trade = float(wallet_cfg.get("max_trade_usd", 50.0))
        if usd_amount > max_trade:
            raise PermissionError(
                f"Trade amount ${usd_amount:.2f} exceeds per-trade limit ${max_trade:.2f}."
            )

        # Check daily limit
        daily_limit = float(wallet_cfg.get("daily_limit_usd", 200.0))
        daily_spent = float(wallet_cfg.get("daily_spent_usd", 0.0))
        reset_date = wallet_cfg.get("daily_reset_date")
        today = date.today().isoformat()
        if reset_date != today:
            daily_spent = 0.0  # New day — reset counter

        if daily_spent + usd_amount > daily_limit:
            remaining = max(0.0, daily_limit - daily_spent)
            raise PermissionError(
                f"Daily limit reached. Spent ${daily_spent:.2f}, limit ${daily_limit:.2f}. "
                f"${remaining:.2f} remaining today."
            )

    def record_trade(self, usd_amount: float, settings_manager) -> None:
        """Update daily spend counter after a successful trade."""
        today = date.today().isoformat()
        wallet_cfg = settings_manager.get().get("wallet", {})
        reset_date = wallet_cfg.get("daily_reset_date")
        daily_spent = float(wallet_cfg.get("daily_spent_usd", 0.0)) if reset_date == today else 0.0
        settings_manager.update("wallet", {
            "daily_spent_usd": daily_spent + usd_amount,
            "daily_reset_date": today,
        })

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self, settings: dict) -> dict:
        """Return wallet connection status (never exposes keys)."""
        wallet_cfg = settings.get("wallet", {})
        return {
            "evm_connected": self._evm_file.exists(),
            "evm_address": self.get_evm_address() or "",
            "solana_connected": self._sol_file.exists(),
            "solana_address": self.get_solana_address() or "",
            "agent_trading_enabled": wallet_cfg.get("agent_trading_enabled", False),
            "policy_accepted": wallet_cfg.get("policy_accepted", False),
            "max_trade_usd": wallet_cfg.get("max_trade_usd", 50.0),
            "daily_limit_usd": wallet_cfg.get("daily_limit_usd", 200.0),
            "daily_spent_usd": wallet_cfg.get("daily_spent_usd", 0.0),
            "allowed_chains": wallet_cfg.get("allowed_chains", ["base", "solana"]),
        }
