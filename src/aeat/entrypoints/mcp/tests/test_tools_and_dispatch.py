"""Tests for the MCP tool descriptors and the name/argv dispatch mapping."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, override

import pytest
import typer
from typer._click.core import Command as ClickCommand
from typer._click.core import Context as ClickContext
from typer.core import TyperGroup
from typer.main import get_command as _typer_get_command

from .._annotations import annotation_coverage_gaps
from .._dispatch import command_key_for_tool, tool_name_for_command
from .._input_schema import (
    JsonType,
    SchemaResolutionError,
    VerbInputSchema,
    VerbParameter,
    VerbParamKind,
    _json_safe_default,
    _parameter_from_click,
    _resolve_command,
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
    assert "contract" in keys
    assert "modelo.work.calculate" in keys


def test_descriptors_are_well_formed() -> None:
    for descriptor in build_tool_descriptors():
        assert descriptor.name.startswith("aeat_")
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
    assert name == "aeat_modelo_iva_wallet_balance"
    assert command_key_for_tool(name, command_keys=keys) == "modelo.iva_wallet.balance"
    assert command_key_for_tool("aeat_not_a_real_tool", command_keys=keys) is None


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


class _RaisingGroup(TyperGroup):
    """A real Typer group whose subcommand resolution raises, as a hostile subtree would."""

    @override
    def get_command(self, ctx: ClickContext, cmd_name: str) -> ClickCommand | None:
        raise RuntimeError("Type not yet supported: <hostile parameter>")


def test_schema_coverage_gate_raises_on_a_resolution_failure() -> None:
    # A raising subtree makes _resolve_command SIGNAL the failure rather than
    # silently returning an empty schema, and the gate raises naming the verb.
    command, _resolved, error = _resolve_command(_RaisingGroup(name="app"), "app.hostile.command")
    assert command is None
    assert error is not None
    assert "Type not yet supported" in error
    with pytest.raises(SchemaResolutionError) as excinfo:
        assert_schema_coverage({"app.hostile.command": error})
    assert "app.hostile.command" in str(excinfo.value)
    # An empty error map is a healthy no-op.
    assert_schema_coverage({})


def test_schema_coverage_gate_passes_on_the_real_command_set() -> None:
    keys = tuple(descriptor.command_key for descriptor in build_tool_descriptors())
    schemas = build_verb_input_schemas(keys)  # must not trip the coverage gate
    assert len(schemas) == len(keys)


# --- P03.S16/S17: provider enum + one-of identifier fidelity -------------------


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


def test_config_reset_scope_renders_as_a_json_enum() -> None:
    """The ``config.reset`` scope is a closed set, so its schema is an enum.

    ``--scope`` cannot be typed as its ``ConfigResetScope`` enum directly because
    the enum values are upper-case (``ALL``) while the CLI tokens are lower-case
    (``all``); it therefore uses ``click_type=click.Choice(<lowercase tokens>)``.
    Typer wraps that Choice in a ``FuncParamType`` whose own ``.choices`` is
    ``None`` but whose ``.func`` carries the original Choice, so the input-schema
    builder unwraps ``.func`` and surfaces the closed set as a JSON ``enum`` rather
    than a bare string (``aeat-architecture-boundaries``: a closed value set must
    surface its accepted values). Generic — no per-command special case.
    """
    from ....application.config_reset import CONFIG_RESET_SCOPE_CLI_VALUES

    by_key = {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}
    scope_property = by_key["config.reset"].input_schema["properties"]["scope"]
    assert scope_property["type"] == "string"
    assert scope_property["enum"] == list(CONFIG_RESET_SCOPE_CLI_VALUES)
    assert scope_property["enum"], "the recognised reset-scope set must be non-empty"


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
