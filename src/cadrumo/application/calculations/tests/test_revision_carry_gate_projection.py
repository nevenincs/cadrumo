"""The revision-carry gate resolves the law revision of a projected year through the work unit's own selection.

A filing year no edition authors is carried forward from the nearest authored one, so
a calculation stamped with that edition is current. A stamp the law's selection does
not give, a year below the support floor read as authored history, and a modelo the
registry does not know keep their refusals.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    newest_authored_edition,
    projected_exercise,
)
from ..revision_carry_gate import revision_carry_outcome

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _stamp(*, revision_id: str, year: int, modelo: str = "100") -> RegistrySnapshotRef:
    return RegistrySnapshotRef(modelo=modelo, revision_id=revision_id, modelo_year=year, period="0A")


def test_a_projected_year_stamped_with_its_source_edition_is_current() -> None:
    source = str(newest_authored_edition("100"))
    with bundled_indexed_authority().operation() as operation:
        outcome = revision_carry_outcome(
            _stamp(revision_id=source, year=projected_exercise("100")), operation=operation
        )

    assert not outcome.refused
    assert outcome.selected_revision_id == source


def test_a_projected_year_stamped_with_another_edition_diverges() -> None:
    source = str(newest_authored_edition("100"))
    older = str(authored_revisions("100")[-2].id)
    with bundled_indexed_authority().operation() as operation:
        outcome = revision_carry_outcome(_stamp(revision_id=older, year=projected_exercise("100")), operation=operation)

    assert outcome.refused
    assert outcome.selected_revision_id == source


def test_an_authored_year_below_the_support_floor_still_reads_as_authored_history() -> None:
    oldest = authored_revisions("100")[0]
    with bundled_indexed_authority().operation() as operation:
        assert not operation.supported_filing_years().admits_filing_year(oldest.valid_from.year)
        outcome = revision_carry_outcome(
            _stamp(revision_id=str(oldest.id), year=oldest.valid_from.year), operation=operation
        )

    assert not outcome.refused
    assert outcome.selected_revision_id == str(oldest.id)


def test_a_modelo_the_registry_does_not_know_is_unresolvable() -> None:
    with bundled_indexed_authority().operation() as operation:
        outcome = revision_carry_outcome(
            _stamp(revision_id="2025", year=newest_authored_edition("100"), modelo="999"), operation=operation
        )

    assert outcome.refused
    assert outcome.selected_revision_id is None
