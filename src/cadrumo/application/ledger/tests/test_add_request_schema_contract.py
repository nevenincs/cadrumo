"""The request schema served for ``ledger.add`` lists exactly what the operation accepts."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core.config import override_settings
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n.render import tr
from ....core.type_guards import is_object_list, is_str_keyed_dict
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.errors import TransactionValidationError
from ...operations.form_field_annotation import OperationFormFieldV1, served_form_field
from ..ledger_add_command import resolve_ledger_add_flow
from ..ledger_add_contracts import LedgerAddRequest
from .add_request_description_support import ledger_add_description

_BOOKED_DATE = date.today().isoformat()

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
#: Written out here, not derived from the model: the classifications a person may assign by hand.
_ACCEPTED_CLASSIFICATIONS = ["BUSINESS", "PERSONAL", "MIXED", "NOT_YET_PROCESSED"]


def _property(name: str) -> dict[str, object]:
    properties = ledger_add_description().request_json_schema["properties"]
    assert is_str_keyed_dict(properties)
    served = properties[name]
    assert is_str_keyed_dict(served)
    return served


def _request_values(direction: str = "OUTGOING", classification: str = "NOT_YET_PROCESSED") -> dict[str, object]:
    return {
        "profile_id": _PROFILE,
        "booked_date": _BOOKED_DATE,
        "amount": "10.00",
        "direction": direction,
        "description": "Office materials",
        "business_classification": classification,
    }


def test_the_required_facts_are_the_ones_the_operation_cannot_default() -> None:
    required = ledger_add_description().request_json_schema["required"]

    assert is_object_list(required)
    assert set(required) == {"profile_id", "booked_date", "amount", "direction", "description"}


def test_the_direction_choices_are_every_direction() -> None:
    direction = _property("direction")

    assert direction["enum"] == [member.value for member in TransactionDirection]
    assert "default" not in direction


def test_the_classification_choices_are_exactly_the_ones_a_person_may_assign() -> None:
    classification = _property("business_classification")

    assert classification["enum"] == _ACCEPTED_CLASSIFICATIONS
    assert classification["default"] == "NOT_YET_PROCESSED"


@pytest.mark.parametrize("member", list(BusinessClassification), ids=lambda member: member.value)
def test_the_operation_accepts_each_served_classification_and_refuses_every_other_one(
    member: BusinessClassification,
) -> None:
    served = _property("business_classification")["enum"]
    assert is_object_list(served)
    values = _request_values(classification=member.value)

    if member.value in served:
        classification, _direction = resolve_ledger_add_flow(LedgerAddRequest.model_validate(values))
        assert classification is member
        return
    with pytest.raises(ValidationError, match="business_classification"):
        LedgerAddRequest.model_validate(values)
    unvalidated = LedgerAddRequest.model_construct(
        profile_id=_PROFILE,
        booked_date=_BOOKED_DATE,
        amount="10.00",
        direction="OUTGOING",
        description="Office materials",
        business_classification=member.value,
    )
    with pytest.raises(TransactionValidationError, match="assigned by the ledger pipeline"):
        resolve_ledger_add_flow(unvalidated)


@pytest.mark.parametrize("token", ["SIDEWAYS", "outgoing", ""])
def test_a_direction_the_schema_does_not_list_is_refused(token: str) -> None:
    with pytest.raises(ValidationError, match="direction"):
        LedgerAddRequest.model_validate(_request_values(direction=token))


@pytest.mark.parametrize("direction", list(TransactionDirection), ids=lambda member: member.value)
def test_every_served_direction_is_accepted(direction: TransactionDirection) -> None:
    _classification, accepted = resolve_ledger_add_flow(
        LedgerAddRequest.model_validate(_request_values(direction=direction.value))
    )

    assert accepted is direction


def _served_annotations() -> dict[str, OperationFormFieldV1]:
    properties = ledger_add_description().request_json_schema["properties"]
    assert is_str_keyed_dict(properties)
    served: dict[str, OperationFormFieldV1] = {}
    for name, prop in properties.items():
        assert is_str_keyed_dict(prop)
        annotation = served_form_field(prop)
        if annotation is not None:
            served[name] = annotation
    return served


def test_every_required_fact_is_put_to_a_person_or_bound_to_the_session() -> None:
    required = ledger_add_description().request_json_schema["required"]
    assert is_object_list(required)
    served = _served_annotations()

    assert {str(name) for name in required} <= set(served)
    assert served["profile_id"].bound == "profile"


def test_the_served_link_facts_name_their_entry_option_families() -> None:
    families = {
        name: annotation.entry_option_family
        for name, annotation in _served_annotations().items()
        if annotation.entry_option_family is not None
    }

    assert families == {
        "arrendamiento_ref": "rental_lease",
        "inmueble_ref": "rental_property",
        "gasto_capital_inmobiliario": "gasto_capital_inmobiliario",
    }


def test_each_served_choice_word_names_a_served_token() -> None:
    for name in ("direction", "business_classification"):
        enum = _property(name)["enum"]
        assert is_object_list(enum)
        assert set(_served_annotations()[name].choice_label_keys) == set(enum)


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_every_served_word_key_has_words_in_each_language(language: str) -> None:
    keys = [
        key
        for annotation in _served_annotations().values()
        for key in (annotation.label_key, *annotation.choice_label_keys.values())
        if key is not None
    ]
    with override_settings(cadrumo_output_language=language):
        unworded = [key for key in keys if tr(key) in ("", key)]

    assert keys
    assert unworded == []
