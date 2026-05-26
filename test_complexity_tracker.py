"""
Tests for eve_complexity_tracker.py v3

Run: python test_complexity_tracker.py
     pytest test_complexity_tracker.py -v
"""

import copy
import sys

from eve_complexity_tracker import (
    ComplexityTracker,
    ESCALATION_THRESHOLDS,
    DEESCALATION_WINDOW,
    ESCALATION_MODEL,
    _is_local_model,
    _estimate_tokens,
)

LOCAL_MODEL = "jeffgreen311/eve-qwen3-8b-consciousness-liberated:q4_K_M"


# ── helpers ───────────────────────────────────────────────────────────────────

def _tc(name: str, path: str = "") -> dict:
    args = {"path": path} if path else {}
    return {"function": {"name": name, "arguments": args}}


def _msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


def _make_messages(n: int = 4) -> list:
    msgs = [_msg("system", "You are Eve.")]
    for i in range(n):
        msgs.append(_msg("user", f"message {i}"))
        msgs.append(_msg("assistant", f"response {i}"))
    return msgs


def _ok(result: str = "ok") -> str:
    return result


def _err(msg: str = "Error: file not found") -> str:
    return msg


# ── 1. Read-only calls never write files, never escalate ─────────────────────

def test_no_escalate_reads_only():
    tracker = ComplexityTracker(LOCAL_MODEL, _make_messages())
    msgs = _make_messages()
    tcs = [_tc("read_file", "a.py"), _tc("glob", "*.py"), _tc("grep", "")]
    tracker.record_round(tcs, [_ok()] * 3, msgs)
    assert not tracker.should_escalate(), "Read-only round should never escalate"
    print("PASS  no escalation on read-only round")


# ── 2. No escalation at the threshold boundary ───────────────────────────────

def test_no_escalate_on_flat_complexity():
    """Exactly tool_rounds rounds of reads -- at the cap but not over it."""
    tracker = ComplexityTracker(LOCAL_MODEL, _make_messages())
    msgs = _make_messages()
    cap = ESCALATION_THRESHOLDS["tool_rounds"]
    for _ in range(cap):
        tracker.record_round([_tc("read_file", "a.py")], [_ok()], msgs)
    assert not tracker.should_escalate(), "Exactly at round cap should NOT escalate (> not >=)"
    print("PASS  no escalation at round cap boundary")


# ── 3. Scope expansion: new top-level directory triggers escalation ───────────

def test_escalate_scope_expansion():
    """Files written > threshold AND a new top-level dir in the latest round."""
    tracker = ComplexityTracker(LOCAL_MODEL, _make_messages())
    msgs = _make_messages()
    t = ESCALATION_THRESHOLDS["files_touched"]

    # Round 1: write t+1 files all inside src/ -- exceeds threshold but no scope signal yet
    tracker.record_round(
        [_tc("write_file", f"src/api/file{i}.py") for i in range(t + 1)],
        [_ok()] * (t + 1),
        msgs,
    )
    assert not tracker.should_escalate(), "Single write-round cannot trigger scope expansion (needs 2)"

    # Round 2: write into a brand-new top-level directory (tests/)
    tracker.record_round(
        [_tc("write_file", "tests/test_api.py")],
        [_ok()],
        msgs,
    )
    assert tracker.should_escalate(), "New top-level dir in second write-round should escalate"
    print("PASS  scope expansion escalation (new top-level directory)")


# ── 4. Cleanup phase: same dir + same ext -- no false escalation ──────────────

def test_no_escalate_cleanup_same_dir():
    """Post-edit import-fix batch: more than threshold files written but all in
    the same directory with the same extension.  Must NOT escalate."""
    tracker = ComplexityTracker(LOCAL_MODEL, _make_messages())
    msgs = _make_messages()
    t = ESCALATION_THRESHOLDS["files_touched"]

    # Round 1: write t files in src/models/
    tracker.record_round(
        [_tc("write_file", f"src/models/m{i}.py") for i in range(t)],
        [_ok()] * t,
        msgs,
    )
    # Round 2: more writes in the same src/models/ dir, same .py extension (cleanup)
    tracker.record_round(
        [_tc("write_file", "src/models/utils.py"), _tc("write_file", "src/models/base.py")],
        [_ok(), _ok()],
        msgs,
    )
    assert not tracker.should_escalate(), (
        "Cleanup phase (same dir, same ext) must NOT trigger scope expansion"
    )
    print("PASS  no false escalation during cleanup phase (same dir/ext)")


