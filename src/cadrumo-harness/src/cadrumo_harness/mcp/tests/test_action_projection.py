"""Real-schema proofs for resolver-backed MCP action capabilities."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from cadrumo.application.operator_actions import (
    OPERATOR_ACTION_CATALOGUE,
    ActionCatalogueEntry,
    build_action_catalogue,
)
from cadrumo.application.operator_surface import OperatorSurfaceContractError
from cadrumo.core.json_contract import Notice
from cadrumo.entrypoints.cli import (
    build_verb_input_schemas,
    command_schema_refs,
    is_exposable_command,
)

from .._action_capabilities import (
    build_mcp_action_input_schemas,
    resolve_mcp_action_capabilities,
)
from .._server import build_sdk_tools
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ACTION_CAPABILITIES_KEY = "x-cadrumo-action-capabilities"


def _exposable_refs():
    return tuple(schema_ref for schema_ref in command_schema_refs() if is_exposable_command(schema_ref.command))


def _refs_for(*command_keys: str):
    selected = set(command_keys)
    return tuple(schema_ref for schema_ref in command_schema_refs() if schema_ref.command in selected)


def _catalogue_entry(action_id: str) -> ActionCatalogueEntry:
    return next(entry for entry in OPERATOR_ACTION_CATALOGUE.entries if entry.action_id == action_id)


def _all_mapping_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        keys: set[str] = set()
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise TypeError("schema mapping keys must be strings")
            keys.add(raw_key)
            keys.update(_all_mapping_keys(item))
        return keys
    if isinstance(value, list | tuple):
        return {key for item in value for key in _all_mapping_keys(item)}
    return set()


def test_every_canonical_action_projects_once_onto_its_live_mcp_target_schema() -> None:
    schemas = build_mcp_action_input_schemas(_exposable_refs())
    projected = tuple(capability for schema in schemas.values() for capability in schema.action_capabilities)
    projected_by_id = {capability.action_id: capability for capability in projected}

    assert len(projected_by_id) == len(projected)
    assert set(projected_by_id) == {entry.action_id for entry in OPERATOR_ACTION_CATALOGUE.entries}

    for declaration in OPERATOR_ACTION_CATALOGUE.entries:
        capability = projected_by_id[declaration.action_id]
        target_schema = schemas[declaration.target_command_key]
        assert capability.target_command_key == declaration.target_command_key
        assert capability.cli_path == target_schema.resolved_leaf.cli_path
        assert capability.required_input_names == tuple(parameter.name for parameter in target_schema.required_inputs)
        assert capability.argument_specifications == declaration.argument_specifications
        assert target_schema.json_schema()[_ACTION_CAPABILITIES_KEY] == [
            item.model_dump(mode="json") for item in target_schema.action_capabilities
        ]

    assert _ACTION_CAPABILITIES_KEY not in schemas["config.check"].json_schema()


def test_action_capabilities_reach_the_real_sdk_tools_list_projection() -> None:
    descriptors = build_tool_descriptors()
    descriptors_by_name = {descriptor.name: descriptor for descriptor in descriptors}
    sdk_tools_by_name = {tool.name: tool for tool in build_sdk_tools(descriptors)}

    for declaration in OPERATOR_ACTION_CATALOGUE.entries:
        descriptor = next(item for item in descriptors if item.command_key == declaration.target_command_key)
        sdk_tool = sdk_tools_by_name[descriptor.name]
        assert sdk_tool.input_schema[_ACTION_CAPABILITIES_KEY] == descriptor.input_schema[_ACTION_CAPABILITIES_KEY]
        assert descriptors_by_name[sdk_tool.name].command_key == declaration.target_command_key


def test_mcp_action_projection_refuses_a_duplicate_result_schema_identity() -> None:
    refs = _refs_for("config.profile.create")
    schemas = build_verb_input_schemas(("config.profile.create",))
    catalogue = build_action_catalogue((_catalogue_entry("operator.profile.create"),))

    with pytest.raises(ValueError, match="duplicate MCP result-schema identity"):
        resolve_mcp_action_capabilities(
            catalogue=catalogue,
            command_schemas=(*refs, *refs),
            verb_schemas=schemas,
        )


def test_mcp_action_projection_refuses_a_schema_stored_under_the_wrong_identity() -> None:
    refs = _refs_for("config.profile.create")
    overview_schema = build_verb_input_schemas(("overview.status",))["overview.status"]
    catalogue = build_action_catalogue((_catalogue_entry("operator.profile.create"),))

    with pytest.raises(ValueError, match="MCP input-schema identity mismatch"):
        resolve_mcp_action_capabilities(
            catalogue=catalogue,
            command_schemas=refs,
            verb_schemas={"config.profile.create": overview_schema},
        )


def test_distinct_action_ids_sharing_one_target_remain_distinct_and_ordered() -> None:
    refs = _refs_for("config.profile.edit")
    schemas = build_verb_input_schemas(("config.profile.edit",))
    existing = _catalogue_entry("operator.profile.edit")
    second = ActionCatalogueEntry(
        action_id="operator.profile.edit_alternative",
        target_command_key=existing.target_command_key,
        argument_specifications=existing.argument_specifications,
    )

    projected = resolve_mcp_action_capabilities(
        catalogue=build_action_catalogue((second, existing)),
        command_schemas=refs,
        verb_schemas=schemas,
    )

    assert tuple(capability.action_id for capability in projected["config.profile.edit"]) == (
        "operator.profile.edit",
        "operator.profile.edit_alternative",
    )


def test_mcp_action_projection_refuses_an_orphan_target_and_insufficient_sources() -> None:
    # ``config.profile.edit`` declares every wizard field, including
    # ``profile_name``, as a schema-optional CLI argument -- required-ness is
    # enforced in the command body (``_require_profile_name``), not the
    # advertised schema, the same headless-dispatch shape ``modelo.work.*``
    # uses. Its ``required_input_names`` is therefore empty, so it cannot
    # exercise the "insufficient sources" refusal: zero declared
    # specifications trivially cover zero required names. The orphan case
    # stays on it (identity mismatch does not depend on required-ness);
    # the insufficient case targets ``config.auth.certificate.remove``,
    # whose ``name`` argument is genuinely schema-required.
    refs = _refs_for("config.profile.edit", "config.auth.certificate.remove")
    schemas = build_verb_input_schemas(("config.profile.edit", "config.auth.certificate.remove"))
    orphan_catalogue = build_action_catalogue(
        (
            ActionCatalogueEntry(
                action_id="operator.orphan.recovery",
                target_command_key="config.profile.not_real",
            ),
        )
    )
    insufficient_catalogue = build_action_catalogue(
        (
            ActionCatalogueEntry(
                action_id="operator.certificate.remove_without_source",
                target_command_key="config.auth.certificate.remove",
            ),
        )
    )

    with pytest.raises(OperatorSurfaceContractError, match="orphan action target command identity"):
        resolve_mcp_action_capabilities(
            catalogue=orphan_catalogue,
            command_schemas=refs,
            verb_schemas=schemas,
        )
    with pytest.raises(ValueError, match="insufficient action argument specifications"):
        resolve_mcp_action_capabilities(
            catalogue=insufficient_catalogue,
            command_schemas=refs,
            verb_schemas=schemas,
        )


def test_mcp_action_projection_refuses_an_ambiguous_live_click_path() -> None:
    command_keys = ("config.profile.create", "overview.status")
    refs = _refs_for(*command_keys)
    live_schemas = build_verb_input_schemas(command_keys)
    create_schema = live_schemas["config.profile.create"]
    overview_schema = live_schemas["overview.status"]
    ambiguous_schemas = {
        **live_schemas,
        "overview.status": overview_schema.model_copy(update={"cli_path": create_schema.cli_path}),
    }
    catalogue = build_action_catalogue((_catalogue_entry("operator.profile.create"),))

    with pytest.raises(OperatorSurfaceContractError, match="ambiguous reconciled CLI path"):
        resolve_mcp_action_capabilities(
            catalogue=catalogue,
            command_schemas=refs,
            verb_schemas=ambiguous_schemas,
        )


def test_mcp_output_schema_uses_the_canonical_notice_action_wire_without_suggestion() -> None:
    descriptor = next(item for item in build_tool_descriptors() if item.command_key == "config.check")
    success_branch, error_branch = descriptor.output_schema["oneOf"]
    success_notices = success_branch["properties"]["notices"]
    error_notices = error_branch["properties"]["notices"]

    for notices in (success_notices, error_notices):
        notice_properties = notices["items"]["properties"]
        assert set(notice_properties) == set(Notice.model_fields)
        assert set(notices["items"]["required"]) == {"severity", "code", "message"}
        assert "action" in notice_properties

    assert "suggestion" not in _all_mapping_keys(descriptor.output_schema)
    assert {
        "ResolvedActionReference",
        "ResolvedPreconditionAction",
    } <= set(descriptor.output_schema["$defs"])
