"""A request field's form annotation is admitted by the operation model contract only when it is well formed."""

from __future__ import annotations

from typing import Annotated

import pytest
from pydantic import BaseModel, ConfigDict, Field

from ....core.models import STRICT_FROZEN_CONFIG
from ....core.type_guards import is_str_keyed_dict
from ..form_field_annotation import OPERATION_FORM_FIELD_SCHEMA_KEY, form_field_schema, served_form_field
from ..registry_schema_validation import strict_model_json_schema
from ..schema_identity import OperationSchemaIdentityV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _AnnotatedPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    owner: Annotated[str, Field(json_schema_extra=form_field_schema(bound="profile"))]
    note: Annotated[str, Field(json_schema_extra=form_field_schema(label_key="application.example.note"))] = ""


class _MalformedAnnotationPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    note: Annotated[str, Field(json_schema_extra={OPERATION_FORM_FIELD_SCHEMA_KEY: {"label_key": "Note, in words"}})]


class _AnnotatedModelPayload(BaseModel):
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        validate_default=True,
        json_schema_extra={OPERATION_FORM_FIELD_SCHEMA_KEY: {"bound": "profile"}},
    )

    note: str


def _identity(model_type: type[BaseModel]) -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1.from_model(
        schema_id="example.form-annotation", schema_version=1, model_type=model_type
    )


def test_a_well_formed_annotation_is_served_on_its_property() -> None:
    _identity(_AnnotatedPayload)
    properties = strict_model_json_schema(_AnnotatedPayload)["properties"]
    assert is_str_keyed_dict(properties)
    note_schema, owner_schema = properties["note"], properties["owner"]
    assert is_str_keyed_dict(note_schema)
    assert is_str_keyed_dict(owner_schema)

    note = served_form_field(note_schema)
    owner = served_form_field(owner_schema)

    assert note is not None
    assert note.label_key == "application.example.note"
    assert owner is not None
    assert owner.bound == "profile"


def test_a_malformed_annotation_is_refused_by_the_contract() -> None:
    with pytest.raises(ValueError, match=OPERATION_FORM_FIELD_SCHEMA_KEY):
        _identity(_MalformedAnnotationPayload)


def test_an_annotation_on_the_whole_model_is_refused_by_the_contract() -> None:
    with pytest.raises(ValueError, match="nonstructural annotations only"):
        _identity(_AnnotatedModelPayload)


@pytest.mark.parametrize(
    "annotation",
    [
        {},
        {"label_key": "application.example.note", "bound": "profile"},
        {"bound": "profile", "entry_option_family": "rental_lease"},
        {
            "label_key": "application.example.note",
            "entry_option_family": "rental_lease",
            "choice_label_keys": {"A": "application.example.a"},
        },
        {"label_key": "application.example.note", "words": "Note"},
    ],
    ids=["empty", "asked and bound", "bound with a family", "family and worded choices", "served words"],
)
def test_an_annotation_that_is_not_exactly_asked_or_bound_is_refused(annotation: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="malformed"):
        served_form_field({"type": "string", OPERATION_FORM_FIELD_SCHEMA_KEY: annotation})


def test_a_property_without_an_annotation_is_not_put_to_a_person() -> None:
    assert served_form_field({"type": "string"}) is None
