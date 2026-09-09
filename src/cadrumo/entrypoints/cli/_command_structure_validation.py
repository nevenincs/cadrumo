"""Command lifecycle and graph-shape invariants plus graph projections."""

from __future__ import annotations

from collections.abc import Callable
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from .command_spec import (
        CommandNodeKind,
        CommandSpec,
        CommandSpecNode,
        InvocationSpec,
        LazyBinding,
        ParameterSpec,
    )


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _raise_first(checks: tuple[tuple[bool, str], ...]) -> None:
    """Raise the first failed structural invariant."""
    for failed, message in checks:
        if failed:
            raise ValueError(message)


def validate_recovery_directions(handoff_direction: str, verification_direction: str) -> None:
    _raise_first(
        (
            (
                handoff_direction != "write" or verification_direction != "read",
                "recovery handoff directions must be write then read",
            ),
        )
    )


def validate_recovery_parameters(
    handoff_parameter: str,
    verification_parameter: str,
    collides_with_parameters: tuple[str, ...],
    *,
    require_identifier: Callable[..., None],
) -> None:
    for value in (handoff_parameter, verification_parameter, *collides_with_parameters):
        require_identifier(value, field="recovery handoff parameter")
    _raise_first(
        ((handoff_parameter == verification_parameter, "recovery handoff descriptors must be distinct parameters"),)
    )


def validate_recovery_json_fields(
    json_fields: tuple[str, ...],
    *,
    require_identifier: Callable[..., None],
) -> None:
    _raise_first(
        (
            (
                not json_fields or len(json_fields) != len(set(json_fields)),
                "recovery handoff JSON fields must be non-empty and unique",
            ),
        )
    )
    for field_name in json_fields:
        require_identifier(field_name, field="recovery handoff JSON field")


def validate_recovery_limits(
    maximum_bytes: int,
    required_together: bool,
    strict_utf8_object: bool,
    duplicate_extra_missing_fields_refused: bool,
    descriptors_closed: bool,
    descriptors_must_differ: bool,
) -> None:
    _raise_first(((maximum_bytes <= 0, "recovery handoff maximum bytes must be positive"),))
    if not all(
        isinstance(value, bool)
        for value in (
            required_together,
            strict_utf8_object,
            duplicate_extra_missing_fields_refused,
            descriptors_closed,
            descriptors_must_differ,
        )
    ):
        raise TypeError("recovery handoff protocol flags must be bools")


def validate_recovery_reserved_descriptors(reserved_descriptors: tuple[int, ...]) -> None:
    _raise_first(
        (
            (
                not reserved_descriptors or any(value < 0 for value in reserved_descriptors),
                "recovery handoff reserved descriptors must be non-negative",
            ),
            (
                len(reserved_descriptors) != len(set(reserved_descriptors)),
                "recovery handoff reserved descriptors must be unique",
            ),
        )
    )


def validate_recovery_bootstrap(windows_handle_bootstrap: str) -> None:
    _raise_first(
        (
            (
                not windows_handle_bootstrap or any(character.isspace() for character in windows_handle_bootstrap),
                "recovery handoff Windows bootstrap must be a non-empty token",
            ),
        )
    )


def validate_command_identity(
    key: str,
    parent_key: str | None,
    token: str,
    kind: CommandNodeKind,
    *,
    require_identifier: Callable[..., None],
    require_token: Callable[..., None],
) -> None:
    """Validate command identity without importing the public command kernel."""
    require_identifier(key, field="command key")
    if parent_key is not None:
        require_identifier(parent_key, field="command parent key")
    require_token(token, field="command token")
    kind_value = _enum_value(kind)
    _raise_first(
        (
            (kind_value not in {"root", "group", "leaf"}, f"unknown command node kind: {kind}"),
            (all((kind_value == "root", parent_key is not None)), "root command cannot declare a parent"),
            (all((kind_value != "root", parent_key is None)), "non-root command must declare a parent"),
        )
    )


