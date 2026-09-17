"""The carry gate re-confirms prior filings below the supported filing floor.

The support envelope decides which years the product files; it does not decide
which design the law applied to an earlier year. A carried prior-year value is
therefore re-confirmed against the law-selected revision even when that year
sits below the floor, and a stamp naming any other revision is still refused.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ..revision_carry_gate import revision_carry_outcome

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _below_floor_year() -> int:
    support = published_supported_filing_years()
    assert support is not None
    return support.floor - 1


def _law_selected_m100_revision(operation: PinnedAuthorityOperation, year: int) -> str:
    covering = [
        revision
        for revision in operation.modelo_directory("100").revisions
        if revision.period_selector.includes_year(year)
    ]
    assert len(covering) == 1, f"expected one authored modelo 100 revision covering {year}"
    return str(covering[0].id)


def test_carry_below_the_floor_is_confirmed_against_its_law_selected_revision(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = _below_floor_year()
    ref = RegistrySnapshotRef(
        modelo="100",
        revision_id=_law_selected_m100_revision(authority_operation, year),
        modelo_year=year,
        period="0A",
    )

    outcome = revision_carry_outcome(ref, operation=authority_operation)

    assert outcome.refused is False
    assert outcome.selected_revision_id == ref.revision_id


def test_carry_below_the_floor_with_a_divergent_stamp_is_refused(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = _below_floor_year()
    law_selected = _law_selected_m100_revision(authority_operation, year)
    other = next(
        str(revision.id)
        for revision in authority_operation.modelo_directory("100").revisions
        if str(revision.id) != law_selected
    )
    ref = RegistrySnapshotRef(modelo="100", revision_id=other, modelo_year=year, period="0A")

    outcome = revision_carry_outcome(ref, operation=authority_operation)

    assert outcome.refused is True
    assert outcome.selected_revision_id == law_selected
