"""Which of a profile's calculation revisions consumed one amortization claim.

A claim's identity hashes its content, so it cannot carry the calculation that
used it. The calculation records the claims it consumed instead, and this query
inverts that record for the callers that must show a claim's consumers.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...domain.modelos.calculation_revision import CalculationRevision
from ..ledger.stale_filing_query import StaleFilingWorkUnitLookupV1


def calculation_revisions_consuming_claim(
    claim_id: str,
    *,
    bucket_id: str,
    revisions: Iterable[CalculationRevision],
    work_units: StaleFilingWorkUnitLookupV1,
) -> tuple[CalculationRevision, ...]:
    """List this bucket's calculation revisions that rested on the claim.

    The revision catalogue is not bucket-scoped, so a revision whose work unit
    is missing or belongs to another profile is excluded.

    Args:
        claim_id: Identity of the amortization claim.
        bucket_id: The owning profile bucket.
        revisions: The calculation revisions to consider.
        work_units: The work units the revisions are addressed through.

    Returns:
        The consuming revisions, oldest first.
    """
    consumers: list[CalculationRevision] = []
    for revision in revisions:
        if claim_id not in revision.activity_asset_consumption.claim_ids:
            continue
        work_unit = work_units.get(revision.work_unit_id)
        if work_unit is None or work_unit.bucket_id != bucket_id:
            continue
        consumers.append(revision)
    return tuple(sorted(consumers, key=lambda revision: (revision.created_at, revision.calculation_revision_id)))


__all__ = ["calculation_revisions_consuming_claim"]
