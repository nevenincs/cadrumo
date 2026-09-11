"""Process-backed adapter for the application-owned command-surface ports.

The retained harness is an independent outer composition root.  It consumes
the inward command contracts, but it does not import the product's CLI module.
The installed ``aeat`` executable exposes one closed JSON projection of the
authoritative command graph; this adapter launches that process once and
materialises the application port records locally.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType
from typing import Any, ClassVar

from pydantic import ConfigDict

from cadrumo.application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from cadrumo.application.operator_actions.models import PreconditionVerdict
from cadrumo.application.operator_actions.ports import (
    PreconditionActionResolutionPort,
    project_precondition_action,
)
from cadrumo.application.operator_surface.command_ports import (
    CommandCapabilityClass,
    CommandExecutionPolicy,
    CommandNodeKind,
    CommandParameterMetadata,
    CommandPolicyMetadata,
    CommandRegistrationMetadata,
    CommandRegistrationProjection,
    CommandSurfacePort,
    JsonType,
    LiveNodeRegistrationMetadata,
    MachineSecretFieldMetadata,
    MachineSecretPayloadMetadata,
    MachineSecretPresence,
    MachineSecretVariantConditionMetadata,
    ParameterKind,
    ProfileAuthenticationContractMetadata,
    ProfileAuthenticationPosture,
    SchemaResolutionError,
    VerbInputSchema,
    VerbLeafResolutionFailure,
)
from cadrumo.application.operator_surface.manifest import CommandSchemaRef
from cadrumo.core.json_contract import OutputSchema, ResolvedActionReference
from cadrumo.core.operator_action_enums import ActionArgumentStatus


class _WireOutputSchema(OutputSchema):
    """A strict envelope result carrier backed by a graph-projected schema."""

    model_config = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="allow")
    _wire_schema: ClassVar[dict[str, Any]] = {}

    @classmethod
    def model_json_schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Return the exact result JSON Schema projected by the CLI process."""
        return copy.deepcopy(cls._wire_schema)


def _wire_schema_type(command: str, schema: dict[str, Any]) -> type[OutputSchema]:
    suffix = hashlib.sha256(command.encode("utf-8")).hexdigest()[:16]
    return type(
        f"CommandResult_{suffix}",
        (_WireOutputSchema,),
        {"__module__": __name__, "_wire_schema": copy.deepcopy(schema)},
    )


def _cli_executable() -> str:
    executable = os.environ.get("CADRUMO_CLI_EXECUTABLE") or shutil.which("aeat")
    if not executable:
        raise RuntimeError("the installed aeat executable is required for the command-surface port")
    return executable


