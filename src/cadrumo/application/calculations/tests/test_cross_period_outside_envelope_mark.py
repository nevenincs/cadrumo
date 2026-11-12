"""The envelope mark on a previous-filing dependency, and the one predicate edit admission shares with it.

The first-quarter Modelo 130 reads the previous ejercicio's net activity income from that
year's Modelo 100. When the pinned support envelope refuses that year the requirement is
marked, never dropped: the dependency inventory is the same whatever the envelope, and the
mark is derived from the pinned catalogue, so it is not part of the requirement's serialized form.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.filing_record import ModeloRecordCatalogue
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...modelo.tests.advisory_diagnostic_repositories import EmptyObservationRepository
from ..cross_period_clean_state import (
    attestable_carry_sources,
    cross_period_dependency_requirements,
)
from ..cross_period_models import CrossPeriodDependencyOrigin

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The carry a first-quarter Modelo 130 reads from the previous ejercicio's Modelo 100.
_BINDING = "irpf.previous_year_economic_activity_net_income"


def _attestable(snapshot, operation, *units):
    return attestable_carry_sources(
        snapshot,
        operation=operation,
        observation_repository=EmptyObservationRepository(),
        filing_catalogue=ModeloRecordCatalogue(),
        work_catalogue=WorkUnitCatalogue(work_units={unit.work_unit_id: unit for unit in units}),
    )


def _held(year: int) -> WorkUnit:
    period = Period.from_year_and_code(year, "0A")
    now = datetime(1980, 9, 21, 10, 0, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="held-bucket", modelo="100", filing_year=year, period=period, revision_id="held"
        ),
        bucket_id="held-bucket",
        modelo="100",
        filing_year=year,
        period=period,
        revision_id="held",
        name="Renta",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.parametrize("offset", [0, 1], ids=["floor", "floor-plus-one"])
def test_a_source_nothing_is_held_for_is_attestable_and_one_held_is_not(offset: int) -> None:
    year = filing_year_envelope().floor + offset
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("130", filing_year=year, period="1T", grade=RegistryAuthorityGrade.CALCULATION)
        absent = _attestable(snapshot, operation)
        held = _attestable(snapshot, operation, _held(year - 1))

    assert set(absent) == {_BINDING}
    (source,) = absent[_BINDING]
    assert source.origin is CrossPeriodDependencyOrigin.PREVIOUS_FILING_BINDING
    assert (source.source_modelo, source.filing_year, source.period.registry_token) == ("100", year - 1, "0A")
    assert held == {}


def test_marking_never_drops_a_requirement_so_the_inventory_is_the_same_whatever_the_envelope() -> None:
    floor = filing_year_envelope().floor
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("130", filing_year=floor, period="1T", grade=RegistryAuthorityGrade.CALCULATION)
        marked = cross_period_dependency_requirements(snapshot, support=operation.supported_filing_years())
        unmarked = cross_period_dependency_requirements(snapshot.model_copy(update={"supported_filing_years": None}))

    assert [requirement.key for requirement in marked] == [requirement.key for requirement in unmarked]
    assert any(requirement.source_outside_envelope for requirement in marked)
    assert not any(requirement.source_outside_envelope for requirement in unmarked)


def test_the_mark_is_derived_from_the_pinned_catalogue_and_is_not_serialized() -> None:
    floor = filing_year_envelope().floor
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("130", filing_year=floor, period="1T", grade=RegistryAuthorityGrade.CALCULATION)
        marked = [
            requirement
            for requirement in cross_period_dependency_requirements(snapshot)
            if requirement.source_outside_envelope
        ]

    assert marked
    assert all("source_outside_envelope" not in requirement.model_dump() for requirement in marked)
