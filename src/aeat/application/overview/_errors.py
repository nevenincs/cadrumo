"""Narrow exceptions for overview read-model assembly.

Overview services are local application projections. These exceptions
cover failures to assemble status, calendar, agenda, backlog, or explain
payloads from already-loaded inputs rather than transport or AEAT live
read failures. They inherit from :class:`~aeat.core.errors.AeatError` so the
central error registry can map overview failures to stable CLI envelopes.
"""

from __future__ import annotations

from ...core.errors import AeatError


class OverviewError(AeatError):
    """Base error for overview status, calendar, agenda, backlog, and explain failures."""


class OverviewCalendarError(OverviewError):
    """Raised when :func:`aeat.application.overview.build_overview_calendar` fails."""


class OverviewAgendaError(OverviewError):
    """Raised when :func:`aeat.application.overview.build_overview_agenda` fails."""


class OverviewBacklogError(OverviewError):
    """Raised when :func:`aeat.application.overview.build_overview_backlog` fails."""


class OverviewExplainError(OverviewError):
    """Raised when :func:`aeat.application.overview.build_overview_explain` fails."""
