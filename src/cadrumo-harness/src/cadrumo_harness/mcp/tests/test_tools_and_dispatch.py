"""Tests for the MCP tool descriptors and the name/argv dispatch mapping."""

from __future__ import annotations

import pytest

from cadrumo.entrypoints.cli.command_api import (
    JsonType,
    SchemaResolutionError,
    VerbInputSchema,
    VerbLeafResolutionFailure,
    VerbParameter,
    VerbParamKind,
    assert_schema_coverage,
    build_verb_input_schemas,
    cli_argv_for,
    is_exposable_command,
)

from .._annotations import annotation_coverage_gaps
from .._dispatch import command_key_for_tool, tool_name_for_command
from .._tools import build_tool_descriptors
from .._toolsets import Toolset, build_toolsets

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _live_authentication_contract():
    """Read the authentication contract off the live projection.

    Not hand-built: its field set derives from the root profile secret and its
    booleans are policy, so a copy here would be a second declaration of a
    product invariant and free to drift from the one that governs.
    """
    from cadrumo.entrypoints.cli._command_schema import command_registration_projection

    return command_registration_projection().profile_authentication_contract


def test_every_exposable_command_has_a_descriptor() -> None:
    descriptors = build_tool_descriptors()
    assert len(descriptors) >= 200
    # Group-callback help surfaces are not operator-callable tools.
    keys = {d.command_key for d in descriptors}
    assert "root.status" not in keys
    assert "root.app" not in keys
    assert "root.config" not in keys
    assert "registry.inspect" in keys
    assert "modelo.work.calculate" in keys


def test_descriptors_are_well_formed() -> None:
    for descriptor in build_tool_descriptors():
        assert descriptor.name.startswith("cadrumo_")
        assert descriptor.description
        assert descriptor.input_schema["type"] == "object"
        assert descriptor.output_schema  # the graph-authored result model schema
        assert descriptor.annotations.title


def test_every_descriptor_carries_a_per_verb_schema_not_the_args_bag() -> None:
    for descriptor in build_tool_descriptors():
        # The retired ``{args: [string]}`` bag must not survive anywhere.
        assert "args" not in descriptor.input_schema["properties"]
        # The rendered schema is exactly the structured verb schema's projection.
        assert descriptor.input_schema == descriptor.verb_schema.json_schema()
        assert descriptor.verb_schema.command_key == descriptor.command_key


def test_every_descriptor_carries_the_freshly_derived_verb_schema() -> None:
    """The descriptor's embedded schema equals an independent live derivation.

    ``build_tool_descriptors`` derives its schemas through the action-capability
    projection, so this proves that projection does not alter the resolved path,
    parameters or help a plain ``build_verb_input_schemas`` walk produces - the
    argv the server reconstructs is the argv the CLI declares.
    """
    descriptors = build_tool_descriptors()
    raw = build_verb_input_schemas(tuple(sorted(d.command_key for d in descriptors)))
    for descriptor in descriptors:
        derived = raw[descriptor.command_key]
        assert (
            descriptor.verb_schema.command_key,
            descriptor.verb_schema.cli_path,
            descriptor.verb_schema.parameters,
            descriptor.verb_schema.help,
        ) == (derived.command_key, derived.cli_path, derived.parameters, derived.help)


def test_descriptor_presentation_carries_no_authored_cli_invocation() -> None:
    # The resolver-backed capability extension owns executable identity. Tool
    # prose may describe the operator intent, but cannot duplicate a CLI form.
    for descriptor in build_tool_descriptors():
        for presentation in (descriptor.description, descriptor.annotations.title):
            normalized = presentation.casefold()
            assert "aeat app" not in normalized
            assert "aeat config" not in normalized
            assert "`aeat" not in normalized
            assert "run aeat" not in normalized
        assert descriptor.verb_schema.cli_path


def test_mutability_projects_onto_annotations() -> None:
    by_key = {d.command_key: d for d in build_tool_descriptors()}
    assert by_key["registry.inspect"].annotations.read_only_hint is True
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
    "config.recover",
    "config.recovery.create",
    "config.recovery.rotate",
    "config.recovery.status",
    "config.recovery.verify",
    "config.sandbox.use",
    "modelo.audit.replay",
)