def validate_leaf_execution(
    kind: CommandNodeKind,
    handler: LazyBinding | None,
    invocation: InvocationSpec,
) -> None:
    """Validate handler and chaining invariants owned by command leaves."""
    leaf = _enum_value(kind) == "leaf"
    _raise_first(
        (
            (all((leaf, handler is None)), "leaf command must declare a handler binding"),
            (all((leaf, invocation.chain)), "leaf command cannot enable command chaining"),
        )
    )


def validate_callback_parameters(
    kind: CommandNodeKind,
    parameters: tuple[ParameterSpec, ...],
    invocation: InvocationSpec,
) -> None:
    """Reject callback parameters on non-executable groups."""
    _raise_first(
        (
            (
                all((_enum_value(kind) != "leaf", bool(parameters), not invocation.invoke_without_command)),
                "non-executable groups cannot declare callback parameters",
            ),
        )
    )


def validate_terminal_execution(
    kind: CommandNodeKind,
    handler: LazyBinding | None,
    invocation: InvocationSpec,
) -> None:
    """Validate terminal invocation, handler, and context relationships."""
    _raise_first(
        (
            (
                all((invocation.invoke_without_command, handler is None)),
                "executable root/group must declare a handler binding",
            ),
            (
                all((invocation.invoke_without_command, invocation.terminal_behavior is None)),
                "invoke-without-command nodes must classify terminal behavior",
            ),
            (
                all((not invocation.invoke_without_command, invocation.terminal_behavior is not None)),
                "non-terminal nodes cannot classify terminal behavior",
            ),
            (
                all((invocation.terminal_behavior == "executable", invocation.context_parameter is None)),
                "terminal executable groups require an invocation context",
            ),
            (
                all((not invocation.invoke_without_command, _enum_value(kind) != "leaf", handler is not None)),
                "metadata-only root/group cannot declare a handler binding",
            ),
        )
    )


def validate_result_schema(
    state: object,
    target: object,
    reason_key: object,
    identity: str | None,
    *,
    validate_target: Callable[..., None],
    validate_not_supported: Callable[..., None],
    validate_unavailable: Callable[..., None],
) -> None:
    """Dispatch result-schema shape validation in declaration order."""
    state_value = _enum_value(state)
    validators = {
        "target": validate_target,
        "not-supported": validate_not_supported,
        "unavailable": validate_unavailable,
    }
    validator = validators.get(cast(str, state_value))
    if validator is not None:
        validator(target, reason_key, identity)


def validate_command_spec(
    key: str,
    parent_key: str | None,
    token: str,
    kind: object,
    handler: object,
    invocation: object,
    parameters: tuple[Any, ...],
    profile_target_parameter: str | None,
    search_terms: tuple[str, ...],
    machine_secret: object,
    profile_secret: object,
    recovery_handoff: object,
    *,
    require_identifier: Callable[..., None],
    require_token: Callable[..., None],
    validate_identity: Callable[..., None],
    validate_leaf: Callable[..., None],
    validate_callbacks: Callable[..., None],
    validate_terminal: Callable[..., None],
    validate_parameters: Callable[..., tuple[str, ...]],
    validate_machine_secret: Callable[..., None],
    validate_profile_secret: Callable[..., None],
    validate_recovery: Callable[..., None],
) -> None:
    """Run command-node invariants in the canonical refusal order."""
    validate_identity(
        key,
        parent_key,
        token,
        kind,
        require_identifier=require_identifier,
        require_token=require_token,
    )
    validate_leaf(kind, handler, invocation)
    validate_callbacks(kind, parameters, invocation)
    validate_terminal(kind, handler, invocation)
    parameter_names = validate_parameters(parameters, profile_target_parameter, search_terms)
    option_parameters = tuple(
        parameter for parameter in parameters if _enum_value(getattr(parameter, "kind", None)) == "option"
    )
    secret_channels = tuple(
        parameter.machine_secret_channel
        for parameter in option_parameters
        if parameter.machine_secret_channel is not None
    )
    profile_secret_channels = tuple(
        parameter.profile_secret_channel
        for parameter in option_parameters
        if parameter.profile_secret_channel is not None
    )
    validate_machine_secret(kind, parameters, machine_secret, secret_channels)
    validate_profile_secret(kind, machine_secret, profile_secret, profile_secret_channels)
    validate_recovery(
        kind,
        parameters,
        parameter_names,
        recovery_handoff,
        require_identifier=require_identifier,
    )


