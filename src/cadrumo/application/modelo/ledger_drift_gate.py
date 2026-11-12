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
    :mod:`~application.modelo.ledger_evidence_gate`:
        The sibling filing-grade gate over the frozen evidence bundle.
    :func:`~application.aggregation.ledger_filing_snapshot.evaluate_ledger_filing_staleness`:
        The shared comparison, which also guards finalized revisions;
:class:`TransactionCatalogue`, the profile's transaction catalogue.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from ...core.aggregation import LEDGER_BINDING_SOURCE_KINDS
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.iva.schema import is_iva_cash_accounting_none
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.calculation_revision_sources import ActivityAssetConsumption
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ...domain.transactions.enums import TransactionDirection, TransactionLifecycleState
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.iva_ledger_classification import iva_mixed_use_treatment_is_undetermined
from ..aggregation.ledger_filing_snapshot import (
    ACCRUAL_DATE_FIELD_SET_VERSION,
    OPERATION_DATE_FIELD_SET_VERSION,
    evaluate_ledger_filing_staleness,
)
from ..aggregation.ledger_membership import (
    LedgerSourceMembership,
    consumed_inventory_rows,
    ledger_transaction_ref_identity,
    recorded_book_claimed_transaction_ids,
)

if TYPE_CHECKING:
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.ledger_filing_snapshot import LedgerFilingSnapshot
    from ...domain.modelos.work_unit import WorkUnit
    from ...domain.transactions.models import TransactionCatalogue

#: Grounding for the drift refusal. A declaración must reflect the operator's
#: real accounting records (LIVA art. 164.1.4 the IVA declaration duty, RD
#: 1619/2012 art. 2 the invoicing duty that fixes what those records say), so
#: filing values the ledger no longer supports is not a filing the operator may
#: complete.
LEDGER_DRIFT_LEGAL_REFS: tuple[str, ...] = (
    "ley-37-1992:art-164",
    "rd-1619-2012:art-2",
)

#: Grounding for the register drift refusal: the amortization deducted in direct
#: estimation is the one the register's recorded claims and schedules yield
#: (LIRPF art. 30, RIRPF art. 30), so a declaración built on a register that has
#: since changed deducts a figure the register no longer supports.
ASSET_REGISTER_DRIFT_LEGAL_REFS: tuple[str, ...] = (
    "ley-35-2006:art-30",
    "rd-439-2007:art-30",
)

#: Grounding for the inventory drift refusal: stock variation enters the
#: activity's net income through the valuation of existencias (LIRPF art. 28,
#: LIS art. 17), so a declaración built on rows the ledgers no longer yield
#: states a variation those ledgers do not support.
INVENTORY_REGISTER_DRIFT_LEGAL_REFS: tuple[str, ...] = (
    "ley-35-2006:art-28",
    "ley-27-2014:art-17",
)

#: Grounding for the warning on a stored draft that counted an uncategorized mixed
#: row: simultaneous use deducts nothing unless the good is a bien de inversión or
#: follows one (LIVA art. 95), and a share affects only a separately usable part
#: (RIRPF art. 22), so what the row is decides whether its share counts at all.
UNDETERMINED_MIXED_USE_LEGAL_REFS: tuple[str, ...] = (
    "ley-37-1992:art-95",
    "rd-439-2007:art-22",
)

type _BlockingFindingObserver = Callable[
    [ModeloVerificationFinding, bool, tuple[str, ...], tuple[str, ...], tuple[str, ...]], None
]


