"""Test-owned schema-family enrollment diagnostics."""

from pydantic import BaseModel

from cadrumo.domain.calculations.registry.schema_base import (
    chain_family_fields,
    collection_shaped_fields,
    schema_family_fields,
)

__all__ = ["schema_family_enrollment_failures"]


def schema_family_enrollment_failures(model: type[BaseModel]) -> tuple[str, ...]:
    """Return diagnostics for collection fields whose family enrolment disagrees with their shape.

    A collection of schema models must carry exactly one of the two markers: a
    coverage family (``SCHEMA_FAMILY``) or a chain-statement family
    (``CHAIN_FAMILY``). Both, neither, or a marker on a non-collection is a
    defect.
    """
    families = schema_family_fields(model)
    chains = chain_family_fields(model)
    declared = families | chains
    shaped = collection_shaped_fields(model)
    failures = [
        f"field {name!r} carries both SCHEMA_FAMILY and CHAIN_FAMILY; a field is a coverage claim or a "
        "chain statement, never both"
        for name in sorted(families & chains)
    ]
    failures.extend(
        f"field {name!r} is a collection of schema models but is marked neither SCHEMA_FAMILY nor "
        "CHAIN_FAMILY, so its emptiness would never be reported or explained"
        for name in sorted(shaped - declared)
    )
    failures.extend(
        f"field {name!r} is marked as a family but is not a collection of schema models, so it has no "
        "emptiness for a disposition to describe"
        for name in sorted(declared - shaped)
    )
    return tuple(failures)
