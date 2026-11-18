"""
Unit tests for the pure decision logic in solana_presign_guard.py.

No network, no solders, no aiohttp needed: `evaluate_flow` is pure, so we
stub aiohttp at import time and exercise the verdict logic directly with
fabricated pre/post balances.

Run:  python3 test_presign_guard.py
"""

import sys
import types
from pathlib import Path

# Stub aiohttp so the guard module imports without the real package installed.
aiohttp_stub = types.ModuleType("aiohttp")


class _ClientSession:  # pragma: no cover - never instantiated in these tests
    pass


aiohttp_stub.ClientSession = _ClientSession
aiohttp_stub.ClientTimeout = lambda **kw: None
sys.modules["aiohttp"] = aiohttp_stub

sys.path.insert(0, str(Path(__file__).resolve().parent))
from solana_presign_guard import (  # noqa: E402
    ExpectedFlow,
    ObservedFlow,
    evaluate_flow,
)

WALLET = "4uQeVj5tqViQh7yWWGStvkEG1Zmhx6uasJtWCJziofM"
SOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
BONK = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
OTHER = "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE"

LAMPORTS = 1_000_000_000
FEES = 5_000 + 5_000 + 100_000  # priority + base fee + slack


def base_expected(**over):
    kw = dict(
        wallet_pubkey=WALLET,
        input_mint=SOL,
        output_mint=USDC,
        amount_in=500_000_000,          # 0.5 SOL in
        min_out=100_000_000,            # at least 100 USDC out
        max_out=101_000_000,            # ~101 USDC expected
        sol_is_input=True,
        sol_is_output=False,
        sol_allowance_lamports=FEES + 2_039_280,  # fees + one new ATA rent
    )
    kw.update(over)
    return ExpectedFlow(**kw)


def check(name, expected, observed, should_pass):
    violations = evaluate_flow(expected, observed)
    passed = not violations
    ok = passed == should_pass
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: "
          f"{'clean' if passed else 'blocked: ' + '; '.join(violations)}")
    return ok


results = []

# 1. Clean SOL -> USDC: 0.5 SOL out + fees + ATA rent, 100.5 USDC in.
results.append(check(
    "clean SOL->USDC swap passes",
    base_expected(),
    ObservedFlow(
        sol_delta_lamports=-(500_000_000 + 5_000 + 5_000 + 2_039_280),
        token_deltas={USDC: 100_500_000},
        output_account_owner=WALLET,
    ),
    should_pass=True,
))

# 2. Same swap, but an extra 1 SOL drains out of the wallet.
results.append(check(
    "extra 1 SOL drain is blocked",
    base_expected(),
    ObservedFlow(
        sol_delta_lamports=-(500_000_000 + 5_000 + 5_000 + 2_039_280 + LAMPORTS),
        token_deltas={USDC: 100_500_000},
        output_account_owner=WALLET,
    ),
    should_pass=False,
))

# 3. Output token account owned by someone else — the swap pays a stranger.
results.append(check(
    "output to another wallet is blocked",
    base_expected(),
    ObservedFlow(
        sol_delta_lamports=-(500_000_000 + 5_000 + 5_000 + 2_039_280),
        token_deltas={USDC: 100_500_000},
        output_account_owner="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
    ),
    should_pass=False,
))

# 4. Output below the slippage floor.
results.append(check(
    "output below quoted minimum is blocked",
    base_expected(),
    ObservedFlow(
        sol_delta_lamports=-(500_000_000 + 5_000 + 5_000 + 2_039_280),
        token_deltas={USDC: 50_000_000},
        output_account_owner=WALLET,
    ),
    should_pass=False,
))

# 5. Unrelated token drains (BONK leaves the wallet).
results.append(check(
    "unrelated token drain is blocked",
    base_expected(),
    ObservedFlow(
        sol_delta_lamports=-(500_000_000 + 5_000 + 5_000 + 2_039_280),
        token_deltas={USDC: 100_500_000, BONK: -250_000},
        output_account_owner=WALLET,
    ),
    should_pass=False,
))

# 6. Input amount wrong: twice the quoted SOL leaves.
results.append(check(
    "input amount mismatch is blocked",
    base_expected(),
    ObservedFlow(
        sol_delta_lamports=-(1_000_000_000 + 5_000 + 5_000 + 2_039_280),
        token_deltas={USDC: 100_500_000},
        output_account_owner=WALLET,
    ),
    should_pass=False,
))

# 7. Clean token -> SOL: 100 USDC in, ~0.5 SOL out.
results.append(check(
    "clean USDC->SOL swap passes",
    base_expected(
        input_mint=USDC, output_mint=SOL,
        amount_in=100_000_000, min_out=495_000_000, max_out=500_000_000,
        sol_is_input=False, sol_is_output=True,
        sol_allowance_lamports=FEES,
    ),
    ObservedFlow(
        sol_delta_lamports=499_000_000 - 10_000,
        token_deltas={USDC: -100_000_000},
        output_account_owner=None,  # SOL output has no token account
    ),
    should_pass=True,
))

# 8. Clean token -> token: USDC in, BONK out, only fees leave SOL.
results.append(check(
    "clean USDC->BONK swap passes",
    base_expected(
        input_mint=USDC, output_mint=BONK,
        amount_in=100_000_000, min_out=9_000_000, max_out=9_500_000,
        sol_is_input=False, sol_is_output=False,
        sol_allowance_lamports=FEES + 2_039_280,
    ),
    ObservedFlow(
        sol_delta_lamports=-(5_000 + 5_000 + 2_039_280),
        token_deltas={USDC: -100_000_000, BONK: 9_200_000},
        output_account_owner=WALLET,
    ),
    should_pass=True,
))

# 9. Output account missing entirely after simulation.
results.append(check(
    "missing output account is blocked",
    base_expected(),
    ObservedFlow(
        sol_delta_lamports=-(500_000_000 + 5_000 + 5_000 + 2_039_280),
        token_deltas={USDC: 100_500_000},
        output_account_owner=None,
    ),
    should_pass=False,
))

failed = results.count(False)
print(f"\n{len(results) - failed}/{len(results)} scenarios behaved as expected")
sys.exit(1 if failed else 0)