type _AssetRegisterDriftObserver = Callable[
    [ModeloVerificationFinding, ActivityAssetConsumption, ActivityAssetConsumption], None
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
    asset_register_drift_observer: _AssetRegisterDriftObserver | None = None,
) -> list[ModeloVerificationFinding]:
    """Refuse a :class:`CalculationRevision` draft whose ledger rows or register state moved.

    Two views are compared. The ledger rows are compared through the anchor, and
    the activity-asset register through the claims and schedule fingerprints the
    draft recorded. Both resolve to the same operator move, calculating again.
    """
    findings = _transaction_drift_findings(
        target=target,
        work_unit=work_unit,
        transaction_repository=transaction_repository,
        current_membership=current_membership,
        source_refs=source_refs,
        blocking_finding_observer=blocking_finding_observer,
    )
    if target.state is not CalculationRevisionState.BORRADOR or not current_membership.available:
        return findings
    inventory_finding = _inventory_drift_finding(target, work_unit, current_membership, source_refs=source_refs)
    if inventory_finding is not None:
        findings = [*findings, inventory_finding]
    claim_finding = _book_claim_drift_finding(target, work_unit, current_membership, source_refs=source_refs)
    if claim_finding is not None:
        findings = [*findings, claim_finding]
    recorded = target.activity_asset_consumption
    current = current_membership.activity_asset_consumption
    if recorded == current:
        return findings
    finding = _asset_register_drift_finding(work_unit, recorded, current, source_refs=source_refs)
    if asset_register_drift_observer is not None:
        asset_register_drift_observer(finding, recorded, current)
    return [*findings, finding]


