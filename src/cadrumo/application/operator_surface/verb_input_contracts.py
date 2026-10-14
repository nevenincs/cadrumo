"""Validated verb-input records an outer command adapter supplies to the application.

The command graph projects each executable leaf onto a :class:`VerbInputSchema`;
the surface manifest, the reconciliation projection and automation harnesses consume
it. The plain declaration vocabulary these records reuse lives in
:mod:`.command_ports`, which the command graph imports at startup and which
therefore carries no pydantic model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from cadrumo_client.contracts.command_ports import (
    JsonType,
    MachineSecretPayloadMetadata,
    ParameterKind,
    ProfileAuthenticationContractMetadata,
    ProfileAuthenticationPostureValue,
)

from ...core.errors.hierarchy import CadrumoError
from ...core.type_guards import is_object_list_or_tuple

#: ``defer_build`` keeps these records out of the import cost of their first
#: importer: pydantic builds each on its first use.
_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid", defer_build=True)


class RecoveryHandoffContract(BaseModel):
    """Value-free machine discovery for a two-way secret handoff."""

    model_config = _FROZEN

    handoff_option: str
    handoff_direction: Literal["write"]
    verification_option: str
    verification_direction: Literal["read"]
    required_together: bool
    json_fields: tuple[str, ...]
    maximum_bytes: int
    strict_utf8_object: bool
    duplicate_extra_missing_fields_refused: bool
    descriptors_closed: bool
    reserved_descriptors: tuple[int, ...]
    descriptors_must_differ: bool
    collides_with: tuple[str, ...]
    windows_handle_bootstrap: str


class VerbLeafKind(StrEnum):
    """Kind of resolved outer command leaf."""

    COMMAND = "command"
    CALLBACK = "callback"


class VerbParameter(BaseModel):
    """One input parameter in an application-owned verb schema."""

    model_config = _FROZEN

    name: str = Field(min_length=1)
    kind: ParameterKind
    cli_flag: str = ""
    off_flag: str = ""
    json_type: JsonType
    required: bool
    is_flag: bool
    multiple: bool
    choices: tuple[str, ...] = ()
    default: bool | int | float | str | list[Any] | None = None
    help: str = ""


class ResolvedVerbLeaf(BaseModel):
    """One command key resolved to its canonical outer path."""

    model_config = _FROZEN

    subject_leaf_key: str = Field(min_length=1)
    cli_path: tuple[str, ...]
    alias_paths: tuple[tuple[str, ...], ...] = ()
    kind: VerbLeafKind


class VerbLeafResolutionFailure(BaseModel):
    """One failed command-key-to-schema resolution."""

    model_config = _FROZEN

    subject_leaf_key: str = Field(min_length=1)
    attempted_cli_path: tuple[str, ...]
    resolved_cli_path: tuple[str, ...] = ()
    reason: str = Field(min_length=1)


class VerbInputSchema(BaseModel):
    """Application-owned input schema supplied by an outer command adapter."""

    model_config = _FROZEN

    command_key: str = Field(min_length=1)
    cli_path: tuple[str, ...]
    parameters: tuple[VerbParameter, ...] = ()
    machine_secret_payloads: tuple[MachineSecretPayloadMetadata, ...] = ()
    recovery_handoff_contract: RecoveryHandoffContract | None = None
    profile_authentication: ProfileAuthenticationPostureValue
    profile_authentication_contract: ProfileAuthenticationContractMetadata
    help: str = ""

    @property
    def resolved_leaf(self) -> ResolvedVerbLeaf:
        """Return the canonical command-leaf identity represented by this schema."""
        return ResolvedVerbLeaf(subject_leaf_key=self.command_key, cli_path=self.cli_path, kind=VerbLeafKind.COMMAND)

    @property
    def required_inputs(self) -> tuple[VerbParameter, ...]:
        """Return parameters that must be supplied by a caller."""
        return tuple(parameter for parameter in self.parameters if parameter.required)


class SchemaResolutionError(CadrumoError):
    """Raised by an outer adapter when its live schema projection is incomplete."""

    def __init__(self, failures: tuple[VerbLeafResolutionFailure, ...]) -> None:
        """Store every unresolved leaf so an adapter can report them together."""
        self.failures = failures
        super().__init__("; ".join(f"{item.subject_leaf_key}: {item.reason}" for item in failures))


def _parameter_values(parameter: VerbParameter, value: object) -> Sequence[object]:
    """Preserve repeated list/tuple inputs while treating other values as scalar."""
    return value if parameter.multiple and is_object_list_or_tuple(value) else (value,)


def _option_tokens(parameter: VerbParameter, value: object, values: Sequence[object]) -> tuple[str, ...]:
    """Encode one option, flag or repeated option without changing token order."""
    if parameter.is_flag:
        if value:
            return (parameter.cli_flag,)
        return (parameter.off_flag,) if parameter.off_flag else ()
    if parameter.multiple:
        return tuple(token for item in values for token in (parameter.cli_flag, str(item)))
    return parameter.cli_flag, str(value)


def _parameter_tokens(parameter: VerbParameter, value: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return positional and option tokens for one supplied parameter."""
    values = _parameter_values(parameter, value)
    if parameter.kind is ParameterKind.ARGUMENT:
        return tuple(str(item) for item in values), ()
    return (), _option_tokens(parameter, value, values)


def cli_argv_for(schema: VerbInputSchema, arguments: Mapping[str, object]) -> list[str]:
    """Encode named schema arguments into the canonical command argv tail."""
    positional: list[str] = []
    options: list[str] = []
    for parameter in schema.parameters:
        if parameter.name not in arguments:
            continue
        parameter_positional, parameter_options = _parameter_tokens(parameter, arguments[parameter.name])
        positional.extend(parameter_positional)
        options.extend(parameter_options)
    return ["--format", "json", *schema.cli_path, *positional, *options]


def assert_schema_coverage(resolution_errors: tuple[VerbLeafResolutionFailure, ...]) -> None:
    """Raise one typed error when an outer adapter cannot project a leaf."""
    if resolution_errors:
        raise SchemaResolutionError(resolution_errors)


__all__ = [
    "RecoveryHandoffContract",
    "ResolvedVerbLeaf",
    "SchemaResolutionError",
    "VerbInputSchema",
    "VerbLeafKind",
    "VerbLeafResolutionFailure",
    "VerbParameter",
    "assert_schema_coverage",
    "cli_argv_for",
]
