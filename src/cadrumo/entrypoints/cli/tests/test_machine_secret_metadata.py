"""Cross-surface conformance for the closed machine-secret CLI capability."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pytest
from typer.testing import CliRunner

from .. import app
from .._command_schema import command_registration_metadata
from .._config._command_specs import CONFIG_COMMAND_SPECS
from .._config._secure_input import MachineSecretPayload
from .._machine_secret_contract import (
    MACHINE_SECRET_COMMANDS,
    missing_machine_secret_payload_models,
    registered_machine_secret_payload_models,
)
from .._verb_input_schema import _build_materialized_verb_input_schemas, build_verb_input_schemas

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_COMMAND_KEYS = tuple(contract.command_key for contract in MACHINE_SECRET_COMMANDS)
_PATHS = {contract.command_key: contract.cli_path for contract in MACHINE_SECRET_COMMANDS}
_EXPECTED_CHANNELS: tuple[tuple[object, ...], ...] = (
    ("secrets_stdin", "--secrets-stdin", "boolean", False, True, False, False),
    ("secrets_fd", "--secrets-fd", "integer", None, False, False, False),
)
_SPEC_KEYS = (
    "config_login",
    "config_profile_create",
    "config_passphrase_change",
    "config_profile_restore",
    "config_auth_certificate_secret_set",
)


def _verb_channel_signature(parameters: tuple[Any, ...]) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            parameter.name,
            parameter.cli_flag,
            parameter.json_type.value,
            parameter.default,
            parameter.is_flag,
            parameter.required,
            parameter.multiple,
        )
        for parameter in parameters
        if parameter.name in {"secrets_stdin", "secrets_fd"}
    )


def _spec_channel_signature(parameters: tuple[Any, ...]) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            parameter.name,
            parameter.declarations[0],
            "boolean" if parameter.value.annotation.qualname == "bool" else "integer",
            parameter.default.literal,
            parameter.is_flag,
            parameter.default.kind.value == "required",
            parameter.multiple,
        )
        for parameter in parameters
        if parameter.name in {"secrets_stdin", "secrets_fd"}
    )


def test_inventory_channels_are_single_ordered_and_semantically_identical_where_declared() -> None:
    specs = {spec.key: spec for spec in CONFIG_COMMAND_SPECS}
    materialized = _build_materialized_verb_input_schemas(_COMMAND_KEYS)
    runner = CliRunner()

    for command_key, spec_key in zip(_COMMAND_KEYS, _SPEC_KEYS, strict=True):
        help_result = runner.invoke(app, [*_PATHS[command_key], "--help"])
        assert help_result.exit_code == 0, help_result.output
        assert help_result.output.count("--secrets-stdin") == 1
        assert help_result.output.count("--secrets-fd") <= 1
        if "--secrets-fd" in help_result.output:
            assert help_result.output.index("--secrets-stdin") < help_result.output.index("--secrets-fd")

        live_signature = _verb_channel_signature(materialized[command_key].parameters)
        spec_signature = _spec_channel_signature(specs[spec_key].parameters)
        assert live_signature == spec_signature
        assert live_signature == _EXPECTED_CHANNELS[: len(live_signature)]


def test_no_command_outside_the_closed_inventory_adopts_either_channel() -> None:
    adopters = {
        spec.key
        for spec in CONFIG_COMMAND_SPECS
        if any(parameter.name in {"secrets_stdin", "secrets_fd"} for parameter in spec.parameters)
    }
    assert adopters == set(_SPEC_KEYS)


def test_payload_metadata_is_value_free_exact_and_restore_is_conditional() -> None:
    registration = {row.command: row for row in command_registration_metadata()}
    schemas = build_verb_input_schemas(_COMMAND_KEYS)
    expected = {
        contract.command_key: tuple(
            (
                variant.key,
                tuple((field.name, field.json_type.value) for field in variant.fields),
                (
                    (variant.condition.option_name, variant.condition.presence.value)
                    if variant.condition is not None
                    else None
                ),
            )
            for variant in contract.variants
        )
        for contract in MACHINE_SECRET_COMMANDS
    }

    for command_key in _COMMAND_KEYS:
        projected = registration[command_key].machine_secret_payloads
        actual = tuple(
            (
                variant.key,
                tuple((field.name, field.json_type) for field in variant.fields),
                (variant.condition.option_name, variant.condition.presence) if variant.condition is not None else None,
            )
            for variant in projected
        )
        assert actual == expected[command_key]
        assert schemas[command_key].machine_secret_payloads == projected

        rendered = asdict(registration[command_key])["machine_secret_payloads"]
        serialized = repr(rendered).lower()
        assert all(forbidden not in serialized for forbidden in ("value", "default", "example", "secretstr"))

    restore = registration["config.profile.restore"].machine_secret_payloads
    assert tuple(
        (variant.condition.option_name, variant.condition.presence)
        for variant in restore
        if variant.condition is not None
    ) == (("artifact", "absent"), ("artifact", "present"))


def test_every_declared_payload_registration_uses_the_canonical_base() -> None:
    # Materializing current adopters imports their owners. Later migration Steps
    # fill the declared slots; every registration accepted at any point is
    # already bound by this canonical-base gate.
    _build_materialized_verb_input_schemas(_COMMAND_KEYS)

    registered = registered_machine_secret_payload_models()
    expected_slots = {
        (contract.command_key, variant.key)
        for contract in MACHINE_SECRET_COMMANDS
        for variant in contract.variants
    }
    assert set(registered) <= expected_slots
    assert set(missing_machine_secret_payload_models()) == expected_slots - set(registered)
    assert all(issubclass(model, MachineSecretPayload) for model in registered.values())
