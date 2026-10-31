"""The form options serve the facts each basis stage and opening status carries, and the Modelo 130 periods."""

from __future__ import annotations

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetFormOptionsView
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    BASIS_STAGE_FACTS,
    OPENING_STATUS_FACTS,
    AssetBasisStage,
    AssetKind,
)

from .test_register import _NAME, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _options(tax_year: int = 2025) -> ActivityAssetFormOptionsView:
    operations, _ = _operations()
    operations.create(_revision(), _NAME)
    return operations.form_options(asset_kind=AssetKind.MATERIAL, tax_year=tax_year)


def test_each_basis_stage_serves_its_facts_and_only_the_whole_property_stage_is_property() -> None:
    options = _options()

    assert {item.stage: item.facts for item in options.basis_stages} == dict(BASIS_STAGE_FACTS)
    assert {item.stage for item in options.basis_stages if item.is_property} == {AssetBasisStage.WHOLE_PROPERTY}


def test_each_opening_status_serves_the_facts_it_can_state() -> None:
    assert {item.status: item.facts for item in _options().opening_statuses} == dict(OPENING_STATUS_FACTS)


def test_the_modelo_130_periods_come_from_the_registry_selector() -> None:
    assert _options().m130_periods == ("1T", "2T", "3T", "4T")
