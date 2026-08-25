"""Application read models for ``aeat app overview``.

The package owns the typed DTOs and pure builders behind the overview
``status``, ``calendar``, ``agenda``, ``backlog``, and ``explain``
surfaces. CLI adapters supply the active profile or bucket state,
already-persisted live-read snapshots, local filing records, and query dates;
these builders do not contact AEAT and do not mutate storage.

``overview status`` delegates to
:func:`application.state_projection.build_operator_state_projection`
and projects the canonical
:class:`application.state_projection.OperatorStateProjection` through
:func:`overview_status_report_from_projection` into
:class:`OverviewStatusReport`. ``overview calendar`` composes the existing
:class:`domain.deadlines.DeadlineEngine` over the requested year
window, returning :class:`OverviewCalendarEntry` obligation rows, additive
:class:`OverviewCalendarEvent` observations, and
:class:`OverviewCalendarFilingEvidence` rows.

Calendar evidence deliberately keeps :class:`OverviewLocalFilingState`
separate from :class:`OverviewAeatSubmissionState`: a local ready/filed
record never implies an AEAT submission, and an observed AEAT submission
is not a verified justificante until persisted receipt metadata proves
the CSV/model/year/period/taxpayer match. Raw profile values may also
produce typed :class:`CalendarWarning` and :class:`CalendarCompleteness`
records through :func:`build_filing_obligation_advisories` so
deadline-engine defaults are visible rather than silent.

See Also:
    :mod:`application.state_projection`
        Canonical producer for the :class:`application.state_projection.OperatorStateProjection`
        consumed by ``overview status``.
    :mod:`domain.deadlines`
        Deadline engine and :class:`domain.deadlines.Schedule` authority
        used by calendar, agenda, backlog, and explain read models.
    :mod:`application.live`
        Read-only capture surface that persists the live evidence this package
        can display without opening AEAT again.
    :mod:`domain.modelos`
        Local :class:`domain.modelos.ModeloRecord` and
        :class:`domain.modelos.ExternalEvidence` records projected into
        overview calendar evidence.
    :mod:`application.workflow`
        Active-profile and pending-obligation state that remains upstream of
        overview rendering.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ...core import Modelo as _Modelo
from ...core.decimal import coerce_decimal_strict as _coerce_decimal_strict
from ...core.logging import get_logger as _get_logger
from ...domain.calculations.registry.applicability import derive_modelo_applicability
from ...domain.deadlines import (
    evaluate_multiple_pagadores_obligation as _evaluate_multiple_pagadores_obligation,
)
from ._calendar import (
    actionable_post_filing_events,
    build_overview_calendar,
    build_overview_calendar_events,
    calendar_events_from_expedientes_snapshots,
    calendar_events_from_justificante_capture_snapshots,
    calendar_events_from_modelo_records,
    calendar_events_from_notification_snapshots,
)
from ._calendar_evidence import (
    NO_AEAT_HISTORY_NOTICE_CODE,
    calendar_filing_evidence_from_sources,
    no_aeat_history_notice,
)
from ._calendar_models import (
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
    user_state_for,
)
from ._calendar_warnings import (
    calendar_applicability_profile_keys_for_modelo,
    calendar_censo_enrolment_profile_keys,
)
from ._coverage import (
    AdvisedObligation,
    CoverageAdviceReason,
    ObligationCoverageReport,
    build_obligation_coverage,
)
from ._data_prep import (
    DataPrepStep,
    DataPrepStepId,
    DataPrepStepState,
    DataPrepWalkthrough,
    build_data_prep_walkthrough,
)
from .errors import (
    OverviewAgendaError,
    OverviewBacklogError,
    OverviewCalendarError,
    OverviewError,
    OverviewExplainError,
)
from ._next_actions import (
    OverviewStatusNextStep,
    OverviewStatusNextStepId,
    build_overview_status_next_steps,
    declare_next_action,
)
from ._pipeline_health import (
    ModeloHealthRow,
    ModeloReadinessState,
    PipelineHealthReport,
    build_pipeline_health_report,
)

if TYPE_CHECKING:
    from ..state_projection import OperatorStateProjection
    from cadrumo.application.workflow.state_models import WorkflowState
    from ._agenda import build_overview_agenda
    from ._backlog import build_overview_backlog
    from ._explain import build_overview_explain

_log = _get_logger(__name__)

#: Advisory locale key surfaced when the Art. 96.3 LIRPF multiple-pagadores
#: filing obligation is detected. Named as a ``_LOCALE_KEY`` constant so the
#: locale scaffold's AST scanner discovers it for parity (the key is returned
#: from a builder rather than passed to ``tr()`` at this call site).
_MULTIPLE_PAGADORES_OBLIGATION_LOCALE_KEY = "cli.overview.status.filing_obligation_multiple_pagadores"


def build_filing_obligation_advisories(
    raw_values: Mapping[str, object] | None,
    *,
    filing_year: int | None = None,
) -> tuple[str, ...]:
    """Derive overview-status advisory locale keys from raw profile values.

    The helper feeds :class:`OverviewStatusReport` and stays on the local
    read-model path. It implements the Art. 96.2.a)/96.3 LIRPF
    multiple-pagadores rule through
    :func:`domain.deadlines.evaluate_multiple_pagadores_obligation`:
    when the operator has declared ``irpf.pagadores_count >= 2`` and
    ``irpf.pagadores_secondary_income > 1500``, the work-income exemption
    limit drops from the general €22,000 to the per-year reduced limit, and
    Modelo 100 filing is mandatory when ``irpf.pagadores_total_work_income``
    exceeds that reduced limit. When the total work income is undeclared, the
    advisory surfaces conservatively rather than granting a false clear.

    Args:
        raw_values: Profile raw values mapping, or ``None``.
        filing_year: The income year selecting the dated reduced limit; when
            ``None`` the latest known reduced limit is used (the current
            figure for a year-agnostic operator surface).

    Returns a tuple of ``tr()``-resolvable locale keys, empty when no
    evidence of a mandatory obligation is present. Malformed raw values are
    logged only by profile-field name and exception type.
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
    total_work_income = _to_decimal(
        "irpf.pagadores_total_work_income",
        raw_values.get("irpf.pagadores_total_work_income"),
    )

    if _evaluate_multiple_pagadores_obligation(
        pagadores_count,
        secondary_income,
        total_work_income,
        filing_year,
    ):
        return (_MULTIPLE_PAGADORES_OBLIGATION_LOCALE_KEY,)
    return ()


