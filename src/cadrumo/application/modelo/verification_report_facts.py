"""Derive verification report identity, completeness, and bounded source findings."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...core.identity.hex_ids import CalculationRevisionId
from ...domain.calculations.registry.formula_runtime import RegistryCalculationUnresolvedOutcome
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
    derive_verification_report_id,
)
from ._m210_rate import resolve_m210_rate as _resolve_m210_rate
from .verification_finding_contracts import BLOCKED_VERDICT_KINDS, M210_UNRESOLVED_RATE_REASONS

if TYPE_CHECKING:
    pass


def m210_unresolved_outcome_findings(
    unresolved_outcomes: tuple[RegistryCalculationUnresolvedOutcome, ...],
    *,
    profile: TaxpayerProfile,
    snapshot: RegistrySnapshot,
    year: int,
    devengo_date: date,
    tipo_renta: str,
    blocking_finding_observer: Callable[
        [ModeloVerificationFinding, RegistryCalculationUnresolvedOutcome],
        None,
    ]
    | None = None,
) -> list[ModeloVerificationFinding]:
    """Convert typed M210 unresolved engine outcomes into verification findings.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`,
    :class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
    """
    findings: list[ModeloVerificationFinding] = []
    for outcome in unresolved_outcomes:
        if outcome.reason not in M210_UNRESOLVED_RATE_REASONS:
            continue
        resolved_tipo_renta = tipo_renta or outcome.context.get("tipo_renta", "")
        _rate, obs_findings = _resolve_m210_rate(
            profile,
            resolved_tipo_renta,
            year,
            snapshot,
            devengo_date=devengo_date,
            casilla_id=outcome.casilla_id,
        )
        findings.extend(obs_findings)
        if blocking_finding_observer is not None:
            for finding in obs_findings:
                blocking_finding_observer(finding, outcome)
    return findings


def granting_verification_report(
    catalogue: VerificationReportCatalogue,
    calculation_revision_id: CalculationRevisionId,
) -> VerificationReport | None:
    """Return the granting verification report for a locked revision, or ``None``.

    Used by the idempotent re-verify no-op: a revision that has transitioned out
    of ``BORRADOR`` (``VERIFICADO_COMPLETO`` / ``PRESENTADO``) was granted
    verification, so exactly one granting :class:`VerificationReport` exists for
    it; ``None`` flags an inconsistent state (a non-draft revision with no
    granting report) that the caller refuses rather than papering over.
    """
    for report in catalogue.reports.values():
        if report.calculation_revision_id == calculation_revision_id and report.granted_verificado_completo:
            return report
    return None


def build_verification_report(
    *,
    calculation_revision_id: CalculationRevisionId,
    registry_snapshot_ref: RegistrySnapshotRef,
    findings: Iterable[ModeloVerificationFinding],
    resolved_casilla_ids: Iterable[CasillaId],
    missing_required_casilla_ids: Iterable[CasillaId],
    completeness: VerificationCompletenessStatus,
    granted: bool,
    actor: str,
    run_at: datetime,
) -> VerificationReport:
    """Build the immutable, content-addressed verification report."""
    frozen_findings = tuple(findings)
    verified_by = actor.strip()
    return VerificationReport(
        verification_report_id=derive_verification_report_id(
            calculation_revision_id=calculation_revision_id,
            completeness_status=completeness,
            findings=frozen_findings,
            verified_by=verified_by,
        ),
        calculation_revision_id=calculation_revision_id,
        registry_snapshot_ref=registry_snapshot_ref,
        completeness_status=completeness,
        findings=frozen_findings,
        resolved_casilla_ids=tuple(resolved_casilla_ids),
        missing_required_casilla_ids=tuple(missing_required_casilla_ids),
        run_at=run_at,
        verified_by=verified_by,
        granted_verificado_completo=granted,
    )


def classify_verification_outcome(
    *,
    findings: list[ModeloVerificationFinding],
    missing_required: list[CasillaId],
) -> tuple[VerificationCompletenessStatus, bool]:
    """Compute the completeness status + granted flag from finding shape.

    With no BLOCKING-severity finding, the report is COMPLETE and the
    verified-complete transition is granted, even if WARNING ADVISORY findings
    are present. With at least one BLOCKING_RULE finding, or a calculation the
    records changed under (STALE_CALCULATION), the report is BLOCKED: completing
    inputs cannot release a calculation that must be run again. With BLOCKING
    findings that are exclusively MISSING_REQUIRED_CASILLA, the report is
    INCOMPLETE so the operator sees that completing the inputs unblocks the
    transition.
    """
    has_blocking = any(f.severity is ModeloVerificationFindingSeverity.BLOCKING for f in findings)
    if not has_blocking:
        return VerificationCompletenessStatus.COMPLETE, True
    has_blocking_rule = any(f.kind in BLOCKED_VERDICT_KINDS for f in findings)
    if missing_required and not has_blocking_rule:
        return VerificationCompletenessStatus.INCOMPLETE, False
    return VerificationCompletenessStatus.BLOCKED, False
