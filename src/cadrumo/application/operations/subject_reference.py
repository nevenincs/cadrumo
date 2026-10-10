"""The declared form of the subject reference one operation is submitted with.

Every submission names a subject, and each operation family admits exactly one
form of it. The form is declared on the definition and published in its public
contract, so a client learns it from the contract instead of guessing a string
the family then refuses.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import UnionType
from typing import Annotated, TypeAliasType, Union, cast, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import profile_operation_subject
from .models import OperationReference

type OperationSubjectPayloadField = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$"),
]
"""One request field name on the way to the value a subject is read from."""


class OperationSubjectKind(StrEnum):
    """Closed forms a registered operation's subject reference takes."""

    PROFILE = "profile"
    PAYLOAD_FIELD = "payload_field"
    PAYLOAD_FIELD_OR_PROFILE = "payload_field_or_profile"
    STORED_WORK_UNIT = "stored_work_unit"
    FIXED = "fixed"


_PAYLOAD_KINDS = frozenset({OperationSubjectKind.PAYLOAD_FIELD, OperationSubjectKind.PAYLOAD_FIELD_OR_PROFILE})
_PATH_KINDS = _PAYLOAD_KINDS | {OperationSubjectKind.STORED_WORK_UNIT}


class OperationSubjectReferenceV1(BaseModel):
    """Where the subject of one operation comes from.

    ``payload_path`` names a request field, outermost first. For the payload
    kinds the subject is that field's value; for a stored work unit it is the
    field naming the stored record whose owning work unit is the subject, which
    only the store can supply.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: OperationSubjectKind
    payload_path: tuple[OperationSubjectPayloadField, ...]
    literal: OperationReference | None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_shape(self) -> OperationSubjectReferenceV1:
        if bool(self.payload_path) != (self.kind in _PATH_KINDS):
            raise ValueError("a subject reference names a payload field exactly when its kind reads one")
        if (self.literal is not None) != (self.kind is OperationSubjectKind.FIXED):
            raise ValueError("a subject reference carries a literal exactly when its kind is fixed")
        return self

    @classmethod
    def profile(cls) -> OperationSubjectReferenceV1:
        """Declare the subject as the profile the session is admitted for."""
        return cls(kind=OperationSubjectKind.PROFILE, payload_path=(), literal=None)

    @classmethod
    def payload_field(cls, *path: str) -> OperationSubjectReferenceV1:
        """Declare the subject as the verbatim value of one required request field."""
        return cls(kind=OperationSubjectKind.PAYLOAD_FIELD, payload_path=path, literal=None)

    @classmethod
    def payload_field_or_profile(cls, *path: str) -> OperationSubjectReferenceV1:
        """Declare the subject as one request field when it is set, and the profile otherwise."""
        return cls(kind=OperationSubjectKind.PAYLOAD_FIELD_OR_PROFILE, payload_path=path, literal=None)

    @classmethod
    def stored_work_unit(cls, *key_path: str) -> OperationSubjectReferenceV1:
        """Declare the subject as the work unit owning the stored record one request field names."""
        return cls(kind=OperationSubjectKind.STORED_WORK_UNIT, payload_path=key_path, literal=None)

    @classmethod
    def fixed(cls, literal: str) -> OperationSubjectReferenceV1:
        """Declare one subject every submission of the operation shares."""
        return cls(kind=OperationSubjectKind.FIXED, payload_path=(), literal=literal)


def expected_operation_subject(
    reference: OperationSubjectReferenceV1,
    *,
    profile_id: UUID,
    payload: BaseModel | Mapping[str, object],
) -> str | None:
    """Render the subject one request must be submitted with, or ``None`` when only the store knows it.

    ``payload`` is the typed request or its JSON object; both render the same
    subject for the same request. ``None`` is returned for a stored work unit
    alone. A payload that lacks a required subject field raises ``ValueError``.
    """
    kind = reference.kind
    if kind is OperationSubjectKind.STORED_WORK_UNIT:
        return None
    if kind is OperationSubjectKind.PROFILE:
        return profile_operation_subject(str(profile_id))
    if kind is OperationSubjectKind.FIXED:
        return _declared_literal(reference)
    value = _payload_value(payload, reference.payload_path)
    if value is None:
        if kind is OperationSubjectKind.PAYLOAD_FIELD_OR_PROFILE:
            return profile_operation_subject(str(profile_id))
        raise ValueError("operation payload does not carry its declared subject field")
    if isinstance(value, (str, UUID)):
        return str(value)
    raise ValueError("operation payload subject field is not a reference")


def require_declared_subject_path(request_type: type[BaseModel], reference: OperationSubjectReferenceV1) -> None:
    """Refuse a declaration the request model cannot honour.

    Every step but the last must be one nested model, and the last may be
    absent only where the declaration says what the subject is without it.
    """
    model = request_type
    last = len(reference.payload_path) - 1
    for index, name in enumerate(reference.payload_path):
        field = model.model_fields.get(name)
        if field is None:
            raise ValueError("operation subject reference names a field its request type does not declare")
        if index == last:
            if _admits_none(field.annotation) != (reference.kind is OperationSubjectKind.PAYLOAD_FIELD_OR_PROFILE):
                raise ValueError(
                    "operation subject field may be absent exactly when the declaration falls back to the profile"
                )
            return
        nested = _nested_model(field.annotation)
        if nested is None:
            raise ValueError("operation subject reference passes through a field that is not one nested model")
        model = nested


def _declared_literal(reference: OperationSubjectReferenceV1) -> str:
    if reference.literal is None:
        raise ValueError("a fixed subject reference carries its literal")
    return reference.literal


def _payload_value(payload: BaseModel | Mapping[str, object], path: tuple[str, ...]) -> object:
    value: object = payload
    for name in path:
        value = _field_value(value, name)
        if value is None:
            return None
    return value


def _field_value(holder: object, name: str) -> object:
    if isinstance(holder, BaseModel):
        return getattr(holder, name, None)
    if isinstance(holder, Mapping):
        return cast("Mapping[str, object]", holder).get(name)
    raise ValueError("operation payload does not carry its declared subject field")


def _unwrapped(annotation: object) -> object:
    while True:
        if isinstance(annotation, TypeAliasType):
            annotation = annotation.__value__
        elif get_origin(annotation) is Annotated:
            annotation = get_args(annotation)[0]
        else:
            return annotation


def _admits_none(annotation: object) -> bool:
    annotation = _unwrapped(annotation)
    if annotation is None or annotation is type(None):
        return True
    if get_origin(annotation) in (Union, UnionType):
        return any(_admits_none(member) for member in get_args(annotation))
    return False


def _nested_model(annotation: object) -> type[BaseModel] | None:
    annotation = _unwrapped(annotation)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


__all__ = [
    "OperationSubjectKind",
    "OperationSubjectPayloadField",
    "OperationSubjectReferenceV1",
    "expected_operation_subject",
    "require_declared_subject_path",
]
