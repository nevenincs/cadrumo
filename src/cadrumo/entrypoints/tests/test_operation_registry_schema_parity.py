"""Real production definitions keep exact schemas and public contract bytes."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema

from ...application.operations import registry_schema_validation
from ...core.config import Settings
from ...core.hashing import canonical_json_bytes
from ..operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_production_registry_matches_default_schema_generator(monkeypatch: pytest.MonkeyPatch) -> None:
    generate = registry_schema_validation._generate_closed_model_schema
    schemas: dict[type[BaseModel], bytes] = {}
    checked: set[type[BaseModel]] = set()

    def record_schema(model_type: type[BaseModel]) -> dict[str, object]:
        schema = generate(model_type)
        schemas[model_type] = canonical_json_bytes(schema)
        return schema

    settings = Settings(_env_file=None, cadrumo_profile_kdf_measure_calibration=False)
    monkeypatch.setattr(registry_schema_validation, "_generate_closed_model_schema", record_schema)
    optimized = build_production_operation_registry(settings=settings)

    def compare_default_schema(model_type: type[BaseModel]) -> dict[str, object]:
        schema = generate(model_type)
        assert canonical_json_bytes(schema) == schemas[model_type], model_type.__name__
        checked.add(model_type)
        return schema

    monkeypatch.setattr(registry_schema_validation, "_UnambiguousDefinitionsSchemaGenerator", GenerateJsonSchema)
    monkeypatch.setattr(registry_schema_validation, "_generate_closed_model_schema", compare_default_schema)
    default = build_production_operation_registry(settings=settings)
    assert schemas
    assert checked == schemas.keys()
    assert optimized.public_contract_set == default.public_contract_set
    optimized_contracts = optimized.public_contract_set.model_dump(mode="json")
    default_contracts = default.public_contract_set.model_dump(mode="json")
    assert canonical_json_bytes(optimized_contracts) == canonical_json_bytes(default_contracts)
