"""Per-round complexity tracking for Eve V2U Unleashed.

Implements the suggestion from Deep_Ad1959 on Reddit:
  "route on a running complexity/token estimate per round rather than
   one-shot at the start"

The STEER injection and fork-at-known-good are the same primitive from two
directions -- this class unifies them:
  - fork-at-known-good: checkpoint is updated after every clean round so the
    escalated model gets clean history, not whatever the 4B compacted away
  - STEER injection: build_clean_thread() injects a handoff directive that
    orients the 480B model to the task state without replaying raw history

Changelog:
  v1 -- initial implementation
  v2 -- delta gating, fixed-budget checkpoint, reversible escalation
  v3 -- Fix 1: scope-expansion signal (rising count + new file type/dir, not
             raw count) prevents cleanup phase from false-tripping escalation.
       Fix 2: deescalation threshold raised to 5, switched from round-count
             to tool-call entropy (no write/bash in window), errors-since-
             last-edit carry heavier weight.
       Fix 3: _FILE_TOOLS split into write vs search sets -- glob/grep/find
             no longer inflate the files_touched escalation score.
       Fix 4: build_clean_thread() replaces existing system msg instead of
             prepending -- prevents double system message on handoff.
       Fix 5: _is_local_model() fuzzy match -- model ID variants no longer
             silently skip escalation logic.
       Fix 6: deepcopy checkpoint -- prevents shared-reference corruption.

Usage inside the tool loop (eve_server.py):
    tracker = ComplexityTracker(model_id, messages_before_loop)
    for round_num in range(max_rounds):
        ... run tool calls ...
        tracker.record_round(tool_calls, results, messages)
        if tracker.should_escalate():
            clean_msgs = tracker.build_clean_thread(original_user_request)
            # switch model_id -> ESCALATION_MODEL
            # replace messages with clean_msgs
            # rebuild client
        if tracker.should_deescalate():
            # release session lock -- next message routes from scratch
"""

from __future__ import annotations

import copy
import os
import time
from dataclasses import dataclass, field
from typing import List


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Thresholds at which a local model run escalates to the 480B cloud coder
ESCALATION_THRESHOLDS = {
    "files_touched":  3,       # written files before scope-expansion check kicks in
    "tool_rounds":    4,       # hard cap: escalate after this many rounds regardless
    "error_rounds":   2,       # escalate after this many error rounds
    "token_estimate": 8_000,   # accumulated token estimate across history
}

# Consecutive trivial rounds required to de-escalate.
# 5 is the floor that survives the post-edit import-fix cleanup batch.
# 3 trips on cleanup in almost every real refactor; 4 is break-even on
# context-rebuild overhead, so 5 gives a safety margin.
DEESCALATION_WINDOW = 5

ESCALATION_MODEL = "qwen3-coder:480b-cloud"

# Substring fragments that identify local/personality models.
# Fuzzy match is more robust than an exact frozenset -- handles tag variants
# like :latest, :q4_K_M, and future model name changes.
_LOCAL_MODEL_FRAGMENTS = (
    "eve-v2-unleashed",
    "eve-qwen3",
    "consciousness-liberated",
    "solforg3",
    "4b-merged",
    "eve-unleashed",
)

# Write/modify tools -- the ones that actually change state and drive escalation
_WRITE_TOOLS = frozenset({
    "write_file",
    "replace_lines",
    "insert_after_line",
    "bash",
})

# Read/search tools -- trivial, never inflate the files_touched escalation score
_SEARCH_TOOLS = frozenset({
    "read_file",
    "read_lines",
    "grep",
    "glob",
    "find_file",
    "list_directory",
    "list_dir",
})

_ERROR_MARKERS = (
    "error:", "exception", "traceback",
    "failed:", "not found", "permission denied",
    "no such file", "syntax error",
)


# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _RoundRecord:
    round_num:     int
    tools_called:  List[str]
    files_written: List[str]   # write/modify tools only
    files_read:    List[str]   # read/search tools only
    had_error:     bool
    token_delta:   int
    timestamp:     float = field(default_factory=time.time)

    @property
    def is_trivial(self) -> bool:
        """True when round contains only read/search tool calls and no errors."""
        return (
            not self.had_error
            and not self.files_written
            and all(t in _SEARCH_TOOLS for t in self.tools_called)
        )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CLASS
# ─────────────────────────────────────────────────────────────────────────────

