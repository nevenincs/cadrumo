"""Finite annual-age predicate retained by household-count fixtures."""

from ..descendant_record import DescendantRecordBase
from ..family_fact_context import FamilyFactResolutionContext


def is_eligible_menor_tres(
    descendant: DescendantRecordBase, filing_year: int, *, context: FamilyFactResolutionContext
) -> bool:
    """Apply the fixture annual age and household test without extending Art. 81 eligibility."""
    return descendant.convive_con_contribuyente and descendant.age_at_year_end(filing_year) < context.integer(
        "lirpf-art-58-under-three-maximum-age"
    )