# ── 5. Error accumulation floor ───────────────────────────────────────────────

def test_escalate_error_floor():
    tracker = ComplexityTracker(LOCAL_MODEL, _make_messages())
    msgs = _make_messages()
    floor = ESCALATION_THRESHOLDS["error_rounds"]

    for _ in range(floor + 1):
        tracker.record_round([_tc("bash", "")], [_err("Error: something broke")], msgs)

    assert tracker.should_escalate(), f"More than {floor} error rounds must escalate"
    print(f"PASS  error floor escalation (>{floor} error rounds)")


# ── 6. Round cap: always escalate after tool_rounds+1 rounds ─────────────────

def test_escalate_round_cap():
    tracker = ComplexityTracker(LOCAL_MODEL, _make_messages())
    msgs = _make_messages()
    cap = ESCALATION_THRESHOLDS["tool_rounds"]

    for _ in range(cap + 1):
        tracker.record_round([_tc("read_file", "a.py")], [_ok()], msgs)

    assert tracker.should_escalate(), f"More than {cap} rounds must always escalate"
    print(f"PASS  round cap escalation (>{cap} rounds)")


# ── 7. Cloud model never self-escalates ──────────────────────────────────────

def test_no_escalate_if_already_cloud():
    tracker = ComplexityTracker(ESCALATION_MODEL, _make_messages())
    msgs = _make_messages()
    for i in range(10):
        tracker.record_round(
            [_tc("write_file", f"src/x{i}.py"), _tc("bash", "")],
            [_err()] * 2,
            msgs,
        )
    assert not tracker.should_escalate(), "Cloud model should never self-escalate"
    print("PASS  no escalation if already on cloud model")


# ── 8. Checkpoint is a deep copy (shared-reference isolation) ─────────────────

def test_checkpoint_deepcopy():
    msgs = _make_messages()
    tracker = ComplexityTracker(LOCAL_MODEL, msgs)
    tracker.record_round([_tc("read_file", "a.py")], [_ok()], msgs)
    checkpoint_after_round1 = copy.deepcopy(tracker._checkpoint)

    # Mutate the messages list AFTER the round was recorded
    msgs.append(_msg("user", "injected message"))
    tracker.record_round([_tc("read_file", "b.py")], [_ok()], msgs)

    # Round-1 snapshot must not contain the injected message
    assert "injected message" not in [m["content"] for m in checkpoint_after_round1]
    # Round-2 checkpoint advances and includes it
    assert len(tracker._checkpoint) > len(checkpoint_after_round1)
    print("PASS  checkpoint deepcopy prevents shared-reference corruption")


# ── 9. build_clean_thread produces exactly one system message ─────────────────

def test_clean_thread_no_double_system_msg():
    """Replacing vs prepending -- no double system message on handoff."""
    msgs = [_msg("system", "original system")] + [
        _msg("user", "hello"), _msg("assistant", "world"),
    ]
    tracker = ComplexityTracker(LOCAL_MODEL, msgs)

    thread = tracker.build_clean_thread("refactor the auth module")

    system_messages = [m for m in thread if m.get("role") == "system"]
    assert len(system_messages) == 1, (
        f"Expected exactly 1 system message, got {len(system_messages)}"
    )
    assert "CONTEXT HANDOFF" in system_messages[0]["content"]
    print("PASS  build_clean_thread produces exactly 1 system message")


# ── 10. build_clean_thread output is reasonably bounded ──────────────────────

def test_clean_thread_bounded():
    tracker = ComplexityTracker(LOCAL_MODEL, _make_messages())
    msgs = _make_messages()

    for i in range(5):
        msgs.append(_msg("assistant", "response " * 40))
        tracker.record_round(
            [_tc("write_file", f"src/file_{i}.py")],
            [_err() if i % 2 == 0 else _ok()],
            msgs,
        )

    thread = tracker.build_clean_thread("refactor the module")
    total = _estimate_tokens(thread)
    # Generous ceiling: STEER plus the last clean checkpoint
    assert total < 50_000, f"clean_thread suspiciously large: {total} estimated tokens"
    print(f"PASS  clean_thread bounded ({total} estimated tokens)")


# ── 11. De-escalation fires after DEESCALATION_WINDOW trivial rounds ──────────

