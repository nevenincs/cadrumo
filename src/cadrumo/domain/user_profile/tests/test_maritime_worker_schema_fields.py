"""Shape + legal-grounding tests for maritime-worker profile fields."""

from __future__ import annotations

import pytest

from ....core.resources import resources
from ..schema import ProfileSchemaDefinition
from ._schema_loader_fixtures import function_scoped_schema  # noqa: F401

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_maritime_worker_fields_use_canonical_legal_refs(schema: ProfileSchemaDefinition) -> None:
    catalogues = resources().modelos.authority.catalogues
    legal_ids = set(catalogues.legal)
    expected = {
        "maritime_worker.worker_class": {
            "ley-35-2006:art-7",
            "ley-19-1994:art-75",
            "ley-35-2006:da-41",
            "ley-35-2006:art-96",
        },
        "maritime_worker.vessel_flag": {"ley-35-2006:art-7"},
        "maritime_worker.waters_type": {"ley-35-2006:art-7"},
        "maritime_worker.vessel_registry": {"ley-19-1994:art-75"},
        "maritime_worker.retmar_registered": {"ley-35-2006:art-96"},
        "maritime_worker.tuna_fleet": {"ley-35-2006:da-41"},
        "maritime_worker.pending_eu_clearance": {"ley-35-2006:da-41"},
    }

    for field_path, expected_refs in expected.items():
        refs = set(schema.field(field_path).legal_refs)
        assert refs == expected_refs
        assert refs <= legal_ids


def test_maritime_worker_selectors_match_runtime_facts(schema: ProfileSchemaDefinition) -> None:
    worker_class = schema.field("maritime_worker.worker_class")
    assert worker_class.type.value == "enum"
    assert worker_class.enum_values == ("trabajador_del_mar",)
    assert worker_class.schedule_predicates == ("maritime_worker.worker_class",)

    vessel_registry = schema.field("maritime_worker.vessel_registry")
    assert vessel_registry.type.value == "enum"
    assert set(vessel_registry.enum_values) == {
        "REBECA",
        "rebeca_eu_eea",
        "scheduled_canary_route",
        "other",
    }

    for field_path in (
        "maritime_worker.tuna_fleet",
        "maritime_worker.pending_eu_clearance",
    ):
        field = schema.field(field_path)
        assert field.type.value == "boolean"
        assert field.model_selectors == (field_path,)
        assert field.schedule_predicates == (field_path,)
