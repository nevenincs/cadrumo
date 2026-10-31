"""A purchase affected wholly to the activity from the start is registered without a split source."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from cadrumo.application.actividad_asset.operation_dtos import ActivityAssetBasisSnapshot
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    WHOLLY_BUSINESS_STAGE_FACTS,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
)

from .test_form_options_stage_facts import _options
from .test_register import _NAME, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_exactly_one_stage_serves_the_facts_that_state_a_wholly_business_purchase() -> None:
    options = _options()

    served = {item.stage: item.wholly_business_facts for item in options.basis_stages if item.wholly_business_facts}
    assert set(served) == set(WHOLLY_BUSINESS_STAGE_FACTS)
    assert AssetBasisStage.BUSINESS_ALLOCATED not in served
    (stage,) = served
    stage_option = next(item for item in options.basis_stages if item.stage is stage)
    assert {item.fact for item in served[stage]} <= set(stage_option.facts)
    assert {item.fact: Decimal(item.value.decimal) for item in served[stage]} == dict(
        WHOLLY_BUSINESS_STAGE_FACTS[stage]
    )


def test_an_element_stated_from_the_served_facts_registers_and_amortizes_its_whole_cost() -> None:
    options = _options()
    option = next(item for item in options.basis_stages if item.wholly_business_facts)
    base = _revision(basis="2000")
    basis = ActivityAssetBasisSnapshot.from_domain(base.basis).model_dump(mode="python")
    basis.update(
        stage=option.stage,
        prior_allocation_provenance=None,
        **{item.fact: item.value for item in option.wholly_business_facts},
    )
    facts: dict[str, Any] = {name: getattr(base, name) for name in type(base).model_fields}
    facts["basis"] = ActivityAssetBasisSnapshot.model_validate(basis).to_domain()
    operations, _ = _operations()

    operations.create(ActivityAssetRevision(**facts), _NAME)

    (listed,) = operations.list_elements()
    assert listed.basis.decimal == "2000.00"
    assert operations.form_options(asset_kind=AssetKind.MATERIAL, tax_year=2025).basis_stages == options.basis_stages
