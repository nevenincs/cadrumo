"""Closed, value-free contract for scalar-secret CLI inputs.

This module is the inventory authority for commands that may consume the
canonical machine-secret channels.  It describes only public command identity,
payload field names, JSON scalar types, and the public option presence that
selects a conditional payload.  Secret values, defaults, examples, and
invocation-derived facts do not belong here.

Command modules register their strict payload models against these declarations
when imported.  Registration checks the model shape without importing command
modules from this authority, keeping the inventory usable by metadata and
conformance code without creating a CLI import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, SecretStr


class MachineSecretContractError(RuntimeError):
    """Raised when a command or payload model violates the closed contract."""


class MachineSecretJsonType(StrEnum):
    """Safe JSON scalar types publishable for secret payload fields."""

    STRING = "string"


class OptionPresence(StrEnum):
    """Presence rule selecting a conditional payload variant."""

    ABSENT = "absent"
    PRESENT = "present"


@dataclass(frozen=True, slots=True)
class MachineSecretField:
    """One value-free field declaration in a strict secret JSON object."""

    name: str
    json_type: MachineSecretJsonType


@dataclass(frozen=True, slots=True)
class MachineSecretVariantCondition:
    """Public CLI option-presence condition selecting one payload variant."""

    option_name: str
    presence: OptionPresence


@dataclass(frozen=True, slots=True)
class MachineSecretPayloadVariant:
    """One strict payload shape for a command."""

    key: str
    fields: tuple[MachineSecretField, ...]
    condition: MachineSecretVariantCondition | None = None


@dataclass(frozen=True, slots=True)
class MachineSecretCommandContract:
    """Machine-secret declaration for exactly one canonical CLI leaf."""

    command_key: str
    cli_path: tuple[str, ...]
    variants: tuple[MachineSecretPayloadVariant, ...]

    def variant_for(self, *, artifact_present: bool | None = None) -> MachineSecretPayloadVariant:
        """Resolve the sole or artifact-selected payload variant.

        ``artifact_present`` is accepted only by a conditional contract.  It is
        a public invocation-shape fact; no secret value participates in variant
        selection.
        """
        if len(self.variants) == 1:
            if artifact_present is not None:
                raise MachineSecretContractError(
                    f"{self.command_key!r} has no conditional machine-secret payload",
                )
            return self.variants[0]
        if artifact_present is None:
            raise MachineSecretContractError(
                f"{self.command_key!r} requires the public artifact-presence selector",
            )
        wanted = OptionPresence.PRESENT if artifact_present else OptionPresence.ABSENT
        matches = tuple(
            variant
            for variant in self.variants
            if variant.condition is not None
            and variant.condition.option_name == "artifact"
            and variant.condition.presence is wanted
        )
        if len(matches) != 1:
            raise MachineSecretContractError(
                f"{self.command_key!r} has no unique payload for artifact {wanted.value}",
            )
        return matches[0]


def _field(name: str) -> MachineSecretField:
    return MachineSecretField(name=name, json_type=MachineSecretJsonType.STRING)


def _variant(
    key: str,
    *field_names: str,
    condition: MachineSecretVariantCondition | None = None,
) -> MachineSecretPayloadVariant:
    return MachineSecretPayloadVariant(
        key=key,
        fields=tuple(_field(name) for name in field_names),
        condition=condition,
    )


_ARTIFACT_ABSENT: Final = MachineSecretVariantCondition(
    option_name="artifact",
    presence=OptionPresence.ABSENT,
)
_ARTIFACT_PRESENT: Final = MachineSecretVariantCondition(
    option_name="artifact",
    presence=OptionPresence.PRESENT,
)

MACHINE_SECRET_COMMANDS: Final[tuple[MachineSecretCommandContract, ...]] = (
    MachineSecretCommandContract(
        command_key="config.login",
        cli_path=("config", "login"),
        variants=(_variant("passphrase", "passphrase"),),
    ),
    MachineSecretCommandContract(
        command_key="config.profile.create",
        cli_path=("config", "profile", "create"),
        variants=(_variant("passphrase", "passphrase", "passphrase_confirmation"),),
    ),
    MachineSecretCommandContract(
        command_key="config.passphrase.change",
        cli_path=("config", "passphrase", "change"),
        variants=(
            _variant(
                "rotation",
                "current_passphrase",
                "new_passphrase",
                "new_passphrase_confirmation",
            ),
        ),
    ),
    MachineSecretCommandContract(
        command_key="config.profile.restore",
        cli_path=("config", "profile", "restore"),
        variants=(
            _variant("passphrase", "passphrase", condition=_ARTIFACT_ABSENT),
            _variant("recovery", "recovery_secret", condition=_ARTIFACT_PRESENT),
        ),
    ),
    MachineSecretCommandContract(
        command_key="config.auth.certificate.secret.set",
        cli_path=("config", "auth", "certificate", "secret", "set"),
        variants=(_variant("certificate", "certificate_passphrase"),),
    ),
)

_CONTRACT_BY_COMMAND: Final = MappingProxyType(
    {contract.command_key: contract for contract in MACHINE_SECRET_COMMANDS},
)
_REGISTERED_MODELS: dict[tuple[str, str], type[BaseModel]] = {}


def machine_secret_contract(command_key: str) -> MachineSecretCommandContract:
    """Return the declared contract for ``command_key`` or refuse outsiders."""
    try:
        return _CONTRACT_BY_COMMAND[command_key]
    except KeyError as exc:
        raise MachineSecretContractError(
            f"{command_key!r} is outside the scalar-secret command inventory",
        ) from exc


def register_machine_secret_payload_model(
    command_key: str,
    variant_key: str,
    model: type[BaseModel],
) -> type[BaseModel]:
    """Register one strict command-local payload model after shape validation.

    Registration is idempotent for the same model identity.  A command module
    cannot register an undeclared variant, fields with a different order or
    name, non-``SecretStr`` fields, or a competing model for an occupied slot.
    The returned model allows direct use as a class decorator target.
    """
    contract = machine_secret_contract(command_key)
    variants = {variant.key: variant for variant in contract.variants}
    try:
        variant = variants[variant_key]
    except KeyError as exc:
        raise MachineSecretContractError(
            f"{variant_key!r} is not a declared payload variant for {command_key!r}",
        ) from exc

    declared_names = tuple(field.name for field in variant.fields)
    actual_names = tuple(model.model_fields)
    if actual_names != declared_names:
        raise MachineSecretContractError(
            f"payload fields for {command_key!r}/{variant_key!r} do not match the declared contract",
        )
    if any(field.annotation is not SecretStr for field in model.model_fields.values()):
        raise MachineSecretContractError(
            f"payload fields for {command_key!r}/{variant_key!r} must use SecretStr",
        )

    slot = (command_key, variant_key)
    incumbent = _REGISTERED_MODELS.get(slot)
    if incumbent is not None and incumbent is not model:
        raise MachineSecretContractError(
            f"payload model already registered for {command_key!r}/{variant_key!r}",
        )
    _REGISTERED_MODELS[slot] = model
    return model


def registered_machine_secret_payload_models() -> MappingProxyType[tuple[str, str], type[BaseModel]]:
    """Return a read-only snapshot of command-local payload registrations."""
    return MappingProxyType(dict(_REGISTERED_MODELS))


def missing_machine_secret_payload_models() -> tuple[tuple[str, str], ...]:
    """Return declared command/variant slots not yet registered by live modules."""
    expected = (
        (contract.command_key, variant.key)
        for contract in MACHINE_SECRET_COMMANDS
        for variant in contract.variants
    )
    return tuple(slot for slot in expected if slot not in _REGISTERED_MODELS)


__all__ = [
    "MACHINE_SECRET_COMMANDS",
    "MachineSecretCommandContract",
    "MachineSecretContractError",
    "MachineSecretField",
    "MachineSecretJsonType",
    "MachineSecretPayloadVariant",
    "MachineSecretVariantCondition",
    "OptionPresence",
    "machine_secret_contract",
    "missing_machine_secret_payload_models",
    "register_machine_secret_payload_model",
    "registered_machine_secret_payload_models",
]
