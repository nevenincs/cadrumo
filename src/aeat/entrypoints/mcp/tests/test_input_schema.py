"""Tests for the per-verb CLI input-schema derivation.

Exercised against the live ``aeat`` command tree - no mocks - so the schemas and
the argv reconstruction are verified against the real click parameters an
operator would see.
"""

from __future__ import annotations

import click
import pytest

from ...cli import command_schema_refs
from .._dispatch import is_exposable_command
from .._input_schema import (
    JsonType,
    VerbParamKind,
    build_verb_input_schema,
    build_verb_input_schemas,
    cli_argv_for,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _RaisingGroup(click.Group):
    """A real click group whose subcommand resolution raises, as a hostile subtree would."""

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        raise RuntimeError("Type not yet supported: <hostile parameter>")


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


def test_an_unintrospectable_subtree_degrades_to_an_argument_free_schema() -> None:
    # A subtree that raises during click materialisation (a Typer-unconvertible
    # parameter type) must not brick the build: the key degrades to an
    # argument-free schema over the naive path instead of propagating the raise.
    schema = build_verb_input_schema(_RaisingGroup(name="app"), "app.hostile.command")
    assert schema.command_key == "app.hostile.command"
    assert schema.cli_path == ("app", "hostile", "command")
    assert schema.parameters == ()
    assert schema.json_schema()["properties"] == {}


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
