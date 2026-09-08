"""Parity and bite gates for spec-owned machine-secret authority."""

from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from .._command_runtime import resolve_deferred_target
from .._command_schema import command_registration_metadata
from .._verb_input_schema import build_verb_input_schemas
from ..command_spec import (
    DeferredTarget,
    MachineSecretChannelKind,
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
)
from ..command_specs import COMMAND_GRAPH
from ..config.secure_input import MachineSecretPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _secret_specs():
    return {
        identity: spec
        for identity, spec in COMMAND_GRAPH.by_schema_identity().items()
        if spec.machine_secret is not None
    }


def test_machine_secret_specs_are_the_exact_graph_and_projection_authority() -> None:
    specs = _secret_specs()
    assert specs
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
        for payload in registration[command].machine_secret_payloads:
            assert payload.maximum_bytes == 8192
            assert payload.same_scope_exclusive is True
            assert payload.duplicate_keys_forbidden is True
            assert payload.extra_fields_forbidden is True


def test_verb_schemas_preserve_secret_shapes_and_root_posture_without_values() -> None:
    registration = {row.command: row for row in command_registration_metadata()}
    schemas = build_verb_input_schemas(tuple(sorted(registration)))
    for command, row in registration.items():
        schema = schemas[command]
        assert schema.machine_secret_payloads == row.machine_secret_payloads
        assert schema.profile_authentication == row.profile_authentication
        assert schema.profile_authentication_contract.maximum_bytes == 8192
        rendered = repr(
            (
                tuple(asdict(payload) for payload in schema.machine_secret_payloads),
                asdict(schema.profile_authentication_contract),
            )
        ).lower()
        assert all(token not in rendered for token in ('"value"', '"example"', "secretstr"))

    restore = schemas["config.profile.archive.import"].machine_secret_payloads
    assert tuple(
        (payload.condition.option_name, payload.condition.presence)
        for payload in restore
        if payload.condition is not None
    ) == (("artifact", "absent"), ("artifact", "present"))


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
        DeferredTarget("cadrumo.entrypoints.cli.config.custody", "LoginSecrets"),
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
