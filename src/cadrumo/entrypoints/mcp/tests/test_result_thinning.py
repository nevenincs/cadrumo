"""Real-behavior tests for result thinning.

The thinning logic (:mod:`.._result_thinning`) is exercised directly - no mocks -
and the declared thinning / resolution tables are bound to the LIVE tool surface
so a verb rename, a moved result field, or a dropped resolver verb reds a gate
rather than silently shipping a link that resolves nothing.
"""

from __future__ import annotations

import json

import pytest

from ....core.json_contract import SCHEMA_REGISTRY
from .._resources import BUCKET_SCOPED_RESOURCE_KINDS, parse_resource_uri
from .._result_thinning import (
    BULK_RESOLUTION,
    THINNED_VERBS,
    ResourceLinkRef,
    thin_envelope,
    thin_output_schema,
    thinned_arrays_for,
)
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _populate_schema_registry() -> None:
    # SCHEMA_REGISTRY is populated as a side effect of the CLI payload discovery
    # that build_tool_descriptors() drives; trigger it so the registered result
    # models are available to the schema-level assertions below.
    build_tool_descriptors()


def _calculate_envelope(observations: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": "1",
        "command": "modelo.work.calculate",
        "status": "success",
        "result": {
            "operation": "modelo.work.calculate",
            "calculation_revision_id": "rev-abc123",
            "casilla_values": {"0001": "100.00"},
            "observations": observations,
        },
        "notices": [],
    }


def test_thin_envelope_moves_the_bulk_array_to_a_link_and_leaves_a_summary_marker() -> None:
    env = _calculate_envelope([{"casilla": "0001"}, {"casilla": "0002"}])
    thinned, links = thin_envelope("modelo.work.calculate", env)
    result = thinned["result"]
    assert isinstance(result, dict)
    assert "observations" not in result  # bulk array moved out
    assert result["observations_resource"] == "cadrumo://observations/rev-abc123"
    assert result["observations_count"] == 2
    assert result["calculation_revision_id"] == "rev-abc123"  # summary preserved
    assert [(ref.uri, ref.count) for ref in links] == [("cadrumo://observations/rev-abc123", 2)]


def test_thin_envelope_does_not_mutate_the_source_envelope() -> None:
    env = _calculate_envelope([{"casilla": "0001"}])
    thin_envelope("modelo.work.calculate", env)
    assert env["result"]["observations"] == [{"casilla": "0001"}]  # type: ignore[index]


def test_thin_envelope_is_a_noop_for_an_unthinned_verb() -> None:
    env = {"result": {"observations": [{"a": 1}], "calculation_revision_id": "r"}}
    thinned, links = thin_envelope("modelo.work.list", env)
    assert links == ()
    assert thinned["result"]["observations"] == [{"a": 1}]  # type: ignore[index]


def test_thin_envelope_leaves_an_empty_array_inline() -> None:
    # Nothing to thin: an empty observation list stays inline and emits no link.
    env = _calculate_envelope([])
    thinned, links = thin_envelope("modelo.work.calculate", env)
    assert links == ()
    assert thinned["result"]["observations"] == []  # type: ignore[index]


def test_thin_envelope_skips_when_the_id_is_missing() -> None:
    env = _calculate_envelope([{"a": 1}])
    del env["result"]["calculation_revision_id"]  # type: ignore[union-attr]
    thinned, links = thin_envelope("modelo.work.calculate", env)
    assert links == ()  # cannot address the resource, so leave the array inline
    assert "observations" in thinned["result"]  # type: ignore[operator]


def test_thin_envelope_ignores_an_error_envelope_without_a_result_mapping() -> None:
    env = {"status": "error", "raw": "boom"}
    thinned, links = thin_envelope("modelo.work.calculate", env)
    assert links == ()
    assert thinned == env


def test_thin_output_schema_drops_the_property_and_declares_summary_markers() -> None:
    schema = SCHEMA_REGISTRY["modelo.work.calculate"].model_json_schema()
    thinned = thin_output_schema("modelo.work.calculate", schema)
    props = thinned["properties"]
    assert "observations" not in props
    assert props["observations_resource"]["type"] == "string"
    assert props["observations_count"]["type"] == "integer"