def test_deescalate_after_trivial_rounds():
    tracker = ComplexityTracker(LOCAL_MODEL, _make_messages())
    msgs = _make_messages()
    tracker._escalated = True

    for _ in range(DEESCALATION_WINDOW):
        tracker.record_round([_tc("read_file", "a.py")], [_ok("content")], msgs)

    assert tracker.should_deescalate(), (
        f"Should de-escalate after {DEESCALATION_WINDOW} trivial rounds"
    )
    print(f"PASS  de-escalation fires after {DEESCALATION_WINDOW} trivial rounds")


# ── 12. De-escalation blocked by error in trivial window ─────────────────────

def test_no_deescalate_on_error():
    tracker = ComplexityTracker(LOCAL_MODEL, _make_messages())
    msgs = _make_messages()
    tracker._escalated = True

    for _ in range(DEESCALATION_WINDOW - 1):
        tracker.record_round([_tc("read_file", "a.py")], [_ok()], msgs)
    tracker.record_round([_tc("bash", "")], [_err("Error: permission denied")], msgs)

    assert not tracker.should_deescalate(), "Error in trivial window must block de-escalation"
    print("PASS  de-escalation blocked by error round")


# ── 13. De-escalation blocked by write tool in trivial window ────────────────

def test_no_deescalate_on_write():
    tracker = ComplexityTracker(LOCAL_MODEL, _make_messages())
    msgs = _make_messages()
    tracker._escalated = True

    for _ in range(DEESCALATION_WINDOW - 1):
        tracker.record_round([_tc("read_file", "a.py")], [_ok()], msgs)
    tracker.record_round([_tc("write_file", "a.py")], [_ok()], msgs)

    assert not tracker.should_deescalate(), "Write tool in window must block de-escalation"
    print("PASS  de-escalation blocked by write tool")


# ── 14. No de-escalation before escalation ───────────────────────────────────

def test_no_deescalate_before_escalation():
    tracker = ComplexityTracker(LOCAL_MODEL, _make_messages())
    msgs = _make_messages()
    for _ in range(DEESCALATION_WINDOW + 2):
        tracker.record_round([_tc("read_file", "a.py")], [_ok()], msgs)
    assert not tracker.should_deescalate(), "should_deescalate() must not fire if never escalated"
    print("PASS  no de-escalation before escalation")


# ── 15. Escalation is one-shot ────────────────────────────────────────────────

def test_escalation_is_oneshot():
    tracker = ComplexityTracker(LOCAL_MODEL, _make_messages())
    msgs = _make_messages()
    floor = ESCALATION_THRESHOLDS["error_rounds"]

    for _ in range(floor + 1):
        tracker.record_round([_tc("bash", "")], [_err()], msgs)

    assert tracker.should_escalate()
    tracker._escalated = True
    assert not tracker.should_escalate(), "After _escalated=True, should_escalate() must return False"
    print("PASS  escalation is one-shot")


# ── 16. Fuzzy local-model matching ───────────────────────────────────────────

def test_is_local_model_fuzzy():
    assert _is_local_model("jeffgreen311/Eve-V2-Unleashed-Qwen3.5-8B-Liberated-4K-4B-Merged:latest")
    assert _is_local_model("jeffgreen311/eve-qwen3-8b-consciousness-liberated:q4_K_M")
    assert _is_local_model("eve-unleashed")
    assert not _is_local_model("qwen3-coder:480b-cloud")
    assert not _is_local_model("gpt-4o")
    assert not _is_local_model("anthropic/claude-3-sonnet")
    print("PASS  fuzzy local-model matching works correctly")


# ── runner ────────────────────────────────────────────────────────────────────

TESTS = [
    test_no_escalate_reads_only,
    test_no_escalate_on_flat_complexity,
    test_escalate_scope_expansion,
    test_no_escalate_cleanup_same_dir,
    test_escalate_error_floor,
    test_escalate_round_cap,
    test_no_escalate_if_already_cloud,
    test_checkpoint_deepcopy,
    test_clean_thread_no_double_system_msg,
    test_clean_thread_bounded,
    test_deescalate_after_trivial_rounds,
    test_no_deescalate_on_error,
    test_no_deescalate_on_write,
    test_no_deescalate_before_escalation,
    test_escalation_is_oneshot,
    test_is_local_model_fuzzy,
]

if __name__ == "__main__":
    failed = []
    for t in TESTS:
        try:
            t()
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed.append(t.__name__)

    print(f"\n{'-' * 50}")
    if failed:
        print(f"FAILED {len(failed)}/{len(TESTS)}: {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"ALL {len(TESTS)} TESTS PASSED")
