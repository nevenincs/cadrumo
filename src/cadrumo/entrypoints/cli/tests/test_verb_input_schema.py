"""Tests for the per-verb CLI input-schema derivation.

Exercised against the live ``aeat`` command tree - no mocks - so the schemas and
the argv reconstruction are verified against the real click parameters an
operator would see.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pytest
import typer
from typer._click.core import Command as ClickCommand
from typer.main import get_command as _typer_get_command

from .._command_schema import command_schema_refs
from .._verb_input_schema import (
    DECLARED_UNIMPLEMENTED_SURFACES,
    JsonType,
    SchemaResolutionError,
    VerbLeafKind,
    VerbLeafResolutionFailure,
    VerbParamKind,
    _json_safe_default,
    _naive_cli_path,
    _parameter_from_click,
    _resolve_command,
    assert_schema_coverage,
    build_verb_input_schemas,
    cli_argv_for,
    is_exposable_command,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _exposable_keys() -> tuple[str, ...]:
    return tuple(ref.command for ref in command_schema_refs() if is_exposable_command(ref.command))


def test_every_exposable_key_has_a_non_bag_schema() -> None:
    schemas = build_verb_input_schemas(_exposable_keys())
    assert len(schemas) >= 200
    for schema in schemas.values():
        rendered = schema.json_schema()
        assert rendered["type"] == "object"
        assert rendered["additionalProperties"] is False
        # The retired ``{args: [string]}`` bag must not survive anywhere.
        assert "args" not in rendered["properties"]


#: The accepted commands whose CLI shape changed, each paired with the resolved
#: CLI path click dispatches on. All three families are NESTED two levels under
#: ``config``, which is the shape the earlier flat keys did not exercise.
_ACCEPTED_CHANGED_COMMANDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("config.reset.start", ("config", "reset", "start")),
    ("config.reset.status", ("config", "reset", "status")),
    ("config.reset.resume", ("config", "reset", "resume")),
)


def test_every_accepted_changed_command_derives_a_nested_schema() -> None:
    """Each changed command is exposable AND derives a typed nested schema.

    The membership assertion is the point. The sweep above iterates whatever
    happens to be exposable and asserts a shape over it, so a command silently
    dropping out of the exposable set removes itself from that sweep and the
    floor of two hundred absorbs the loss without a failure. Naming these keys
    makes their disappearance a red test rather than a smaller corpus.
    """

    exposable = _exposable_keys()
    schemas = build_verb_input_schemas(exposable)

    for key, cli_path in _ACCEPTED_CHANGED_COMMANDS:
        assert key in exposable, f"accepted changed command is no longer exposable: {key}"
        schema = schemas[key]
        rendered = schema.json_schema()
        assert rendered["type"] == "object"
        assert rendered["additionalProperties"] is False
        assert "args" not in rendered["properties"], f"{key} fell back to the retired args bag"
        assert schema.cli_path == cli_path
        assert schema.parameters, f"{key} derived an empty parameter list"


def test_the_nested_reset_family_derives_each_verbs_own_arguments() -> None:
    """The changed commands are checked for real parameters, not just shape.

    Every assertion in the sweep above holds for a schema that resolved the
    right command path and read none of its parameters, so at least one family
    is read for its contents.

    The reset family discriminates itself: an operation id addresses an
    EXISTING operation, so ``status`` and ``resume`` take one while ``start``,
    which creates the operation, does not. A derivation that emitted one
    parameter set for the whole group would fail this, which is what makes it
    evidence of per-verb derivation rather than of a family default.
    """

    schemas = build_verb_input_schemas(_exposable_keys())

    def names(key: str) -> set[str]:
        return {parameter.name for parameter in schemas[key].parameters}

    assert "operation_id" in names("config.reset.resume")
    assert "operation_id" in names("config.reset.status")
    assert "operation_id" not in names("config.reset.start")

    # Resume carries the confirmation and retention arguments that status does
    # not, so the two are distinguished on more than the shared id.
    assert {"yes", "override_retention", "reason"} <= names("config.reset.resume")
    assert names("config.reset.status") == {"operation_id"}


def test_positional_argument_is_not_an_option() -> None:
    schemas = build_verb_input_schemas(_exposable_keys())
    calculate = schemas["modelo.work.calculate"]
    by_name = {parameter.name: parameter for parameter in calculate.parameters}
    work_unit = by_name["work_unit_id"]
    assert work_unit.kind is VerbParamKind.ARGUMENT
    assert work_unit.cli_flag == ""
    # A repeated option is an array; a scalar option is not.
    assert by_name["casilla"].multiple is True
    assert calculate.json_schema()["properties"]["casilla"]["type"] == "array"
    assert by_name["year"].json_type is JsonType.INTEGER


def test_required_options_and_enum_choices_are_surfaced() -> None:
    schemas = build_verb_input_schemas(_exposable_keys())
    add = schemas["ledger.add"]
    required = set(add.json_schema()["required"])
    assert {"booked_date", "amount", "direction", "description"} <= required
    direction = add.json_schema()["properties"]["direction"]
    assert direction["type"] == "string"
    assert set(direction["enum"]) == {"INCOMING", "OUTGOING", "INTERNAL_TRANSFER"}


def test_resolved_cli_path_uses_the_hyphenated_command_name() -> None:
    schemas = build_verb_input_schemas(_exposable_keys())
    # The command key segment is ``iva_wallet`` but the live CLI command is
    # ``iva-wallet``; the resolved path must carry the name click dispatches on.
    pull = schemas["app.live.iva_wallet.pull"]
    assert pull.cli_path == ("app", "live", "iva-wallet", "pull")


def test_stable_history_schema_key_resolves_relocated_cli_path() -> None:
    schemas = build_verb_input_schemas(("config.bucket.history",))

    schema = schemas["config.bucket.history"]

    assert schema.cli_path == ("config", "profile", "history")
    assert schema.resolved_leaf.subject_leaf_key == "config.bucket.history"
    assert schema.resolved_leaf.cli_path == ("config", "profile", "history")
    assert schema.resolved_leaf.alias_paths == (("config", "bucket", "history"),)


def test_resolved_leaf_exposes_hyphenated_click_identity_without_replacing_schema_key() -> None:
    schema = build_verb_input_schemas(("app.live.iva_wallet.pull",))["app.live.iva_wallet.pull"]

    assert schema.resolved_leaf.subject_leaf_key == "app.live.iva_wallet.pull"
    assert schema.resolved_leaf.cli_path == ("app", "live", "iva-wallet", "pull")
    assert schema.resolved_leaf.alias_paths == (("app", "live", "iva_wallet", "pull"),)
    assert schema.resolved_leaf.kind is VerbLeafKind.COMMAND


def test_required_inputs_keep_the_live_argument_and_option_metadata() -> None:
    schemas = build_verb_input_schemas(("config.bucket.history", "ledger.add"))
    # The bucket-history subject was deliberately widened to optional (the
    # verb falls back to the active profile), so it is read from the live
    # parameter metadata rather than the required-input set.
    history = {parameter.name: parameter for parameter in schemas["config.bucket.history"].parameters}
    add = {parameter.name: parameter for parameter in schemas["ledger.add"].required_inputs}

    assert history["profile"].kind is VerbParamKind.ARGUMENT
    assert history["profile"].cli_flag == ""
    assert history["profile"].required is False
    assert schemas["config.bucket.history"].required_inputs == ()
    assert add["booked_date"].kind is VerbParamKind.OPTION
    assert add["booked_date"].cli_flag == "--date"
    assert add["direction"].choices == ("INCOMING", "OUTGOING", "INTERNAL_TRANSFER")
    assert all(parameter.required for parameter in add.values())


def test_group_callback_is_classified_without_losing_its_live_inputs() -> None:
    schema = build_verb_input_schemas(("config.repair",))["config.repair"]

    assert schema.resolved_leaf.kind is VerbLeafKind.CALLBACK
    assert schema.resolved_leaf.subject_leaf_key == "config.repair"
    assert schema.resolved_leaf.cli_path == ("config", "repair")


def test_root_status_callback_has_an_empty_canonical_cli_path() -> None:
    schema = build_verb_input_schemas(("root.status",))["root.status"]

    assert schema.resolved_leaf.kind is VerbLeafKind.CALLBACK
    assert schema.resolved_leaf.subject_leaf_key == "root.status"
    assert schema.resolved_leaf.cli_path == ()
    assert schema.cli_path == ()


def test_root_app_callback_has_its_real_cli_path() -> None:
    schema = build_verb_input_schemas(("root.app",))["root.app"]

    assert schema.resolved_leaf.kind is VerbLeafKind.CALLBACK
    assert schema.resolved_leaf.subject_leaf_key == "root.app"
    assert schema.resolved_leaf.cli_path == ("app",)


def test_root_config_callback_has_its_real_cli_path() -> None:
    schema = build_verb_input_schemas(("root.config",))["root.config"]

    assert schema.resolved_leaf.kind is VerbLeafKind.CALLBACK
    assert schema.resolved_leaf.subject_leaf_key == "root.config"
    assert schema.resolved_leaf.cli_path == ("config",)


def test_unresolved_leaf_retains_key_and_click_path_evidence() -> None:
    with pytest.raises(SchemaResolutionError) as excinfo:
        build_verb_input_schemas(("app.not-a-real-command",))

    (failure,) = excinfo.value.failures
    assert failure.subject_leaf_key == "app.not-a-real-command"
    assert failure.attempted_cli_path == ("app", "not-a-real-command")
    assert failure.resolved_cli_path == ("app",)
    assert "not-a-real-command" in failure.reason


def test_argv_places_positionals_first_then_options() -> None:
    schemas = build_verb_input_schemas(_exposable_keys())
    calculate = schemas["modelo.work.calculate"]
    argv = cli_argv_for(calculate, {"work_unit_id": "wu_123", "year": 2024, "casilla": ["01", "02"]})
    assert argv == [
        "--format",
        "json",
        "app",
        "modelo",
        "work",
        "calculate",
        "wu_123",
        "--year",
        "2024",
        "--casilla",
        "01",
        "--casilla",
        "02",
    ]


def test_argv_maps_option_names_to_cli_flags_and_flags_emit_only_the_token() -> None:
    schemas = build_verb_input_schemas(_exposable_keys())
    add = schemas["ledger.add"]
    argv = cli_argv_for(
        add,
        {
            "booked_date": "2024-01-01",
            "amount": "100",
            "direction": "INCOMING",
            "description": "x",
            "attachment_ids": ["a", "b"],
        },
    )
    assert argv[:6] == ["--format", "json", "app", "ledger", "add", "--date"]
    # The multiple option repeats its flag per element.
    assert argv.count("--attachment-id") == 2

    create = schemas["config.profile.create"]
    flag_argv = cli_argv_for(create, {"profile_name": "acme", "quiet": True, "accept_defaults": False})
    assert flag_argv == ["--format", "json", "config", "profile", "create", "acme", "--quiet"]


def test_the_declared_unimplemented_surface_names_its_unmet_obligation() -> None:
    """The subject-access surface stays declared, with its reason, or it vanishes.

    The register holds every key whose schema outlives its verb. This one is
    pinned by name because the capability it named has no successor: no surviving
    surface discloses which personal-data categories a profile bundle carries and
    which stay in encrypted storage. The entry is deliberately NOT a claim about
    a legal duty -- nothing in this repository grounds one, and the withdrawn verb
    exported the operator's own profile to the operator's own disk -- so the
    reason text states the missing capability instead.

    So the declaration is the record, and a record nothing asserts is deleted by
    the next sweep that finds it unreferenced. The gap must stay stated rather
    than merely present: an entry whose reason is blank would pass a
    membership check while saying nothing to the reader who finds it.
    """
    assert "config.profile.subject_access_request" in DECLARED_UNIMPLEMENTED_SURFACES
    reason = DECLARED_UNIMPLEMENTED_SURFACES["config.profile.subject_access_request"]
    assert "subject-access" in reason.lower()
    assert len(reason.split()) >= 20, "the declaration must state the obligation, not merely name the key"


def test_every_declared_unimplemented_key_states_its_reason() -> None:
    """No entry rides in on the pinned one's coat-tails.

    The check above pins a single key by name, so the other entries were
    unasserted: a blank or one-line reason on any of them would pass
    everything. An entry here is a decision about a capability, and a decision
    nobody wrote down is indistinguishable from a build being made to pass.
    """
    thin = {
        key: reason
        for key, reason in DECLARED_UNIMPLEMENTED_SURFACES.items()
        if len(reason.split()) < 20 or not reason.strip()
    }
    assert not thin, (
        f"declared-unimplemented entries must state why the capability is owed, not merely name the key: {sorted(thin)}"
    )


def test_every_declared_unimplemented_key_still_names_an_absent_verb() -> None:
    """No entry outlives the gap it records.

    The reverse arm, and the register's missing half. Membership here does two
    things: it exempts the key from the coverage gate, and it makes
    :func:`is_exposable_command` return False, which withholds the verb from the
    MCP surface. Both are correct while the verb is genuinely absent and both
    become defects the moment it lands — a shipped verb would be silently kept
    off the wire by a note describing a gap that has closed, and the coverage
    gate would stop watching a key it now could watch.

    The sibling family-level register in the operator-surface manifest already
    carries this arm: a declared-unimplemented family the live tree reaches is
    reported stale, with the rule that the note goes in the same change that
    closes the gap. This register had the exit condition in prose only
    (``Restoring the verb removes this entry``), which is a request rather than
    a gate. Derived from the live tree, so it needs no list of its own.
    """
    from ... import cli as _cli_package

    root = _typer_get_command(_cli_package.app)
    resurrected: list[str] = []
    for key in DECLARED_UNIMPLEMENTED_SURFACES:
        command, _resolved, _failure = _resolve_command(root, key)
        if command is not None:
            resurrected.append(f"{key} (now resolves as `aeat {' '.join(_naive_cli_path(key))}`)")
    assert not resurrected, (
        "keys declared unimplemented now resolve in the live CLI; the recorded gap is closed, so "
        "the entry must go with the change that closed it — while it stays, the verb is withheld "
        f"from the MCP surface and exempted from the coverage gate: {sorted(resurrected)}"
    )


def test_the_coverage_gate_still_refuses_an_undeclared_missing_verb() -> None:
    """The carve-out is one named key, not a hole in the gate.

    Anti-tautology for the test above: proving the exemption exists is worthless
    unless the gate still bites for everything outside it, which is the property
    that makes the exemption safe to keep.
    """
    declared = VerbLeafResolutionFailure(
        subject_leaf_key="config.profile.subject_access_request",
        attempted_cli_path=("config", "profile", "subject-access-request"),
        reason="command did not resolve",
    )
    undeclared = VerbLeafResolutionFailure(
        subject_leaf_key="config.profile.invented_verb",
        attempted_cli_path=("config", "profile", "invented-verb"),
        reason="command did not resolve",
    )

    assert_schema_coverage((declared,))

    with pytest.raises(SchemaResolutionError) as excinfo:
        assert_schema_coverage((declared, undeclared))
    assert "config.profile.invented_verb" in str(excinfo.value)
    assert "subject_access_request" not in str(excinfo.value)


def test_json_safe_default_renders_paths_tuples_and_falls_back_to_none() -> None:
    # Scalars pass through unchanged.
    assert _json_safe_default(True) is True
    assert _json_safe_default(7) == 7
    assert _json_safe_default("x") == "x"
    # A Path renders as its string form.
    assert _json_safe_default(Path("probe-cert-store") / "cert.p12") == str(Path("probe-cert-store") / "cert.p12")
    # A tuple/list renders as a JSON array of recursively json-safe items.
    assert _json_safe_default(("a", 1)) == ["a", 1]
    assert _json_safe_default([Path("p"), ("nested",)]) == [str(Path("p")), ["nested"]]
    # Only a genuinely unserialisable object falls back to None.
    assert _json_safe_default(object()) is None


def _probe_leaf_command() -> ClickCommand:
    """A real Typer command carrying a Path default, a list default, and a flag pair.

    ``probe-cert-store`` is a fictional parent segment, deliberately not a real
    ``StorageCategory`` subpath: this default only exercises the click-to-schema
    Path-rendering projection and never resolves against
    ``cadrumo_local_storage_root``, so it must not spell a taxonomy-governed name
    a reader could mistake for a real, application-chosen location.
    """
    probe = typer.Typer()

    @probe.command()
    def run(
        cert: Annotated[Path, typer.Option("--cert")] = Path("probe-cert-store/cert.p12"),
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
    assert cert.default == str(Path("probe-cert-store/cert.p12"))
    assert cert.property_schema()["default"] == str(Path("probe-cert-store/cert.p12"))
    # A list default renders as a JSON array on the array-typed property.
    tags = by_name["tags"]
    assert tags.multiple is True
    assert tags.default == ["a", "b"]
    tags_property = tags.property_schema()
    assert tags_property["type"] == "array"
    assert tags_property["default"] == ["a", "b"]
