"""CLIHumanFeedbackAdapter: routes @human_feedback to stdin/stdout (D0-10).

Per spec cli-runner requirement 2: 3 confirmation points MUST block on stdin.
The CrewAI @human_feedback decorator is replaced by this adapter in Dev-Phase 0.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class FeedbackResult:
    kind: str
    approved: bool
    edited_payload: dict[str, Any] | None = None
    comment: str | None = None


def prompt_user(
    kind: str,
    payload: dict[str, Any],
    *,
    prompt_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None] | None = None,
) -> FeedbackResult:
    """Block on stdin/stdout, asking user to confirm/edit/reject.

    Args:
        kind: confirmation point name (requirement_confirmation / design_confirmation / task_confirmation)
        payload: data to display
        prompt_fn: stdin reader (default: input)
        output_fn: stdout writer (default: print)

    Returns:
        FeedbackResult with approved + optional edited_payload + comment
    """
    pfn = prompt_fn or input
    ofn = output_fn or print

    ofn("")
    ofn("=" * 60)
    ofn(f"确认点: {kind}")
    ofn("=" * 60)
    _pretty_print(payload, output_fn=ofn)
    ofn("")
    ofn("选项: [y] 同意继续  /  [n] 中止流程  /  [e] 编辑（输入注释后继续）")
    while True:
        try:
            choice = pfn("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return FeedbackResult(kind=kind, approved=False, comment="user-aborted")
        if choice in {"y", "yes"}:
            return FeedbackResult(kind=kind, approved=True)
        if choice in {"n", "no"}:
            return FeedbackResult(kind=kind, approved=False)
        if choice in {"e", "edit"}:
            try:
                comment = pfn("注释（可选，直接回车跳过）: ").strip()
            except (EOFError, KeyboardInterrupt):
                comment = "edit-aborted"
            return FeedbackResult(kind=kind, approved=True, comment=comment or None)
        ofn("无效选项，请输入 y / n / e")


def _pretty_print(d: Any, *, indent: int = 0, output_fn: Callable[[str], None] = print) -> None:
    """Pretty-print a dict/list/value to output_fn."""
    pad = "  " * indent
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, (dict, list)):
                output_fn(f"{pad}{k}:")
                _pretty_print(v, indent=indent + 1, output_fn=output_fn)
            else:
                output_fn(f"{pad}{k}: {v}")
    elif isinstance(d, list):
        for i, item in enumerate(d):
            if isinstance(item, (dict, list)):
                output_fn(f"{pad}[{i}]:")
                _pretty_print(item, indent=indent + 1, output_fn=output_fn)
            else:
                output_fn(f"{pad}- {item}")
    else:
        output_fn(f"{pad}{d}")


class CLIHumanFeedbackAdapter:
    """Adapter that connects LinearPhase02Flow's confirmation points to prompt_user().

    Returns True if approved, False if rejected (flow aborts).
    """

    def __init__(
        self,
        *,
        prompt_fn: Callable[[str], str] | None = None,
        output_fn: Callable[[str], None] | None = None,
        auto_approve: bool = False,
    ) -> None:
        self.prompt_fn = prompt_fn
        self.output_fn = output_fn
        self.auto_approve = auto_approve
        self.history: list[FeedbackResult] = []

    def __call__(self, kind: str, payload: dict[str, Any]) -> bool:
        """Invoke the confirmation prompt. Returns True if approved."""
        if self.auto_approve:
            self.history.append(FeedbackResult(kind=kind, approved=True))
            return True
        result = prompt_user(kind, payload, prompt_fn=self.prompt_fn, output_fn=self.output_fn)
        self.history.append(result)
        return result.approved
