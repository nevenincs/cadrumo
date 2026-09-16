"""Focused authority gates for the self-authenticating rotation and reset verbs."""

from __future__ import annotations

import inspect

import pytest

from cadrumo.application.operator_surface.command_ports import ProfileAuthenticationPosture

from ...command_schema import command_registration_metadata
from ...command_spec import (
    MachineSecretChannelKind,
    OptionSpec,
)
from ...command_specs import COMMAND_GRAPH
from .._spec_policies import BOOTSTRAP_DESTRUCTIVE, ENCRYPTED_DESTRUCTIVE, STATE_FREE
from ..passphrase import PassphraseChangeSecrets, PassphraseResetSecrets, passphrase_change, passphrase_reset

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_passphrase_exposes_exactly_the_change_and_reset_leaves() -> None:
    nodes = COMMAND_GRAPH.nodes()
    passphrase_nodes = tuple(node for node in nodes if node.path[:3] == ("aeat", "config", "passphrase"))
    assert tuple(node.path for node in passphrase_nodes) == (
        ("aeat", "config", "passphrase"),
        ("aeat", "config", "passphrase", "change"),
        ("aeat", "config", "passphrase", "reset"),
    )


def test_passphrase_change_declares_exact_channels_payload_and_exemption() -> None:
    spec = COMMAND_GRAPH.by_schema_identity()["config.passphrase.change"]
    group = COMMAND_GRAPH.resolve_path(("aeat", "config", "passphrase"))
    assert group.policy == STATE_FREE
    assert spec.policy == ENCRYPTED_DESTRUCTIVE
    assert spec.profile_authentication is ProfileAuthenticationPosture.SELF_AUTHENTICATING
    assert tuple(parameter.name for parameter in spec.parameters) == (
        "secrets_stdin",
        "secrets_fd",
        "output_language",
    )
    assert tuple(
        parameter.machine_secret_channel
        for parameter in spec.parameters
        if isinstance(parameter, OptionSpec) and parameter.machine_secret_channel is not None
    ) == (MachineSecretChannelKind.STDIN, MachineSecretChannelKind.FILE_DESCRIPTOR)
    assert spec.machine_secret is not None
    assert (
        tuple(field.name for field in spec.machine_secret.variants[0].fields)
        == tuple(PassphraseChangeSecrets.model_fields)
        == (
            "current_passphrase",
            "new_passphrase",
            "new_passphrase_confirmation",
        )
    )


def test_passphrase_change_handler_signature_and_public_metadata_match_spec() -> None:
    assert tuple(inspect.signature(passphrase_change).parameters) == (
        "ctx",
        "secrets_stdin",
        "secrets_fd",
        "output_language",
    )
    row = next(row for row in command_registration_metadata() if row.command == "config.passphrase.change")
    assert row.profile_authentication == "self-authenticating"
    assert tuple(
        (variant.key, tuple(field.name for field in variant.fields)) for variant in row.machine_secret_payloads
    ) == (("rotation", ("current_passphrase", "new_passphrase", "new_passphrase_confirmation")),)


def test_passphrase_reset_declares_the_recovery_code_payload_and_bootstrap_exemption() -> None:
    """Reset is the forgotten-passphrase door: it names its target and proves the recovery code."""
    spec = COMMAND_GRAPH.by_schema_identity()["config.passphrase.reset"]
    assert spec.policy == BOOTSTRAP_DESTRUCTIVE
    assert spec.profile_authentication is ProfileAuthenticationPosture.SELF_AUTHENTICATING
    assert tuple(parameter.name for parameter in spec.parameters) == (
        "name",
        "secrets_stdin",
        "secrets_fd",
        "output_language",
    )
    assert tuple(
        parameter.machine_secret_channel
        for parameter in spec.parameters
        if isinstance(parameter, OptionSpec) and parameter.machine_secret_channel is not None
    ) == (MachineSecretChannelKind.STDIN, MachineSecretChannelKind.FILE_DESCRIPTOR)
    assert spec.machine_secret is not None
    assert (
        tuple(field.name for field in spec.machine_secret.variants[0].fields)
        == tuple(PassphraseResetSecrets.model_fields)
        == ("recovery_code", "new_passphrase", "new_passphrase_confirmation")
    )


def test_passphrase_reset_handler_signature_and_public_metadata_match_spec() -> None:
    assert tuple(inspect.signature(passphrase_reset).parameters) == (
        "ctx",
        "name",
        "secrets_stdin",
        "secrets_fd",
        "output_language",
    )
    row = next(row for row in command_registration_metadata() if row.command == "config.passphrase.reset")
    assert row.profile_authentication == "self-authenticating"
    assert tuple(
        (variant.key, tuple(field.name for field in variant.fields)) for variant in row.machine_secret_payloads
    ) == (("reset", ("recovery_code", "new_passphrase", "new_passphrase_confirmation")),)
