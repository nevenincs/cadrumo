"""Verify-time invoice-drift gate for BORRADOR calculation drafts.

Beside the ledger gate and resolved the same way: the operator calculates again.
This never recomputes, because a verify that quietly recalculated would mint
values the operator never saw.

A sealed revision is not compared, matching the ledger gate. Verify is the only
gate: export and file refuse a revision that verify did not seal.
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
    revision_reads_invoices,
)
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPersistenceError, InvoiceCatalogueReadPorts
from ._ledger_drift_gate import LEDGER_DRIFT_LEGAL_REFS

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnit

type _InvoiceDriftObserver = Callable[[ModeloVerificationFinding, InvoiceFingerprintVerdict | None], None]


def _finding(
    work_unit: WorkUnit,
    *,
    kind: ModeloVerificationFindingKind,
    severity: ModeloVerificationFindingSeverity,
    key: str,
    source_refs: tuple[str, ...],
    verdict: InvoiceFingerprintVerdict | None = None,
) -> ModeloVerificationFinding:
    facts: dict[str, str | int] = {
        "modelo": str(work_unit.modelo),
        "filing_year": work_unit.filing_year,
        "period": work_unit.period.registry_token,
    }
    if verdict is not None:
        facts |= {
            "changed_count": len(verdict.changed),
            "removed_count": len(verdict.removed),
            "added_count": len(verdict.added),
        }
    return ModeloVerificationFinding(
        kind=kind,
        severity=severity,
        message_locale_key=key,
        message_facts=facts,
        legal_refs=LEDGER_DRIFT_LEGAL_REFS,
        source_refs=source_refs,
    )


def invoice_drift_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    revision: ModeloRevision,
    ports: InvoiceCatalogueReadPorts,
    source_refs: tuple[str, ...] = (),
    blocking_finding_observer: _InvoiceDriftObserver | None = None,
) -> list[ModeloVerificationFinding]:
    """Compare a draft's stored invoice fingerprint with the catalogue.

    A draft calculated before fingerprints existed gets a warning saying so: its
    invoices are neither known to match nor known to differ, and refusing it would
    block every such draft over nothing observed.
    """
    if target.state is not CalculationRevisionState.BORRADOR:
        return []
    if not revision_reads_invoices(revision, work_unit=work_unit):
        return []
    snapshot = target.invoice_fingerprint
    if snapshot is None:
        return [
            _finding(
                work_unit,
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                key="application.modelo.findings.invoice_fingerprint_absent",
                source_refs=source_refs,
            )
        ]
    try:
        verdict = evaluate_invoice_fingerprint(
            snapshot,
            work_unit=work_unit,
            revision=revision,
            contributors=draft_contributor_identities(target.source_transaction_ids, target.source_issues),
            ports=ports,
        )
    except InvoiceCatalogueReadPersistenceError:
        finding = _finding(
            work_unit,
            kind=ModeloVerificationFindingKind.STALE_CALCULATION,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            key="application.modelo.findings.invoice_fingerprint_unavailable",
            source_refs=source_refs,
        )
        if blocking_finding_observer is not None:
            blocking_finding_observer(finding, None)
        return [finding]
    if not verdict.is_stale:
        return []
    finding = _finding(
        work_unit,
        kind=ModeloVerificationFindingKind.STALE_CALCULATION,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        key="application.modelo.findings.invoice_fingerprint_drift",
        source_refs=source_refs,
        verdict=verdict,
    )
    if blocking_finding_observer is not None:
        blocking_finding_observer(finding, verdict)
    return [finding]


__all__ = ["invoice_drift_findings"]
