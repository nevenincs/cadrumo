"""The form options say per table class whether a vehicle declaration applies, by the registry's own classification."""

from __future__ import annotations

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetFormOptionsView
from cadrumo.domain.calculations.registry.actividad_asset_bindings import resolve_activity_asset_schedule_authority
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetIncompleteError
from cadrumo.domain.renta.actividad_asset.lifecycle import AssetKind

from .test_filing_handoff_without_period import _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = 2025


def _options(asset_kind: AssetKind) -> ActivityAssetFormOptionsView:
    return _operations().form_options(asset_kind=asset_kind, tax_year=_YEAR)


def _asks_for_a_vehicle_declaration(class_key: str) -> bool:
    """Run the resolver on a material election of this class that states no vehicle affectation."""
    with bundled_indexed_authority().operation() as operation:
        try:
            resolve_activity_asset_schedule_authority(
                operation.revision_for_context("100", filing_year=_YEAR, period="0A"),
                tax_year=_YEAR,
                asset_revision=_revision(class_key=class_key),
                authority_generation="vehicle-class-test",
                workforce=(),
                legal_reference=operation.legal_reference,
            )
        except ActividadAssetIncompleteError as error:
            return error.translated_message == "ledger.actividad_asset.errors.vehicle_affectation_required_for_class"
    return False


def test_the_flag_of_each_material_class_is_what_the_resolver_enforces() -> None:
    groups = _options(AssetKind.MATERIAL).table_groups

    assert groups
    for group in groups:
        assert group.can_hold_vehicle is _asks_for_a_vehicle_declaration(group.class_key), group.class_key


def test_some_material_class_can_hold_a_vehicle_and_some_cannot() -> None:
    flags = {group.class_key: group.can_hold_vehicle for group in _options(AssetKind.MATERIAL).table_groups}

    assert flags["transporte"] is True
    assert flags["equipo-informacion-software"] is False
    assert any(flags.values())
    assert not all(flags.values())


def test_no_intangible_class_can_hold_a_vehicle() -> None:
    groups = _options(AssetKind.INTANGIBLE).table_groups

    assert groups
    assert not any(group.can_hold_vehicle for group in groups)
