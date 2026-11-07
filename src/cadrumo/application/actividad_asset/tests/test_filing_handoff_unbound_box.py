"""A filing handoff states a kind the edition binds no Modelo 100 box for as a gap, never as a refusal."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import date

import pytest

from cadrumo.application.actividad_asset.operation_dtos import ActivityAssetFilingHandoffSnapshot
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.core.period import Period
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.lifecycle import AssetKind
from cadrumo.domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ..schedule_walk import M100GapKind
from .ledger_support import MemoryLedger
from .operations_support import ACQUISITION, build_forecast, build_revision
from .register_support import MemoryRepository, memory_register_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIRST = build_revision().in_service_date.year


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    """Hold the authority the runtime holds, so code that reads a form fact has it."""
    with bundled_indexed_authority().operation():
        yield


def _operations_without_a_material_box() -> ActivityAssetOperations:
    """Wire a register whose edition binds a box for intangible assets only."""
    authority = memory_register_authority()
    published = authority.m100_amortization_casillas
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(ACQUISITION),
        forecast_operation=build_forecast,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=replace(
            authority,
            m100_amortization_casillas=lambda year: {
                kind: box for kind, box in published(year).items() if kind is not AssetKind.MATERIAL
            },
        ),
    )
    operations.create(build_revision(), ActivityAssetDescriptorFacts(name="Office laptop"))
    return operations


def test_a_kind_without_a_box_is_a_gap_over_the_year_it_was_in_service_and_the_other_kind_is_stated() -> None:
    handoff = _operations_without_a_material_box().filing_handoff(tax_year=_FIRST)

    assert handoff.material_m100 is None
    assert handoff.material_m100_box_name is None
    assert handoff.intangible_m100 is not None
    assert handoff.intangible_m100.tax_year == _FIRST
    (gap,) = handoff.m100_gaps
    assert (gap.asset_id, gap.kind, gap.accrued) == ("laptop-1", M100GapKind.BOX_UNBOUND, None)
    assert (gap.covered_from, gap.covered_until) == (date(_FIRST, 1, 1), date(_FIRST + 1, 1, 1))


def test_a_kind_without_a_box_leaves_out_nothing_of_a_year_before_the_element_was_in_service() -> None:
    handoff = _operations_without_a_material_box().filing_handoff(tax_year=_FIRST - 1)

    assert handoff.material_m100 is None
    assert handoff.m100_gaps == ()


def test_the_unbound_gap_and_the_absent_box_keep_their_meaning_across_the_wire() -> None:
    operations = _operations_without_a_material_box()
    handoff = operations.filing_handoff(tax_year=_FIRST, m130_period=Period.from_year_and_code(_FIRST, "4T"))

    snapshot = ActivityAssetFilingHandoffSnapshot.model_validate_json(
        ActivityAssetFilingHandoffSnapshot.from_domain(handoff).model_dump_json()
    )

    assert snapshot.material_m100 is None
    assert snapshot.m100_gaps[0].kind is M100GapKind.BOX_UNBOUND
    assert snapshot.m100_gaps[0].covered_through == date(_FIRST, 12, 31)
    assert snapshot.to_domain() == handoff
