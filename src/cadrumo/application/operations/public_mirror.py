"""Strict public mirrors of canonical owner read models for runtime transport.

A registered operation result must be a strict, closed Pydantic graph without
custom core schemas, coercive validators or serializers, and it must survive a
JSON round trip with its meaning intact. Canonical read models are not always
that shape: a domain code customises its core schema, a scalar union reads a
decimal back as text, a mapping has no strict JSON form. This module mirrors
exactly those nodes into reviewed ``Public*`` models and back again.

Only incompatible canonical nodes are mirrored; compatible children keep their
existing typed models. A public mirror carries the same field names as its
canonical model, so any canonical field added, removed or renamed fails the
inventory check instead of silently dropping or inventing data. Union arms are
matched by the ``Public`` name prefix. Projection and restoration both validate
the original canonical models.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import is_dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from types import GenericAlias, UnionType
from typing import Annotated, Literal, Self, TypeAliasType, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_CONFIG
from ._dataclass_fields import dataclass_type_fields


class PublicFactEntryV1(BaseModel):
    """One typed, ordered fact from a canonical immutable fact map."""

    model_config = STRICT_FROZEN_CONFIG

    key: str
    kind: Literal["string", "integer", "boolean", "decimal", "null"]
    text: str

    @model_validator(mode="after")
    def _validate_value(self) -> Self:
        _validate_scalar_text(self.kind, self.text, "fact")
        return self


class PublicScalarValueV1(BaseModel):
    """Preserve scalar kind and decimal precision across the public schema."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["string", "integer", "boolean", "decimal", "date", "null"]
    text: str

    @model_validator(mode="after")
    def _validate_value(self) -> Self:
        _validate_scalar_text(self.kind, self.text, "scalar")
        return self


class PublicTextEntryV1(BaseModel):
    """One ordered string entry from a canonical text map."""

    model_config = STRICT_FROZEN_CONFIG

    key: str
    value: str


type MirrorCompletion = Callable[[type[object], dict[str, object], BaseModel], None]
"""Fill canonical fields withheld from restoration, from the restored siblings and the public value."""


def _validate_boolean_text(text: str, subject: str) -> None:
    if text not in {"true", "false"}:
        raise ValueError(f"invalid boolean {subject}")


def _validate_integer_text(text: str, subject: str) -> None:
    if str(int(text)) != text:
        raise ValueError(f"invalid integer {subject}")


def _validate_decimal_text(text: str, subject: str) -> None:
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"invalid decimal {subject}") from None
    if not value.is_finite() or str(value) != text:
        raise ValueError(f"invalid decimal {subject}")


def _validate_date_text(text: str, subject: str) -> None:
    try:
        value_date = date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"invalid date {subject}") from None
    if value_date.isoformat() != text:
        raise ValueError(f"invalid date {subject}")


def _validate_null_text(text: str, subject: str) -> None:
    if text:
        raise ValueError(f"null {subject} must carry no text")


def _validate_scalar_text(kind: str, text: str, subject: str) -> None:
    if kind == "boolean":
        _validate_boolean_text(text, subject)
    elif kind == "integer":
        _validate_integer_text(text, subject)
    elif kind == "decimal":
        _validate_decimal_text(text, subject)
    elif kind == "date":
        _validate_date_text(text, subject)
    elif kind == "null":
        _validate_null_text(text, subject)


def bare_annotation(annotation: object) -> object:
    """Strip aliases, ``Annotated`` metadata and an optional ``None`` arm from one annotation."""
    if isinstance(annotation, TypeAliasType):
        return bare_annotation(annotation.__value__)
    origin = get_origin(annotation)
    if origin is Annotated:
        return bare_annotation(get_args(annotation)[0])
    if origin in (Union, UnionType):
        present = tuple(item for item in get_args(annotation) if item is not type(None))
        if len(present) == 1:
            return bare_annotation(present[0])
    if isinstance(origin, TypeAliasType) and origin.__name__ == "_BoundedRefList":
        return GenericAlias(tuple, (get_args(annotation)[0], Ellipsis))
    if isinstance(origin, TypeAliasType):
        raise ValueError("unreviewed generic public-mirror type alias")
    return annotation


