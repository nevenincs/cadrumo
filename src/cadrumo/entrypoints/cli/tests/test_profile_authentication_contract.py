"""Universal gates for the distinct root profile-authentication capability."""

from __future__ import annotations

from dataclasses import replace

import pytest
from pydantic import ValidationError

from ....tests.cli_runner import cadrumo_click_command, invoke_cached_cli
from .._command_schema import command_registration_metadata, command_registration_projection
from .._command_spec import (
    MachineSecretChannelKind,
    MachineSecretFieldSpec,
    OptionSpec,
    ProfileAuthenticationPosture,
    ProfileSecretChannelKind,
)
from .._command_specs import COMMAND_GRAPH
from .._config._secure_input import (
    MACHINE_SECRET_MAX_BYTES,
    ProfileSecretChannel,
    select_profile_secret_channel,
)
from .._profile_authentication_contract import (
    ProfileAuthenticationSecrets,
    ProfileSecretSourceOptions,
    profile_authentication_posture,
    resolve_profile_secret_model,
    root_profile_secret_model,
)
from ..errors import CliRefusedBoundaryError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_root_owns_exactly_one_distinct_profile_secret_channel_pair() -> None:
    root = COMMAND_GRAPH.by_key()["root"]
    channels = tuple(
        parameter.profile_secret_channel
        for parameter in root.parameters
        if isinstance(parameter, OptionSpec) and parameter.profile_secret_channel is not None
    )
    assert channels == (
        ProfileSecretChannelKind.STDIN,
        ProfileSecretChannelKind.FILE_DESCRIPTOR,
    )
    assert tuple(
        declaration
        for parameter in root.parameters
        if isinstance(parameter, OptionSpec) and parameter.profile_secret_channel is not None
        for declaration in parameter.declarations
    ) == ("--profile-secrets-stdin", "--profile-secrets-fd")
    assert root.machine_secret is None
    assert root.profile_secret is not None
    for node in COMMAND_GRAPH.nodes():
        if node.spec is root:
            continue
        assert all(getattr(parameter, "profile_secret_channel", None) is None for parameter in node.spec.parameters)


def test_live_root_click_contract_contains_each_profile_option_once() -> None:
    parameters = {parameter.name: parameter for parameter in cadrumo_click_command().params}
    assert parameters["profile_secrets_stdin"].opts == ["--profile-secrets-stdin"]
    assert parameters["profile_secrets_stdin"].default is False
    assert parameters["profile_secrets_fd"].opts == ["--profile-secrets-fd"]
    assert parameters["profile_secrets_fd"].default is None
    all_options = tuple(option for parameter in parameters.values() for option in parameter.opts)
    assert all_options.count("--profile-secrets-stdin") == 1
    assert all_options.count("--profile-secrets-fd") == 1


def test_leaf_machine_secret_inventory_remains_leaf_only_and_scope_disjoint() -> None:
    adopters = tuple(node for node in COMMAND_GRAPH.nodes() if node.spec.machine_secret is not None)
    assert {node.spec.result_schema.identity for node in adopters} == {
        "config.login",
        "config.passphrase.change",
        "config.profile.create",
        "config.profile.archive.import",
        "config.auth.certificate.secret.set",
    }
    for node in adopters:
        assert node.spec.kind == "leaf"
        channels = {
            parameter.machine_secret_channel
            for parameter in node.spec.parameters
            if isinstance(parameter, OptionSpec) and parameter.machine_secret_channel is not None
        }
        assert channels == {MachineSecretChannelKind.STDIN, MachineSecretChannelKind.FILE_DESCRIPTOR}
        assert all(getattr(parameter, "profile_secret_channel", None) is None for parameter in node.spec.parameters)


def test_profile_payload_is_strict_frozen_secretstr_and_value_free_in_repr() -> None:
    payload = ProfileAuthenticationSecrets.model_validate({"profile_passphrase": "not-a-real-passphrase"})
    assert tuple(ProfileAuthenticationSecrets.model_fields) == ("profile_passphrase",)
    assert "not-a-real-passphrase" not in repr(payload)
    with pytest.raises(ValidationError):
        ProfileAuthenticationSecrets.model_validate({})
    with pytest.raises(ValidationError):
        ProfileAuthenticationSecrets.model_validate(
            {"profile_passphrase": "not-a-real-passphrase", "extra": "forbidden"}
        )
    with pytest.raises(ValidationError):
        payload.profile_passphrase = payload.profile_passphrase  # ty: ignore[invalid-assignment]  # reason: frozen-model refusal probe


