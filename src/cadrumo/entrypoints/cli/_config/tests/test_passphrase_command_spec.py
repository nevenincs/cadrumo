"""Focused authority gates for the self-authenticating rotation verb."""

from __future__ import annotations

import inspect

import pytest

from ..._command_schema import command_registration_metadata
from ..._command_spec import MachineSecretChannelKind, OptionSpec, ProfileAuthenticationPosture
from ..._command_specs import COMMAND_GRAPH
from .._passphrase import PassphraseChangeSecrets, passphrase_change
from .._spec_policies import ENCRYPTED_DESTRUCTIVE, STATE_FREE

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_passphrase_change_is_the_sole_public_rotation_leaf() -> None:
    nodes = COMMAND_GRAPH.nodes()
    passphrase_nodes = tuple(node for node in nodes if node.path[:3] == ("aeat", "config", "passphrase"))
    assert tuple(node.path for node in passphrase_nodes) == (
        ("aeat", "config", "passphrase"),
        ("aeat", "config", "passphrase", "change"),
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