class ComplexityTracker:
    """Track per-round complexity and drive mid-loop escalation decisions.

    Initialize once before the tool loop starts.  Call record_round() after
    every batch of tool calls completes.  Check should_escalate() before the
    next loop iteration.  Check should_deescalate() after the loop finishes.
    """

    def __init__(self, initial_model: str, initial_messages: list) -> None:
        self.initial_model = initial_model
        self.rounds: List[_RoundRecord] = []

        # Checkpoint: last clean (error-free) copy of messages -- the "known-good fork"
        # deepcopy prevents shared-reference corruption when messages list is mutated
        self._checkpoint: list = copy.deepcopy(initial_messages)

        # Track written files and their metadata for scope-expansion detection
        self._written_files: set = set()

        self._token_estimate: int = _estimate_tokens(initial_messages)
        self._escalated: bool = False

    # ── public API ────────────────────────────────────────────────────────────

    def record_round(
        self,
        tool_calls: list,
        results: list,
        current_messages: list,
    ) -> None:
        """Call after every tool-call batch completes."""
        files_written_this_round: set = set()
        files_read_this_round: set = set()
        had_error = False

        for tc, result in zip(tool_calls, results):
            name = _tc_name(tc)
            args = _tc_args(tc)
            path = args.get("path", "") if isinstance(args, dict) else ""

            if name in _WRITE_TOOLS and path:
                files_written_this_round.add(path)
            elif name in _SEARCH_TOOLS and path:
                files_read_this_round.add(path)

            if any(m in str(result).lower() for m in _ERROR_MARKERS):
                had_error = True

        self._written_files.update(files_written_this_round)

        new_msgs = current_messages[len(self._checkpoint):]
        delta = _estimate_tokens(new_msgs)
        self._token_estimate += delta

        self.rounds.append(_RoundRecord(
            round_num=len(self.rounds) + 1,
            tools_called=[_tc_name(tc) for tc in tool_calls],
            files_written=list(files_written_this_round),
            files_read=list(files_read_this_round),
            had_error=had_error,
            token_delta=delta,
        ))

        # Advance checkpoint only on clean rounds -- "known-good fork"
        if not had_error:
            self._checkpoint = copy.deepcopy(current_messages)

    def should_escalate(self) -> bool:
        """True when a threshold has been crossed and we're on a local model."""
        if self._escalated:
            return False
        if not _is_local_model(self.initial_model):
            return False

        t = ESCALATION_THRESHOLDS

        # Scope-expansion signal: rising write-file count AND new file type or dir.
        # Raw count alone fires on the cleanup phase (updating imports across affected
        # files makes count rise even as scope contracts). The combined signal only
        # fires when the latest round genuinely introduces a new area of the codebase.
        if len(self._written_files) > t["files_touched"] and self._is_scope_expanding():
            return True

        # Hard round cap -- escalate regardless after N rounds
        if len(self.rounds) > t["tool_rounds"]:
            return True

        # Error accumulation
        if sum(1 for r in self.rounds if r.had_error) > t["error_rounds"]:
            return True

        # Token budget
        if self._token_estimate > t["token_estimate"]:
            return True

        return False

    def should_deescalate(self) -> bool:
        """True when the 480B has finished hard work and the last N rounds are trivial.

        Uses tool-call entropy rather than a raw round count:
          - All calls in the window must be read/search (no write, no bash)
          - No errors anywhere in the window
          - At least DEESCALATION_WINDOW rounds must have passed since the last write
          - No errors since the last write (an error inside the quiet period means
            the model has an open loop it hasn't surfaced yet)

        Break-even on context-rebuild overhead is ~4 trivial rounds, so 5 gives
        a safety margin.
        """
        if not self._escalated:
            return False
        if len(self.rounds) < DEESCALATION_WINDOW:
            return False

        recent = self.rounds[-DEESCALATION_WINDOW:]
        for r in recent:
            if not r.is_trivial:
                return False

        # Errors since last write carry heavier weight
        last_write_idx = -1
        for i, r in enumerate(self.rounds):
            if r.files_written or any(t == "bash" for t in r.tools_called):
                last_write_idx = i

        if last_write_idx >= 0:
            rounds_after_write = len(self.rounds) - 1 - last_write_idx
            if rounds_after_write < DEESCALATION_WINDOW:
                return False
            for r in self.rounds[last_write_idx + 1:]:
                if r.had_error:
                    return False

        return True

    def escalation_reason(self) -> str:
        t = ESCALATION_THRESHOLDS
        reasons = []
        if len(self._written_files) > t["files_touched"] and self._is_scope_expanding():
            label = "extension" if self._new_extension_in_latest() else "directory"
            reasons.append(f"{len(self._written_files)} files written + new {label}")
        if len(self.rounds) > t["tool_rounds"]:
            reasons.append(f"{len(self.rounds)} rounds")
        error_count = sum(1 for r in self.rounds if r.had_error)
        if error_count > t["error_rounds"]:
            reasons.append(f"{error_count} error rounds")
        if self._token_estimate > t["token_estimate"]:
            reasons.append(f"~{self._token_estimate} tokens")
        return ", ".join(reasons) if reasons else "threshold crossed"

    def build_clean_thread(self, user_request: str) -> list:
        """Fork-at-known-good + STEER injection combined.

        Returns a message list suitable for the escalated model.  Replaces
        the existing system message (rather than prepending) to avoid a
        double system-message at the top of the thread.
        """
        self._escalated = True

        tool_counts: dict = {}
        for r in self.rounds:
            for t in r.tools_called:
                tool_counts[t] = tool_counts.get(t, 0) + 1

        lines = [
            "CONTEXT HANDOFF -- task escalated from local model due to scope expansion.",
            f"Escalation reason: {self.escalation_reason()}",
            "",
            f"Original request: {user_request}",
            "",
        ]
        if self._written_files:
            lines.append(f"Files written/modified: {', '.join(sorted(self._written_files))}")
        if tool_counts:
            summary = ", ".join(f"{k}x{v}" for k, v in sorted(tool_counts.items()))
            lines.append(f"Tools used: {summary}")
        error_rounds = sum(1 for r in self.rounds if r.had_error)
        if error_rounds:
            lines.append(f"Rounds with errors: {error_rounds}")
        lines += [
            "",
            "The conversation history below is the last known-good checkpoint.",
            "Pick up from here and complete the task.",
        ]

        steer = {"role": "system", "content": "\n".join(lines)}
        checkpoint = copy.deepcopy(self._checkpoint)

        # Replace existing system message to avoid double system message on handoff
        if checkpoint and checkpoint[0].get("role") == "system":
            checkpoint[0] = steer
        else:
            checkpoint.insert(0, steer)

        return checkpoint

    # ── private helpers ───────────────────────────────────────────────────────

    def _is_scope_expanding(self) -> bool:
        """True when write count is rising AND a new file type or directory appears.

        Requires BOTH the latest and previous rounds to have written files --
        if there's a read-only round between two write rounds, the signal is
        not consecutive and the cleanup heuristic doesn't apply.
        """
        if len(self.rounds) < 2:
            return False
        if not self.rounds[-1].files_written or not self.rounds[-2].files_written:
            return False
        return self._new_extension_in_latest() or self._new_dir_in_latest()

    def _new_extension_in_latest(self) -> bool:
        """True if the latest round wrote to a file type not seen in any prior round."""
        if not self.rounds:
            return False
        prev_exts: set = set()
        for r in self.rounds[:-1]:
            for f in r.files_written:
                ext = os.path.splitext(f)[1]
                if ext:
                    prev_exts.add(ext)
        latest_exts: set = set()
        for f in self.rounds[-1].files_written:
            ext = os.path.splitext(f)[1]
            if ext:
                latest_exts.add(ext)
        return bool(latest_exts - prev_exts)

    def _new_dir_in_latest(self) -> bool:
        """True if the latest round wrote to a top-level directory not seen before."""
        if not self.rounds:
            return False
        prev_dirs: set = set()
        for r in self.rounds[:-1]:
            for f in r.files_written:
                top = f.replace("\\", "/").split("/")[0]
                prev_dirs.add(top)
        latest_dirs: set = set()
        for f in self.rounds[-1].files_written:
            top = f.replace("\\", "/").split("/")[0]
            latest_dirs.add(top)
        return bool(latest_dirs - prev_dirs)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _is_local_model(model_id: str) -> bool:
    """Fuzzy match on model ID -- handles tag variants without exact string dependence."""
    lower = model_id.lower()
    return any(fragment in lower for fragment in _LOCAL_MODEL_FRAGMENTS)


def _estimate_tokens(messages: list) -> int:
    return sum(len(str(m.get("content", ""))) // 4 for m in messages)


def _tc_name(tc) -> str:
    if isinstance(tc, dict):
        return tc.get("function", {}).get("name", "?")
    fn = getattr(tc, "function", None)
    return getattr(fn, "name", "?") if fn else "?"


def _tc_args(tc) -> dict:
    if isinstance(tc, dict):
        return tc.get("function", {}).get("arguments", {})
    fn = getattr(tc, "function", None)
    if fn is None:
        return {}
    args = getattr(fn, "arguments", {})
    return args if isinstance(args, dict) else {}
