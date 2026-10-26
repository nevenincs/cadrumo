"""Application-owned notices for ledger workflow outcomes."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity


class StaleFinalizedRevisionFacts(Protocol):
    """The facts of one finalized revision that will not receive changed evidence."""

    @property
    def work_unit_id(self) -> str:
        """Return the work unit that owns the finalized revision."""
        ...

    @property
    def calculation_revision_id(self) -> str:
        """Return the finalized calculation revision."""
        ...

    @property
    def revision_state(self) -> str:
        """Return the finalized revision's lifecycle state."""
        ...

    @property
    def modelo(self) -> str:
        """Return the revision's modelo."""
        ...

    @property
    def filing_year(self) -> int:
        """Return the revision's filing year."""
        ...

    @property
    def period(self) -> str:
        """Return the revision's period token."""
        ...


def stale_finalized_revision_notices(stale_revisions: Iterable[StaleFinalizedRevisionFacts]) -> list[Notice]:
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
        for blocker in stale_revisions
    ]


__all__ = ["StaleFinalizedRevisionFacts", "stale_finalized_revision_notices"]