#: The accepted successors that must be present. They are the positive control
#: for the retirement assertions below.
_ACCEPTED_SUCCESSOR_KEYS: tuple[str, ...] = ("config.reset.resume",)


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


def test_retired_commands_are_not_exposable_or_registered() -> None:
    """A retired key is absent from both the exposability policy and descriptors."""
    exposed = {descriptor.command_key for descriptor in build_tool_descriptors()}
    for retired in _RETIRED_COMMAND_KEYS:
        assert is_exposable_command(retired) is False
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


def test_default_true_flag_pair_is_expressible_false_and_emits_the_off_token() -> None:
    schema = VerbInputSchema(
        command_key="probe.flag",
        cli_path=("app", "probe", "flag"),
        profile_authentication="not-applicable",
        profile_authentication_contract=_live_authentication_contract(),
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
    failure = VerbLeafResolutionFailure(
        subject_leaf_key="app.hostile.command",
        attempted_cli_path=("app", "hostile", "command"),
        resolved_cli_path=("app",),
        reason="Type not yet supported: <hostile parameter>",
    )
    with pytest.raises(SchemaResolutionError) as excinfo:
        assert_schema_coverage((failure,))
    assert "app.hostile.command" in str(excinfo.value)
    assert excinfo.value.failures == (failure,)
    # An empty typed failure tuple is a healthy no-op.
    assert_schema_coverage(())


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
    from cadrumo.application.ledger.actions_import import LedgerProviderID

    expected = [provider.value for provider in LedgerProviderID]
    by_key = {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}
    provider_property = by_key["ledger.import"].input_schema["properties"]["provider"]
    assert provider_property["type"] == "string"
    assert provider_property["enum"] == expected
    assert provider_property["enum"], "the recognised provider set must be non-empty"


def test_invoice_operation_type_renders_as_a_json_enum_on_every_writing_verb() -> None:
    """Every invoice verb accepting ``--operation-type`` exposes the closed M349 set.

    The M349 clave is a closed set, so each writing verb declares
    :class:`~core.IntracomOperationType` at the Typer boundary and the built MCP
    input schema surfaces every letter as a JSON ``enum``. The operator on this
    surface is an autonomous agent reading the schema: a bare ``string`` forces it
    to guess the claves, and a guess lands a wrong operation key on a filed M349.

    Asserting the full member set rather than a count keeps the gate honest when a
    clave is added to the enum, and covering all three writing verbs stops one of
    them regressing to a hand-parsed ``str`` while its siblings stay typed.
    """
    from cadrumo.core.aggregation import IntracomOperationType

    expected = [operation.value for operation in IntracomOperationType]
    by_key = {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}
    writing_verbs = ("ledger.invoice.add", "ledger.invoice.wizard", "ledger.invoice.update")
    for command_key in writing_verbs:
        operation_property = by_key[command_key].input_schema["properties"]["operation_type"]
        assert operation_property["type"] == "string", command_key
        assert operation_property["enum"] == expected, command_key
    assert expected, "the recognised M349 operation set must be non-empty"


@pytest.mark.parametrize(
    ("command_key", "parameter_name", "enum_import"),
    [
        ("app.diagnostics.telemetry.status", "tier", "core.telemetry:TelemetryTier"),
        ("app.diagnostics.telemetry.flush", "tier", "core.telemetry:TelemetryTier"),
        # "registry.audit_oracles" carries no CLI, application, or MCP
        # declaration anywhere in production -- `OracleEnvironment` gates only
        # the internal domain oracle-binding audit
        # (`domain.calculations.registry.audit_oracle_bindings`), which has no
        # operator-facing verb wrapping it. This axis is retired from the
        # parametrize set rather than pinned against a fictional command; a
        # real "registry audit-oracles" verb would re-enroll it here.
        (
            "modelo.filing_record.import",
            "evidence_kind",
            "domain.modelos._filing_record:ExternalEvidenceKind",
        ),
        ("app.review.queue", "state", "application.review:ReviewState"),
        (
            "app.live.borrador.100.list",
            "state",
            "application.live.snapshot_base:SnapshotStateFilter",
        ),
    ],
)
def test_closed_value_axes_reach_the_mcp_schema_as_enums(
    command_key: str,
    parameter_name: str,
    enum_import: str,
) -> None:
    """A closed-set CLI option must surface its accepted values in the MCP schema.

    Each axis here is a ``StrEnum`` whose members are exactly the accepted CLI
    tokens. Declaring the enum at the Typer boundary is what makes the input-schema
    builder emit a JSON ``enum``; a bare ``str`` annotation compiles, passes lint,
    and silently ships a schema that tells the agent-operator nothing about the
    accepted set. Hand-parsing the token inside the handler does not repair that,
    because the refusal only arrives after the agent has already guessed.

    The expected set is read from the enum itself rather than restated, so adding a
    member cannot leave this gate asserting a stale list; the assertion that still
    bites is that the schema and the enum agree.
    """
    import importlib

    module_path, _, class_name = enum_import.partition(":")
    enum_class = getattr(importlib.import_module(f"cadrumo.{module_path}"), class_name)
    expected = [member.value for member in enum_class]

    by_key = {descriptor.command_key: descriptor for descriptor in build_tool_descriptors()}
    schema_property = by_key[command_key].input_schema["properties"][parameter_name]
    assert schema_property["type"] == "string"
    assert schema_property["enum"] == expected
    assert expected, f"{class_name} must declare at least one member"


def test_every_modelo_work_verb_pins_the_registry_eligible_modelo_set() -> None:
    """The whole ``modelo work`` family must advertise its accepted modelo codes.

    Every verb in this family resolves a registry revision from
    ``(modelo, filing_year, period)``, so a code with no registry definition can
    never address one. The accepted set is therefore the core taxonomy minus
    :data:`NON_REGISTRY_MODELOS`, derived here from the same two core objects the
    CLI derives it from rather than restated as a literal list.

    The surface is asserted to be complete rather than sampled: a new ``work``
    verb that declares a bare ``str`` modelo option reds this gate instead of
    quietly shipping an unhinted axis. ``NON_REGISTRY_MODELOS`` is asserted
    non-empty so the exclusion cannot become vacuous and let a retired code in.

    ``modelo.work.create`` is exempt, and the exemption is the interesting part.
    It is the one verb an operator reaches with a modelo the application does not
    handle, so it deliberately accepts any code in order to run
    ``guard_unsupported_work_modelo`` and answer with a legally-grounded refusal —
    ITP-AJD and ISD are ceded autonomic taxes, and the refusal names the regional
    filing route. A ``click.Choice`` would refuse first with a bare "not one of",
    trading an actionable answer for an unhinted one. The exemption is asserted to
    still be bare, so silently pinning it later also reds this gate.
    """
    from cadrumo.core import NON_REGISTRY_MODELOS, Modelo

    expected = [modelo.value for modelo in Modelo if modelo not in NON_REGISTRY_MODELOS]
    assert NON_REGISTRY_MODELOS, "the exclusion must exclude something, or this gate is vacuous"
    assert expected

    #: Accepts out-of-taxonomy codes on purpose; see the docstring.
    instructive_refusal_verbs = {"modelo.work.create"}

    work_verbs = {
        descriptor.command_key: descriptor
        for descriptor in build_tool_descriptors()
        if descriptor.command_key.startswith("modelo.work.")
        and "modelo" in descriptor.input_schema.get("properties", {})
    }
    assert work_verbs, "positive control failed: no modelo.work.* verb takes a modelo option"
    assert instructive_refusal_verbs <= work_verbs.keys()

    for command_key, descriptor in sorted(work_verbs.items()):
        schema_property = descriptor.input_schema["properties"]["modelo"]
        if command_key in instructive_refusal_verbs:
            assert schema_property.get("enum") is None, command_key
            continue
        assert schema_property.get("enum") == expected, command_key


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
