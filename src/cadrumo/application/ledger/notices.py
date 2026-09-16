"""Application-owned notices for ledger workflow outcomes."""

from __future__ import annotations

from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from .models import ManualLedgerTransactionResult


def stale_finalized_revision_notices(result: ManualLedgerTransactionResult) -> list[Notice]:
    """Warn that each finalized revision citing this row will not pick the evidence up.

    A revision bundles its ledger evidence when it is verified, and that bundle
    is frozen. An attachment landing afterwards is stored on the ledger row but
    never reaches the already-verified filing, so an export or filing gate
    reading the bundle keeps refusing.

    The advisory deliberately names no recovery verb, because neither candidate
    works: ``work calculate`` re-derives the same content-addressed revision id
    (evidence is not part of that hash) and returns the existing finalized
    revision untouched, and ``work discard`` marks the work unit ``descartado``
    while the follow-up ``work create`` re-derives the same work-unit id and
    hands the discarded unit back, permanently stranding that target. The
    guidance is the ordering rule that does work: link invoices before
    calculating.
    """
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code="ledger.attach.finalized_revision_stale",
            message=tr(
                "cli.ledger.attach.finalized_revision_stale",
                modelo=blocker.modelo,
                filing_year=str(blocker.filing_year),
                period=blocker.period,
            ),
            context={
                "work_unit_id": blocker.work_unit_id,
                "calculation_revision_id": blocker.calculation_revision_id,
                "revision_state": blocker.revision_state,
                "modelo": blocker.modelo,
                "filing_year": str(blocker.filing_year),
                "period": blocker.period,
                "reason": "finalized_revision_predates_evidence",
                # Saying so explicitly keeps a deliberate absence of action
                # distinguishable from one nobody got round to attaching.
                "actionability": "finalized_revision_has_no_safe_recovery_action",
            },
        )
        for blocker in result.stale_finalized_revisions
    ]


__all__ = ["stale_finalized_revision_notices"]
