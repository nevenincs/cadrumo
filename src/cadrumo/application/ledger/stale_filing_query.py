"""Which of this profile's finalized filings no longer match the live ledger.

``stale_filed_revisions`` already decides whether one revision has drifted, but
it is pure over inputs a caller must assemble: the revision catalogue, the work
units, and the live transactions. Assembling them -- and deciding which
revisions belong to this profile at all -- was done inside the CLI status verb,
so the finding existed only where that verb happened to look.

The bucket filter is the part that most needs a home. A revision reaches this
code through a catalogue that is not itself bucket-scoped, so ownership is
established by joining to the work unit and comparing its bucket. Getting that
wrong shows one profile another profile's filings, which is why it is a
cross-aggregate rule rather than a display detail.

The work-unit join also supplies the only address an operator recognises: a
revision id names nothing they filed, whereas modelo, year and period do.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, NonNegativeInt

from ...core.models import STRICT_FROZEN_CONFIG
from ..aggregation.ledger_filing_snapshot import stale_filed_revisions

type StaleRevisionDetectorV1 = Callable[..., tuple[tuple[Any, Any], ...]]


if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnitCatalogue
    from ...domain.transactions.models import TransactionCatalogue


class LedgerStaleFilingV1(BaseModel):
    """One finalized filing whose ledger basis has since changed.

    Carries the natural filing address rather than only the revision id,
    because that is what an operator can act on.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    filing_year: int
    period: str
    calculation_revision_id: str
    work_unit_id: str
    changed_count: NonNegativeInt
    removed_count: NonNegativeInt


def read_stale_ledger_filings(
    *,
    bucket_id: str,
    revisions: Mapping[str, CalculationRevision],
    work_units: WorkUnitCatalogue,
    transactions: TransactionCatalogue,
    detector: StaleRevisionDetectorV1 = stale_filed_revisions,
) -> tuple[LedgerStaleFilingV1, ...]:
    """Report this bucket's finalized filings that no longer match the ledger.

    A revision whose work unit is missing, or belongs to another profile, is
    excluded: the revision catalogue is not bucket-scoped, so ownership can
    only be established through the work-unit join.

    Args:
        bucket_id: The owning profile bucket.
        revisions: The calculation revisions to consider.
        work_units: The work units the revisions are addressed through.
        transactions: The live ledger the snapshots are re-evaluated against.
        detector: The staleness decision, injectable so the ownership join can
            be exercised without reproducing a drifted snapshot.

    Returns:
        One entry per drifted filing owned by ``bucket_id``.
    """
    findings: list[LedgerStaleFilingV1] = []
    for revision, verdict in detector(revisions=revisions, catalogue=transactions):
        work_unit = work_units.get(revision.work_unit_id)
        if work_unit is None or work_unit.bucket_id != bucket_id:
            continue
        findings.append(
            LedgerStaleFilingV1(
                modelo=str(work_unit.modelo),
                filing_year=int(work_unit.filing_year),
                period=work_unit.period.registry_token,
                calculation_revision_id=revision.calculation_revision_id,
                work_unit_id=revision.work_unit_id,
                changed_count=len(verdict.changed),
                removed_count=len(verdict.removed),
            )
        )
    return tuple(findings)


__all__ = ["LedgerStaleFilingV1", "read_stale_ledger_filings"]
