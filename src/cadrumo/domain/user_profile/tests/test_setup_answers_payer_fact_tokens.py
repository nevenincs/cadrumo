"""Every three-state payer fact parses its answer through one token contract.

The obligations facts (Modelo 347, 720, 721 and the lottery prize) routed their
answers through the canonical optional-token validator, while the withholding
and intracommunity facts were plain three-state fields with no validator at
all. Under the model's strict configuration that made a string answer depend on
which fact was being answered: ``third_party_transactions_above_347_threshold``
took ``"true"``, ``has_employees`` refused it, although both are the same kind
of operator yes/no/unanswered.

These tests read both families through the same table, so the contract is one
contract: the registry's canonical tokens in either language parse, a blank or
whitespace answer stays unanswered rather than becoming a declared no, and an
unrecognised token is refused instead of being read as a no.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..setup_answers import SetupAnswers

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_TAX_ID = "00000000T"

WITHHOLDING_PAYER_FACTS = (
    "has_employees",
    "pays_professionals_with_retencion",
    "pays_rent_with_retencion",
    "art109_activity_income_withholding_ge_70pct",
    "does_intracomunitario",
)
"""The family that carried no validator before this contract was shared."""

OBLIGATION_PAYER_FACTS = (
    "third_party_transactions_above_347_threshold",
    "bienes_extranjero_above_threshold",
    "monedas_virtuales_extranjero_above_threshold",
    "premio_loteria_gravamen_especial_sin_retencion",
)
"""The family that already routed through the canonical token validator."""

_PAYER_FACTS = (*WITHHOLDING_PAYER_FACTS, *OBLIGATION_PAYER_FACTS)

_ACCEPTED: tuple[tuple[object, bool], ...] = (
    ("true", True),
    ("false", False),
    ("TRUE", True),
    ("yes", True),
    ("no", False),
    ("sí", True),
    ("1", True),
    ("0", False),
    (True, True),
    (False, False),
)

_UNANSWERED: tuple[object, ...] = ("", "   ", None)

_REFUSED: tuple[object, ...] = ("garbage", "maybe", 42)


def _answered(field_name: str, value: object) -> object:
    return getattr(SetupAnswers.model_validate({"tax_id": _TAX_ID, field_name: value}), field_name)


@pytest.mark.parametrize("field_name", _PAYER_FACTS)
@pytest.mark.parametrize(("value", "expected"), _ACCEPTED)
def test_an_accepted_token_parses_to_its_boolean(field_name: str, value: object, expected: bool) -> None:
    assert _answered(field_name, value) is expected


@pytest.mark.parametrize("field_name", _PAYER_FACTS)
@pytest.mark.parametrize("value", _UNANSWERED)
def test_a_blank_answer_stays_unanswered(field_name: str, value: object) -> None:
    """A blank must not become a declared no: persistence drops an unanswered fact."""
    assert _answered(field_name, value) == ""


@pytest.mark.parametrize("field_name", _PAYER_FACTS)
@pytest.mark.parametrize("value", _REFUSED)
def test_an_unrecognised_token_is_refused(field_name: str, value: object) -> None:
    with pytest.raises(ValidationError, match="payer applicability fact"):
        SetupAnswers.model_validate({"tax_id": _TAX_ID, field_name: value})


def test_both_families_read_the_same_tokens() -> None:
    """The point of the shared validator: no answer depends on which fact is asked."""
    for value, _expected in _ACCEPTED:
        answers = {field_name: _answered(field_name, value) for field_name in _PAYER_FACTS}
        assert len(set(answers.values())) == 1, answers
