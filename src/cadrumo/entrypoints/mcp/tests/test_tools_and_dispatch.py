"""Tests for the MCP tool descriptors and the name/argv dispatch mapping."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pytest
import typer
from typer._click.core import Command as ClickCommand
from typer.main import get_command as _typer_get_command

from .._annotations import annotation_coverage_gaps
from .._dispatch import command_key_for_tool, is_exposable_command, tool_name_for_command
from .._input_schema import (
    JsonType,
    SchemaResolutionError,
    VerbInputSchema,
    VerbParameter,
    VerbParamKind,
    _json_safe_default,
    _parameter_from_click,
    assert_schema_coverage,
    build_verb_input_schemas,
    cli_argv_for,
)
from .._tools import build_tool_descriptors
from .._toolsets import Toolset, build_toolsets

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_every_exposable_command_has_a_descriptor() -> None:
    descriptors = build_tool_descriptors()
    assert len(descriptors) >= 200
    # Group-callback help surfaces are not operator-callable tools.
    keys = {d.command_key for d in descriptors}
    assert "root.status" not in keys
    assert "root.app" not in keys
    assert "root.config" not in keys
    assert "contract" in keys
    assert "modelo.work.calculate" in keys


def test_descriptors_are_well_formed() -> None:
    for descriptor in build_tool_descriptors():
        assert descriptor.name.startswith("cadrumo_")
        assert descriptor.description
        assert descriptor.input_schema["type"] == "object"
        assert descriptor.output_schema  # the registered result model schema
        assert descriptor.annotations.title


def test_every_descriptor_carries_a_per_verb_schema_not_the_args_bag() -> None:
    for descriptor in build_tool_descriptors():
        # The retired ``{args: [string]}`` bag must not survive anywhere.
        assert "args" not in descriptor.input_schema["properties"]
        # The rendered schema is exactly the structured verb schema's projection.
        assert descriptor.input_schema == descriptor.verb_schema.json_schema()
        assert descriptor.verb_schema.command_key == descriptor.command_key


def test_mutability_projects_onto_annotations() -> None:
    by_key = {d.command_key: d for d in build_tool_descriptors()}
    assert by_key["contract"].annotations.read_only_hint is True
    assert by_key["overview.status"].annotations.read_only_hint is True
    assert by_key["ledger.add"].annotations.read_only_hint is False
    assert by_key["ledger.remove"].annotations.destructive_hint is True
    assert by_key["ledger.add"].annotations.destructive_hint is False


def test_tool_name_round_trips_including_segment_underscores() -> None:
    keys = [d.command_key for d in build_tool_descriptors()]
    # iva_wallet has a segment-internal underscore; the round-trip must be exact.
    name = tool_name_for_command("modelo.iva_wallet.balance")
    assert name == "cadrumo_modelo_ivaw_balance"
    assert command_key_for_tool(name, command_keys=keys) == "modelo.iva_wallet.balance"
    assert command_key_for_tool("cadrumo_not_a_real_tool", command_keys=keys) is None


def test_descriptor_argv_places_format_json_at_root_and_maps_named_arguments() -> None:
    by_key = {d.command_key: d for d in build_tool_descriptors()}
    calculate = by_key["modelo.work.calculate"].verb_schema
    assert cli_argv_for(calculate, {"work_unit_id": "wu_123"}) == [
        "--format",
        "json",
        "app",
        "modelo",
        "work",
        "calculate",
        "wu_123",
    ]
    # config keys carry their own leading root segment.
    create = by_key["config.profile.create"].verb_schema
    assert cli_argv_for(create, {"profile_name": "acme"}) == [
        "--format",
        "json",
        "config",
        "profile",
        "create",
        "acme",
    ]
    # The resolved path uses the hyphenated command name click dispatches on.
    pull = by_key["app.live.iva_wallet.pull"].verb_schema
    assert cli_argv_for(pull, {})[2:5] == ["app", "live", "iva-wallet"]


#: Command keys retired from the accepted CLI surface. Each is absent from the
#: live registrations, so the MCP surface must neither describe nor dispatch it.
#: Listed literally rather than derived, because deriving "what is absent" from
#: the same registration the descriptors are built from would restate the
#: implementation instead of pinning the retirement.
_RETIRED_COMMAND_KEYS: tuple[str, ...] = (
    "config.lock",
    "config.rekey",
    "config.recovery",
    "config.sandbox.use",
    "modelo.audit.replay",
)

#: The accepted successors that must be present. They are the positive control
#: for the retirement assertions below.
_ACCEPTED_SUCCESSOR_KEYS: tuple[str, ...] = (
    "config.passphrase.change",
    "config.recovery.status",
    "config.reset.resume",
)


def test_retired_command_keys_are_neither_described_nor_dispatchable() -> None:
    """A retired key gets no descriptor and no tool-name round-trip.

    The positive control runs FIRST and is not decoration. Every assertion
    below is an absence, and an absence proves nothing unless the same lookup
    is shown to find something when it should: a descriptor set that failed to
    build, or a round-trip that always returned ``None``, would satisfy the
    retirement checks while measuring nothing at all.
    """

    descriptors = build_tool_descriptors()
    keys = [descriptor.command_key for descriptor in descriptors]
    exposed = set(keys)

    for accepted in _ACCEPTED_SUCCESSOR_KEYS:
        assert accepted in exposed, f"positive control failed: {accepted} is not exposed"
        assert command_key_for_tool(tool_name_for_command(accepted), command_keys=keys) == accepted

    for retired in _RETIRED_COMMAND_KEYS:
        assert retired not in exposed, f"retired key still exposed as an MCP tool: {retired}"
        assert command_key_for_tool(tool_name_for_command(retired), command_keys=keys) is None, (
            f"retired key still dispatchable: {retired}"
        )


def test_exposability_is_a_filter_and_not_a_registration_guard() -> None:
    """Records what stops a retired key, because it is not the exposability check.

    ``is_exposable_command`` only removes the root landing keys, so it answers
    ``True`` for a key that is not registered at all. What actually keeps a
    retired verb off the surface is that descriptors are built from the
    registered schema refs. Pinning this stops a later reader from adding a
    retirement to the exposability filter and believing that is the guard, and
    stops the opposite error of reading the permissive answer as a leak.
    """

    exposed = {descriptor.command_key for descriptor in build_tool_descriptors()}
    for retired in _RETIRED_COMMAND_KEYS:
        assert is_exposable_command(retired) is True
        assert retired not in exposed


def test_annotation_coverage_is_total_over_the_descriptor_set() -> None:
    descriptors = build_tool_descriptors()
    gaps = annotation_coverage_gaps((descriptor.command_key, descriptor.annotations) for descriptor in descriptors)
    assert gaps == ()


def test_toolset_membership_derives_from_the_live_descriptor_set() -> None:
    descriptor_keys = {descriptor.command_key for descriptor in build_tool_descriptors()}
    groups = build_toolsets()
    # Every toolset is one of the five curated domains and non-empty.
    assert {group.toolset for group in groups} == set(Toolset)
    for group in groups:
        assert group.command_keys, f"toolset {group.toolset} is empty"
        # Every grouped command is a real exposed descriptor - the toolsets
        # derive from the live surface, never a hand-listed set that could drift.
        assert set(group.command_keys) <= descriptor_keys


# --- H2: input-schema fidelity -------------------------------------------------


def test_json_safe_default_renders_paths_tuples_and_falls_back_to_none() -> None:
    # Scalars pass through unchanged.
    assert _json_safe_default(True) is True
    assert _json_safe_default(7) == 7
    assert _json_safe_default("x") == "x"
    # A Path renders as its string form.
    assert _json_safe_default(Path("secrets") / "cert.p12") == str(Path("secrets") / "cert.p12")
    # A tuple/list renders as a JSON array of recursively json-safe items.
    assert _json_safe_default(("a", 1)) == ["a", 1]
    assert _json_safe_default([Path("p"), ("nested",)]) == [str(Path("p")), ["nested"]]
    # Only a genuinely unserialisable object falls back to None.
    assert _json_safe_default(object()) is None


def _probe_leaf_command() -> ClickCommand:
    """A real Typer command carrying a Path default, a list default, and a flag pair."""
    probe = typer.Typer()

    @probe.command()
    def run(  # pyright: ignore[reportUnusedFunction]
        cert: Annotated[Path, typer.Option("--cert")] = Path("secrets/cert.p12"),
        tags: Annotated[list[str], typer.Option("--tag")] = ["a", "b"],  # noqa: B006
        colour: Annotated[bool, typer.Option("--colour/--no-colour")] = True,
    ) -> None: ...

    return _typer_get_command(probe)


def test_path_and_list_option_defaults_project_and_round_trip_into_the_schema() -> None:
    leaf = _probe_leaf_command()
    by_name = {
        projected.name: projected
        for parameter in leaf.params
        if (projected := _parameter_from_click(parameter)) is not None
    }
    # A Path default renders as a string, both on the parameter and in its property.
    cert = by_name["cert"]
    assert cert.default == str(Path("secrets/cert.p12"))
    assert cert.property_schema()["default"] == str(Path("secrets/cert.p12"))
    # A list default renders as a JSON array on the array-typed property.
    tags = by_name["tags"]
    assert tags.multiple is True
    assert tags.default == ["a", "b"]
    tags_property = tags.property_schema()
    assert tags_property["type"] == "array"
    assert tags_property["default"] == ["a", "b"]


def test_default_true_flag_pair_is_expressible_false_and_emits_the_off_token() -> None:
    schema = VerbInputSchema(
        command_key="probe.flag",
        cli_path=("app", "probe", "flag"),
        parameters=(
            VerbParameter(
                name="colour",
                kind=VerbParamKind.OPTION,
                cli_flag="--colour",
                off_flag="--no-colour",
                json_type=JsonType.BOOLEAN,
                required=False,
                is_flag=True,
                multiple=False,
                default=True,
            ),
        ),
    )
    # The schema advertises the boolean (so a client may pass false) and the on default.
    colour_property = schema.json_schema()["properties"]["colour"]
    assert colour_property["type"] == "boolean"
    assert colour_property["default"] is True
    assert "colour" not in schema.json_schema()["required"]
    # An explicit false emits the off-token; an explicit true emits the on-token.
    assert cli_argv_for(schema, {"colour": False}) == ["--format", "json", "app", "probe", "flag", "--no-colour"]
    assert cli_argv_for(schema, {"colour": True}) == ["--format", "json", "app", "probe", "flag", "--colour"]


def test_real_boolean_pair_option_carries_off_token_and_can_be_disabled() -> None:
    by_key = {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}
    create = by_key["config.profile.create"].verb_schema
    by_name = {parameter.name: parameter for parameter in create.parameters}
    # ``--spouse-non-resident-irpf/--no-spouse-non-resident-irpf`` is a real CONFIRM pair.
    pair = by_name["spouse_non_resident_irpf"]
    assert pair.is_flag is True
    assert pair.off_flag == "--no-spouse-non-resident-irpf"
    argv = cli_argv_for(create, {"profile_name": "acme", "spouse_non_resident_irpf": False})
    assert "--no-spouse-non-resident-irpf" in argv
    assert "--spouse-non-resident-irpf" not in argv
    # A single ``--quiet`` switch (no off-token) still emits nothing when false.
    quiet_argv = cli_argv_for(create, {"profile_name": "acme", "quiet": False})
    assert "--quiet" not in quiet_argv


def test_schema_coverage_gate_raises_on_a_resolution_failure() -> None:
    with pytest.raises(SchemaResolutionError) as excinfo:
        assert_schema_coverage({"app.hostile.command": "Type not yet supported: <hostile parameter>"})
    assert "app.hostile.command" in str(excinfo.value)
    # An empty error map is a healthy no-op.
    assert_schema_coverage({})


def test_schema_coverage_gate_passes_on_the_real_command_set() -> None:
    keys = tuple(descriptor.command_key for descriptor in build_tool_descriptors())
    schemas = build_verb_input_schemas(keys)  # must not trip the coverage gate
    assert len(schemas) == len(keys)


def test_schema_coverage_gate_rejects_a_key_missing_from_the_real_command_tree() -> None:
    with pytest.raises(SchemaResolutionError, match=r"app\.not-a-real-command"):
        build_verb_input_schemas(("app.not-a-real-command",))


# --- Provider enum + one-of identifier fidelity --------------------------------


def test_ledger_import_provider_renders_as_a_json_enum() -> None:
    """The ``ledger.import`` provider is a closed set, so its schema is an enum.

    ``--provider`` is typed as the ``LedgerProviderID`` enum, so Typer renders a
    ``Choice`` and the built MCP input schema surfaces the closed provider set as a
    JSON ``enum`` rather than a bare string. This proves the enum declared at the
    CLI boundary flows through the input-schema builder without any per-command
    special case (the ``FuncParamType`` wrapping a ``click_type=click.Choice`` does
    NOT carry choices; an enum-typed option is the idiom that does).
    """
    from ....application.ledger import LedgerProviderID

    expected = [provider.value for provider in LedgerProviderID]
    by_key = {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}
    provider_property = by_key["ledger.import"].input_schema["properties"]["provider"]
    assert provider_property["type"] == "string"
    assert provider_property["enum"] == expected
    assert provider_property["enum"], "the recognised provider set must be non-empty"


def test_config_reset_lifecycle_schemas_expose_only_start_status_and_resume() -> None:
    """The MCP mirror follows the durable reset lifecycle without scope compatibility."""
    by_key = {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}
    assert "config.reset" not in by_key
    assert {
        "config.reset.start",
        "config.reset.status",
        "config.reset.resume",
    } <= set(by_key)

    start = by_key["config.reset.start"].input_schema["properties"]
    assert set(start) == {"yes", "override_retention", "reason"}
    assert start["yes"]["type"] == "boolean"
    assert start["override_retention"]["type"] == "boolean"
    assert start["reason"]["type"] == "string"

    status = by_key["config.reset.status"].input_schema["properties"]
    assert set(status) == {"operation_id"}
    assert status["operation_id"]["type"] == "string"

    resume = by_key["config.reset.resume"].input_schema["properties"]
    assert set(resume) == {
        "operation_id",
        "yes",
        "override_retention",
        "reason",
    }
    assert resume["operation_id"]["type"] == "string"
    assert resume["yes"]["type"] == "boolean"
    assert resume["override_retention"]["type"] == "boolean"
    assert resume["reason"]["type"] == "string"


def test_modelo_work_addressing_exposes_both_identifier_forms_as_optional() -> None:
    """One-of identifier alternation is enforced in the body, not the schema.

    The work-addressing verbs accept EITHER a ``work_unit_id`` OR a
    ``modelo``/``year``/``period`` triple to address the target. That alternation
    is resolved inside the command body (work addressing), not declared on the CLI
    parameters, so click models each identifier as an independent optional option
    and the generic input-schema builder cannot infer a JSON-Schema ``anyOf`` from
    the declaration. Expressing one would require hand-encoding the identifier
    groups in the schema builder - a per-command special case that would drift from
    the CLI authority - so the honest current shape is both forms present, both
    optional, no ``anyOf``. This test pins that shape so a regression that silently
    drops one identifier form fails here.
    """
    by_key = {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}
    for key in ("modelo.work.calculate", "modelo.work.verify", "modelo.work.file", "modelo.export"):
        schema = by_key[key].input_schema
        properties = schema["properties"]
        assert "work_unit_id" in properties
        assert {"modelo", "year", "period"} <= set(properties)
        # The alternation is a runtime concern; the schema declares no anyOf/oneOf
        # and leaves every identifier optional.
        assert "anyOf" not in schema
        assert "oneOf" not in schema
        required = schema.get("required", [])
        assert "work_unit_id" not in required
        assert "modelo" not in required
