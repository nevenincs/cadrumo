"""Inert rendering of already-safe canonical error envelopes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, override

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from ._safe_text import bounded_pre_redacted_text

MAX_ERROR_MESSAGE_CHARACTERS: Final[int] = 320
"""Maximum public error prose retained by the reusable component."""

MAX_ERROR_ACTION_LABEL_CHARACTERS: Final[int] = 80
"""Maximum public retry/next-step action label retained by the component."""

MAX_ERROR_RUNBOOK_ID_CHARACTERS: Final[int] = 80
"""Maximum public runbook identifier retained by the component."""

_ERROR_CODE = re.compile(r"[a-z][a-z0-9_.-]{0,127}\Z")


@dataclass(frozen=True, slots=True)
class SafeErrorRecord:
    """Bounded display facts extracted from one canonical error envelope.

    Mirrors the safe subset of :class:`core.errors.ErrorEnvelope` this
    reusable component is permitted to show: code, category, localized
    message, a typed action label, and retryability with its runbook. The
    envelope's ``context`` and ``trace_id`` fields are deliberately never
    accepted here -- diagnostic-shaped material stays operator-support-only,
    never a public TUI surface.
    """

    code: str
    category: str
    message: str
    action_label: str | None = None
    retryable: bool = False
    runbook_id: str | None = None

    def __post_init__(self) -> None:
        """Retain only bounded, pre-redacted presentation facts."""
        if _ERROR_CODE.fullmatch(self.code) is None:
            raise ValueError("error code is not a stable presentation identifier")
        if self.category not in {"BUG", "CONFLICT", "REFUSED", "TRANSIENT", "UNAVAILABLE"}:
            raise ValueError("error category is not a closed presentation category")
        object.__setattr__(
            self,
            "message",
            bounded_pre_redacted_text(
                self.message,
                field="error envelope message",
                maximum_characters=MAX_ERROR_MESSAGE_CHARACTERS,
            ),
        )
        if self.action_label is not None:
            object.__setattr__(
                self,
                "action_label",
                bounded_pre_redacted_text(
                    self.action_label,
                    field="error envelope action label",
                    maximum_characters=MAX_ERROR_ACTION_LABEL_CHARACTERS,
                ),
            )
        if self.runbook_id is not None:
            object.__setattr__(
                self,
                "runbook_id",
                bounded_pre_redacted_text(
                    self.runbook_id,
                    field="error envelope runbook identifier",
                    maximum_characters=MAX_ERROR_RUNBOOK_ID_CHARACTERS,
                ),
            )


class ErrorPanel(Vertical, can_focus=False):
    """Render a safe error envelope without retaining exception authority."""

    def __init__(self, record: SafeErrorRecord, *, id: str | None = None, classes: str | None = None) -> None:
        """Store only the bounded facts this panel is permitted to display."""
        super().__init__(id=id, classes=classes)
        if not isinstance(record, SafeErrorRecord):
            raise TypeError("error renderer accepts SafeErrorRecord, never a raw exception")
        self._record = record

    @property
    def record(self) -> SafeErrorRecord:
        """Return the immutable display facts mounted by this panel."""
        return self._record

    @override
    def compose(self) -> ComposeResult:
        record = self._record
        yield Static(
            f"{record.category}: {record.code}",
            classes="cadrumo-error-heading",
            markup=False,
        )
        yield Static(record.message, classes="cadrumo-error-message", markup=False)
        if record.action_label is not None:
            yield Static(
                record.action_label,
                classes="cadrumo-error-action",
                id="cadrumo-error-action",
                markup=False,
            )
        retry_glyph = "↻" if record.retryable else "✕"
        retry_text = "retry" if record.retryable else "not retryable"
        yield Static(
            f"{retry_glyph} {retry_text}",
            classes=f"cadrumo-error-retry cadrumo-error-retry-{'yes' if record.retryable else 'no'}",
            id="cadrumo-error-retry",
            markup=False,
        )
        if record.runbook_id is not None:
            yield Static(
                record.runbook_id,
                classes="cadrumo-error-runbook",
                id="cadrumo-error-runbook",
                markup=False,
            )


__all__ = [
    "MAX_ERROR_ACTION_LABEL_CHARACTERS",
    "MAX_ERROR_MESSAGE_CHARACTERS",
    "MAX_ERROR_RUNBOOK_ID_CHARACTERS",
    "ErrorPanel",
    "SafeErrorRecord",
]