def validate_recovery_presence(parameter_names: tuple[str, ...], recovery_handoff: object) -> None:
    recovery_parameter_names = {"recovery_handoff_fd", "recovery_verification_fd"}
    declared_recovery_parameters = recovery_parameter_names.intersection(parameter_names)
    _raise_first(
        (
            (
                bool(declared_recovery_parameters) and recovery_handoff is None,
                "recovery descriptor parameters require a recovery handoff spec",
            ),
        )
    )


def validate_recovery_shape(kind: object, recovery_handoff: object) -> None:
    _raise_first(
        (
            (
                recovery_handoff is not None and _enum_value(kind) != "leaf",
                "recovery handoff specs belong only to command leaves",
            ),
        )
    )


def recovery_references(parameter_names: tuple[str, ...], recovery_handoff: Any) -> set[str]:
    referenced = {
        recovery_handoff.handoff_parameter,
        recovery_handoff.verification_parameter,
        *recovery_handoff.collides_with_parameters,
    }
    _raise_first(
        ((not referenced.issubset(parameter_names), "recovery handoff spec references a missing command parameter"),)
    )
    return referenced


def recovery_descriptor_parameters(parameters: tuple[Any, ...], referenced: set[str]) -> dict[str, Any]:
    descriptor_parameters = dict(
        (parameter.name, parameter)
        for parameter in parameters
        if all((_enum_value(getattr(parameter, "kind", None)) == "option", parameter.name in referenced))
    )
    _raise_first(((descriptor_parameters.keys() != referenced, "recovery handoff parameters must be command options"),))
    return descriptor_parameters


def _target_matches(annotation: object) -> bool:
    return all(
        (
            annotation.__class__.__name__ == "DeferredTarget",
            getattr(annotation, "module", None) == "builtins",
            getattr(annotation, "qualname", None) == "int",
        )
    )


def validate_recovery_integer_options(descriptor_parameters: dict[str, Any]) -> None:
    _raise_first(
        (
            (
                any(not _target_matches(parameter.value.annotation) for parameter in descriptor_parameters.values()),
                "recovery handoff parameters must be integer options",
            ),
        )
    )


def validate_recovery_handoff_contract(
    kind: object,
    parameters: tuple[Any, ...],
    parameter_names: tuple[str, ...],
    recovery_handoff: object,
    *,
    require_identifier: Callable[..., None],
) -> None:
    validate_recovery_presence(parameter_names, recovery_handoff)
    if recovery_handoff is None:
        return
    validate_recovery_shape(kind, recovery_handoff)
    referenced = recovery_references(parameter_names, recovery_handoff)
    descriptor_parameters = recovery_descriptor_parameters(parameters, referenced)
    validate_recovery_integer_options(descriptor_parameters)


def validate_graph(specs: tuple[CommandSpec, ...]) -> None:
    """Require one rooted, acyclic graph with valid parent edges and paths."""
    _raise_first(((not specs, "command spec graph cannot be empty"),))
    by_key = {spec.key: spec for spec in specs}
    roots = tuple(spec for spec in specs if spec.parent_key is None)
    _raise_first(
        (
            (len(by_key) != len(specs), "command spec keys must be unique"),
            (len(roots) != 1, "command spec graph must declare exactly one root"),
        )
    )
    for spec in specs:
        parent_key = spec.parent_key
        if parent_key is None:
            continue
        if parent_key not in by_key:
            raise ValueError(f"command spec {spec.key!r} has unknown parent {parent_key!r}")
        _raise_first(
            ((_enum_value(by_key[parent_key].kind) == "leaf", f"leaf command {parent_key!r} cannot own children"),)
        )
    paths = derive_graph_paths(by_key)
    _raise_first(((len(set(paths.values())) != len(paths), "command spec operator paths must be unique"),))