def _load_wire_manifest() -> dict[str, Any]:
    """Read the closed command-surface projection from the installed CLI."""
    completed = subprocess.run(  # noqa: S603 - fixed console executable and literal argument
        [_cli_executable(), "--cadrumo-command-surface"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "the command-surface process returned no diagnostic"
        raise RuntimeError(f"command-surface process failed with exit code {completed.returncode}: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("command-surface process returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise RuntimeError("command-surface process returned a non-object projection")
    return payload


def _machine_secret_field(payload: dict[str, Any]) -> MachineSecretFieldMetadata:
    return MachineSecretFieldMetadata(name=str(payload["name"]), json_type="string")


def _machine_secret_payload(payload: dict[str, Any]) -> MachineSecretPayloadMetadata:
    condition = payload.get("condition")
    return MachineSecretPayloadMetadata(
        key=str(payload["key"]),
        fields=tuple(_machine_secret_field(item) for item in payload["fields"]),
        condition=(
            MachineSecretVariantConditionMetadata(
                option_name=str(condition["option_name"]),
                presence=MachineSecretPresence(str(condition["presence"])),
            )
            if condition is not None
            else None
        ),
        maximum_bytes=int(payload["maximum_bytes"]),
        same_scope_exclusive=bool(payload["same_scope_exclusive"]),
        duplicate_keys_forbidden=bool(payload["duplicate_keys_forbidden"]),
        extra_fields_forbidden=bool(payload["extra_fields_forbidden"]),
    )


def _profile_authentication_contract(payload: dict[str, Any]) -> ProfileAuthenticationContractMetadata:
    return ProfileAuthenticationContractMetadata(
        fields=tuple(_machine_secret_field(item) for item in payload["fields"]),
        maximum_bytes=int(payload["maximum_bytes"]),
        same_scope_exclusive=bool(payload["same_scope_exclusive"]),
        stdin_exclusive_across_scopes=bool(payload["stdin_exclusive_across_scopes"]),
        descriptors_must_differ_across_scopes=bool(payload["descriptors_must_differ_across_scopes"]),
        duplicate_keys_forbidden=bool(payload["duplicate_keys_forbidden"]),
        extra_fields_forbidden=bool(payload["extra_fields_forbidden"]),
    )


def _command_parameter(payload: dict[str, Any]) -> CommandParameterMetadata:
    default = payload.get("default")
    return CommandParameterMetadata(
        name=str(payload["name"]),
        kind=ParameterKind(str(payload["kind"])),
        cli_flag=str(payload.get("cli_flag", "")),
        off_flag=str(payload.get("off_flag", "")),
        json_type=JsonType(str(payload["json_type"])),
        required=bool(payload["required"]),
        is_flag=bool(payload["is_flag"]),
        multiple=bool(payload["multiple"]),
        choices=tuple(str(item) for item in payload.get("choices", ())),
        default=tuple(default) if isinstance(default, list) else default,
        help=str(payload.get("help", "")),
    )


def _command_policy_metadata(payload: dict[str, Any] | None) -> CommandPolicyMetadata | None:
    if payload is None:
        return None
    return CommandPolicyMetadata(
        capabilities=frozenset(str(item) for item in payload["capabilities"]),
        side_effects=frozenset(str(item) for item in payload["side_effects"]),
        performance=str(payload["performance"]),
        write_route=str(payload["write_route"]),
        destructive=bool(payload["destructive"]),
        handoff=bool(payload["handoff"]),
        live_write=bool(payload["live_write"]),
    )


def _registration_projection(payload: dict[str, Any]) -> CommandRegistrationProjection:
    commands: list[CommandRegistrationMetadata] = []
    for row in payload["commands"]:
        parameters: list[tuple[str, tuple[CommandParameterMetadata, ...] | None]] = []
        for language, values in row["parameters_by_language"]:
            parameters.append(
                (
                    str(language),
                    None if values is None else tuple(_command_parameter(item) for item in values),
                )
            )
        commands.append(
            CommandRegistrationMetadata(
                command=str(row["command"]),
                schema_name=str(row["schema_name"]),
                schema_owner=str(row["schema_owner"]),
                schema_source_sha256=str(row["schema_source_sha256"]),
                cli_path=None if row["cli_path"] is None else tuple(str(item) for item in row["cli_path"]),
                parameters_by_language=tuple(parameters),
                help_by_language=tuple((str(language), str(value)) for language, value in row["help_by_language"]),
                hidden=row["hidden"],
                policy=_command_policy_metadata(row["policy"]),
                handler_owner=row["handler_owner"],
                source_sha256=row["source_sha256"],
                machine_secret_payloads=tuple(
                    _machine_secret_payload(item) for item in row.get("machine_secret_payloads", ())
                ),
                profile_authentication=ProfileAuthenticationPosture(
                    str(row.get("profile_authentication", ProfileAuthenticationPosture.NOT_APPLICABLE))
                ),
            )
        )

    nodes = tuple(
        LiveNodeRegistrationMetadata(
            path=tuple(str(item) for item in row["path"]),
            kind=CommandNodeKind(str(row["kind"])),
            loader_owner=row["loader_owner"],
            handler_owner=str(row["handler_owner"]),
            source_sha256=row["source_sha256"],
            policy=_command_policy_metadata(row["policy"]),
        )
        for row in payload["nodes"]
    )
    return CommandRegistrationProjection(
        commands=tuple(commands),
        nodes=nodes,
        profile_authentication_contract=_profile_authentication_contract(payload["profile_authentication_contract"]),
    )


@dataclass(frozen=True, slots=True)
class CommandSurfaceSnapshot(CommandSurfacePort):
    """One immutable process projection implementing the inward command port."""

    _schema_refs: tuple[CommandSchemaRef, ...]
    _schema_types: MappingProxyType[str, type[OutputSchema]]
    _input_schemas: MappingProxyType[str, VerbInputSchema]
    _policies: MappingProxyType[str, CommandExecutionPolicy]
    _search_terms: MappingProxyType[str, tuple[str, ...]]
    _global_flags: frozenset[str]
    _exposable: frozenset[str]
    _registration: CommandRegistrationProjection

    def command_schema_refs(self) -> tuple[CommandSchemaRef, ...]:
        return self._schema_refs

    def command_schema_type(self, command: str) -> type[OutputSchema]:
        try:
            return self._schema_types[command]
        except KeyError as error:
            raise LookupError(f"unknown command schema identity: {command}") from error

    def command_schema_types(self) -> MappingProxyType[str, type[OutputSchema]]:
        return self._schema_types

    def command_registration_projection(self) -> CommandRegistrationProjection:
        return self._registration

    def build_verb_input_schemas(self, command_keys: tuple[str, ...]) -> dict[str, VerbInputSchema]:
        missing = tuple(key for key in command_keys if key not in self._input_schemas)
        if missing:
            raise SchemaResolutionError(
                tuple(
                    VerbLeafResolutionFailure(
                        subject_leaf_key=key,
                        attempted_cli_path=(),
                        reason="no command-surface input schema",
                    )
                    for key in missing
                )
            )
        return {key: self._input_schemas[key] for key in command_keys}

    def cli_path_for_command_key(self, command_key: str) -> tuple[str, ...]:
        try:
            return self._input_schemas[command_key].cli_path
        except KeyError as error:
            raise LookupError(f"unknown command schema identity: {command_key}") from error

    def is_exposable_command(self, command_key: str) -> bool:
        return command_key in self._exposable

    def command_search_terms(self, command_key: str) -> tuple[str, ...]:
        try:
            return self._search_terms[command_key]
        except KeyError as error:
            raise LookupError(f"unknown command schema identity: {command_key}") from error

    def global_flags(self) -> frozenset[str]:
        return self._global_flags

    def command_execution_policy_for_cli_path(self, cli_path: tuple[str, ...]) -> CommandExecutionPolicy:
        for key, schema in self._input_schemas.items():
            if schema.cli_path == cli_path:
                return self._policies[key]
        raise LookupError(f"unknown command spec path: {' '.join(cli_path)}")


def _build_snapshot(payload: dict[str, Any]) -> CommandSurfaceSnapshot:
    references = tuple(CommandSchemaRef.model_validate_json(json.dumps(item)) for item in payload["command_schemas"])
    input_schemas = {
        key: VerbInputSchema.model_validate_json(json.dumps(value)) for key, value in payload["input_schemas"].items()
    }
    schema_types = {key: _wire_schema_type(key, value) for key, value in payload["result_schemas"].items()}
    policies = {
        key: CommandExecutionPolicy(
            classification=CommandCapabilityClass(
                capabilities=frozenset(str(item) for item in value["capabilities"]),
                side_effects=frozenset(str(item) for item in value["side_effects"]),
                performance=str(value["performance"]),
            ),
            write_route=str(value["write_route"]),
            destructive=bool(value["destructive"]),
            handoff=bool(value["handoff"]),
            live_write=bool(value["live_write"]),
        )
        for key, value in payload["policies"].items()
    }
    return CommandSurfaceSnapshot(
        _schema_refs=references,
        _schema_types=MappingProxyType(schema_types),
        _input_schemas=MappingProxyType(input_schemas),
        _policies=MappingProxyType(policies),
        _search_terms=MappingProxyType(
            {key: tuple(str(item) for item in value) for key, value in payload["search_terms"].items()}
        ),
        _global_flags=frozenset(str(item) for item in payload["global_flags"]),
        _exposable=frozenset(str(item) for item in payload["exposable_commands"]),
        _registration=_registration_projection(payload["registration_projection"]),
    )


@cache
def command_surface() -> CommandSurfaceSnapshot:
    """Return the one process-backed command-surface projection for this server."""
    return _build_snapshot(_load_wire_manifest())


class _PreconditionResolver(PreconditionActionResolutionPort):
    """Resolve application actions against the process-projected input surface."""

    def __init__(self, surface: CommandSurfaceSnapshot) -> None:
        self._surface = surface

    def resolve_action_reference(self, verdict: PreconditionVerdict) -> ResolvedActionReference | None:
        if verdict.action is None:
            return None
        declaration = OPERATOR_ACTION_CATALOGUE.lookup(str(verdict.action.action_id))
        schema = self._surface.build_verb_input_schemas((declaration.target_command_key,)).get(
            declaration.target_command_key
        )
        if schema is None:
            raise LookupError(f"action target has no live input schema: {declaration.target_command_key}")
        specifications_by_name: dict[str, list[object]] = {}
        for specification in declaration.argument_specifications:
            specifications_by_name.setdefault(specification.argument_name, []).append(specification)
        for binding in verdict.argument_bindings:
            if binding.status is ActionArgumentStatus.MISSING:
                continue
            matching = tuple(
                specification
                for specification in specifications_by_name.get(binding.argument_name, ())
                if binding.source is specification.source
                and binding.source_key == specification.source_key
                and binding.source_evidence_id == specification.source_evidence_id
            )
            if len(matching) != 1:
                raise ValueError(f"action argument source contradicts catalogue: {binding.argument_name}")
        return ResolvedActionReference(
            action_id=declaration.action_id,
            target_command_key=declaration.target_command_key,
            cli_path=schema.cli_path,
        )


def resolve_precondition_action(verdict: PreconditionVerdict):
    """Project an application verdict through the retained harness surface."""
    surface = command_surface()
    return project_precondition_action(verdict, resolver=_PreconditionResolver(surface))


__all__ = ["CommandSurfaceSnapshot", "command_surface", "resolve_precondition_action"]
