"""Project operator input contracts from the immutable command-spec graph."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, Final, cast

from pydantic import BaseModel, ConfigDict, Field

from ._command_schema import CommandRegistrationMetadata, MachineSecretPayloadMetadata, command_registration_metadata

_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class VerbParamKind(StrEnum):
    ARGUMENT = "argument"
    OPTION = "option"


class JsonType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"


class VerbLeafKind(StrEnum):
    COMMAND = "command"
    CALLBACK = "callback"


class VerbParameter(BaseModel):
    model_config = _FROZEN
    name: str = Field(min_length=1)
    kind: VerbParamKind
    cli_flag: str = ""
    off_flag: str = ""
    json_type: JsonType
    required: bool
    is_flag: bool
    multiple: bool
    choices: tuple[str, ...] = ()
    default: bool | int | float | str | list[Any] | None = None
    help: str = ""

    def property_schema(self) -> dict[str, Any]:
        scalar: dict[str, Any] = {"type": self.json_type.value}
        if self.choices:
            scalar["enum"] = list(self.choices)
        if self.help:
            scalar["description"] = self.help
        schema: dict[str, Any] = {"type": "array", "items": scalar} if self.multiple else scalar
        if self.default is not None:
            schema["default"] = self.default
        return schema


class ResolvedVerbLeaf(BaseModel):
    model_config = _FROZEN
    subject_leaf_key: str = Field(min_length=1)
    cli_path: tuple[str, ...]
    alias_paths: tuple[tuple[str, ...], ...] = ()
    kind: VerbLeafKind


class VerbLeafResolutionFailure(BaseModel):
    model_config = _FROZEN
    subject_leaf_key: str = Field(min_length=1)
    attempted_cli_path: tuple[str, ...]
    resolved_cli_path: tuple[str, ...] = ()
    reason: str = Field(min_length=1)


class VerbInputSchema(BaseModel):
    model_config = _FROZEN
    command_key: str = Field(min_length=1)
    cli_path: tuple[str, ...]
    parameters: tuple[VerbParameter, ...] = ()
    machine_secret_payloads: tuple[MachineSecretPayloadMetadata, ...] = ()
    help: str = ""

    @property
    def resolved_leaf(self) -> ResolvedVerbLeaf:
        return ResolvedVerbLeaf(subject_leaf_key=self.command_key, cli_path=self.cli_path, kind=VerbLeafKind.COMMAND)

    @property
    def required_inputs(self) -> tuple[VerbParameter, ...]:
        return tuple(parameter for parameter in self.parameters if parameter.required)

    def json_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {p.name: p.property_schema() for p in self.parameters},
            "required": [p.name for p in self.parameters if p.required],
            "additionalProperties": False,
        }


class SchemaResolutionError(RuntimeError):
    def __init__(self, failures: tuple[VerbLeafResolutionFailure, ...]) -> None:
        self.failures = failures
        super().__init__("; ".join(f"{item.subject_leaf_key}: {item.reason}" for item in failures))


DECLARED_UNIMPLEMENTED_SURFACES: Final[Mapping[str, str]] = {}


def _rows() -> dict[str, CommandRegistrationMetadata]:
    return {row.command: row for row in command_registration_metadata()}


def cli_path_for_command_key(command_key: str) -> tuple[str, ...]:
    row = _rows().get(command_key)
    if row is None or row.cli_path is None:
        raise LookupError(f"unknown command schema identity: {command_key}")
    return row.cli_path


def is_exposable_command(command_key: str) -> bool:
    return command_key in _rows()


def assert_schema_coverage(resolution_errors: tuple[VerbLeafResolutionFailure, ...]) -> None:
    if resolution_errors:
        raise SchemaResolutionError(resolution_errors)


def build_verb_input_schemas(command_keys: tuple[str, ...]) -> dict[str, VerbInputSchema]:
    rows = _rows()
    schemas: dict[str, VerbInputSchema] = {}
    failures: list[VerbLeafResolutionFailure] = []
    for key in command_keys:
        row = rows.get(key)
        if row is None or row.cli_path is None:
            failures.append(
                VerbLeafResolutionFailure(
                    subject_leaf_key=key, attempted_cli_path=(), reason="no CommandSpec result-schema identity"
                )
            )
            continue
        parameters = next((values for _, values in row.parameters_by_language if values is not None), ())
        schemas[key] = VerbInputSchema(
            command_key=key,
            cli_path=row.cli_path,
            parameters=tuple(
                VerbParameter(
                    name=p.name,
                    kind=VerbParamKind(p.kind),
                    cli_flag=p.cli_flag,
                    off_flag=p.off_flag,
                    json_type=JsonType(p.json_type),
                    required=p.required,
                    is_flag=p.is_flag,
                    multiple=p.multiple,
                    choices=p.choices,
                    default=list(p.default) if isinstance(p.default, tuple) else p.default,
                    help=p.help,
                )
                for p in parameters
            ),
            machine_secret_payloads=row.machine_secret_payloads,
            help=next((value for _, value in row.help_by_language), ""),
        )
    assert_schema_coverage(tuple(failures))
    return schemas


def _build_materialized_verb_input_schemas(command_keys: tuple[str, ...]) -> dict[str, VerbInputSchema]:
    return build_verb_input_schemas(command_keys)


def cli_argv_for(schema: VerbInputSchema, arguments: dict[str, object]) -> list[str]:
    positional: list[str] = []
    options: list[str] = []
    for parameter in schema.parameters:
        if parameter.name not in arguments:
            continue
        value = arguments[parameter.name]
        if parameter.kind is VerbParamKind.ARGUMENT:
            positional.extend(str(item) for item in cast(Sequence[object], value)) if parameter.multiple and isinstance(
                value, list | tuple
            ) else positional.append(str(value))
        elif parameter.is_flag:
            if value:
                options.append(parameter.cli_flag)
            elif parameter.off_flag:
                options.append(parameter.off_flag)
        elif parameter.multiple and isinstance(value, list | tuple):
            for item in cast(Sequence[object], value):
                options.extend((parameter.cli_flag, str(item)))
        else:
            options.extend((parameter.cli_flag, str(value)))
    return ["--format", "json", *schema.cli_path, *positional, *options]


__all__ = [
    "DECLARED_UNIMPLEMENTED_SURFACES",
    "JsonType",
    "ResolvedVerbLeaf",
    "SchemaResolutionError",
    "VerbInputSchema",
    "VerbLeafKind",
    "VerbLeafResolutionFailure",
    "VerbParamKind",
    "VerbParameter",
    "assert_schema_coverage",
    "build_verb_input_schemas",
    "cli_argv_for",
    "cli_path_for_command_key",
    "is_exposable_command",
]
