"""Verify-time ledger-drift gate for BORRADOR calculation drafts.

Verify targets the work unit's current calculation revision. The
deductible-evidence gate beside it reads the LIVE transaction catalogue, while
the casilla values under audit come from the STORED draft. Those are the same
view only while nothing changes in between, and nothing required that.

The reachable sequence this closes: an operator meets the blocking
deductible-evidence finding, reclassifies the row to drop the deduction rather
than attaching an invoice, and re-runs verify without recalculating. No
recalculate means the work unit still points at the same draft. The evidence
gate reads the live ledger, sees a row that is no longer deductible, and raises
nothing; the casilla values still assert the deduction. Granting there freezes
an evidence bundle over an over-declaration.

The gate lives here rather than beside the finding collectors it runs with,
because it is a distinct responsibility: those collectors project registry and
profile state onto findings, while this one compares two views of the ledger
across time. Keeping it separate also lets the comparison be exercised without
standing up the whole verify path.

See Also:
    :mod:`~application.modelo._ledger_evidence_gate`:
        The sibling filing-grade gate over the frozen evidence bundle.
    :func:`~application.aggregation.ledger_filing_snapshot.evaluate_ledger_filing_staleness`:
        The shared comparison, which also guards finalized revisions.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ...core.aggregation import LEDGER_BINDING_SOURCE_KINDS
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.ledger_filing_snapshot import evaluate_ledger_filing_staleness
from ..aggregation.ledger_membership import LedgerSourceMembership, ledger_transaction_ref_identity

if TYPE_CHECKING:
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnit

#: Grounding for the drift refusal. A declaración must reflect the operator's
#: real accounting records (LIVA art. 164.1.4 the IVA declaration duty, RD
#: 1619/2012 art. 2 the invoicing duty that fixes what those records say), so
#: filing values the ledger no longer supports is not a filing the operator may
#: complete.
LEDGER_DRIFT_LEGAL_REFS: tuple[str, ...] = (
    "ley-37-1992:art-164",
    "rd-1619-2012:art-2",
)


type _BlockingFindingObserver = Callable[
    [ModeloVerificationFinding, bool, tuple[str, ...], tuple[str, ...], tuple[str, ...]], None
]


def _observe_drift_finding(
    observer: _BlockingFindingObserver | None,
    finding: ModeloVerificationFinding,
    anchored: bool,
    changed: tuple[str, ...],
    removed: tuple[str, ...],
    added: tuple[str, ...],
) -> None:
    """Publish the original identifier-only evidence when an observer is bound."""
    if observer is not None:
        observer(finding, anchored, changed, removed, added)


def _draft_ledger_baseline(target: CalculationRevision) -> set[str]:
    """Retain draft source identities and identified ledger-source issues."""
    baseline = set(target.source_transaction_ids)
    for issue in target.source_issues:
        if issue.binding_source not in LEDGER_BINDING_SOURCE_KINDS:
            continue
        identity = ledger_transaction_ref_identity(issue.source_ref)
        if identity is not None:
            baseline.add(identity)
    return baseline


def ledger_drift_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    current_membership: LedgerSourceMembership,
    source_refs: tuple[str, ...] = (),
    blocking_finding_observer: _BlockingFindingObserver | None = None,
) -> list[ModeloVerificationFinding]:
    """Refuse a draft whose contributing ledger rows moved since it was calculated.

    The comparison is the draft's own ledger anchor against the live rows,
    through the same staleness evaluator that guards finalized revisions. The
    two views it holds apart are exactly the two arguments: ``target`` is the
    stored :class:`CalculationRevision` the casilla values came from, and
    ``transaction_repository`` is the live
    :class:`TransactionCatalogueRepositoryProtocol` the evidence gate reads.
    The caller supplies the repository bound to the work unit's bucket, so the
    live side is never silently absent. The
    anchor's fingerprint covers tax facts only, so a reclassify moves it and an
    evidence attach does not — which is what lets this refuse the stale-draft
    path without refusing the attach-and-re-verify recovery the
    deductible-evidence promotion depends on.

    A ledger-derived draft with NO anchor is refused on the same terms rather
    than passed. It was calculated before the anchor existed, so whether its
    values still match the ledger is unknown, and an unknown is not a pass
    (``no-silent-under-declaration``). Both branches resolve to the same
    operator move, which is why they carry the same instruction.

    This never recomputes. A verify that quietly recalculated would mint values
    the operator never saw and file them under a report they never read.
    """
    if target.state is not CalculationRevisionState.BORRADOR:
        return []
    baseline = _draft_ledger_baseline(target)
    added = tuple(sorted(set(current_membership.observed_transaction_ids) - baseline))
    tx_repo = transaction_repository
    anchor = target.ledger_filing_snapshot
    if not current_membership.available:
        finding = _drift_finding(
            work_unit=work_unit,
            source_refs=source_refs,
            changed=0,
            removed=0,
            anchored=anchor is not None,
            membership_available=False,
        )
        _observe_drift_finding(blocking_finding_observer, finding, anchor is not None, (), (), ())
        return [finding]
    if anchor is None:
        if not target.source_transaction_ids and not added:
            return []
        finding = _drift_finding(
            work_unit=work_unit,
            source_refs=source_refs,
            changed=0,
            removed=0,
            anchored=False,
            added=len(added),
        )
        _observe_drift_finding(blocking_finding_observer, finding, False, (), (), added)
        return [finding]
    verdict = evaluate_ledger_filing_staleness(anchor, tx_repo.load())
    if not verdict.is_stale and not added:
        return []
    finding = _drift_finding(
        work_unit=work_unit,
        source_refs=source_refs,
        changed=len(verdict.changed),
        removed=len(verdict.removed),
        anchored=True,
        added=len(added),
    )
    _observe_drift_finding(
        blocking_finding_observer, finding, True, tuple(verdict.changed), tuple(verdict.removed), added
    )
    return [finding]


def _drift_finding(
    *,
    work_unit: WorkUnit,
    source_refs: tuple[str, ...],
    changed: int,
    removed: int,
    anchored: bool,
    added: int = 0,
    membership_available: bool = True,
) -> ModeloVerificationFinding:
    """Build the blocking drift finding without persisting recovery prose.

    The locale-neutral presentation facts carry counts; the exact changed and
    removed identities remain on the paired precondition evidence record. The
    sentence names only the counts that are not zero: entries changed, entries
    removed, or both.
    """
    facts = {
        "modelo": str(work_unit.modelo),
        "filing_year": work_unit.filing_year,
        "period": work_unit.period.registry_token,
        "anchored": anchored,
        "changed_count": changed,
        "removed_count": removed,
        "added_count": added,
        "membership_available": membership_available,
    }
    if not membership_available:
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.STALE_CALCULATION,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.ledger_snapshot_membership_unavailable",
            message_facts=facts,
            legal_refs=LEDGER_DRIFT_LEGAL_REFS,
            source_refs=source_refs,
        )
    if added and (changed or removed):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.STALE_CALCULATION,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.ledger_snapshot_drift_with_added",
            message_facts=facts,
            legal_refs=LEDGER_DRIFT_LEGAL_REFS,
            source_refs=source_refs,
        )
    if added:
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.STALE_CALCULATION,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.ledger_snapshot_drift_added",
            message_facts=facts,
            legal_refs=LEDGER_DRIFT_LEGAL_REFS,
            source_refs=source_refs,
        )
    if changed and not removed:
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.STALE_CALCULATION,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.ledger_snapshot_drift_changed",
            message_facts=facts,
            legal_refs=LEDGER_DRIFT_LEGAL_REFS,
            source_refs=source_refs,
        )
    if removed and not changed:
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.STALE_CALCULATION,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.ledger_snapshot_drift_removed",
            message_facts=facts,
            legal_refs=LEDGER_DRIFT_LEGAL_REFS,
            source_refs=source_refs,
        )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.STALE_CALCULATION,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.ledger_snapshot_drift",
        message_facts=facts,
        legal_refs=LEDGER_DRIFT_LEGAL_REFS,
        source_refs=source_refs,
    )


__all__ = [
    "LEDGER_DRIFT_LEGAL_REFS",
    "ledger_drift_findings",
]
