"""Typed overview-status surface for ``aeat app overview``.

The CLI exposes::

    aeat app overview status                                # bare readiness
    aeat app overview status --period {period} --verbose
    aeat app overview calendar --from DATE --to DATE

The calendar view uses a closed 4-state user-facing taxonomy that maps
from the existing :class:`aeat.domain.deadlines.ObligationStatus`
six-state enum. The typed query record
(:class:`OverviewCalendarRange`), the per-period entry record
(:class:`OverviewCalendarEntry`), the result wrapper
(:class:`OverviewCalendar`), the user-facing state enum
(:class:`OverviewPeriodState`), and the
:func:`build_overview_calendar` aggregator that composes the existing
:class:`aeat.domain.deadlines.DeadlineEngine` over the year window.

The aggregator is pure: no I/O, no mutation. The CLI wires it to the
operator's active :class:`TaxpayerProfile` and the parsed ``--from`` /
``--to`` dates. The resulting :class:`Schedule` drives obligation
date computation and period-level state classification.

When the caller supplies ``raw_values`` (the operator's user_cli
profile values mapping), the aggregator additionally detects which
deadline-engine-consumed keys are unset and surfaces a typed
``CalendarWarning`` per missing key plus a ``CalendarCompleteness``
breakdown listing computable / under-default modelos. The
profile-completeness surface ensures the engine never silently
computes obligations from its defaults without flagging that the
operator never declared a gating field.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ...core import Modelo as _Modelo
from ...core.decimal import coerce_decimal_strict as _coerce_decimal_strict
from ...core.logging import get_logger as _get_logger
from ...domain.deadlines import (
    evaluate_multiple_pagadores_obligation as _evaluate_multiple_pagadores_obligation,
)
from ._calendar import (
    CalendarCompleteness,
    CalendarWarning,
    OverviewAeatSubmissionState,
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    OverviewCensoEnrolmentState,
    OverviewLocalFilingState,
    OverviewPeriodState,
    OverviewStatusReport,
    SuppressedCalendarEntry,
    build_overview_calendar,
    build_overview_calendar_events,
    calendar_applicability_profile_keys_for_modelo,
    calendar_censo_enrolment_profile_keys,
    calendar_events_from_expedientes_snapshots,
    calendar_events_from_justificante_capture_snapshots,
    calendar_events_from_modelo_records,
    calendar_events_from_notification_snapshots,
    calendar_filing_evidence_from_sources,
    derive_modelo_applicability,
    user_state_for,
)
from ._errors import (
    OverviewAgendaError,
    OverviewBacklogError,
    OverviewCalendarError,
    OverviewError,
    OverviewExplainError,
)

if TYPE_CHECKING:
    from ..state_projection import OperatorStateProjection
    from ..workflow import WorkflowState
    from ._agenda import build_overview_agenda
    from ._backlog import build_overview_backlog
    from ._explain import build_overview_explain

_log = _get_logger(__name__)


def build_filing_obligation_advisories(
    raw_values: Mapping[str, object] | None,
) -> tuple[str, ...]:
    """Derive filing-obligation advisory locale keys from the profile values.

    Currently implements the Art. 96.3 LIRPF multiple-pagadores rule:
    when the operator has declared ``irpf.pagadores_count >= 2`` and
    ``irpf.pagadores_secondary_income > 1500``, Modelo 100 filing is
    mandatory regardless of the general income thresholds.

    Returns a tuple of ``tr()``-resolvable locale keys, empty when no
    evidence of a mandatory obligation is present.
    """
    if raw_values is None:
        return ()

    def _to_int(field_name: str, v: object) -> int | None:
        if v is None or str(v).strip() == "":
            return None
        try:
            return int(str(v).strip())
        except ValueError as exc:
            _log.debug(
                "overview filing obligation advisory ignored invalid integer profile value",
                extra={"profile_field": field_name, "error_type": type(exc).__name__},
            )
            return None

    def _to_decimal(field_name: str, v: object) -> Decimal | None:
        if v is None or str(v).strip() == "":
            return None
        try:
            return _coerce_decimal_strict(v)
        except (InvalidOperation, ValueError) as exc:
            _log.debug(
                "overview filing obligation advisory ignored invalid decimal profile value",
                extra={"profile_field": field_name, "error_type": type(exc).__name__},
            )
            return None

    pagadores_count = _to_int("irpf.pagadores_count", raw_values.get("irpf.pagadores_count"))
    secondary_income = _to_decimal("irpf.pagadores_secondary_income", raw_values.get("irpf.pagadores_secondary_income"))

    if _evaluate_multiple_pagadores_obligation(pagadores_count, secondary_income):
        return ("cli.overview.status.filing_obligation_multiple_pagadores",)
    return ()


def build_unsupported_work_create_modelos(
    raw_values: Mapping[str, object] | None,
) -> tuple[str, ...]:
    """Return registry-visible modelos whose local work-create path is unsupported."""
    if raw_values is None:
        return ()
    fiscal_residency = (
        str(
            raw_values.get("taxpayer.fiscal_residency") or raw_values.get("taxpayer_type.fiscal_residency") or "",
        )
        .strip()
        .lower()
    )
    if fiscal_residency == "non_resident_irnr":
        return (_Modelo.M210.value,)
    return ()


def overview_status_report_from_projection(
    projection: OperatorStateProjection,
    *,
    raw_values: Mapping[str, object] | None = None,
) -> OverviewStatusReport:
    """Project the canonical state projection into the ``overview status`` emit shape.

    The :class:`OverviewStatusReport` is a CLI emit shape derived from
    the one :class:`OperatorStateProjection`; it is not a second
    state-assembly path. Both the legacy ``ModeloDraft`` count and the
    ``WorkUnitCatalogue`` count are carried distinctly.

    Args:
        projection: The canonical state projection to project.
        raw_values: Optional profile raw values mapping. When supplied,
            used to evaluate filing-obligation advisories (e.g., the
            Art. 96.3 LIRPF multiple-pagadores rule).

    Returns:
        An :class:`OverviewStatusReport` derived from the projection.
    """
    return OverviewStatusReport(
        active_profile=projection.active_profile.profile_id,
        active_profile_name=projection.active_profile.label,
        transactions=projection.workspace.transactions,
        invoices=projection.workspace.invoices,
        drafts=projection.workspace.drafts,
        work_units=projection.workspace.work_units,
        discarded_work_units=projection.workspace.discarded_work_units,
        calculation_revisions=projection.workspace.calculation_revisions,
        unreadable_rows=projection.workspace.unreadable_rows,
        filing_obligation_advisories=build_filing_obligation_advisories(raw_values),
        unsupported_work_create_modelos=build_unsupported_work_create_modelos(raw_values),
    )


def build_overview_status_report(
    *,
    state: WorkflowState | None = None,
    raw_values: Mapping[str, object] | None = None,
) -> OverviewStatusReport:
    """Build and return the :class:`OverviewStatusReport` used by root and overview status.

    Consumes the canonical :func:`build_operator_state_projection`; the
    bespoke per-surface store assembly this function once carried is
    deleted. ``overview status`` therefore reports the same counters as
    every other operator surface — including the ``modelo work`` work
    units the old assembly never read.
    """
    from ..state_projection import build_operator_state_projection

    projection = build_operator_state_projection(state=state)
    return overview_status_report_from_projection(projection, raw_values=raw_values)


__all__ = [
    "CalendarCompleteness",
    "CalendarWarning",
    "OverviewAeatSubmissionState",
    "OverviewAgendaError",
    "OverviewBacklogError",
    "OverviewCalendar",
    "OverviewCalendarEntry",
    "OverviewCalendarError",
    "OverviewCalendarEvent",
    "OverviewCalendarEventType",
    "OverviewCalendarFilingEvidence",
    "OverviewCalendarRange",
    "OverviewCensoEnrolmentState",
    "OverviewError",
    "OverviewExplainError",
    "OverviewLocalFilingState",
    "OverviewPeriodState",
    "OverviewStatusReport",
    "SuppressedCalendarEntry",
    "build_filing_obligation_advisories",
    "build_overview_agenda",
    "build_overview_backlog",
    "build_overview_calendar",
    "build_overview_calendar_events",
    "build_overview_explain",
    "build_overview_status_report",
    "build_unsupported_work_create_modelos",
    "calendar_applicability_profile_keys_for_modelo",
    "calendar_censo_enrolment_profile_keys",
    "calendar_events_from_expedientes_snapshots",
    "calendar_events_from_justificante_capture_snapshots",
    "calendar_events_from_modelo_records",
    "calendar_events_from_notification_snapshots",
    "calendar_filing_evidence_from_sources",
    "derive_modelo_applicability",
    "overview_status_report_from_projection",
    "user_state_for",
]


def __getattr__(name: str):
    """Lazy-import the agenda / backlog / explain entrypoints.

    The eager top-of-module import would trigger a circular-import:
    those submodules import names from this package while it is
    still initialising. The lazy path keeps the symbols reachable
    through the package boundary per the
    ``service-imports-via-top-level-reexports`` rule.
    """
    if name == "build_overview_agenda":
        from ._agenda import build_overview_agenda as _impl

        return _impl
    if name == "build_overview_backlog":
        from ._backlog import build_overview_backlog as _impl

        return _impl
    if name == "build_overview_explain":
        from ._explain import build_overview_explain as _impl

        return _impl
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
