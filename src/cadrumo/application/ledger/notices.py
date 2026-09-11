"""Application-owned notices for ledger workflow outcomes."""

from __future__ import annotations

from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from .models import ManualLedgerTransactionResult


def stale_finalized_revision_notices(result: ManualLedgerTransactionResult) -> list[Notice]:
    """Describe finalized revisions that cannot absorb newly attached evidence.

    The application owns the factual stale-revision outcome and its structured
    reason.  An entrypoint decides how to render the returned notice; it does
    not own or reconstruct this workflow contract.
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
                "actionability": "finalized_revision_has_no_safe_recovery_action",
            },
        )
        for blocker in result.stale_finalized_revisions
    ]


__all__ = ["stale_finalized_revision_notices"]
