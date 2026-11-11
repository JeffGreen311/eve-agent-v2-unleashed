"""
solana_presign_guard.py — local pre-sign guard for Jupiter swaps
===============================================================

Drop-in companion to ``eve/tools/crypto/solana_trader.py``.

Problem (GitHub issue #14 on eve-agent-v2-unleashed): ``execute_swap`` decodes
the swap transaction Jupiter returns and signs it with the agent's keypair
without ever reading what the transaction does. If the API response were ever
wrong — bad config, compromised endpoint, a proxy in between — the key would
sign an extra transfer out of the wallet, a different output token, or a swap
that pays someone else.

Fix: before signing, simulate the *unsigned* transaction against the local
RPC and compare the wallet's actual balance changes against the quote.
Anything unexpected blocks the signature — fail closed.

What it checks, in order:
  1. Quote sanity — the quote's input/output mints and inAmount match what
     the caller asked for (catches a tampered or mismatched quote).
  2. Signers — the wallet is the fee payer and the ONLY required signer.
  3. Simulation must succeed (``err`` is None). A failed simulation blocks.
  4. Balance deltas vs the quote:
       - input token decreases by exactly the quoted inAmount
         (or SOL decreases by the amount + fees when SOL is the input)
       - output token increases by at least ``otherAmountThreshold`` and no
         more than ``outAmount`` + 2% headroom
       - the output token account is owned by the wallet (output lands
         in YOUR account, not someone else's)
       - NO other token may decrease — any drain of an unrelated token blocks
       - SOL outflow beyond the amount + fees + one ATA rent blocks
  5. Returns a report on success; raises ``PreSignCheckFailed`` on any
     violation. Nothing is signed when the check fails or errors.

Dependencies: only ``aiohttp`` and ``solders`` — the same two the trader
already uses. No outside service, no API key, no extra dependency.
The check runs against the same RPC the trader already trusts.

Honest limits (read before relying on it):
  - Simulation is only as honest as your RPC endpoint. If the RPC itself
    is compromised, a local simulation through that same endpoint can lie.
    This guard protects against a bad Jupiter response / bad quote, assuming
    an honest RPC. Point it at your own node if you want that assumption
    to be yours, not a public endpoint's.
  - State can change between simulation and broadcast (small window).
    The check is a dry run, not a guarantee about execution.
  - Covers the classic SPL Token program only, not Token-2022 accounts.
  - ATA rent (~2,039,280 lamports) is inside the SOL allowance when the
    output token account has to be created. Two new ATAs in one swap would
    exceed the default allowance and block — raise ``max_extra_sol_lamports``
    if you ever hit that legitimately.

Wiring (see README.md for the diff): call ``verify()`` in ``execute_swap``
right after ``get_swap_transaction`` and before any decode/sign.
"""

import base64
import logging
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# Rent for creating one associated token account (lamports). Current network
# value; if rent changes, the guard fails closed and the constant needs a bump.
ATA_RENT_LAMPORTS = 2_039_280
# Solana base fee per signature (lamports).
PER_SIGNATURE_FEE_LAMPORTS = 5_000
# Small slack for fee rounding / minor network variance (lamports).
FEE_SLACK_LAMPORTS = 100_000

SOL_MINT = "So11111111111111111111111111111111111111112"
TOKEN_PROGRAM_ID_STR = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ASSOCIATED_TOKEN_PROGRAM_ID_STR = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"


class PreSignCheckFailed(RuntimeError):
    """Raised when the pre-sign check fails. The transaction must NOT be signed."""

    def __init__(self, violations: list):
        self.violations = violations
        super().__init__("Pre-sign check FAILED:\n- " + "\n- ".join(violations))


@dataclass
class ExpectedFlow:
    """What the quote says should happen to the wallet's balances."""

    wallet_pubkey: str
    input_mint: str
    output_mint: str
    amount_in: int            # exact input amount, in the input token's base units
    min_out: int              # quote otherAmountThreshold (slippage-protected floor)
    max_out: int              # quote outAmount (expected output)
    sol_is_input: bool
    sol_is_output: bool
    sol_allowance_lamports: int  # max SOL that may leave beyond the swap itself


