"""Project operator input contracts from the immutable command-spec graph."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...application.operator_surface.command_ports import (
    CommandRegistrationMetadata,
    JsonType,
    ParameterKind,
    RecoveryHandoffContract,
    ResolvedVerbLeaf,
    SchemaResolutionError,
    VerbInputSchema,
    VerbLeafKind,
    VerbLeafResolutionFailure,
    VerbParameter,
    assert_schema_coverage,
    cli_argv_for,
)
from .command_schema import command_registration_metadata, command_registration_projection

if TYPE_CHECKING:
    from .command_spec import CommandSpec


def _rows() -> dict[str, CommandRegistrationMetadata]:
    return {row.command: row for row in command_registration_metadata()}


def cli_path_for_command_key(command_key: str) -> tuple[str, ...]:
    row = _rows().get(command_key)
    if row is None or row.cli_path is None:
        raise LookupError(f"unknown command schema identity: {command_key}")
    return row.cli_path


def is_exposable_command(command_key: str) -> bool:
    from .command_spec import BindingState
    from .command_specs import COMMAND_GRAPH

    spec = COMMAND_GRAPH.by_schema_identity().get(command_key)
    return (
        spec is not None
        and spec.parent_key not in {None, "root"}
        and spec.handler is not None
        and spec.handler.state is BindingState.TARGET
        and (spec.kind == "leaf" or spec.invocation.invoke_without_command)
    )


def assert_schema_coverage(resolution_errors: tuple[VerbLeafResolutionFailure, ...]) -> None:
    if resolution_errors:
        raise SchemaResolutionError(resolution_errors)


def project_recovery_handoff_contract(spec: CommandSpec) -> RecoveryHandoffContract | None:
    """Project one command's validated recovery protocol into discovery metadata."""
    from .command_spec import OptionSpec

    recovery = spec.recovery_handoff
    if recovery is None:
        return None
    option_by_name = {parameter.name: parameter for parameter in spec.parameters if isinstance(parameter, OptionSpec)}
    return RecoveryHandoffContract(
        handoff_option=option_by_name[recovery.handoff_parameter].declarations[0],
        handoff_direction=recovery.handoff_direction,
        verification_option=option_by_name[recovery.verification_parameter].declarations[0],
        verification_direction=recovery.verification_direction,
        required_together=recovery.required_together,
        json_fields=recovery.json_fields,
        maximum_bytes=recovery.maximum_bytes,
        strict_utf8_object=recovery.strict_utf8_object,
        duplicate_extra_missing_fields_refused=recovery.duplicate_extra_missing_fields_refused,
        descriptors_closed=recovery.descriptors_closed,
        reserved_descriptors=recovery.reserved_descriptors,
        descriptors_must_differ=recovery.descriptors_must_differ,
        collides_with=tuple(option_by_name[name].declarations[0] for name in recovery.collides_with_parameters),
        windows_handle_bootstrap=recovery.windows_handle_bootstrap,
    )


def build_verb_input_schemas(command_keys: tuple[str, ...]) -> dict[str, VerbInputSchema]:
    from .command_specs import COMMAND_GRAPH

    rows = _rows()
    specs = COMMAND_GRAPH.by_schema_identity()
    profile_contract = command_registration_projection().profile_authentication_contract
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
        spec = specs[key]
        schemas[key] = VerbInputSchema(
            command_key=key,
            cli_path=row.cli_path,
            parameters=tuple(
                VerbParameter(
                    name=p.name,
                    kind=ParameterKind(p.kind),
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
            recovery_handoff_contract=project_recovery_handoff_contract(spec),
            profile_authentication=row.profile_authentication,
            profile_authentication_contract=profile_contract,
            help=next((value for _, value in row.help_by_language), ""),
        )
    assert_schema_coverage(tuple(failures))
    return schemas


__all__ = [
    "JsonType",
    "ParameterKind",
    "ResolvedVerbLeaf",
    "SchemaResolutionError",
    "VerbInputSchema",
    "VerbLeafKind",
    "VerbLeafResolutionFailure",
    "VerbParameter",
    "assert_schema_coverage",
    "build_verb_input_schemas",
    "cli_argv_for",
    "cli_path_for_command_key",
    "is_exposable_command",
    "project_recovery_handoff_contract",
]
