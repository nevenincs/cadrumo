"""Unit contract for the closed scalar-secret CLI inventory."""

from __future__ import annotations

import subprocess
import sys

import pytest
from pydantic import BaseModel, SecretStr

from .. import _machine_secret_contract as contract_module
from .._config._secure_input import MachineSecretPayload
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
    password_condition = restore.variant_for(artifact_present=False).condition
    recovery_condition = restore.variant_for(artifact_present=True).condition
    assert password_condition is not None
    assert password_condition.presence is OptionPresence.ABSENT
    assert recovery_condition is not None
    assert recovery_condition.presence is OptionPresence.PRESENT
    with pytest.raises(MachineSecretContractError, match="requires the public artifact-presence selector"):
        restore.variant_for()


def test_registration_accepts_only_the_declared_secret_model_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(contract_module, "_REGISTERED_MODELS", {})

    class LoginPayload(MachineSecretPayload):
        passphrase: SecretStr

    assert register_machine_secret_payload_model("config.login", "passphrase", LoginPayload) is LoginPayload
    assert register_machine_secret_payload_model("config.login", "passphrase", LoginPayload) is LoginPayload

    class WrongName(BaseModel):
        wrong: SecretStr

    with pytest.raises(MachineSecretContractError, match="must inherit MachineSecretPayload"):
        register_machine_secret_payload_model("config.login", "passphrase", WrongName)

    class CanonicalWrongName(MachineSecretPayload):
        wrong: SecretStr

    with pytest.raises(MachineSecretContractError, match="do not match"):
        register_machine_secret_payload_model("config.login", "passphrase", CanonicalWrongName)

    class PublicString(MachineSecretPayload):
        passphrase: str

    with pytest.raises(MachineSecretContractError, match="must use SecretStr"):
        register_machine_secret_payload_model("config.login", "passphrase", PublicString)


def test_commands_outside_the_inventory_are_refused() -> None:
    with pytest.raises(MachineSecretContractError, match="outside the scalar-secret command inventory"):
        machine_secret_contract("config.auth.certificate.register")


def test_inventory_import_does_not_eagerly_load_secure_input() -> None:
    probe = (
        "import sys; import cadrumo.entrypoints.cli._machine_secret_contract; "
        "print('cadrumo.entrypoints.cli._config._secure_input' in sys.modules)"
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and constant import-hygiene probe
        [sys.executable, "-I", "-c", probe],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=True,
    )

    assert completed.stdout.strip() == "False"
