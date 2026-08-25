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

_ERROR_CODE = re.compile(r"[a-z][a-z0-9_.-]{0,127}\Z")


@dataclass(frozen=True, slots=True)
class SafeErrorRecord:
    """Bounded display facts extracted from one canonical error envelope."""

    code: str
    category: str
    message: str

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
        yield Static(
            f"{self._record.category}: {self._record.code}",
            classes="cadrumo-error-heading",
            markup=False,
        )
        yield Static(self._record.message, classes="cadrumo-error-message", markup=False)


__all__ = ["MAX_ERROR_MESSAGE_CHARACTERS", "ErrorPanel", "SafeErrorRecord"]