def test_graph_profile_payload_model_is_exact_runtime_authority() -> None:
    root = COMMAND_GRAPH.by_key()["root"]
    assert root.profile_secret is not None
    assert resolve_profile_secret_model(root.profile_secret) is ProfileAuthenticationSecrets
    assert root_profile_secret_model() is ProfileAuthenticationSecrets
    planted = replace(root.profile_secret, fields=(MachineSecretFieldSpec("planted_passphrase"),))
    with pytest.raises(ValueError, match="exactly match"):
        resolve_profile_secret_model(planted)


def test_profile_selection_is_distinct_and_conflict_refuses_without_reading() -> None:
    assert select_profile_secret_channel(profile_secrets_stdin=False, profile_secrets_fd=None) is None
    stdin = select_profile_secret_channel(profile_secrets_stdin=True, profile_secrets_fd=None)
    assert stdin is not None and stdin.channel is ProfileSecretChannel.STDIN
    descriptor = select_profile_secret_channel(profile_secrets_stdin=False, profile_secrets_fd=0)
    assert descriptor is not None and descriptor.descriptor == 0
    with pytest.raises(CliRefusedBoundaryError) as refusal:
        select_profile_secret_channel(profile_secrets_stdin=True, profile_secrets_fd=9)
    assert refusal.value.translated_message is not None
    assert refusal.value.translated_message.endswith("profile_secrets_channel_conflict")


def test_profile_authentication_posture_is_graph_and_exemption_derived() -> None:
    postures = {
        node.spec.result_schema.identity: profile_authentication_posture(node) for node in COMMAND_GRAPH.nodes()
    }
    assert postures["config.passphrase.change"] is ProfileAuthenticationPosture.SELF_AUTHENTICATING
    assert postures["config.login"] is ProfileAuthenticationPosture.NOT_APPLICABLE
    assert postures["config.profile.create"] is ProfileAuthenticationPosture.NOT_APPLICABLE
    assert postures["config.profile.archive.import"] is ProfileAuthenticationPosture.NOT_APPLICABLE
    assert postures["ledger.list"] is ProfileAuthenticationPosture.RESUME_FALLBACK
    metadata = {row.command: row.profile_authentication for row in command_registration_metadata()}
    assert metadata == {identity: posture.value for identity, posture in postures.items() if identity is not None}


def test_profile_authentication_metadata_is_public_bounded_and_value_free() -> None:
    contract = command_registration_projection().profile_authentication_contract
    assert tuple((field.name, field.json_type) for field in contract.fields) == (("profile_passphrase", "string"),)
    assert contract.maximum_bytes == MACHINE_SECRET_MAX_BYTES == 8192
    assert contract.same_scope_exclusive is True
    assert contract.stdin_exclusive_across_scopes is True
    assert contract.descriptors_must_differ_across_scopes is True
    assert contract.duplicate_keys_forbidden is True
    assert contract.extra_fields_forbidden is True
    assert "passphrase" not in repr(contract).replace("profile_passphrase", "")


def test_root_source_options_are_parse_only_authority() -> None:
    both = ProfileSecretSourceOptions(stdin=True, descriptor=7)
    assert both.supplied is True
    assert replace(both, stdin=False, descriptor=None).supplied is False


@pytest.mark.parametrize(
    "arguments",
    (
        ("--profile-secrets-stdin", "--help"),
        ("--profile-secrets-stdin", "--version"),
        ("--profile-secrets-stdin",),
        ("--profile-secrets-stdin", "unknown-command"),
        ("--profile-secrets-fd", "not-an-integer", "app"),
    ),
)
def test_introspection_bare_unknown_and_parse_surfaces_do_not_read_profile_source(arguments: tuple[str, ...]) -> None:
    result = invoke_cached_cli(list(arguments), input="this-is-deliberately-not-json")
    assert "profile_secrets_stdin_invalid_json" not in result.output
    assert "profile_secrets_stdin_missing_fields" not in result.output


def test_planted_profile_channels_outside_root_are_refused() -> None:
    root = COMMAND_GRAPH.by_key()["root"]
    login = COMMAND_GRAPH.by_schema_identity()["config.login"]
    planted = tuple(
        replace(parameter, name=f"profile_{parameter.name}")
        for parameter in root.parameters
        if getattr(parameter, "profile_secret_channel", None) is not None
    )
    with pytest.raises(ValueError, match="require a profile-secret spec"):
        replace(login, parameters=(*login.parameters, *planted))
