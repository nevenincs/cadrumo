"""Unit contract for the closed scalar-secret CLI inventory."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from .. import _machine_secret_contract as contract_module
from .._machine_secret_contract import (
    MACHINE_SECRET_COMMANDS,
    MachineSecretContractError,
    OptionPresence,
    machine_secret_contract,
    register_machine_secret_payload_model,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_inventory_and_value_free_payload_shapes_are_exact() -> None:
    assert tuple(contract.command_key for contract in MACHINE_SECRET_COMMANDS) == (
        "config.login",
        "config.profile.create",
        "config.passphrase.change",
        "config.profile.restore",
        "config.auth.certificate.secret.set",
    )
    assert {
        contract.command_key: tuple(
            (variant.key, tuple((field.name, field.json_type.value) for field in variant.fields))
            for variant in contract.variants
        )
        for contract in MACHINE_SECRET_COMMANDS
    } == {
        "config.login": (("passphrase", (("passphrase", "string"),)),),
        "config.profile.create": (
            ("passphrase", (("passphrase", "string"), ("passphrase_confirmation", "string"))),
        ),
        "config.passphrase.change": (
            (
                "rotation",
                (
                    ("current_passphrase", "string"),
                    ("new_passphrase", "string"),
                    ("new_passphrase_confirmation", "string"),
                ),
            ),
        ),
        "config.profile.restore": (
            ("passphrase", (("passphrase", "string"),)),
            ("recovery", (("recovery_secret", "string"),)),
        ),
        "config.auth.certificate.secret.set": (
            ("certificate", (("certificate_passphrase", "string"),)),
        ),
    }


def test_restore_variant_is_selected_only_by_public_artifact_presence() -> None:
    restore = machine_secret_contract("config.profile.restore")
    assert restore.variant_for(artifact_present=False).condition is not None
    assert restore.variant_for(artifact_present=False).condition.presence is OptionPresence.ABSENT
    assert restore.variant_for(artifact_present=True).condition is not None
    assert restore.variant_for(artifact_present=True).condition.presence is OptionPresence.PRESENT
    with pytest.raises(MachineSecretContractError, match="requires the public artifact-presence selector"):
        restore.variant_for()


def test_registration_accepts_only_the_declared_secret_model_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(contract_module, "_REGISTERED_MODELS", {})

    class LoginPayload(BaseModel):
        model_config = ConfigDict(extra="forbid", frozen=True)
        passphrase: SecretStr

    assert register_machine_secret_payload_model("config.login", "passphrase", LoginPayload) is LoginPayload
    assert register_machine_secret_payload_model("config.login", "passphrase", LoginPayload) is LoginPayload

    class WrongName(BaseModel):
        wrong: SecretStr

    with pytest.raises(MachineSecretContractError, match="do not match"):
        register_machine_secret_payload_model("config.login", "passphrase", WrongName)

    class PublicString(BaseModel):
        passphrase: str

    with pytest.raises(MachineSecretContractError, match="must use SecretStr"):
        register_machine_secret_payload_model("config.login", "passphrase", PublicString)


def test_commands_outside_the_inventory_are_refused() -> None:
    with pytest.raises(MachineSecretContractError, match="outside the scalar-secret command inventory"):
        machine_secret_contract("config.auth.certificate.register")
