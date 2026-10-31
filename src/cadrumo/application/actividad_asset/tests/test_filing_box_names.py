"""The filing handoff names every box from the registry layout and tells the two Modelo 130 rows apart."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from cadrumo.application.actividad_asset.operation_dtos import ActivityAssetFilingHandoffSnapshot
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.period import Period
from cadrumo.domain.renta.actividad_asset.lifecycle import AssetKind

from ....domain.calculations.registry.authority import bundled_indexed_authority
from .operations_support import build_operations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    """Hold the authority the runtime holds, so code that reads a form fact has it."""
    with bundled_indexed_authority().operation():
        yield


_PERIOD = Period.from_year_and_code(2025, "4T")


def test_the_two_modelo_130_rows_share_a_box_and_are_named_apart_by_their_asset_kind() -> None:
    handoff = build_operations().filing_handoff(tax_year=2025, m130_period=_PERIOD, language=OutputLanguage.ES)

    material, intangible = handoff.material_m130, handoff.intangible_m130
    assert material is not None
    assert intangible is not None
    assert material.target_casilla_id == intangible.target_casilla_id
    assert material.box_name != intangible.box_name
    assert material.box_name == "Gastos - Inmovilizado material"
    assert intangible.box_name == "Gastos - Inmovilizado intangible"


def test_the_modelo_100_boxes_are_named_by_the_registry_layout_in_the_language_asked() -> None:
    operations = build_operations()

    spanish = operations.filing_handoff(tax_year=2025, language=OutputLanguage.ES)
    english = operations.filing_handoff(tax_year=2025, language=OutputLanguage.EN)

    assert spanish.material_m100_box_name == "Amortización del inmovilizado material"
    assert spanish.intangible_m100_box_name == "Amortización del inmovilizado inmaterial"
    assert english.material_m100_box_name == "Depreciation of tangible fixed assets"
    assert english.intangible_m100_box_name == "Depreciation of intangible fixed assets"


def test_the_names_reach_the_wire_beside_their_box_and_restore_from_it() -> None:
    handoff = build_operations().filing_handoff(tax_year=2025, m130_period=_PERIOD, language=OutputLanguage.EN)

    wire = ActivityAssetFilingHandoffSnapshot.from_domain(handoff)

    assert wire.material_m100.box_name == "Depreciation of tangible fixed assets"
    assert wire.material_m130 is not None
    assert wire.intangible_m130 is not None
    assert (wire.material_m130.asset_kind, wire.intangible_m130.asset_kind) == (
        AssetKind.MATERIAL,
        AssetKind.INTANGIBLE,
    )
    assert wire.material_m130.box_name == "Expenses - Tangible asset"
    assert wire.to_domain() == handoff
