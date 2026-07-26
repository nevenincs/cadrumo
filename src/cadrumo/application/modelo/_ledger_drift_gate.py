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
    :func:`~application.aggregation.evaluate_ledger_filing_staleness`:
        The shared comparison, which also guards finalized revisions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...domain.modelos import (
    CalculationRevisionState,
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ..aggregation import evaluate_ledger_filing_staleness

if TYPE_CHECKING:
    from ...domain.modelos import CalculationRevision, WorkUnit

#: Grounding for the drift refusal. A declaración must reflect the operator's
#: real accounting records (LIVA art. 164.1.4 the IVA declaration duty, RD
#: 1619/2012 art. 2 the invoicing duty that fixes what those records say), so
#: filing values the ledger no longer supports is not a filing the operator may
#: complete.
LEDGER_DRIFT_LEGAL_REFS: tuple[str, ...] = (
    "ley-37-1992:art-164",
    "rd-1619-2012:art-2",
)


def ledger_drift_findings(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepository | None,
    source_refs: tuple[str, ...] = (),
) -> list[ModeloVerificationFinding]:
    """Refuse a draft whose contributing ledger rows moved since it was calculated.

    The comparison is the draft's own ledger anchor against the live rows,
    through the same staleness evaluator that guards finalized revisions. The
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
    if not target.source_transaction_ids:
        return []
    if target.state is not CalculationRevisionState.BORRADOR:
        return []
    tx_repo = transaction_repository or TransactionCatalogueRepository(bucket_id=work_unit.bucket_id)
    anchor = target.ledger_filing_snapshot
    if anchor is None:
        return [_drift_finding(work_unit=work_unit, source_refs=source_refs, changed=0, removed=0, anchored=False)]
    verdict = evaluate_ledger_filing_staleness(anchor, tx_repo.load())
    if not verdict.is_stale:
        return []
    return [
        _drift_finding(
            work_unit=work_unit,
            source_refs=source_refs,
            changed=len(verdict.changed),
            removed=len(verdict.removed),
            anchored=True,
        ),
    ]


def _drift_finding(
    *,
    work_unit: WorkUnit,
    source_refs: tuple[str, ...],
    changed: int,
    removed: int,
    anchored: bool,
) -> ModeloVerificationFinding:
    """Build the blocking drift finding, naming the command that moves the operator on.

    ``next_action`` names ``calculate``, not ``verify``. A refusal that names
    the command the operator just ran restates their position instead of
    resolving it.

    The message carries COUNTS rather than a joined id list. A finding message
    is capped at 500 characters and a contributor set is unbounded, so joining
    the drifted ids is the same defect shape found six times across the
    bucket-event payloads — and the ids are recoverable from the recalculate
    this refusal instructs anyway.
    """
    detail = (
        f"{changed} contributing row(s) changed and {removed} were removed since this draft was calculated"
        if anchored
        else "this draft carries no record of the ledger state it was calculated from"
    )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        message=(
            f"the ledger no longer matches the stored calculation for modelo {work_unit.modelo} "
            f"{work_unit.filing_year} {work_unit.period.registry_token}: {detail}. "
            "Verifying it would grant over casilla values the ledger no longer supports."
        ),
        next_action=(
            f"Recalculate first with `aeat app modelo work calculate {work_unit.work_unit_id}`, "
            "then verify the revision that produces."
        ),
        legal_refs=LEDGER_DRIFT_LEGAL_REFS,
        source_refs=source_refs,
    )


__all__ = [
    "LEDGER_DRIFT_LEGAL_REFS",
    "ledger_drift_findings",
]
