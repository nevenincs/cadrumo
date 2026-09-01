"""Inert, bounded rendering of typed pre-redacted log records."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, override

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from ....core.i18n.render import tr
from ..components.theme import tokenised
from ._safe_text import bounded_pre_redacted_text

MAX_LOG_ENTRIES: Final[int] = 16
"""Largest retained log window allowed in the reusable component."""

MAX_LOG_MESSAGE_CHARACTERS: Final[int] = 240
"""Maximum public prose retained for one rendered log entry."""


class LogSeverity(StrEnum):
    """Closed visual severities for supplied safe log records."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class SafeLogRecord:
    """One pre-redacted, bounded record that is safe to show in the TUI."""

    severity: LogSeverity
    message: str

    def __post_init__(self) -> None:
        """Reject arbitrary logging objects and retain only safe display prose."""
        if not isinstance(self.severity, LogSeverity):
            raise TypeError("log severity must be a LogSeverity")
        object.__setattr__(
            self,
            "message",
            bounded_pre_redacted_text(
                self.message,
                field="log message",
                maximum_characters=MAX_LOG_MESSAGE_CHARACTERS,
            ),
        )


class BoundedLogPanel(Vertical, can_focus=True):
    """Render a fixed tail of supplied safe records without subscriptions.

    Owns bounded rendering, severity, wrapping, focus, and the empty state
    (`aeat-interface` D8): a panel with no supplied records renders one
    localized empty-state line rather than mounting nothing, so an operator
    tabbing through a screen sees the log channel exists and is quiet.
    """

    DEFAULT_CSS = tokenised("""
    BoundedLogPanel { height: auto; }
    BoundedLogPanel:focus { border: $cadrumo-radius $accent; }
    """)

    def __init__(
        self,
        records: Sequence[SafeLogRecord],
        *,
        maximum_entries: int = MAX_LOG_ENTRIES,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Copy only the final bounded record window for static presentation."""
        if not 1 <= maximum_entries <= MAX_LOG_ENTRIES:
            raise ValueError(f"maximum_entries must be between 1 and {MAX_LOG_ENTRIES}")
        supplied = tuple(records)
        if any(not isinstance(record, SafeLogRecord) for record in supplied):
            raise TypeError("log renderer accepts SafeLogRecord values only")
        super().__init__(id=id, classes=classes)
        self._records = supplied[-maximum_entries:]

    @property
    def records(self) -> tuple[SafeLogRecord, ...]:
        """Return the bounded immutable record tail rendered by this panel."""
        return self._records

    @override
    def compose(self) -> ComposeResult:
        if not self._records:
            yield Static(
                tr("component.log.empty"),
                id="cadrumo-log-empty",
                classes="cadrumo-log-empty",
                markup=False,
            )
            return
        for index, record in enumerate(self._records):
            yield Static(
                f"{record.severity.value.upper()}: {record.message}",
                id=f"cadrumo-log-{index}",
                classes=f"cadrumo-log cadrumo-log-{record.severity.value}",
                markup=False,
            )


__all__ = [
    "MAX_LOG_ENTRIES",
    "MAX_LOG_MESSAGE_CHARACTERS",
    "BoundedLogPanel",
    "LogSeverity",
    "SafeLogRecord",
]
