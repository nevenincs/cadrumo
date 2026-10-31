"""The condition and further-acquisition tables agree with the validators that enforce them."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ..election import ACQUIRED_CONDITION_FACTS, AcquiredCondition, ActivityAssetAmortizationElection
from ..lifecycle import (
    FURTHER_ACQUISITION_SHAPES,
    REGISTERABLE_ACQUISITION_SHAPES,
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetRevision,
    FurtherAcquisitionRow,
)
from .test_lifecycle import _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _with_condition(condition: AcquiredCondition, **changes: object) -> ActivityAssetRevision:
    base = _revision()
    facts = {name: getattr(base, name) for name in type(base).model_fields}
    return ActivityAssetRevision(**{**facts, "acquired_condition": condition, **changes})


def test_every_condition_is_tabled_and_every_fact_is_a_field_of_the_record() -> None:
    fields = set(ActivityAssetRevision.model_fields) | set(ActivityAssetAmortizationElection.model_fields)

    assert set(ACQUIRED_CONDITION_FACTS) == set(AcquiredCondition)
    assert {fact for facts in ACQUIRED_CONDITION_FACTS.values() for fact in facts} <= fields


def test_the_construction_date_is_stated_exactly_under_the_conditions_that_table_it() -> None:
    built = date(2000, 1, 1)
    for condition, facts in ACQUIRED_CONDITION_FACTS.items():
        if "building_construction_date" in facts:
            assert _with_condition(condition, building_construction_date=built).building_construction_date == built
        else:
            with pytest.raises(ValidationError, match="only a fact of a used asset"):
                _with_condition(condition, building_construction_date=built)


def test_a_further_acquisition_row_takes_exactly_the_tabled_shapes() -> None:
    lineage = AcquisitionLineageReference(
        observed_transaction_id="a" * 64,
        observed_lineage_event_id="b" * 64,
        invoice_evidence_id="invoice-2",
        evidence_fingerprint="c" * 64,
    )
    for shape in AcquisitionShape:
        if shape in FURTHER_ACQUISITION_SHAPES:
            assert FurtherAcquisitionRow(shape=shape, lineage=lineage).shape is shape
        else:
            with pytest.raises(ValidationError, match="split payment or an ancillary cost"):
                FurtherAcquisitionRow(shape=shape, lineage=lineage)


def test_no_shape_is_both_registerable_and_a_further_acquisition() -> None:
    assert not set(REGISTERABLE_ACQUISITION_SHAPES) & set(FURTHER_ACQUISITION_SHAPES)
