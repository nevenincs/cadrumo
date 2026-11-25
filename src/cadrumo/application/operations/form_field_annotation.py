"""How a request field is put to a person, served inside the operation's own request schema.

An operation that a frontend builds a form from annotates each field it offers
under :data:`OPERATION_FORM_FIELD_SCHEMA_KEY`: the catalogue key of the words
the field is shown with, the catalogue key of each closed choice's words, the
served entry-option family a field is picked from, or the binding a frontend
fills itself. A field without the annotation is not offered to a person. The
annotation names catalogue keys, never words, so the served schema and the
operation contract digest stay the same in every output language.

The annotation changes no validation: the model's own types and validators
decide what the operation accepts. The operation model contract admits this
key beside the plain JSON-schema annotations and checks it against
:class:`OperationFormFieldV1`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, Field, JsonValue, ValidationError, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG

OPERATION_FORM_FIELD_SCHEMA_KEY: Final = "x-cadrumo-form-field"
"""The JSON-schema keyword a request field's form annotation is served under."""

type OperationFormFieldBinding = Literal["profile"]
"""What a frontend fills a bound field with: ``profile`` is the exact profile its session was admitted for."""

_LocaleKeyText = Annotated[str, Field(min_length=1, max_length=256, pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")]
_ChoiceToken = Annotated[str, Field(min_length=1, max_length=128)]
_FamilyName = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")]


class OperationFormFieldV1(BaseModel):
    """One request field's form annotation.

    A field is either bound (filled by the frontend from its session) or asked
    for under ``label_key``. An asked field may word its closed choices
    through ``choice_label_keys``, or be picked from the served entry-option
    family ``entry_option_family``, never both.
    """

    model_config = STRICT_FROZEN_CONFIG

    label_key: _LocaleKeyText | None = None
    choice_label_keys: dict[_ChoiceToken, _LocaleKeyText] = Field(default_factory=dict)
    entry_option_family: _FamilyName | None = None
    bound: OperationFormFieldBinding | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _asked_or_bound(self) -> Self:
        if (self.label_key is None) == (self.bound is None):
            raise ValueError("a form field is either asked for under its words or bound, exactly one")
        if self.bound is not None and (self.choice_label_keys or self.entry_option_family is not None):
            raise ValueError("a bound form field carries no words")
        if self.choice_label_keys and self.entry_option_family is not None:
            raise ValueError("a form field is worded by its choices or picked from a family, not both")
        return self


def form_field_schema(
    *,
    label_key: str | None = None,
    choice_label_keys: Mapping[str, str] | None = None,
    entry_option_family: str | None = None,
    bound: OperationFormFieldBinding | None = None,
) -> dict[str, JsonValue]:
    """The ``json_schema_extra`` that serves one field's form annotation."""
    annotation = OperationFormFieldV1(
        label_key=label_key,
        choice_label_keys=dict(choice_label_keys or {}),
        entry_option_family=entry_option_family,
        bound=bound,
    )
    return {OPERATION_FORM_FIELD_SCHEMA_KEY: annotation.model_dump(mode="json", exclude_defaults=True)}


def require_form_field_annotation(value: object) -> OperationFormFieldV1:
    """Validate a served or declared annotation; ``ValueError`` names what is wrong."""
    try:
        return OperationFormFieldV1.model_validate(value)
    except ValidationError as error:
        raise ValueError(f"malformed {OPERATION_FORM_FIELD_SCHEMA_KEY} annotation: {error}") from None


def served_form_field(prop: Mapping[str, object]) -> OperationFormFieldV1 | None:
    """The form annotation one served property carries, or ``None`` when it is not offered to a person."""
    if OPERATION_FORM_FIELD_SCHEMA_KEY not in prop:
        return None
    return require_form_field_annotation(prop[OPERATION_FORM_FIELD_SCHEMA_KEY])


__all__ = [
    "OPERATION_FORM_FIELD_SCHEMA_KEY",
    "OperationFormFieldBinding",
    "OperationFormFieldV1",
    "form_field_schema",
    "require_form_field_annotation",
    "served_form_field",
]