def _inspect_model_fields(
    annotation: type[BaseModel],
    *,
    opaque: frozenset[type[object]],
    discovered: set[tuple[type[BaseModel], str]],
    visited: set[type[BaseModel]],
) -> None:
    if annotation in visited:
        return
    visited.add(annotation)
    for name, field in annotation.model_fields.items():
        if field.exclude not in (None, False):
            discovered.add((annotation, name))
        _inspect_canonical_annotation(
            field.annotation,
            opaque=opaque,
            discovered=discovered,
            visited=visited,
        )


def _inspect_dataclass_fields(
    annotation: type[object],
    *,
    opaque: frozenset[type[object]],
    discovered: set[tuple[type[BaseModel], str]],
    visited: set[type[BaseModel]],
) -> None:
    hints = get_type_hints(annotation)
    for field in dataclass_type_fields(annotation):
        _inspect_canonical_annotation(
            hints[field.name],
            opaque=opaque,
            discovered=discovered,
            visited=visited,
        )


def _inspect_canonical_annotation(
    annotation: object,
    *,
    opaque: frozenset[type[object]],
    discovered: set[tuple[type[BaseModel], str]],
    visited: set[type[BaseModel]],
) -> None:
    annotation = bare_annotation(annotation)
    if isinstance(annotation, type) and annotation in opaque:
        return
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        _inspect_model_fields(
            annotation,
            opaque=opaque,
            discovered=discovered,
            visited=visited,
        )
        return
    if isinstance(annotation, type) and is_dataclass(annotation):
        _inspect_dataclass_fields(
            annotation,
            opaque=opaque,
            discovered=discovered,
            visited=visited,
        )
        return
    for choice in get_args(annotation):
        _inspect_canonical_annotation(
            choice,
            opaque=opaque,
            discovered=discovered,
            visited=visited,
        )


def excluded_canonical_fields(
    root: type[object], *, opaque: frozenset[type[object]] = frozenset()
) -> frozenset[tuple[type[BaseModel], str]]:
    """Every canonical field reachable from ``root`` that its own serializer excludes.

    A caller compares this inventory with its reviewed set before projecting
    owner data, so a newly excluded field fails instead of crossing silently.
    ``opaque`` names types the caller never projects at all.
    """
    discovered: set[tuple[type[BaseModel], str]] = set()
    visited: set[type[BaseModel]] = set()
    _inspect_canonical_annotation(
        root,
        opaque=opaque,
        discovered=discovered,
        visited=visited,
    )
    return frozenset(discovered)


def project_public_mirror(
    value: object,
    canonical: object,
    public: object,
    *,
    omitted: Mapping[type[BaseModel], frozenset[str]] | None = None,
) -> object:
    """Project a canonical value while checking the mirror's exact field inventory.

    ``omitted`` names, per public mirror, canonical fields it deliberately does
    not carry; every other field must exist on both sides.
    """
    from ._public_mirror_projection import project_public_value

    return project_public_value(value, canonical, public, omitted or {})


def restore_public_mirror(
    value: object,
    canonical: object,
    public: object,
    *,
    withheld: frozenset[tuple[type[object], str]] = frozenset(),
    complete: MirrorCompletion | None = None,
) -> object:
    """Rebuild the canonical value from its public mirror, validating the canonical models.

    ``withheld`` names canonical fields not restored from their mirror; the
    ``complete`` hook fills them from the restored siblings before validation.
    """
    from ._public_mirror_restoration import restore_public_value

    return restore_public_value(value, canonical, public, withheld, complete)


__all__ = [
    "MirrorCompletion",
    "PublicFactEntryV1",
    "PublicScalarValueV1",
    "PublicTextEntryV1",
    "bare_annotation",
    "excluded_canonical_fields",
    "project_public_mirror",
    "restore_public_mirror",
]
