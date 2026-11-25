"""Shape + legal-grounding tests for maritime-worker profile fields."""

from __future__ import annotations

import pytest

from ...calculations.registry.tests.published_authority import published_legal_reference
from ..schema import ProfileSchemaDefinition
from .schema_loader_fixtures import function_scoped_schema

__all__ = ["function_scoped_schema"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _published_legal_ids(candidates: set[str]) -> set[str]:
    """Return the candidates the published authority declares; an absent id refuses."""
    return {reference_id for reference_id in candidates if published_legal_reference(reference_id).id == reference_id}


def test_maritime_worker_fields_use_canonical_legal_refs(schema: ProfileSchemaDefinition) -> None:
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
        assert refs <= _published_legal_ids(refs)


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


@pytest.mark.parametrize(
    "field_path",
    [
        "maritime_worker.worker_class",
        "maritime_worker.retmar_registered",
        "maritime_worker.tuna_fleet",
        "maritime_worker.pending_eu_clearance",
    ],
)
def test_every_maritime_predicate_is_addressable_by_its_own_selector(
    field_path: str,
    schema: ProfileSchemaDefinition,
) -> None:
    """A field that gates something must declare the selector that resolves its path back.

    ``path_for_model_selector`` is the only inverse of a selector token, so a
    field declaring ``schedule_predicates`` without the matching
    ``model_selectors`` cannot be resolved from the token a warning or a
    cleared-fact notice holds, and the operator is told nothing about the
    answer that is missing. Both maritime fields below gate the Modelo 100
    route: ``worker_class`` selects the art. 7.p), REBECA (Ley 19/1994 art. 75)
    or DA 41 pathway, and ``retmar_registered`` carries the LIRPF art. 96
    obligation to file whatever the income.
    """
    field = schema.field(field_path)

    assert field.schedule_predicates == (field_path,)
    assert field.model_selectors == (field_path,)
    assert schema.path_for_model_selector(field_path) == field_path
