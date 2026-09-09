"""Test-owned schema-family enrollment diagnostics."""

from typing import get_args, get_origin

from pydantic import BaseModel

from ..schema_base import schema_family_fields


def _collection_shaped_fields(model: type[BaseModel]) -> frozenset[str]:
    families: set[str] = set()
    for name, field in model.model_fields.items():
        if get_origin(field.annotation) is not tuple:
            continue
        args = get_args(field.annotation)
        element = args[0] if args else None
        if isinstance(element, type) and issubclass(element, BaseModel):
            families.add(name)
    return frozenset(families)


def schema_family_enrollment_failures(model: type[BaseModel]) -> tuple[str, ...]:
    declared = schema_family_fields(model)
    shaped = _collection_shaped_fields(model)
    failures = [
        f"field {name!r} is a collection of schema models but is not marked SCHEMA_FAMILY, so its emptiness "
        "would never be reported as a coverage disposition"
        for name in sorted(shaped - declared)
    ]
    failures.extend(
        f"field {name!r} is marked SCHEMA_FAMILY but is not a collection of schema models, so it has no "
        "emptiness for a disposition to describe"
        for name in sorted(declared - shaped)
    )
    return tuple(failures)