def build_unsupported_work_create_modelos(
    raw_values: Mapping[str, object] | None,
) -> tuple[str, ...]:
    """Return modelos whose local work-create path is unsupported.

    The result feeds :class:`OverviewStatusReport` and uses canonical
    :class:`core.Modelo` identifiers. Non-resident IRNR profile state
    currently advertises Modelo 210 because the local work-create path is not
    available for that filing.
    """
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
    the one :class:`application.state_projection.OperatorStateProjection`;
    it is not a second state-assembly path. Both the declaration-draft
    :class:`domain.filing.ModeloDraft` count and the
    :class:`domain.modelos.WorkUnitCatalogue` count are carried
    distinctly.

    Args:
        projection: The canonical state projection to project.
        raw_values: Optional profile raw values mapping. When supplied,
            used to evaluate filing-obligation advisories (e.g., the
            Art. 96.3 LIRPF multiple-pagadores rule).

    Returns:
        An :class:`OverviewStatusReport` derived from the projection.
    """
    return OverviewStatusReport(
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

    Consumes the canonical
    :func:`application.state_projection.build_operator_state_projection`
    and projects it through :func:`overview_status_report_from_projection`;
    the bespoke per-surface store assembly this function once carried is
    deleted. ``overview status`` therefore reports the same counters as
    every other operator surface — including the ``modelo work`` work units the
    old assembly never read.
    """
    from ..state_projection import build_operator_state_projection

    projection = build_operator_state_projection(state=state)
    return overview_status_report_from_projection(projection, raw_values=raw_values)


__all__ = [
    "NO_AEAT_HISTORY_NOTICE_CODE",
    "AdvisedObligation",
    "CalendarCompleteness",
    "CalendarWarning",
    "CoverageAdviceReason",
    "DataPrepStep",
    "DataPrepStepId",
    "DataPrepStepState",
    "DataPrepWalkthrough",
    "ModeloHealthRow",
    "ModeloReadinessState",
    "ObligationCoverageReport",
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
    "OverviewStatusNextStep",
    "OverviewStatusNextStepId",
    "OverviewStatusReport",
    "PipelineHealthReport",
    "SuppressedCalendarEntry",
    "actionable_post_filing_events",
    "build_data_prep_walkthrough",
    "build_filing_obligation_advisories",
    "build_obligation_coverage",
    "build_overview_agenda",
    "build_overview_backlog",
    "build_overview_calendar",
    "build_overview_calendar_events",
    "build_overview_explain",
    "build_overview_status_next_steps",
    "build_overview_status_report",
    "build_pipeline_health_report",
    "build_unsupported_work_create_modelos",
    "calendar_applicability_profile_keys_for_modelo",
    "calendar_censo_enrolment_profile_keys",
    "calendar_events_from_expedientes_snapshots",
    "calendar_events_from_justificante_capture_snapshots",
    "calendar_events_from_modelo_records",
    "calendar_events_from_notification_snapshots",
    "calendar_filing_evidence_from_sources",
    "declare_next_action",
    "derive_modelo_applicability",
    "no_aeat_history_notice",
    "overview_status_report_from_projection",
    "user_state_for",
]


def __getattr__(name: str):
    """Lazy-import the agenda / backlog / explain entrypoints.

    The eager top-of-module import would trigger a circular-import:
    those submodules import names from this package while it is
    still initialising. The lazy path keeps the symbols reachable
    through the package boundary per the
    ``aeat-architecture-boundaries`` rule.
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
