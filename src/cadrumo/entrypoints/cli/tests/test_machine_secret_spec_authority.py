"""Parity and bite gates for spec-owned machine-secret authority."""

from __future__ import annotations

from dataclasses import replace

import pytest

from .._command_runtime import resolve_deferred_target
from .._command_schema import command_registration_metadata
from .._command_spec import (
    DeferredTarget,
    MachineSecretChannelKind,
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
)
from .._command_specs import COMMAND_GRAPH
from .._config._secure_input import MachineSecretPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_COMMANDS = {
    "config.login",
    "config.profile.create",
    "config.profile.restore",
    "config.auth.certificate.secret.set",
}


def _secret_specs():
    return {
        identity: spec
        for identity, spec in COMMAND_GRAPH.by_schema_identity().items()
        if spec.machine_secret is not None
    }


def test_machine_secret_specs_are_the_exact_graph_and_projection_authority() -> None:
    specs = _secret_specs()
    assert set(specs) == _COMMANDS
    registration = {row.command: row for row in command_registration_metadata()}
    for command, spec in specs.items():
        assert spec.machine_secret is not None
        expected = tuple(
            (
                variant.key,
                tuple((field.name, field.json_type) for field in variant.fields),
                (variant.condition.option_name, variant.condition.presence) if variant.condition else None,
            )
            for variant in spec.machine_secret.variants
        )
        actual = tuple(
            (
                variant.key,
                tuple((field.name, field.json_type) for field in variant.fields),
                (variant.condition.option_name, variant.condition.presence) if variant.condition else None,
            )
            for variant in registration[command].machine_secret_payloads
        )
        assert actual == expected


def test_machine_secret_model_targets_are_public_strict_and_shape_exact() -> None:
    for spec in _secret_specs().values():
        assert spec.machine_secret is not None
        for variant in spec.machine_secret.variants:
            assert not variant.model.qualname.startswith("_")
            model = resolve_deferred_target(variant.model)
            assert isinstance(model, type)
            assert issubclass(model, MachineSecretPayload)
            assert tuple(model.model_fields) == tuple(field.name for field in variant.fields)


def test_duplicate_machine_secret_contract_is_refused() -> None:
    variant = MachineSecretVariantSpec(
        "passphrase",
        (MachineSecretFieldSpec("passphrase"),),
        DeferredTarget("cadrumo.entrypoints.cli._config._custody", "LoginSecrets"),
    )
    with pytest.raises(ValueError, match="variant keys must be unique"):
        MachineSecretSpec((variant, variant))


def test_planted_missing_machine_secret_channel_is_refused() -> None:
    login = COMMAND_GRAPH.by_schema_identity()["config.login"]
    parameters = tuple(
        replace(parameter, machine_secret_channel=None)
        if getattr(parameter, "machine_secret_channel", None) is MachineSecretChannelKind.FILE_DESCRIPTOR
        else parameter
        for parameter in login.parameters
    )
    with pytest.raises(ValueError, match="exactly one stdin and file-descriptor"):
        replace(login, parameters=parameters)


def test_planted_duplicate_machine_secret_channel_is_refused() -> None:
    login = COMMAND_GRAPH.by_schema_identity()["config.login"]
    descriptor = next(parameter for parameter in login.parameters if parameter.name == "secrets_fd")
    duplicate = replace(descriptor, name="alternate_descriptor", declarations=("--alternate-secrets-fd",))
    with pytest.raises(ValueError, match="exactly one stdin and file-descriptor"):
        replace(login, parameters=(*login.parameters, duplicate))
