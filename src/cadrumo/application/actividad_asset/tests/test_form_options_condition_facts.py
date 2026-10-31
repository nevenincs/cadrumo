"""The form options serve the facts each acquired condition carries and the shapes a later payment takes."""

from __future__ import annotations

import pytest

from cadrumo.domain.renta.actividad_asset.election import ACQUIRED_CONDITION_FACTS, AcquiredCondition
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    FURTHER_ACQUISITION_SHAPES,
    REGISTERABLE_ACQUISITION_SHAPES,
    AcquisitionShape,
    AssetKind,
)

from .test_form_options_stage_facts import _options
from .test_register import _NAME, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_each_condition_serves_the_facts_only_it_carries() -> None:
    options = _options()

    assert {item.condition: item.facts for item in options.acquired_conditions} == dict(ACQUIRED_CONDITION_FACTS)
    assert next(item.facts for item in options.acquired_conditions if item.condition is AcquiredCondition.NEW) == ()


def test_the_used_condition_serves_the_construction_date_and_the_original_price() -> None:
    used = next(item for item in _options().acquired_conditions if item.condition is AcquiredCondition.USED)

    assert used.facts == ("building_construction_date", "used_original_price")


def test_the_further_acquisition_shapes_stand_apart_from_the_registerable_ones() -> None:
    options = _options()

    assert options.further_acquisition_shapes == FURTHER_ACQUISITION_SHAPES
    assert set(options.further_acquisition_shapes) == {AcquisitionShape.SPLIT_PAYMENT, AcquisitionShape.ANCILLARY_COST}
    assert options.acquisition_shapes == REGISTERABLE_ACQUISITION_SHAPES
    assert not set(options.further_acquisition_shapes) & set(options.acquisition_shapes)


def test_the_served_shapes_do_not_depend_on_the_asset_kind() -> None:
    operations, _ = _operations()
    operations.create(_revision(), _NAME)
    intangible = operations.form_options(asset_kind=AssetKind.INTANGIBLE, tax_year=2025)

    assert intangible.further_acquisition_shapes == FURTHER_ACQUISITION_SHAPES