def _transaction_drift_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    current_membership: LedgerSourceMembership,
    source_refs: tuple[str, ...],
    blocking_finding_observer: _BlockingFindingObserver | None,
) -> list[ModeloVerificationFinding]:
    """Refuse a draft whose contributing ledger rows moved since it was calculated.

    The comparison is the draft's own ledger anchor against the live rows,
    through the same staleness evaluator that guards finalized revisions. The
    two views it holds apart are exactly the two arguments: ``target`` is the
    stored :class:`CalculationRevision` the casilla values came from, and
    ``transaction_repository`` is the live
    :class:`TransactionCatalogueRepositoryProtocol` the evidence gate reads.
    The caller supplies the repository bound to the work unit's bucket, so the
    live side is never silently absent. The anchor's field set says what it can
    see: from version 5 a change to the deduction evidence moves it, attaching
    included, so the recovery from a deductible-evidence refusal is to attach and
    calculate again. An older anchor keeps its own narrower answer, except that an
    operation date written after it was taken is reported below: nothing could
    write one on a general-regime row when that anchor was taken.

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
    catalogue = tx_repo.load()
    verdict = evaluate_ledger_filing_staleness(anchor, catalogue)
    newly_dated = (
        *_operation_dated_since_older_anchor(anchor, catalogue),
        *_accrual_dated_since_older_anchor(anchor, catalogue),
    )
    if newly_dated:
        verdict = verdict.model_copy(
            update={"is_stale": True, "changed": tuple(sorted({*verdict.changed, *newly_dated}))},
        )
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


def _operation_dated_since_older_anchor(
    anchor: LedgerFilingSnapshot,
    catalogue: TransactionCatalogue,
) -> tuple[str, ...]:
    """Name anchored general-regime rows carrying an operation date a pre-version-5 anchor cannot see."""
    if anchor.fingerprint_field_set_version >= OPERATION_DATE_FIELD_SET_VERSION:
        return ()
    anchored = {row.transaction_id for row in anchor.rows}
    return tuple(
        sorted(
            transaction.transaction_id
            for transaction in catalogue.values()
            if transaction.transaction_id in anchored
            and transaction.operation_date is not None
            and is_iva_cash_accounting_none(transaction.cash_accounting_treatment, transaction.operation_date)
        )
    )


def _accrual_dated_since_older_anchor(
    anchor: LedgerFilingSnapshot,
    catalogue: TransactionCatalogue,
) -> tuple[str, ...]:
    """Name anchored rows carrying an accrual date a pre-version-7 anchor cannot see.

    The accrual date is independent of the IVA regime, so no regime filter applies.
    """
    if anchor.fingerprint_field_set_version >= ACCRUAL_DATE_FIELD_SET_VERSION:
        return ()
    anchored = {row.transaction_id for row in anchor.rows}
    return tuple(
        sorted(
            transaction.transaction_id
            for transaction in catalogue.values()
            if transaction.transaction_id in anchored and transaction.accrual_date is not None
        )
    )


def undetermined_mixed_use_contributor_finding(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    source_refs: tuple[str, ...] = (),
) -> ModeloVerificationFinding | None:
    """Warn of a stored draft that counted a mixed expense calculation now holds back.

    Calculation holds such a row back, so it is a contributor of the stored draft
    only when an earlier calculation counted it at its share. That contributor
    set is the marker, and no fingerprint can stand in for it: the row itself did
    not move. The stored values stay as they are and the verdict does not change;
    this only says that calculating again would give a different result.

    ``target`` is the :class:`CalculationRevision`, the saved calculation revision.
    """
    if target.state is not CalculationRevisionState.BORRADOR or not target.source_transaction_ids:
        return None
    contributors = set(target.source_transaction_ids)
    rows = sum(
        1
        for transaction in transaction_repository.load().values()
        if transaction.transaction_id in contributors
        and transaction.direction is TransactionDirection.OUTGOING
        and transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
        and iva_mixed_use_treatment_is_undetermined(transaction, year=work_unit.filing_year, operation=operation)
    )
    if not rows:
        return None
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        message_locale_key="application.modelo.findings.undetermined_mixed_use_contributor",
        message_facts={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "rows": rows,
        },
        legal_refs=UNDETERMINED_MIXED_USE_LEGAL_REFS,
        source_refs=source_refs,
    )


def _inventory_drift_finding(
    target: CalculationRevision,
    work_unit: WorkUnit,
    current_membership: LedgerSourceMembership,
    *,
    source_refs: tuple[str, ...],
) -> ModeloVerificationFinding | None:
    """Refuse a draft whose inventory rows no longer match the ledgers that yield them.

    A draft that consumed no inventory row has nothing to compare: an unresolved
    inventory binding already blocks it through its own source issue.
    """
    recorded = consumed_inventory_rows(target)
    current = current_membership.inventory_row_identities
    if not recorded or recorded == current:
        return None
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.STALE_CALCULATION,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.inventory_register_drift",
        message_facts={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "rows_recorded": len(recorded),
            "rows_current": len(current),
            "rows_changed": len(recorded ^ current),
        },
        legal_refs=INVENTORY_REGISTER_DRIFT_LEGAL_REFS,
        source_refs=source_refs,
    )


def _book_claim_drift_finding(
    target: CalculationRevision,
    work_unit: WorkUnit,
    current_membership: LedgerSourceMembership,
    *,
    source_refs: tuple[str, ...],
) -> ModeloVerificationFinding | None:
    """Refuse a draft whose inventory purchases now claim other ledger rows than it withheld.

    A claim moves a purchase between the ledger expenses and the book's
    acquisition cost, so the draft's casillas no longer follow from the records.
    """
    recorded = recorded_book_claimed_transaction_ids(target)
    current = current_membership.book_claimed_transaction_ids
    if recorded == current:
        return None
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.STALE_CALCULATION,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.inventory_register_drift",
        message_facts={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "rows_recorded": len(recorded),
            "rows_current": len(current),
            "rows_changed": len(recorded ^ current),
        },
        legal_refs=INVENTORY_REGISTER_DRIFT_LEGAL_REFS,
        source_refs=source_refs,
    )


def _asset_register_drift_finding(
    work_unit: WorkUnit,
    recorded: ActivityAssetConsumption,
    current: ActivityAssetConsumption,
    *,
    source_refs: tuple[str, ...],
) -> ModeloVerificationFinding:
    """Build the blocking finding for a register that no longer yields the recorded claims."""
    claims_added = set(current.claim_ids) - set(recorded.claim_ids)
    claims_removed = set(recorded.claim_ids) - set(current.claim_ids)
    schedules_added = set(current.schedule_fingerprints) - set(recorded.schedule_fingerprints)
    schedules_removed = set(recorded.schedule_fingerprints) - set(current.schedule_fingerprints)
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.STALE_CALCULATION,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message_locale_key="application.modelo.findings.activity_asset_register_drift",
        message_facts={
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "claims_added": len(claims_added),
            "claims_removed": len(claims_removed),
            "schedules_changed": max(len(schedules_added), len(schedules_removed)),
            "disposals_changed": current.disposals_changed_from(recorded),
        },
        legal_refs=ASSET_REGISTER_DRIFT_LEGAL_REFS,
        source_refs=source_refs,
    )


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
    "ASSET_REGISTER_DRIFT_LEGAL_REFS",
    "INVENTORY_REGISTER_DRIFT_LEGAL_REFS",
    "LEDGER_DRIFT_LEGAL_REFS",
    "UNDETERMINED_MIXED_USE_LEGAL_REFS",
    "ledger_drift_findings",
    "undetermined_mixed_use_contributor_finding",
]