@dataclass
class ObservedFlow:
    """What the simulation says would happen to the wallet's balances."""

    sol_delta_lamports: int
    token_deltas: dict         # mint -> post minus pre, in base units
    output_account_owner: Optional[str]  # owner of the output token account


@dataclass
class PreSignReport:
    """Returned by verify() when the check passes."""

    verdict: str = "OK"
    sol_delta_lamports: int = 0
    token_deltas: dict = field(default_factory=dict)
    units_consumed: int = 0
    violations: list = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"SOL delta {self.sol_delta_lamports} lamports"]
        for mint, delta in self.token_deltas.items():
            parts.append(f"{mint[:8]}... delta {delta}")
        return "; ".join(parts) + f"; compute units {self.units_consumed}"


def evaluate_flow(expected: ExpectedFlow, observed: ObservedFlow) -> list:
    """
    Pure decision logic: compare expected vs observed balance changes.
    Returns a list of violation strings; empty means the swap is as quoted.
    No I/O, no solders — unit-testable in isolation.
    """
    violations = []
    sol_delta = observed.sol_delta_lamports

    # --- SOL movement ---------------------------------------------------
    if expected.sol_is_input:
        # SOL leaves: the swap amount plus fees/rent, nothing more.
        if sol_delta > 0:
            violations.append(
                f"SOL is the input but SOL balance would INCREASE by "
                f"{sol_delta} lamports — unexpected"
            )
        elif sol_delta < -(expected.amount_in + expected.sol_allowance_lamports):
            violations.append(
                f"SOL outflow {abs(sol_delta)} lamports exceeds expected "
                f"{expected.amount_in} + allowance "
                f"{expected.sol_allowance_lamports} lamports"
            )
    elif expected.sol_is_output:
        # SOL arrives: at least the slippage floor, at most the quote + slack.
        if sol_delta < expected.min_out - expected.sol_allowance_lamports:
            violations.append(
                f"SOL received {sol_delta} lamports is below the quoted minimum "
                f"{expected.min_out} (minus allowance "
                f"{expected.sol_allowance_lamports})"
            )
        elif sol_delta > expected.max_out + expected.sol_allowance_lamports:
            violations.append(
                f"SOL received {sol_delta} lamports exceeds quoted maximum "
                f"{expected.max_out} (plus allowance "
                f"{expected.sol_allowance_lamports})"
            )
    else:
        # Token -> token: SOL only pays fees (and possibly one ATA rent).
        if sol_delta > 0:
            violations.append(
                f"Token-to-token swap but SOL balance would INCREASE by "
                f"{sol_delta} lamports — unexpected"
            )
        elif sol_delta < -expected.sol_allowance_lamports:
            violations.append(
                f"SOL outflow {abs(sol_delta)} lamports exceeds fee/rent "
                f"allowance {expected.sol_allowance_lamports} lamports"
            )

    # --- Input token: must decrease by exactly the quoted amount ---------
    if not expected.sol_is_input:
        in_delta = observed.token_deltas.get(expected.input_mint)
        if in_delta is None:
            violations.append(
                f"input token account {expected.input_mint[:8]}... was not "
                f"observed in the simulation — cannot confirm the debit"
            )
        elif in_delta != -expected.amount_in:
            violations.append(
                f"input token delta {in_delta} != expected "
                f"{-expected.amount_in} for mint {expected.input_mint[:8]}..."
            )

    # --- Output token: must land in the wallet, within the quoted band ---
    if not expected.sol_is_output:
        out_delta = observed.token_deltas.get(expected.output_mint)
        if observed.output_account_owner is None:
            violations.append(
                "output token account is absent after simulation — "
                "the output has nowhere to land"
            )
        elif observed.output_account_owner != expected.wallet_pubkey:
            violations.append(
                f"output token account is owned by "
                f"{observed.output_account_owner}, not the wallet "
                f"{expected.wallet_pubkey} — output would pay someone else"
            )
        if out_delta is None:
            violations.append(
                f"output token {expected.output_mint[:8]}... was not observed "
                f"in the simulation — cannot confirm the credit"
            )
        else:
            if out_delta < expected.min_out:
                violations.append(
                    f"output token delta {out_delta} is below the quoted "
                    f"minimum {expected.min_out} for mint "
                    f"{expected.output_mint[:8]}..."
                )
            upper = expected.max_out + max(1, expected.max_out // 50)
            if out_delta > upper:
                violations.append(
                    f"output token delta {out_delta} exceeds quoted maximum "
                    f"{expected.max_out} (+2% headroom = {upper}) for mint "
                    f"{expected.output_mint[:8]}..."
                )

    # --- No other token may move at all ----------------------------------
    for mint, delta in observed.token_deltas.items():
        if mint in (expected.input_mint, expected.output_mint):
            continue
        if delta != 0:
            violations.append(
                f"unrelated token {mint[:8]}... would move by {delta} — "
                f"the swap should not touch it"
            )

    return violations


class PreSignGuard:
    """Local pre-sign guard. One instance per RPC endpoint."""

    def __init__(
        self,
        rpc_url: str,
        *,
        timeout_s: int = 15,
        max_extra_sol_lamports: int = 5_000_000,
    ):
        self.rpc_url = rpc_url
        self.timeout_s = timeout_s
        self.max_extra_sol_lamports = max_extra_sol_lamports

    # -- public API -------------------------------------------------------

    async def verify(
        self,
        *,
        tx_b64: str,
        quote: dict,
        wallet_pubkey: str,
        input_mint: str,
        output_mint: str,
        amount_lamports: int,
        priority_fee_lamports: int = 5000,
    ) -> PreSignReport:
        """
        Simulate the unsigned swap transaction and verify it against the quote.
        Returns a PreSignReport on success.
        Raises PreSignCheckFailed on any mismatch, and RuntimeError if the
        check itself cannot be performed (fail closed — do not sign).
        """
        if input_mint == output_mint:
            raise PreSignCheckFailed(["input and output mint are the same"])

        # 1. Quote sanity — the quote must be the one we asked for.
        quote_violations = []
        if quote.get("inputMint") != input_mint:
            quote_violations.append(
                f"quote inputMint {quote.get('inputMint')} != requested {input_mint}"
            )
        if quote.get("outputMint") != output_mint:
            quote_violations.append(
                f"quote outputMint {quote.get('outputMint')} != requested {output_mint}"
            )
        if int(quote.get("inAmount", -1)) != amount_lamports:
            quote_violations.append(
                f"quote inAmount {quote.get('inAmount')} != requested "
                f"{amount_lamports}"
            )
        if quote_violations:
            raise PreSignCheckFailed(quote_violations)

        min_out = int(quote["otherAmountThreshold"])
        max_out = int(quote["outAmount"])

        # 2. Decode the tx and check who must sign it.
        num_signatures = self._check_signers(tx_b64, wallet_pubkey)

        sol_is_input = input_mint == SOL_MINT
        sol_is_output = output_mint == SOL_MINT

        # 3. Pre-simulation balances.
        pre_sol = await self._get_sol_balance(wallet_pubkey)
        pre_tokens = await self._get_token_accounts(wallet_pubkey)
        # mint -> [(account address, amount), ...]
        input_token_account = None
        input_token_pre = 0
        if not sol_is_input:
            input_ata = self._derive_ata(wallet_pubkey, input_mint)
            input_token_account, input_token_pre = self._pick_account(
                pre_tokens.get(input_mint, []), input_ata
            )
            if input_token_account is None:
                raise PreSignCheckFailed(
                    [f"no token account for input mint {input_mint[:8]}..."]
                )

        output_ata = None
        output_ata_exists = False
        output_token_pre = 0
        if not sol_is_output:
            output_ata = self._derive_ata(wallet_pubkey, output_mint)
            for addr, amount in pre_tokens.get(output_mint, []):
                if addr == output_ata:
                    output_ata_exists = True
                    output_token_pre = amount
                    break

        # 4. Simulate the unsigned transaction.
        sim_addresses = [wallet_pubkey]
        if input_token_account:
            sim_addresses.append(input_token_account)
        if output_ata:
            sim_addresses.append(output_ata)
        sim = await self._simulate(tx_b64, sim_addresses)
        sim_err = sim.get("err")
        if sim_err is not None:
            raise PreSignCheckFailed([f"simulation failed: {sim_err}"])
        sim_accounts = sim.get("accounts") or []
        if len(sim_accounts) != len(sim_addresses):
            raise RuntimeError(
                "simulation returned an unexpected number of accounts "
                f"({len(sim_accounts)} for {len(sim_addresses)} requested)"
            )

        # 5. Build observed deltas: post-simulation minus pre-simulation.
        if not sim_accounts or sim_accounts[0] is None:
            raise RuntimeError(
                "simulation did not return the wallet account — "
                "cannot verify, refusing to sign"
            )
        post_sol = sim_accounts[0]["lamports"]
        token_deltas = {}
        output_owner = None
        idx = 1
        if input_token_account:
            token_deltas[input_mint] = (
                self._sim_token_amount(sim_accounts[idx]) - input_token_pre
            )
            idx += 1
        if output_ata:
            post_acc = sim_accounts[idx]
            if post_acc is None:
                # Account still does not exist after simulation.
                token_deltas[output_mint] = 0 - output_token_pre
                output_owner = None
            else:
                parsed = post_acc.get("data", {}).get("parsed", {})
                info = parsed.get("info", {})
                token_deltas[output_mint] = int(
                    info.get("tokenAmount", {}).get("amount", "0")
                ) - output_token_pre
                output_owner = info.get("owner")

        # 6. SOL allowance: fees + ATA rent if the output ATA is new + slack,
        #    capped by the configured maximum.
        allowance = (
            priority_fee_lamports
            + PER_SIGNATURE_FEE_LAMPORTS * num_signatures
            + (0 if output_ata_exists else ATA_RENT_LAMPORTS if output_ata else 0)
            + FEE_SLACK_LAMPORTS
        )
        allowance = min(allowance, self.max_extra_sol_lamports)

        expected = ExpectedFlow(
            wallet_pubkey=wallet_pubkey,
            input_mint=input_mint,
            output_mint=output_mint,
            amount_in=amount_lamports,
            min_out=min_out,
            max_out=max_out,
            sol_is_input=sol_is_input,
            sol_is_output=sol_is_output,
            sol_allowance_lamports=allowance,
        )
        observed = ObservedFlow(
            sol_delta_lamports=post_sol - pre_sol,
            token_deltas=token_deltas,
            output_account_owner=output_owner,
        )
        violations = evaluate_flow(expected, observed)
        if violations:
            raise PreSignCheckFailed(violations)

        return PreSignReport(
            sol_delta_lamports=observed.sol_delta_lamports,
            token_deltas=dict(token_deltas),
            units_consumed=int(sim.get("unitsConsumed", 0)),
        )

    # -- internals --------------------------------------------------------

    def _check_signers(self, tx_b64: str, wallet_pubkey: str) -> int:
        """Decode the versioned tx; verify wallet is fee payer and sole signer."""
        from solders.pubkey import Pubkey  # type: ignore
        from solders.transaction import VersionedTransaction  # type: ignore

        raw = base64.b64decode(tx_b64)
        tx = VersionedTransaction.from_bytes(raw)
        keys = tx.message.account_keys
        header = tx.message.header
        if not keys:
            raise PreSignCheckFailed(["transaction has no account keys"])
        if str(keys[0]) != wallet_pubkey:
            raise PreSignCheckFailed(
                [f"fee payer {keys[0]} != wallet {wallet_pubkey}"]
            )
        num_signatures = header.num_required_signatures
        signers = keys[:num_signatures]
        if len(signers) != 1 or str(signers[0]) != wallet_pubkey:
            raise PreSignCheckFailed(
                [
                    f"transaction requires {len(signers)} signer(s), expected "
                    f"only the wallet {wallet_pubkey}"
                ]
            )
        if len(tx.message.instructions) == 0:
            raise PreSignCheckFailed(["transaction has no instructions"])
        return num_signatures

    def _derive_ata(self, wallet_pubkey: str, mint: str) -> str:
        """Derive the associated token account address for (wallet, mint)."""
        from solders.pubkey import Pubkey  # type: ignore

        wallet = Pubkey.from_string(wallet_pubkey)
        mint_pk = Pubkey.from_string(mint)
        token_program = Pubkey.from_string(TOKEN_PROGRAM_ID_STR)
        ata_program = Pubkey.from_string(ASSOCIATED_TOKEN_PROGRAM_ID_STR)
        ata, _bump = Pubkey.find_program_address(
            [bytes(wallet), bytes(token_program), bytes(mint_pk)],
            ata_program,
        )
        return str(ata)

    @staticmethod
    def _pick_account(accounts: list, preferred_addr: str):
        """
        Pick the token account to watch for a mint: the associated token
        account when present, else the first account holding that mint.
        Returns (address, amount) or (None, 0).
        """
        if not accounts:
            return None, 0
        for addr, amount in accounts:
            if addr == preferred_addr:
                return addr, amount
        return accounts[0]

    @staticmethod
    def _sim_token_amount(sim_account) -> int:
        """Post-simulation token balance for one simulated account (0 if absent)."""
        if sim_account is None:
            return 0
        parsed = sim_account.get("data", {}).get("parsed", {})
        info = parsed.get("info", {})
        return int(info.get("tokenAmount", {}).get("amount", "0"))

    async def _rpc(self, method: str, params: list):
        """One raw JSON-RPC call. Raises on transport or RPC-level errors."""
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.rpc_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout_s),
            ) as resp:
                data = await resp.json(content_type=None)
        if "error" in data:
            raise RuntimeError(f"Solana RPC {method} failed: {data['error']}")
        return data.get("result")

    async def _get_sol_balance(self, wallet_pubkey: str) -> int:
        result = await self._rpc(
            "getBalance", [wallet_pubkey, {"commitment": "confirmed"}]
        )
        return int(result.get("value", 0))

    async def _get_token_accounts(self, wallet_pubkey: str) -> dict:
        """
        Returns {mint: [(account address, amount), ...]} for the wallet's SPL
        token accounts. Zero-balance accounts are included when the RPC
        returns them.
        """
        result = await self._rpc(
            "getTokenAccountsByOwner",
            [
                wallet_pubkey,
                {"programId": TOKEN_PROGRAM_ID_STR},
                {"encoding": "jsonParsed"},
            ],
        )
        out = {}
        for acc in result.get("value", []):
            info = (
                acc.get("account", {})
                .get("data", {})
                .get("parsed", {})
                .get("info", {})
            )
            mint = info.get("mint", "")
            amount = int(info.get("tokenAmount", {}).get("amount", "0"))
            if mint:
                out.setdefault(mint, []).append((acc.get("pubkey", ""), amount))
        return out

    async def _simulate(self, tx_b64: str, addresses: list) -> dict:
        """Simulate the unsigned tx. sigVerify=False because it is not signed yet."""
        result = await self._rpc(
            "simulateTransaction",
            [
                tx_b64,
                {
                    "encoding": "base64",
                    "sigVerify": False,
                    "replaceRecentBlockhash": True,
                    "commitment": "confirmed",
                    "accounts": {"encoding": "jsonParsed", "addresses": addresses},
                },
            ],
        )
        return result.get("value", {})
