"""Verify-time invoice-drift gate for BORRADOR calculation drafts.

Beside the ledger gate and resolved the same way: the operator calculates again.
This never recomputes, because a verify that quietly recalculated would mint
values the operator never saw.

A sealed revision is not compared, matching the ledger gate. Verify is the only
gate: export and file refuse a revision that verify did not seal;
:class:`ModeloRevision`, the registry revision a modelo is calculated against;
:class:`CalculationRevision`, the saved calculation revision.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.invoice_fingerprint import InvoiceFingerprintVerdict
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ..aggregation.invoice_filing_fingerprint import (
    draft_contributor_identities,
    evaluate_invoice_fingerprint,
    fingerprint_scope_is_narrower,
    revision_reads_invoices,
)
from ..aggregation.renta_imputation import ImputationFilingHistory, declared_imputation_criteria
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPersistenceError, InvoiceCatalogueReadPorts
from ._ledger_drift_gate import LEDGER_DRIFT_LEGAL_REFS

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnit
    from .work_profile import ModeloWorkProfile

type _InvoiceDriftObserver = Callable[[ModeloVerificationFinding, InvoiceFingerprintVerdict | None], None]


def _message_facts(work_unit: WorkUnit) -> dict[str, str | int]:
    facts: dict[str, str | int] = {
        "modelo": str(work_unit.modelo),
        "filing_year": work_unit.filing_year,
        "period": work_unit.period.registry_token,
    }
    return facts


def _drift_message_facts(work_unit: WorkUnit, verdict: InvoiceFingerprintVerdict) -> dict[str, str | int]:
    # Written out whole, not merged onto the base, so the facts-guarantee gate reads
    # every fact the drift sentence interpolates as supplied on every path.
    facts: dict[str, str | int] = {
        "modelo": str(work_unit.modelo),
        "filing_year": work_unit.filing_year,
        "period": work_unit.period.registry_token,
        "changed_count": len(verdict.changed),
        "removed_count": len(verdict.removed),
        "added_count": len(verdict.added),
    }
    return facts


def invoice_drift_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    ports: InvoiceCatalogueReadPorts,
    profile: ModeloWorkProfile,
    source_refs: tuple[str, ...] = (),
    blocking_finding_observer: _InvoiceDriftObserver | None = None,
    narrower_scope_observer: Callable[[ModeloVerificationFinding], None] | None = None,
    filings: ImputationFilingHistory | None = None,
) -> list[ModeloVerificationFinding]:
    """Compare a draft's stored invoice fingerprint with the catalogue.

    A draft calculated before fingerprints existed gets a warning saying so: its
    invoices are neither known to match nor known to differ. A draft fingerprinted
    under an older, narrower scope has a fingerprint that cannot prove it current, so
    it is sent to be calculated again; its stored fingerprint stays as it was.

    ``target`` is the :class:`CalculationRevision`, the saved calculation revision.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    if target.state is not CalculationRevisionState.BORRADOR:
        return []
    if not revision_reads_invoices(revision, work_unit=work_unit):
        return []
    snapshot = target.invoice_fingerprint
    if snapshot is None:
        return [
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                message_locale_key="application.modelo.findings.invoice_fingerprint_absent",
                message_facts=_message_facts(work_unit),
                legal_refs=LEDGER_DRIFT_LEGAL_REFS,
                source_refs=source_refs,
            )
        ]
    criteria = declared_imputation_criteria(profile.record, filings)
    if fingerprint_scope_is_narrower(snapshot, revision=revision, work_unit=work_unit, criteria=criteria):
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.STALE_CALCULATION,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.invoice_fingerprint_narrower_scope",
            message_facts=_message_facts(work_unit),
            legal_refs=LEDGER_DRIFT_LEGAL_REFS,
            source_refs=source_refs,
        )
        if narrower_scope_observer is not None:
            narrower_scope_observer(finding)
        return [finding]
    try:
        verdict = evaluate_invoice_fingerprint(
            snapshot,
            work_unit=work_unit,
            revision=revision,
            contributors=draft_contributor_identities(target.source_transaction_ids, target.source_issues),
            ports=ports,
            criteria=criteria,
        )
    except InvoiceCatalogueReadPersistenceError:
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.STALE_CALCULATION,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.invoice_fingerprint_unavailable",
            message_facts=_message_facts(work_unit),
            legal_refs=LEDGER_DRIFT_LEGAL_REFS,
            source_refs=source_refs,
        )
        if blocking_finding_observer is not None:
            blocking_finding_observer(finding, None)
        return [finding]
    if not verdict.is_stale:
        return []
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.STALE_CALCULATION,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.invoice_fingerprint_drift",
        message_facts=_drift_message_facts(work_unit, verdict),
        legal_refs=LEDGER_DRIFT_LEGAL_REFS,
        source_refs=source_refs,
    )
    if blocking_finding_observer is not None:
        blocking_finding_observer(finding, verdict)
    return [finding]


__all__ = ["invoice_drift_findings"]
