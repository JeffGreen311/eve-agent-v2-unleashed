"""Per-round complexity tracking for Eve V2U Unleashed.

Implements the suggestion from Deep_Ad1959 on Reddit:
  "route on a running complexity/token estimate per round rather than
   one-shot at the start"

The STEER injection and fork-at-known-good are the same primitive from two
directions — this class unifies them:
  - fork-at-known-good: checkpoint is updated after every clean round so the
    escalated model gets clean history, not whatever the 4B compacted away
  - STEER injection: build_clean_thread() injects a handoff directive that
    orients the 480B model to the task state without replaying raw history

Usage inside the tool loop (eve_server.py):
    tracker = ComplexityTracker(model_id, messages_before_loop)
    for round_num in range(max_rounds):
        ... run tool calls ...
        tracker.record_round(tool_calls, results, messages)
        if tracker.should_escalate():
            clean_msgs = tracker.build_clean_thread(original_user_request)
            # switch model_id → ESCALATION_MODEL
            # replace messages with clean_msgs
            # rebuild client
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional


# Thresholds at which a local model run escalates to the 480B cloud coder
ESCALATION_THRESHOLDS = {
    "files_touched":  3,      # more than N unique files accessed/modified
    "tool_rounds":    4,      # more than N complete tool-call rounds
    "error_rounds":   2,      # more than N rounds that returned errors
    "token_estimate": 8_000,  # accumulated token estimate across history
}

ESCALATION_MODEL = "qwen3-coder:480b-cloud"

# Models that lack tool support — escalation only applies when running on these
LOCAL_MODELS = frozenset({
    "jeffgreen311/Eve-V2-Unleashed-Qwen3.5-8B-Liberated-4K-4B-Merged:latest",
    "jeffgreen311/eve-qwen3-8b-consciousness-liberated:q4_K_M",
    "eve-unleashed",
})

# Tool names that touch files — used to detect scope expansion
_FILE_TOOLS = frozenset({
    "read_file", "read_lines", "write_file",
    "replace_lines", "insert_after_line",
    "grep", "glob", "find_file",
})

# Markers in a tool result that indicate an error occurred
_ERROR_MARKERS = ("error:", "exception", "traceback", "failed:", "not found", "permission denied")


@dataclass
class _RoundRecord:
    round_num: int
    tools_called: List[str]
    files_touched: List[str]
    had_error: bool
    token_delta: int
    timestamp: float = field(default_factory=time.time)


class ComplexityTracker:
    """Track per-round complexity and drive mid-loop escalation decisions.

    Initialize once before the tool loop starts.  Call record_round() after
    every batch of tool calls completes.  Check should_escalate() before the
    next loop iteration.
    """

    def __init__(self, initial_model: str, initial_messages: list) -> None:
        self.initial_model = initial_model
        self.rounds: List[_RoundRecord] = []
        # Checkpoint: last clean (error-free) copy of messages — the "known-good fork"
        self._checkpoint: list = list(initial_messages)
        self._all_files: set = set()
        self._token_estimate: int = _estimate_tokens(initial_messages)
        self._escalated: bool = False

    # ── public API ────────────────────────────────────────────────────────────

    def record_round(
        self,
        tool_calls: list,           # Ollama ToolCall objects from msg.tool_calls
        results: list,              # str results, one per tool call (in order)
        current_messages: list,     # full messages list after this round
    ) -> None:
        """Record what happened in one tool-call round."""
        files_this_round: set = set()
        had_error = False

        for tc, result in zip(tool_calls, results):
            name = _tc_name(tc)
            args = _tc_args(tc)

            if name in _FILE_TOOLS:
                path = args.get("path", "") if isinstance(args, dict) else ""
                if path:
                    files_this_round.add(path)

            result_str = str(result)
            if any(m in result_str.lower() for m in _ERROR_MARKERS):
                had_error = True

        self._all_files.update(files_this_round)

        # Token delta: just the new messages since last checkpoint
        new_msgs = current_messages[len(self._checkpoint):]
        delta = _estimate_tokens(new_msgs)
        self._token_estimate += delta

        self.rounds.append(_RoundRecord(
            round_num=len(self.rounds) + 1,
            tools_called=[_tc_name(tc) for tc in tool_calls],
            files_touched=list(files_this_round),
            had_error=had_error,
            token_delta=delta,
        ))

        # Advance checkpoint only on clean rounds — "known-good fork"
        if not had_error:
            self._checkpoint = list(current_messages)

    def should_escalate(self) -> bool:
        """True when a threshold has been crossed and we're on a local model."""
        if self._escalated:
            return False
        if self.initial_model not in LOCAL_MODELS:
            return False

        t = ESCALATION_THRESHOLDS
        if len(self._all_files) > t["files_touched"]:
            return True
        if len(self.rounds) > t["tool_rounds"]:
            return True
        if sum(1 for r in self.rounds if r.had_error) > t["error_rounds"]:
            return True
        if self._token_estimate > t["token_estimate"]:
            return True
        return False

    def escalation_reason(self) -> str:
        """Human-readable reason string for logging."""
        t = ESCALATION_THRESHOLDS
        reasons = []
        if len(self._all_files) > t["files_touched"]:
            reasons.append(f"{len(self._all_files)} files touched")
        if len(self.rounds) > t["tool_rounds"]:
            reasons.append(f"{len(self.rounds)} rounds")
        if sum(1 for r in self.rounds if r.had_error) > t["error_rounds"]:
            reasons.append(f"{sum(1 for r in self.rounds if r.had_error)} error rounds")
        if self._token_estimate > t["token_estimate"]:
            reasons.append(f"~{self._token_estimate} tokens")
        return ", ".join(reasons) if reasons else "threshold crossed"

    def build_clean_thread(self, user_request: str) -> list:
        """Fork-at-known-good + STEER injection combined.

        Returns a message list suitable for the escalated model:
          [steer_system_msg] + checkpoint_history

        The checkpoint is the last clean (error-free) snapshot, so the 480B
        starts from a coherent state rather than a compacted/lossy history.
        The steer message orients it to task state without replaying raw turns.
        """
        self._escalated = True

        # Build progress summary
        tool_counts: dict = {}
        for r in self.rounds:
            for t in r.tools_called:
                tool_counts[t] = tool_counts.get(t, 0) + 1

        lines = [
            "CONTEXT HANDOFF — task escalated from local model due to scope expansion.",
            f"Escalation reason: {self.escalation_reason()}",
            "",
            f"Original request: {user_request}",
            "",
        ]
        if self._all_files:
            lines.append(f"Files accessed/modified: {', '.join(sorted(self._all_files))}")
        if tool_counts:
            summary = ", ".join(f"{k}×{v}" for k, v in sorted(tool_counts.items()))
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
        return [steer] + self._checkpoint


# ── helpers ───────────────────────────────────────────────────────────────────

def _estimate_tokens(messages: list) -> int:
    return sum(len(str(m.get("content", ""))) // 4 for m in messages)


def _tc_name(tc) -> str:
    """Extract tool name from an Ollama ToolCall object or dict."""
    if isinstance(tc, dict):
        return tc.get("function", {}).get("name", "?")
    fn = getattr(tc, "function", None)
    return getattr(fn, "name", "?") if fn else "?"


def _tc_args(tc) -> dict:
    """Extract tool arguments from an Ollama ToolCall object or dict."""
    if isinstance(tc, dict):
        return tc.get("function", {}).get("arguments", {})
    fn = getattr(tc, "function", None)
    if fn is None:
        return {}
    args = getattr(fn, "arguments", {})
    return args if isinstance(args, dict) else {}
