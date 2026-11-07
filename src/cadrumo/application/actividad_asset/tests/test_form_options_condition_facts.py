"""The form options serve the facts each acquired condition carries and the shapes a later payment takes."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.renta.actividad_asset.election import ACQUIRED_CONDITION_FACTS, AcquiredCondition
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    FURTHER_ACQUISITION_SHAPES,
    REGISTERABLE_ACQUISITION_SHAPES,
    AcquisitionShape,
    AssetKind,
)

from .test_form_options_stage_facts import form_options_stage_facts_options
from .test_register import NAME, register_operations, register_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon


def test_each_condition_serves_the_facts_only_it_carries() -> None:
    options = form_options_stage_facts_options()

    assert {item.condition: item.facts for item in options.acquired_conditions} == dict(ACQUIRED_CONDITION_FACTS)
    assert next(item.facts for item in options.acquired_conditions if item.condition is AcquiredCondition.NEW) == ()


def test_the_used_condition_serves_the_construction_date_and_the_original_price() -> None:
    used = next(
        item
        for item in form_options_stage_facts_options().acquired_conditions
        if item.condition is AcquiredCondition.USED
    )

    assert used.facts == ("building_construction_date", "used_original_price")


def test_the_further_acquisition_shapes_stand_apart_from_the_registerable_ones() -> None:
    options = form_options_stage_facts_options()

    assert options.further_acquisition_shapes == FURTHER_ACQUISITION_SHAPES
    assert set(options.further_acquisition_shapes) == {AcquisitionShape.SPLIT_PAYMENT, AcquisitionShape.ANCILLARY_COST}
    assert options.acquisition_shapes == REGISTERABLE_ACQUISITION_SHAPES
    assert not set(options.further_acquisition_shapes) & set(options.acquisition_shapes)


def test_the_served_shapes_do_not_depend_on_the_asset_kind() -> None:
    operations, _ = register_operations()
    operations.create(register_revision(), NAME)
    intangible = operations.form_options(asset_kind=AssetKind.INTANGIBLE, tax_year=_YEAR)

    assert intangible.further_acquisition_shapes == FURTHER_ACQUISITION_SHAPES
