"""Project operator input contracts from the immutable command-spec graph."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...application.operator_surface.command_ports import (
    CommandRegistrationMetadata,
    JsonType,
    ParameterKind,
    ProfileAuthenticationContractMetadata,
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
from .command_schema import (
    command_registration_for_node,
    command_registration_metadata,
    command_registration_projection,
    profile_authentication_contract,
)

if TYPE_CHECKING:
    from .command_spec import CommandSpec


def _rows() -> dict[str, CommandRegistrationMetadata]:
    return {row.command: row for row in command_registration_metadata()}


def is_exposable_command(command_key: str) -> bool:
    """Return whether a command schema identity is exposed as an operator verb."""
    from .command_specs import COMMAND_GRAPH

    spec = COMMAND_GRAPH.by_schema_identity().get(command_key)
    return spec is not None and is_exposable_command_spec(spec)


def is_exposable_command_spec(spec: CommandSpec) -> bool:
    """Return whether one command declaration is exposed as an operator verb."""
    from .command_spec import BindingState

    return (
        spec.parent_key not in {None, "root"}
        and spec.handler is not None
        and spec.handler.state is BindingState.TARGET
        and (spec.kind == "leaf" or spec.invocation.invoke_without_command)
    )


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
    """Build validated input schemas for the requested command identities."""
    from .command_specs import COMMAND_GRAPH

    rows = _rows()
    specs = COMMAND_GRAPH.by_schema_identity()
    profile_contract = command_registration_projection().profile_authentication_contract
    schemas: dict[str, VerbInputSchema] = {}
    failures: list[VerbLeafResolutionFailure] = []
    for key in command_keys:
        row = rows.get(key)
        if row is None or row.cli_path is None:
            failures.append(_unresolved_leaf(key))
            continue
        schemas[key] = _verb_input_schema(key, row.cli_path, row, specs[key], profile_contract)
    assert_schema_coverage(tuple(failures))
    return schemas


def build_verb_input_schema(command_key: str) -> VerbInputSchema:
    """Build one command's validated input schema, loading only the graph families searched."""
    from .command_specs import COMMAND_GRAPH

    node = COMMAND_GRAPH.find_schema_identity(command_key)
    row = None if node is None else command_registration_for_node(node)
    if node is None or row is None or row.cli_path is None:
        raise SchemaResolutionError((_unresolved_leaf(command_key),))
    return _verb_input_schema(command_key, row.cli_path, row, node.spec, profile_authentication_contract())


def _unresolved_leaf(command_key: str) -> VerbLeafResolutionFailure:
    return VerbLeafResolutionFailure(
        subject_leaf_key=command_key, attempted_cli_path=(), reason="no CommandSpec result-schema identity"
    )


def _verb_input_schema(
    command_key: str,
    cli_path: tuple[str, ...],
    row: CommandRegistrationMetadata,
    spec: CommandSpec,
    profile_contract: ProfileAuthenticationContractMetadata,
) -> VerbInputSchema:
    """Assemble one validated input schema from its registration row and declaration."""
    parameters = next((values for _, values in row.parameters_by_language if values is not None), ())
    return VerbInputSchema(
        command_key=command_key,
        cli_path=cli_path,
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
    "build_verb_input_schema",
    "build_verb_input_schemas",
    "cli_argv_for",
    "is_exposable_command",
    "is_exposable_command_spec",
    "project_recovery_handoff_contract",
]
