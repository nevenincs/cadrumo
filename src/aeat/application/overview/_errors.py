"""Narrow exceptions for overview read-model assembly.

Overview services are local application projections. These exceptions
cover failures to assemble status, calendar, agenda, backlog, or explain
payloads from already-loaded inputs rather than transport or AEAT live
read failures.
"""

from __future__ import annotations

from ...core.errors import AeatError


class OverviewError(AeatError):
    """Base error for overview calendar / agenda / backlog / explain failures."""


class OverviewCalendarError(OverviewError):
    """Raised when the overview calendar cannot be assembled for the requested window."""


class OverviewAgendaError(OverviewError):
    """Raised when the overview agenda cannot enumerate next-due actions."""


class OverviewBacklogError(OverviewError):
    """Raised when the overview backlog cannot classify past-due obligations."""


class OverviewExplainError(OverviewError):
    """Raised when the overview-explain decomposition fails for the requested obligation."""
