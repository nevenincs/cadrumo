"""The finding key of a source disagreement, and the wire form its amounts share with a public result."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from ..source_disagreement import (
    DisagreementDecimalValue,
    DisagreementRelationValue,
    SourceDisagreementEntry,
    SourceDisagreementFact,
)
from .source_disagreement_support import sample_source_disagreement

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _with_cross_check_amount(fact: SourceDisagreementFact, amount: Decimal) -> SourceDisagreementFact:
    value_source, cross_check = fact.sources
    return SourceDisagreementFact.of(
        modelo=fact.modelo,
        filing_year=fact.filing_year,
        period=fact.period,
        work_unit_id=fact.work_unit_id,
        registry_revision_id=fact.registry_revision_id,
        inputs_digest=fact.inputs_digest,
        key=fact.key,
        value_channel=fact.value_channel,
        reached_casillas=fact.reached_casillas,
        sources=(value_source, cross_check.model_copy(update={"value": DisagreementDecimalValue.of(amount)})),
        selected_role=fact.selected_role,
    )


def test_the_key_ignores_the_work_unit_and_the_evidence_locators() -> None:
    fact = sample_source_disagreement()
    elsewhere = sample_source_disagreement(work_unit_id="u" * 64)
    located = fact.model_copy(
        update={"sources": tuple(entry.model_copy(update={"evidence_ref": "snapshot-1"}) for entry in fact.sources)}
    )
    assert elsewhere.finding_key == fact.finding_key
    assert SourceDisagreementFact.model_validate(located.model_dump()).finding_key == fact.finding_key


def test_the_key_moves_with_an_amount_and_with_the_figure() -> None:
    fact = sample_source_disagreement()
    assert _with_cross_check_amount(fact, Decimal("499.98")).finding_key != fact.finding_key
    assert sample_source_disagreement(casilla_id="0597").finding_key != fact.finding_key


def test_a_stored_fact_whose_content_was_altered_is_refused() -> None:
    stored = sample_source_disagreement().model_dump(mode="json")
    stored["sources"][1]["value"]["amount"] = "400.00"
    with pytest.raises(ValidationError, match="finding key does not match"):
        SourceDisagreementFact.model_validate_json(json.dumps(stored))


def test_a_stored_fact_round_trips_through_json_unchanged() -> None:
    fact = sample_source_disagreement()
    assert SourceDisagreementFact.model_validate_json(fact.model_dump_json()) == fact


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        (Decimal("500.00"), "500.00"),
        (Decimal("-0.01"), "-0.01"),
        (Decimal("1E+2"), "100"),
        (Decimal("0"), "0"),
        (Decimal("12.500"), "12.500"),
        (Decimal("1.000"), "1.000"),
        (Decimal("0.00"), "0.00"),
        (Decimal("-3.10"), "-3.10"),
    ],
)
def test_an_amount_is_held_as_canonical_text_and_read_back_exactly(amount: Decimal, text: str) -> None:
    value = DisagreementDecimalValue.of(amount)
    assert value.amount == text
    assert value.decimal == amount


@pytest.mark.parametrize("text", ["12.500", "1.000", "0.00", "-3.10"])
def test_a_canonical_amount_shaped_like_a_thousands_group_is_accepted_as_text(text: str) -> None:
    assert DisagreementDecimalValue(amount=text).amount == text
    assert DisagreementRelationValue(amount=text).decimal == Decimal(text)


@pytest.mark.parametrize(
    "text", ["1e3", "+1", "+5", "1,5", "1,00", "01", "-01.5", " 5", "", "1.000.000", "1.", ".5", "-"]
)
def test_an_amount_that_is_not_canonical_decimal_text_is_refused(text: str) -> None:
    with pytest.raises(ValidationError):
        DisagreementDecimalValue(amount=text)
    with pytest.raises(ValidationError):
        DisagreementRelationValue(amount=text)


@pytest.mark.parametrize("model", [SourceDisagreementFact, SourceDisagreementEntry])
def test_validation_and_serialization_publish_one_json_schema(model: type[BaseModel]) -> None:
    assert model.model_json_schema(mode="validation") == model.model_json_schema(mode="serialization")