def test_thin_output_schema_strictly_shrinks_the_schema() -> None:
    # Anti-tautology: thinning must REDUCE the schema (orphaned $defs pruned),
    # else the size-budget gate would be measuring an unthinned shape.
    for command_key in THINNED_VERBS:
        base = SCHEMA_REGISTRY[command_key].model_json_schema()
        thinned = thin_output_schema(command_key, base)
        assert len(json.dumps(thinned)) < len(json.dumps(base)), command_key


def test_thin_output_schema_prunes_the_orphaned_observation_def() -> None:
    schema = SCHEMA_REGISTRY["modelo.work.observations"].model_json_schema()
    thinned = thin_output_schema("modelo.work.observations", schema)
    assert "ObservationPayload" not in thinned.get("$defs", {})


def test_thin_output_schema_drops_the_property_from_required() -> None:
    unthinned_schema = {
        "type": "object",
        "properties": {"observations": {"type": "array"}, "calculation_revision_id": {"type": "string"}},
        "required": ["observations", "calculation_revision_id"],
    }
    thinned = thin_output_schema("modelo.work.calculate", unthinned_schema)
    assert "observations" not in thinned["required"]
    assert "calculation_revision_id" in thinned["required"]


# ── Table ↔ live-surface binding (drift gates) ──────────────────────────────


def _exposed() -> dict[str, object]:
    return {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}


def test_every_thinned_verb_is_a_real_exposed_command() -> None:
    exposed = _exposed()
    missing = [key for key in THINNED_VERBS if key not in exposed]
    assert missing == [], f"thinned verbs not on the exposed surface: {missing}"


def test_every_thinned_field_exists_on_the_unthinned_result_schema() -> None:
    # The result_key and the uri_id_key must be real properties of the verb's
    # registered result model, else thinning silently pops nothing / emits no id.
    for command_key, specs in THINNED_VERBS.items():
        model = SCHEMA_REGISTRY.get(command_key)
        assert model is not None, command_key
        props = set(model.model_json_schema().get("properties", {}))
        for spec in specs:
            assert spec.result_key in props, f"{command_key}:{spec.result_key}"
            assert spec.uri_id_key in props, f"{command_key}:{spec.uri_id_key}"


def test_every_thinned_resource_kind_has_a_resolver() -> None:
    for specs in THINNED_VERBS.values():
        for spec in specs:
            assert spec.resource_kind in BULK_RESOLUTION
            assert spec.resource_kind in BUCKET_SCOPED_RESOURCE_KINDS


def test_every_resolver_verb_and_field_are_real() -> None:
    exposed = _exposed()
    for kind, resolution in BULK_RESOLUTION.items():
        descriptor = exposed.get(resolution.resolver_command_key)
        assert descriptor is not None, f"resolver verb missing for {kind}: {resolution.resolver_command_key}"
        model = SCHEMA_REGISTRY.get(resolution.resolver_command_key)
        assert model is not None
        props = set(model.model_json_schema().get("properties", {}))
        assert resolution.result_field in props, f"{resolution.resolver_command_key}:{resolution.result_field}"


def test_emitted_link_uri_resolves_to_a_declared_bulk_kind() -> None:
    # The URI the server emits must parse back to a bucket-scoped kind that has a
    # resolver - i.e. every link is resolvable by construction.
    env = _calculate_envelope([{"a": 1}])
    _thinned, links = thin_envelope("modelo.work.calculate", env)
    assert links
    for ref in links:
        assert isinstance(ref, ResourceLinkRef)
        kind, name = parse_resource_uri(ref.uri)
        assert kind in BULK_RESOLUTION
        assert name == "rev-abc123"


def test_thinned_arrays_for_returns_empty_for_unknown_verb() -> None:
    assert thinned_arrays_for("nonexistent.verb") == ()