def derive_graph_paths(by_key: dict[str, CommandSpec]) -> dict[str, tuple[str, ...]]:
    """Derive every operator path while refusing parent cycles."""
    paths: dict[str, tuple[str, ...]] = {}
    visiting: set[str] = set()

    def derive_path(key: str) -> tuple[str, ...]:
        if key in paths:
            return paths[key]
        if key in visiting:
            raise ValueError("command spec parent edges contain a cycle")
        visiting.add(key)
        spec = by_key[key]
        parent_path = () if spec.parent_key is None else derive_path(spec.parent_key)
        path = (*parent_path, spec.token)
        visiting.remove(key)
        paths[key] = path
        return path

    for key in by_key:
        derive_path(key)
    return paths


def graph_by_key(specs: tuple[CommandSpec, ...]) -> MappingProxyType[str, CommandSpec]:
    """Return every command spec indexed by its key."""
    return MappingProxyType({spec.key: spec for spec in specs})


def graph_nodes(
    specs: tuple[CommandSpec, ...],
    *,
    node_type: type[Any],
) -> tuple[CommandSpecNode, ...]:
    """Return command nodes paired with their deterministically derived paths."""
    by_key = graph_by_key(specs)

    def path_for(spec: CommandSpec) -> tuple[str, ...]:
        tokens = [spec.token]
        parent_key = spec.parent_key
        while parent_key is not None:
            parent = by_key[parent_key]
            tokens.append(parent.token)
            parent_key = parent.parent_key
        return tuple(reversed(tokens))

    return tuple(sorted((node_type(path_for(spec), spec) for spec in specs), key=lambda node: node.path))


def graph_by_path(
    specs: tuple[CommandSpec, ...],
    *,
    node_type: type[Any],
) -> MappingProxyType[tuple[str, ...], CommandSpec]:
    """Return the exact derived operator-path index."""
    return MappingProxyType({node.path: node.spec for node in graph_nodes(specs, node_type=node_type)})


def resolve_graph_path(
    specs: tuple[CommandSpec, ...],
    path: tuple[str, ...],
    *,
    node_type: type[Any],
) -> CommandSpec:
    """Resolve one complete operator path, failing closed on absence."""
    try:
        return graph_by_path(specs, node_type=node_type)[path]
    except KeyError as error:
        raise LookupError(f"unknown command spec path: {' '.join(path)!r}") from error


def graph_by_schema_identity(specs: tuple[CommandSpec, ...]) -> MappingProxyType[str, CommandSpec]:
    """Return the unique executable result-schema identity index."""
    target_specs = tuple(
        spec
        for spec in specs
        if all((_enum_value(spec.result_schema.state) == "target", spec.result_schema.identity is not None))
    )
    rows = {cast(str, spec.result_schema.identity): spec for spec in target_specs}
    _raise_first(((len(rows) != len(target_specs), "command result-schema identities must be unique"),))
    return MappingProxyType(rows)


__all__ = [
    "derive_graph_paths",
    "graph_by_key",
    "graph_by_path",
    "graph_by_schema_identity",
    "graph_nodes",
    "recovery_descriptor_parameters",
    "recovery_references",
    "resolve_graph_path",
    "validate_callback_parameters",
    "validate_command_identity",
    "validate_command_spec",
    "validate_graph",
    "validate_leaf_execution",
    "validate_recovery_bootstrap",
    "validate_recovery_directions",
    "validate_recovery_handoff_contract",
    "validate_recovery_integer_options",
    "validate_recovery_json_fields",
    "validate_recovery_limits",
    "validate_recovery_parameters",
    "validate_recovery_presence",
    "validate_recovery_reserved_descriptors",
    "validate_recovery_shape",
    "validate_result_schema",
    "validate_terminal_execution",
]
