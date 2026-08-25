"""Inert rendering of already-safe canonical error envelopes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, override

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from ....core.errors import ErrorCategory, ErrorEnvelope
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


def safe_error_record(envelope: ErrorEnvelope) -> SafeErrorRecord:
    """Project one canonical envelope without reading context or diagnostics."""
    if not isinstance(envelope, ErrorEnvelope):
        raise TypeError("error renderer accepts ErrorEnvelope, never a raw exception")
    if not isinstance(envelope.code, str) or _ERROR_CODE.fullmatch(envelope.code) is None:
        raise ValueError("error envelope code is not a stable presentation identifier")
    try:
        category = ErrorCategory(envelope.category)
    except ValueError as error:
        raise ValueError("error envelope category is not a closed presentation category") from error
    if category.value != envelope.category:
        raise ValueError("error envelope category is not a closed presentation category")
    return SafeErrorRecord(
        code=envelope.code,
        category=category.value,
        message=bounded_pre_redacted_text(
            envelope.message,
            field="error envelope message",
            maximum_characters=MAX_ERROR_MESSAGE_CHARACTERS,
        ),
    )


class ErrorPanel(Vertical, can_focus=False):
    """Render a safe error envelope without retaining exception authority."""

    def __init__(self, envelope: ErrorEnvelope, *, id: str | None = None, classes: str | None = None) -> None:
        """Store only the bounded facts this panel is permitted to display."""
        super().__init__(id=id, classes=classes)
        self._record = safe_error_record(envelope)

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


__all__ = ["MAX_ERROR_MESSAGE_CHARACTERS", "ErrorPanel", "SafeErrorRecord", "safe_error_record"]
