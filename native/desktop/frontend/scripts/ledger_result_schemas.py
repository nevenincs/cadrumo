"""Record the result schema every ``ledger.*`` operation serves into the browser's fixtures.

The scenario host answers the window in the shape the operations serve. This writes the
JSON Schema of each ledger operation's result model, so a spec can hold every answer the
host gives to what the operation really serves, and a field added to a result fails it
until the host answers with the field. Every field of a result is served, because the
operation host emits the whole model, so each is required here:

    uv run --no-sync python native/desktop/frontend/scripts/ledger_result_schemas.py [--check | --output DIR]
"""

from __future__ import annotations

from typing import Any

from dev.fixture_projections.location import family_directory
from dev.fixture_projections.producer_output import emit, producer_arguments
from dev.prettier_json import dump_json

from cadrumo.entrypoints.operation_composition import build_production_operation_registry

_PREFIX = "ledger."


def _every_field_served(schema: Any) -> None:
    """Mark each property of each object schema required, as the host serves the whole model."""
    if isinstance(schema, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict):
            schema["required"] = list(properties)
        for value in schema.values():
            _every_field_served(value)
    elif isinstance(schema, list):
        for value in schema:
            _every_field_served(value)


def result_schemas() -> dict[str, Any]:
    """The serialized-result JSON Schema of each ledger operation that returns one, by definition id."""
    registry = build_production_operation_registry()
    schemas: dict[str, Any] = {}
    for registration in registry.public_registrations:
        contract = registration.contract
        if not contract.definition_id.startswith(_PREFIX) or contract.result_schema is None:
            continue
        # The public result, which a result projector may reshape from the executor's own.
        binding = registry.lookup_public_schema_binding(contract.result_schema)
        schema = binding.model_type.model_json_schema(mode="serialization")
        _every_field_served(schema)
        schemas[contract.definition_id] = schema
    return dict(sorted(schemas.items()))


def main() -> None:
    """Write, check or redirect the result schemas."""
    arguments = producer_arguments(__doc__)
    emit(
        {family_directory("ledger-result-schemas") / "ledgerResultSchemas.json": dump_json(result_schemas())},
        arguments,
        remedy="just fixtures-seed ledger-result-schemas",
    )


if __name__ == "__main__":
    main()
