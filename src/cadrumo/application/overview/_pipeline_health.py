"""Pipeline health: cross-domain readiness summary for one filing period.

:func:`build_pipeline_health_report` is the application service backing
``aeat app overview pipeline --year YEAR --period PERIOD``. It answers the
operator-observable question "is my pipeline healthy for this period?" by
composing three already-existing read models for the requested
``(filing_year, period)`` scope into one typed report:

* ledger health — :func:`~application.ledger.summarize_manual_transactions`
  (active/pending-review/reviewed/skipped counts, readiness-issue count).
* modelo readiness — one :class:`ModeloHealthRow` per
  :class:`~domain.modelos.WorkUnit`
  targeting the requested period, derived from its
  :class:`~domain.modelos.CalculationRevision` state
  (:func:`~application.modelo.get_calculation_revision`) — not-started when
  no work unit exists yet for a modelo the operator would need to file.
* outstanding findings — every ``BLOCKING`` / ``WARNING``
  :class:`~domain.modelos.ModeloVerificationFinding` from the latest
  :class:`~domain.modelos.VerificationReport` against each period work
  unit's current revision.

The builder is READ-ONLY: it inspects the transaction catalogue, the modelo
work-unit catalogue, the calculation-revision catalogue, and the
verification-report catalogue for the requested scope. It persists nothing
and never contacts AEAT. Every counter it reports is already produced by an
existing read model or a direct repository read; this module composes them
into one cross-domain dashboard rather than introducing a new aggregation
(the ``composition-service-no-parallel-write-path`` discipline).

See Also:
    :mod:`~application.overview`
        Sibling read-only overview builders (``status``, ``prepare``,
        ``calendar``, ``agenda``, ``backlog``, ``explain``) this module
        follows the same shape as.
    :func:`~application.ledger.summarize_manual_transactions`
        Owns the ledger status counters this report's ledger section reuses
        rather than re-deriving.
    :class:`~domain.modelos.WorkUnit`
        The modelo work-unit record the readiness rows resolve against.
    :class:`~domain.modelos.VerificationReport`
        The findings source each readiness row's outstanding-findings list
        is drawn from.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...domain.modelos import (
    CalculationRevisionState,
    ModeloVerificationFindingSeverity,
)
from ..ledger import LedgerStatusReport

if TYPE_CHECKING:
    from ...domain.modelos import CalculationRevision, VerificationReport, WorkUnit


class ModeloReadinessState(StrEnum):
    """Closed lifecycle state for one modelo's readiness within a period.

    Attributes:
        NOT_STARTED: No :class:`~domain.modelos.WorkUnit` exists yet for
            this ``(modelo, filing_year, period)``.
        CALCULATED: A work unit exists and its current revision has computed
            casilla values but has not been verified.
        VERIFIED: The current revision reached
            :attr:`~domain.modelos.CalculationRevisionState.VERIFICADO_COMPLETO`.
        FILED: The work unit's filed revision matches its current revision
            (:attr:`~domain.modelos.CalculationRevisionState.PRESENTADO` or
            superseded by a later filed revision of the same unit).
        BLOCKED: The latest verification report against the current revision
            carries at least one ``BLOCKING`` finding.
    """

    NOT_STARTED = "not_started"
    CALCULATED = "calculated"
    VERIFIED = "verified"
    FILED = "filed"
    BLOCKED = "blocked"


class ModeloHealthRow(BaseModel):
    """One modelo's readiness row within a period health report.

    Attributes:
        modelo: AEAT modelo code (e.g. ``"130"``, ``"303"``).
        work_unit_id: The matching :class:`~domain.modelos.WorkUnit`
            id, or ``None`` when :attr:`state` is
            :attr:`~application.overview.ModeloReadinessState.NOT_STARTED`.
        state: Current :class:`ModeloReadinessState` for this modelo/period.
        blocking_finding_count: Count of ``BLOCKING`` severity findings from
            the latest verification report against the current revision.
        warning_finding_count: Count of ``WARNING`` severity (advisory)
            findings from the same report.
        summary: Human-readable one-line progress summary.
        next_command: The exact next ``aeat`` command to run to advance this
            modelo, or resolve its current gap.
    """

    model_config = _STRICT_FROZEN

    modelo: str
    work_unit_id: str | None = None
    state: ModeloReadinessState
    blocking_finding_count: int = Field(default=0, ge=0)
    warning_finding_count: int = Field(default=0, ge=0)
    summary: str
    next_command: str


class PipelineHealthReport(BaseModel):
    """Outcome of :func:`build_pipeline_health_report`.

    Attributes:
        bucket_id: Active profile bucket the report is scoped to.
        filing_year: Filing year for the requested scope.
        period: Registry period token for the requested scope (e.g. ``1T``).
        ledger: The reused :class:`~application.ledger.LedgerStatusReport`
            for the same ``(bucket_id, period)`` scope.
        modelos: Ordered :class:`ModeloHealthRow` rows, one per work unit
            found for the period, sorted by modelo code. Empty when no work
            unit has been created for this period yet.
        total_blocking_findings: Sum of every row's
            :attr:`~application.overview.ModeloHealthRow.blocking_finding_count`.
        total_warning_findings: Sum of every row's
            :attr:`~application.overview.ModeloHealthRow.warning_finding_count`.
        ready: ``True`` only when the ledger reports no unresolved
            readiness issues (or was not scoped) and every modelo row is
            :attr:`~application.overview.ModeloReadinessState.FILED` or
            :attr:`~application.overview.ModeloReadinessState.VERIFIED`, with
            zero modelos in
            :attr:`~application.overview.ModeloReadinessState.BLOCKED`.
            ``False`` when any modelo has not started or is blocked, or the
            ledger still carries pending-review rows or readiness issues. A
            pipeline with zero
            work units for the period is never reported ready — there is
            nothing to be ready about yet.
    """

    model_config = _STRICT_FROZEN

    bucket_id: str
    filing_year: int
    period: str
    ledger: LedgerStatusReport
    modelos: tuple[ModeloHealthRow, ...] = Field(default_factory=tuple)
    total_blocking_findings: int = Field(default=0, ge=0)
    total_warning_findings: int = Field(default=0, ge=0)
    ready: bool = Field(default=False)


def _modelo_health_row(
    *,
    modelo: str,
    work_unit: WorkUnit,
    revision: CalculationRevision | None,
    latest_report: VerificationReport | None,
) -> ModeloHealthRow:
    if revision is None:
        return ModeloHealthRow(
            modelo=modelo,
            work_unit_id=work_unit.work_unit_id,
            state=ModeloReadinessState.NOT_STARTED,
            summary=f"Modelo {modelo} work unit '{work_unit.name}' has no calculation revision yet.",
            next_command=f"aeat app modelo work calculate {work_unit.work_unit_id}",
        )

    blocking = 0
    warning = 0
    if latest_report is not None:
        for finding in latest_report.findings:
            if finding.severity is ModeloVerificationFindingSeverity.BLOCKING:
                blocking += 1
            else:
                warning += 1

    if blocking > 0:
        return ModeloHealthRow(
            modelo=modelo,
            work_unit_id=work_unit.work_unit_id,
            state=ModeloReadinessState.BLOCKED,
            blocking_finding_count=blocking,
            warning_finding_count=warning,
            summary=f"Modelo {modelo}: {blocking} blocking finding(s) on the current revision.",
            next_command=f"aeat app modelo work verify {work_unit.work_unit_id}",
        )

    if revision.state is CalculationRevisionState.PRESENTADO:
        return ModeloHealthRow(
            modelo=modelo,
            work_unit_id=work_unit.work_unit_id,
            state=ModeloReadinessState.FILED,
            warning_finding_count=warning,
            summary=f"Modelo {modelo}: filed.",
            next_command=f"aeat app modelo filing-record list --modelo {modelo}",
        )

    if revision.state is CalculationRevisionState.PRESENTADO_SUPERSEDIDO:
        return ModeloHealthRow(
            modelo=modelo,
            work_unit_id=work_unit.work_unit_id,
            state=ModeloReadinessState.FILED,
            warning_finding_count=warning,
            summary=f"Modelo {modelo}: filed (superseded by a later revision).",
            next_command=f"aeat app modelo work revisions {work_unit.work_unit_id}",
        )

    if revision.state is CalculationRevisionState.VERIFICADO_COMPLETO:
        return ModeloHealthRow(
            modelo=modelo,
            work_unit_id=work_unit.work_unit_id,
            state=ModeloReadinessState.VERIFIED,
            warning_finding_count=warning,
            summary=f"Modelo {modelo}: verified, not yet filed.",
            next_command=f"aeat app modelo work file {work_unit.work_unit_id}",
        )

    # BORRADOR or DESCARTADO (a discarded unit would already be filtered out
    # by the caller's non-discarded work-unit load, so BORRADOR is the
    # remaining real case): calculated but not yet verified.
    return ModeloHealthRow(
        modelo=modelo,
        work_unit_id=work_unit.work_unit_id,
        state=ModeloReadinessState.CALCULATED,
        warning_finding_count=warning,
        summary=f"Modelo {modelo}: calculated, not yet verified.",
        next_command=f"aeat app modelo work verify {work_unit.work_unit_id}",
    )


def build_pipeline_health_report(
    *,
    bucket_id: str,
    filing_year: int,
    period: Period,
    ledger_report: LedgerStatusReport,
    work_units: tuple[WorkUnit, ...],
    revisions_by_id: dict[str, CalculationRevision],
    reports_by_revision_id: dict[str, tuple[VerificationReport, ...]],
) -> PipelineHealthReport:
    """Compose the cross-domain pipeline health report for one period.

    Args:
        bucket_id: Active profile bucket the report is scoped to.
        filing_year: Filing year for the requested scope.
        period: Typed filing :class:`~core.Period` for the requested scope.
        ledger_report: Already-built
            :class:`~application.ledger.LedgerStatusReport` for
            ``(bucket_id, period)`` (period-scoped, so ``ready`` and
            ``readiness_issue_count`` are populated).
        work_units: Non-discarded :class:`~domain.modelos.WorkUnit` rows
            for ``bucket_id`` matching ``(filing_year, period)``. Callers
            filter to the requested scope; this builder does not re-filter.
        revisions_by_id: Mapping of ``calculation_revision_id`` to the loaded
            :class:`~domain.modelos.CalculationRevision`, covering every
            work unit's ``current_calculation_revision_id``. A work unit
            whose id is absent from this mapping is treated as having no
            revision yet.
        reports_by_revision_id: Mapping of ``calculation_revision_id`` to its
            :class:`~domain.modelos.VerificationReport` rows, sorted
            oldest-first (the shape :func:`~application.modelo.list_verification_reports`
            returns). The latest (last) report is used.

    Returns:
        A :class:`PipelineHealthReport` with one :class:`ModeloHealthRow` per
        work unit, findings totals, and an overall ``ready`` verdict.
    """
    rows: list[ModeloHealthRow] = []
    for unit in sorted(work_units, key=lambda u: str(u.modelo)):
        revision = None
        if unit.current_calculation_revision_id is not None:
            revision = revisions_by_id.get(unit.current_calculation_revision_id)
        latest_report: VerificationReport | None = None
        if revision is not None:
            reports = reports_by_revision_id.get(revision.calculation_revision_id, ())
            if reports:
                latest_report = reports[-1]
        rows.append(
            _modelo_health_row(
                modelo=str(unit.modelo),
                work_unit=unit,
                revision=revision,
                latest_report=latest_report,
            ),
        )

    total_blocking = sum(row.blocking_finding_count for row in rows)
    total_warning = sum(row.warning_finding_count for row in rows)

    ledger_clean = ledger_report.readiness_issue_count == 0 and ledger_report.pending_review_count == 0
    modelos_ready = bool(rows) and all(
        row.state in (ModeloReadinessState.VERIFIED, ModeloReadinessState.FILED) for row in rows
    )
    ready = ledger_clean and modelos_ready

    return PipelineHealthReport(
        bucket_id=bucket_id,
        filing_year=filing_year,
        period=period.registry_token,
        ledger=ledger_report,
        modelos=tuple(rows),
        total_blocking_findings=total_blocking,
        total_warning_findings=total_warning,
        ready=ready,
    )


__all__ = [
    "ModeloHealthRow",
    "ModeloReadinessState",
    "PipelineHealthReport",
    "build_pipeline_health_report",
]
