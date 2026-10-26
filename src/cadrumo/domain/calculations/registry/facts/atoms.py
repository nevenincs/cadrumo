"""Typed governed-fact atoms and their lossless authority JSON codec."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Final

from pydantic import BeforeValidator, ValidationInfo

from .....core.errors.hierarchy import pydantic_validation_boundary
from .....core.type_guards import is_object_mapping
from ..errors import RegistryValidationError

FactAtom = str | int | Decimal | bool | date

#: Validation-context key a reader sets when every non-string fact atom arrives
#: in its tagged JSON form. JSON carries a decimal or a date only as a string,
#: which the ``FactAtom`` union would read back as text; the tag keeps the type.
TAGGED_FACT_ATOM_CONTEXT: Final = "tagged_fact_atoms"
_DECIMAL_TAG: Final = "$decimal"
_DATE_TAG: Final = "$date"
_INT_TAG: Final = "$int"
_BOOL_TAG: Final = "$bool"


def tagged_fact_atom_json(value: FactAtom | None) -> object:
    """Return the lossless JSON form of one fact atom.

    A string stays a bare JSON string. Every other atom becomes a single-key
    object naming its type: ``{"$decimal": "0.40"}``, ``{"$date": "2025-01-01"}``,
    ``{"$int": 5}`` and ``{"$bool": true}``. ``None`` stays ``null``.
    """
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return {_BOOL_TAG: value}
    if isinstance(value, int):
        return {_INT_TAG: value}
    if isinstance(value, Decimal):
        return {_DECIMAL_TAG: str(value)}
    return {_DATE_TAG: value.isoformat()}


@pydantic_validation_boundary
def _hydrate_tagged_fact_atom(value: object, info: ValidationInfo) -> object:
    """Rebuild a tagged atom only when the reader declares the tagged JSON form."""
    if not (is_object_mapping(info.context) and info.context.get(TAGGED_FACT_ATOM_CONTEXT)):
        return value
    return _hydrate_declared_fact_atom(value)


def _hydrate_declared_fact_atom(value: object) -> object:
    if value is None or isinstance(value, str):
        return value
    if not is_object_mapping(value) or len(value) != 1:
        raise RegistryValidationError("a non-string fact atom must be a single tagged value")
    ((tag, payload),) = value.items()
    return _coerce_fact_atom_tag(tag, payload)


def _coerce_fact_atom_tag(tag: object, payload: object) -> object:
    if tag == _DECIMAL_TAG and isinstance(payload, str):
        return _decimal_atom(payload)
    if tag == _DATE_TAG and isinstance(payload, str):
        return _date_atom(payload)
    if tag == _INT_TAG and isinstance(payload, int) and not isinstance(payload, bool):
        return payload
    if tag == _BOOL_TAG and isinstance(payload, bool):
        return payload
    raise RegistryValidationError(f"fact atom tag {tag!r} is unknown or carries a payload of the wrong type")


def _decimal_atom(payload: str) -> Decimal:
    try:
        decimal = Decimal(payload)
    except InvalidOperation as exc:
        raise RegistryValidationError(f"fact atom {_DECIMAL_TAG} is not a decimal: {payload!r}") from exc
    if not decimal.is_finite() or str(decimal) != payload:
        raise RegistryValidationError(f"fact atom {_DECIMAL_TAG} is not a canonical finite decimal: {payload!r}")
    return decimal


def _date_atom(payload: str) -> date:
    try:
        parsed = date.fromisoformat(payload)
    except ValueError as exc:
        raise RegistryValidationError(f"fact atom {_DATE_TAG} is not an ISO date: {payload!r}") from exc
    if parsed.isoformat() != payload:
        raise RegistryValidationError(f"fact atom {_DATE_TAG} is not a canonical ISO date: {payload!r}")
    return parsed


FactAtomField = Annotated[FactAtom, BeforeValidator(_hydrate_tagged_fact_atom)]
"""A fact atom that also accepts its tagged JSON form when a reader declares it."""
OptionalFactAtomField = Annotated[FactAtom | None, BeforeValidator(_hydrate_tagged_fact_atom)]
"""An optional fact atom that also accepts its tagged JSON form when a reader declares it."""
