"""Build the MCP tool descriptors from the Layer 0 capability manifest.

Each operator-callable registry command becomes one SDK-independent
:class:`McpToolDescriptor`: a namespaced tool name, a description drawn from the
family's operator intent, a per-verb input schema derived from the command's own
click parameters (via :func:`~entrypoints.mcp._input_schema.build_verb_input_schemas`),
the command's registered result model inside the shared CLI envelope as the output
schema, and the mutability annotations. The server shell adapts these into the MCP
SDK's ``Tool`` / ``ToolAnnotations`` types. This module owns no protocol detail and
is unit-tested.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...application.operator_surface import (
    CommandSchemaRef,
    OperatorMutability,
    build_operator_surface_manifest,
)
from ...core.errors import ErrorEnvelope
from ...core.json_contract import ENVELOPE_SCHEMA_VERSION, SCHEMA_REGISTRY
from ._annotations import McpAnnotations, annotations_for_command
from ._dispatch import is_exposable_command, tool_name_for_command
from ._input_schema import VerbInputSchema, build_verb_input_schemas
from ._result_thinning import thin_output_schema

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

# Read-only command keys that are not a mounted command family (operator meta
# surfaces). Everything else falls back to LOCAL_STATE_MUTATING - the conservative
# default that asks for confirmation more often, never less.
_READ_ONLY_OVERRIDES: frozenset[str] = frozenset({"contract"})


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
    if command_key in _READ_ONLY_OVERRIDES:
        return OperatorMutability.READ_ONLY
    tokens = command_key.split(".")
    family_token = tokens[1] if tokens[0] in {"config", "app"} and len(tokens) > 1 else tokens[0]
    return family_map.get(family_token, OperatorMutability.LOCAL_STATE_MUTATING)


def _family_intent(command_key: str, family_map_intent: dict[str, str]) -> str:
    tokens = command_key.split(".")
    family_token = tokens[1] if tokens[0] in {"config", "app"} and len(tokens) > 1 else tokens[0]
    return family_map_intent.get(family_token, "")


def build_tool_descriptors() -> tuple[McpToolDescriptor, ...]:
    """Build the exposed MCP tool descriptors from the live manifest + registry.

    Reuses the CLI's own payload-discovery so the registry is fully populated, then
    emits one descriptor per operator-callable command key, skipping group-callback
    help surfaces. The output schema is the shared CLI envelope specialised with
    the command's registered result model; the input schema is the CLI argument
    vector.

    Returns:
        Tuple of exposed :class:`McpToolDescriptor` entries.
    """
    from ..cli import command_schema_refs

    refs: tuple[CommandSchemaRef, ...] = command_schema_refs()
    family_map = _family_mutability()
    contract = build_operator_surface_manifest(
        envelope_schema_version=ENVELOPE_SCHEMA_VERSION,
        command_schemas=(),
    ).contract
    intent_map = {family.child.replace("-", "_"): family.operator_question for family in contract.command_families}

    exposable_keys = tuple(ref.command for ref in refs if is_exposable_command(ref.command))
    verb_schemas = build_verb_input_schemas(exposable_keys)

    descriptors: list[McpToolDescriptor] = []
    for key in exposable_keys:
        mutability = _mutability_for_key(key, family_map)
        cli_form = "aeat app " + key.replace(".", " ")
        intent = _family_intent(key, intent_map)
        verb_schema = verb_schemas[key]
        # The model-facing description stays English: the CLI form carries the
        # verb path and the shared family intent follows. The command's own
        # (Spanish) per-verb help is NOT put here - it feeds the search index
        # instead, so discovery gains the verb vocabulary without a Spanish
        # string on the model-facing surface.
        description = f"Run `{cli_form}`." + (f" {intent}." if intent else "")
        annotations = annotations_for_command(command_key=key, mutability=mutability, title=cli_form)
        descriptors.append(
            McpToolDescriptor(
                name=tool_name_for_command(key),
                command_key=key,
                description=description,
                input_schema=verb_schema.json_schema(),
                output_schema=_output_schema_for(key),
                annotations=annotations,
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
    definitions = result_schema.pop("$defs", {})
    error_schema = ErrorEnvelope.model_json_schema()
    error_definitions = error_schema.pop("$defs", {})
    notices_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "severity": {
                    "enum": ["info", "warning"],
                    "type": "string",
                },
                "code": {"minLength": 1, "type": "string"},
                "message": {"minLength": 1, "type": "string"},
                "suggestion": {
                    "anyOf": [{"type": "string"}, {"type": "null"}],
                },
                "context": {
                    "anyOf": [
                        {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                        {"type": "null"},
                    ],
                },
            },
            "required": ["severity", "code", "message", "suggestion", "context"],
            "additionalProperties": False,
        },
    }
    return {
        "$defs": {**definitions, **error_definitions},
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
    }
