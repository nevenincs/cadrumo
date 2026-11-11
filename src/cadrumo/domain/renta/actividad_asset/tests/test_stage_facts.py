"""The stage and status fact tables agree with the validators that enforce them."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..lifecycle import (
    BASIS_STAGE_FACTS,
    OPENING_STATUS_FACTS,
    WHOLLY_BUSINESS_STAGE_FACTS,
    ActivityAssetBasis,
    AssetBasisStage,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
    OwnershipMode,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ALL_STAGE_FACTS = frozenset(name for facts in BASIS_STAGE_FACTS.values() for name in facts)

_VALID: dict[AssetBasisStage, dict[str, object]] = {
    AssetBasisStage.WHOLE_PROPERTY: {
        "is_property": True,
        "construction_cost": Decimal("800"),
        "land_cost": Decimal("200"),
        "ownership_mode": OwnershipMode.SOLE,
        "ownership_share": Decimal("1"),
        "office_area": Decimal("20"),
        "total_area": Decimal("100"),
    },
    AssetBasisStage.TAXPAYER_OWNED: {"business_use_share": Decimal("0.5")},
    AssetBasisStage.BUSINESS_ALLOCATED: {"prior_allocation_provenance": "allocation"},
}


def _basis(stage: AssetBasisStage, **changes: object) -> ActivityAssetBasis:
    facts: dict[str, object] = {
        "stage": stage,
        "basis_amount": Decimal("1000"),
        "non_deductible_iva": Decimal("0"),
        **_VALID[stage],
        **changes,
    }
    return ActivityAssetBasis.model_validate(facts)


@pytest.mark.parametrize("stage", list(AssetBasisStage))
def test_a_stage_states_exactly_the_facts_the_table_names(stage: AssetBasisStage) -> None:
    stated = {name for name in _ALL_STAGE_FACTS if getattr(_basis(stage), name) is not None}

    assert stated == set(BASIS_STAGE_FACTS[stage])


@pytest.mark.parametrize("stage", list(AssetBasisStage))
def test_a_stage_refuses_any_fact_of_another_stage_and_each_one_it_requires(stage: AssetBasisStage) -> None:
    foreign = sorted(_ALL_STAGE_FACTS - set(BASIS_STAGE_FACTS[stage]))
    other_values = {name: value for facts in _VALID.values() for name, value in facts.items()}
    for name in foreign:
        with pytest.raises((ValidationError, ValueError)):
            _basis(stage, **{name: other_values[name]})
    for name in BASIS_STAGE_FACTS[stage]:
        if name in {"ownership_mode", "ownership_share"} and stage is AssetBasisStage.WHOLE_PROPERTY:
            continue
        with pytest.raises((ValidationError, ValueError)):
            ActivityAssetBasis.model_validate(
                {
                    "stage": stage,
                    "basis_amount": Decimal("1000"),
                    "non_deductible_iva": Decimal("0"),
                    **{key: value for key, value in _VALID[stage].items() if key != name},
                },
            )


def test_a_missing_opening_history_states_no_fact_and_a_known_one_may_state_each_of_its_own() -> None:
    assert OPENING_STATUS_FACTS[OpeningHistoryStatus.MISSING] == ()
    with pytest.raises(ValidationError):
        OpeningAmortizationHistory(status=OpeningHistoryStatus.MISSING, accumulated_amount=Decimal("1"))
    known = OpeningAmortizationHistory(
        status=OpeningHistoryStatus.KNOWN,
        accumulated_amount=Decimal("100"),
        covered_through_tax_year=2024,
    )
    assert {name for name in OPENING_STATUS_FACTS[OpeningHistoryStatus.KNOWN] if getattr(known, name) is not None} == {
        "accumulated_amount",
        "covered_through_tax_year",
    }


def test_a_wholly_business_purchase_states_no_split_source_and_keeps_its_full_cost() -> None:
    ((stage, facts),) = WHOLLY_BUSINESS_STAGE_FACTS.items()

    basis = ActivityAssetBasis.model_validate(
        {"stage": stage, "basis_amount": Decimal("1000"), "non_deductible_iva": Decimal("210"), **facts}
    )

    assert basis.prior_allocation_provenance is None
    assert {name for name in _ALL_STAGE_FACTS if getattr(basis, name) is not None} == set(facts)
    assert set(facts) == set(BASIS_STAGE_FACTS[stage])
    assert basis.deductible_basis() == basis.acquisition_cost() == Decimal("1210")


def test_a_split_that_really_happened_still_needs_its_source() -> None:
    with pytest.raises(ValidationError, match="basis_stage_requires_fact"):
        ActivityAssetBasis.model_validate(
            {
                "stage": AssetBasisStage.BUSINESS_ALLOCATED,
                "basis_amount": Decimal("1000"),
                "non_deductible_iva": Decimal("0"),
            }
        )
