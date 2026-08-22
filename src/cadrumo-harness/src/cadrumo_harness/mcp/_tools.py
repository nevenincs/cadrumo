"""Build the MCP tool descriptors from the Layer 0 capability manifest.

Each operator-callable registry command becomes one SDK-independent
:class:`McpToolDescriptor`: a namespaced tool name, a description drawn from the
family's operator intent, a per-verb input schema derived from the command's own
click parameters (via :func:`~entrypoints.cli._verb_input_schema.build_verb_input_schemas`),
the command's registered result model inside the shared CLI envelope as the output
schema, and the mutability annotations. The server shell adapts these into the MCP
SDK's ``Tool`` / ``ToolAnnotations`` types. This module owns no protocol detail and
is unit-tested.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.application.operator_surface import (
    CommandSchemaRef,
    OperatorMutability,
    build_operator_surface_manifest,
)
from cadrumo.core.errors import ErrorEnvelope
from cadrumo.core.json_contract import ENVELOPE_SCHEMA_VERSION, SCHEMA_REGISTRY, Notice
from cadrumo.entrypoints.cli import VerbInputSchema, is_exposable_command

from ._action_capabilities import build_mcp_action_input_schemas
from ._annotations import McpAnnotations, annotations_for_command
from ._command_policy import CommandPolicyProjection, command_policy
from ._dispatch import tool_name_for_command
from ._result_thinning import thin_output_schema

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class McpToolDescriptor(BaseModel):
    """SDK-independent description of one exposed MCP tool.

    ``input_schema`` is the rendered per-verb JSON Schema a client reads to build
    a typed argument form; ``verb_schema`` is the structured source of that render
    plus the resolved CLI path, which the server consumes to reconstruct the argv
    from named arguments. The two are always in lock-step: ``input_schema`` is
    exactly ``verb_schema.json_schema()``.
    """

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    command_key: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    annotations: McpAnnotations
    execution_policy: CommandPolicyProjection
    verb_schema: VerbInputSchema


def _family_mutability() -> dict[str, OperatorMutability]:
    """Map each normalized command-family child to its mutability."""
    contract = build_operator_surface_manifest(
        envelope_schema_version=ENVELOPE_SCHEMA_VERSION,
        command_schemas=(),
    ).contract
    mapping: dict[str, OperatorMutability] = {}
    for family in contract.command_families:
        mapping[family.child.replace("-", "_")] = family.mutability
    return mapping


def _mutability_for_key(command_key: str, family_map: dict[str, OperatorMutability]) -> OperatorMutability:
    # A key whose family is absent from the manifest falls back to
    # LOCAL_STATE_MUTATING - the conservative default that asks for confirmation
    # more often, never less.
    tokens = command_key.split(".")
    family_token = tokens[1] if tokens[0] in {"config", "app"} and len(tokens) > 1 else tokens[0]
    return family_map.get(family_token, OperatorMutability.LOCAL_STATE_MUTATING)


def _family_intent(command_key: str, family_map_intent: dict[str, str]) -> str:
    tokens = command_key.split(".")
    family_token = tokens[1] if tokens[0] in {"config", "app"} and len(tokens) > 1 else tokens[0]
    return family_map_intent.get(family_token, "")


def _cli_form(verb_schema: VerbInputSchema) -> str:
    """Render the model-facing ``aeat ...`` invocation for a resolved verb.

    Built from ``verb_schema.cli_path`` - the command's REAL resolved root
    (``config`` or ``app``) - never re-derived from the dotted command key,
    which would silently hardcode the ``app`` root for every family including
    ``config.*`` verbs.
    """
    return "aeat " + " ".join(verb_schema.cli_path)


def _schema_definitions(value: object) -> dict[str, Any]:
    """Return one JSON Schema definitions mapping, or no definitions."""
    if not isinstance(value, Mapping):
        return {}
    definitions = cast(Mapping[object, Any], value)
    return {str(key): item for key, item in definitions.items()}


def _merge_schema_definitions(*definition_sets: dict[str, Any]) -> dict[str, Any]:
    """Merge generated schema definitions while refusing a name collision."""
    merged: dict[str, Any] = {}
    for definitions in definition_sets:
        for name, definition in definitions.items():
            prior = merged.get(name)
            if prior is not None and prior != definition:
                raise ValueError(f"conflicting generated JSON Schema definition: {name}")
            merged[name] = definition
    return merged


@cache
def build_tool_descriptors() -> tuple[McpToolDescriptor, ...]:
    """Build the exposed MCP tool descriptors from the live manifest + registry.

    Built once per process. The descriptor set is a pure function of the loaded
    command tree, which cannot change while a process runs: the manifest, the
    registry and the CLI argument vectors are all fixed at import. Profiled, one
    build costs 7.7s and renders ~285 output schemas, and the MCP test modules
    were paying it once per test -- 107.3s of a 144s module across 14 rebuilds
    of an identical answer. ``_hitl.py`` also calls it per query.

    Sharing one tuple is safe by construction rather than by convention:
    ``McpToolDescriptor`` is declared with the strict FROZEN config, so a
    caller cannot mutate what the next caller receives. The descriptions are
    deliberately English rather than localised, so no cached value can pin a
    locale either.

    Reuses the CLI's own payload-discovery so the registry is fully populated, then
    emits one descriptor per operator-callable command key, skipping group-callback
    help surfaces. The output schema is the shared CLI envelope specialised with
    the command's registered result model; the input schema is the CLI argument
    vector.

    Returns:
        Tuple of exposed :class:`McpToolDescriptor` entries.
    """
    from cadrumo.entrypoints.cli import command_schema_refs

    refs: tuple[CommandSchemaRef, ...] = command_schema_refs()
    family_map = _family_mutability()
    contract = build_operator_surface_manifest(
        envelope_schema_version=ENVELOPE_SCHEMA_VERSION,
        command_schemas=(),
    ).contract
    intent_map = {family.child.replace("-", "_"): family.operator_question for family in contract.command_families}

    exposable_refs = tuple(ref for ref in refs if is_exposable_command(ref.command))
    exposable_keys = tuple(ref.command for ref in exposable_refs)
    verb_schemas = build_mcp_action_input_schemas(exposable_refs)

    descriptors: list[McpToolDescriptor] = []
    for key in exposable_keys:
        mutability = _mutability_for_key(key, family_map)
        verb_schema = verb_schemas[key]
        cli_form = _cli_form(verb_schema)
        intent = _family_intent(key, intent_map)
        # The model-facing description stays English: the CLI form carries the
        # verb path and the shared family intent follows. The command's own
        # (Spanish) per-verb help is NOT put here - it feeds the search index
        # instead, so discovery gains the verb vocabulary without a Spanish
        # string on the model-facing surface.
        description = f"Run `{cli_form}`." + (f" {intent}." if intent else "")
        execution_policy = command_policy(key)
        annotations = annotations_for_command(
            command_key=key,
            mutability=mutability,
            title=cli_form,
            policy=execution_policy,
        )
        descriptors.append(
            McpToolDescriptor(
                name=tool_name_for_command(key),
                command_key=key,
                description=description,
                input_schema=verb_schema.json_schema(),
                output_schema=_output_schema_for(key),
                annotations=annotations,
                execution_policy=execution_policy,
                verb_schema=verb_schema,
            ),
        )
    return tuple(descriptors)


def _output_schema_for(command_key: str) -> dict[str, Any]:
    schema = SCHEMA_REGISTRY.get(command_key)
    if schema is None:
        return {"type": "object"}
    # A thinned verb moves its bulk arrays to resource_link URIs, so its result
    # schema drops those properties before being wrapped in the shared envelope.
    # The advertised output and emitted structuredContent therefore stay
    # identical while preserving the CLI's command/status/notices contract.
    result_schema = thin_output_schema(command_key, schema.model_json_schema())
    definitions = _schema_definitions(result_schema.pop("$defs", {}))
    error_schema = ErrorEnvelope.model_json_schema()
    error_definitions = _schema_definitions(error_schema.pop("$defs", {}))
    notice_schema = Notice.model_json_schema()
    notice_definitions = _schema_definitions(notice_schema.pop("$defs", {}))
    notices_schema = {"type": "array", "items": notice_schema}
    combined_definitions = _merge_schema_definitions(
        definitions,
        error_definitions,
        notice_definitions,
    )
    return _without_generated_titles(
        {
            "$defs": combined_definitions,
            # MCP's tools/list descriptor requires an object-shaped output schema at
            # the top level. The branches below retain the canonical success/error
            # envelope distinction within that required serializable shape.
            "type": "object",
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "schema_version": {"const": ENVELOPE_SCHEMA_VERSION, "type": "string"},
                        "command": {"const": command_key, "type": "string"},
                        "active_profile": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "status": {"enum": ["success", "warning"], "type": "string"},
                        "result": result_schema,
                        "notices": notices_schema,
                    },
                    "required": ["schema_version", "command", "active_profile", "status", "result", "notices"],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "schema_version": {"const": ENVELOPE_SCHEMA_VERSION, "type": "string"},
                        "command": {"anyOf": [{"type": "string", "minLength": 1}, {"type": "null"}]},
                        "active_profile": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "status": {"const": "error", "type": "string"},
                        "error": error_schema,
                        "notices": notices_schema,
                    },
                    "required": ["schema_version", "command", "active_profile", "status", "error", "notices"],
                    "additionalProperties": False,
                },
            ],
        },
    )


# ANY-RETURN-RATIONALE-JSON-SCHEMA: the recursive JSON-schema tree walked and
# returned here is genuinely arbitrary JSON at every depth, not an escape from
# a known type.
def _without_generated_titles(schema: dict[str, Any]) -> dict[str, Any]:
    """Drop pydantic's auto-generated ``title`` keys from an output schema.

    Every ``title`` pydantic emits here is a pure function of the key it sits
    under: a property title is the field name in title case, and a definition
    title is the class name a consumer resolving ``$ref`` already holds. None
    carries information a consumer cannot compute, and nothing reads them --
    the SDK client uses ``outputSchema`` only to compile a JSON Schema
    validator, and ``title`` is an annotation with no validation effect.

    Dropping them is a saving on ``tools/list``, which every session pays once.
    It is NOT a payload saving: titles never appear in ``structuredContent``, so
    this does not reduce what the per-call result costs. Two exceptions are
    accepted with it -- the envelope's ``result``/``error`` titles name their
    model rather than restating the key -- because the model is derivable from
    the command and no consumer reads either.
    """
    return {key: _without_generated_title_value(cast(object, value)) for key, value in schema.items() if key != "title"}


def _without_generated_title_value(value: object) -> object:
    """Strip generated titles recursively from one nested schema value."""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return _without_generated_titles({str(key): item for key, item in mapping.items()})
    if isinstance(value, list):
        return [_without_generated_title_value(item) for item in cast(list[object], value)]
    return value
