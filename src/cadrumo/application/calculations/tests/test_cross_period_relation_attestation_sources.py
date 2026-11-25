"""Which scalar carries of a relation-prefill binding an operator may state a figure for.

The annual Renta credits the pagos fraccionados from the year's four Modelo 130 quarters, so the
binding has one source requirement per quarter. A figure may be stated for it only while the
application holds none of them: the relation follows its sources, and a partial statement is not
admitted. A binding that carries rows stays sourced from records and is never offered.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.binding_value_contract import BindingValueChannel
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.filing_record import ModeloRecordCatalogue
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...modelo.edit_admission import permitted_binding_entry
from ...modelo.edit_models import ModeloEditNonWritableBindingOverrideSurfaceEntryV1, ModeloEditNonWritableReason
from ...modelo.tests.advisory_diagnostic_repositories import EmptyObservationRepository
from ..cross_period_clean_state import attestable_carry_binding_ids, attestable_carry_sources
from ..cross_period_models import CrossPeriodDependencyOrigin

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The carry the annual Renta reads from the year's Modelo 130 quarters.
_BINDING = "renta-modelo-130-pagos-fraccionados"
_QUARTERS = ("1T", "2T", "3T", "4T")


def _held_quarter(year: int, period_code: str) -> WorkUnit:
    period = Period.from_year_and_code(year, period_code)
    now = datetime(1980, 9, 21, 10, 0, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="held-bucket", modelo="130", filing_year=year, period=period, revision_id="held"
        ),
        bucket_id="held-bucket",
        modelo="130",
        filing_year=year,
        period=period,
        revision_id="held",
        name="Pagos fraccionados",
        created_at=now,
        updated_at=now,
    )


def _sources(snapshot: RegistrySnapshot, operation, *units: WorkUnit):
    return attestable_carry_sources(
        snapshot,
        operation=operation,
        observation_repository=EmptyObservationRepository(),
        filing_catalogue=ModeloRecordCatalogue(),
        work_catalogue=WorkUnitCatalogue(work_units={unit.work_unit_id: unit for unit in units}),
    )


def test_a_relation_is_attestable_for_all_its_source_periods_while_none_is_held() -> None:
    year = filing_year_envelope().floor
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION)
        sources = _sources(snapshot, operation)

    requirements = sources[_BINDING]
    assert {requirement.origin for requirement in requirements} == {CrossPeriodDependencyOrigin.REGISTRY_RELATION}
    assert {(requirement.source_modelo, requirement.filing_year) for requirement in requirements} == {("130", year)}
    assert {requirement.period.registry_token for requirement in requirements} == set(_QUARTERS)


@pytest.mark.parametrize("held", _QUARTERS)
def test_a_relation_with_any_one_source_held_is_not_attestable(held: str) -> None:
    year = filing_year_envelope().floor
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION)
        sources = _sources(snapshot, operation, _held_quarter(year, held))
        ids = attestable_carry_binding_ids(
            snapshot,
            operation=operation,
            observation_repository=EmptyObservationRepository(),
            filing_catalogue=ModeloRecordCatalogue(),
            work_catalogue=WorkUnitCatalogue(
                work_units={unit.work_unit_id: unit for unit in (_held_quarter(year, held),)}
            ),
        )

    assert _BINDING not in sources
    assert _BINDING not in ids


def _with_row_channel(snapshot: RegistrySnapshot, binding_id: str) -> RegistrySnapshot:
    """The snapshot with ``binding_id`` declared as a row channel, which no relation binding is in the registry."""
    bindings = tuple(
        binding.model_copy(update={"value": binding.value.model_copy(update={"channel": BindingValueChannel.ROW_SET})})
        if binding.id == binding_id
        else binding
        for binding in snapshot.revision.bindings
    )
    return snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"bindings": bindings})})


def test_a_row_channel_binding_is_never_attestable_and_the_surface_refuses_it() -> None:
    year = filing_year_envelope().floor
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION)
        rows = _with_row_channel(snapshot, _BINDING)
        sources = _sources(rows, operation)
        (binding,) = [item for item in rows.revision.bindings if item.id == _BINDING]
        entry = permitted_binding_entry(
            binding,
            revision=rows.revision,
            period="0A",
            row_filled=frozenset(),
            attestable_binding_ids=frozenset({_BINDING}),
        )

    assert _BINDING not in sources
    assert isinstance(entry, ModeloEditNonWritableBindingOverrideSurfaceEntryV1)
    assert entry.reason is ModeloEditNonWritableReason.VALUE_CHANNEL_UNAVAILABLE
