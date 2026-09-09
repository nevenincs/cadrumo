"""Parameter, schema, secret-channel, and recovery invariants for command specs."""

from __future__ import annotations

from typing import Any, cast

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape


def _raise_first(checks: tuple[tuple[bool, str], ...]) -> None:
    """Raise the first failed invariant while preserving declaration order."""
    for failed, message in checks:
        if failed:
            raise ValueError(message)


def require_identifier(value: str, *, field: str) -> None:
    """Require an unpadded Python identifier for a structural field."""
    if not value or value.strip() != value or not value.isidentifier():
        raise ValueError(f"{field} must be a non-empty Python identifier")


def require_token(value: str, *, field: str) -> None:
    """Require an unpadded token without whitespace."""
    if not value or value.strip() != value or any(character.isspace() for character in value):
        raise ValueError(f"{field} must be a non-empty whitespace-free token")


def require_coherent_transport(
    locus: TransportLocus,
    shape: TransportShape,
    role: TransportRole,
    *,
    field: str,
) -> None:
    """Refuse transport declarations whose three axes disagree."""
    local = locus in {TransportLocus.LOCAL_IN, TransportLocus.LOCAL_OUT}
    _raise_first(
        (
            (
                not local and shape is not TransportShape.NOT_APPLICABLE,
                f"{field} declares a shape without a local locus",
            ),
            (not local and role is not TransportRole.NOT_APPLICABLE, f"{field} declares a role without a local locus"),
            (local and shape is TransportShape.NOT_APPLICABLE, f"{field} declares a local locus without a shape"),
            (local and role is TransportRole.NOT_APPLICABLE, f"{field} declares a local locus without a role"),
        )
    )


def validate_option_declarations(declarations: tuple[str, ...], metavar: str | None) -> None:
    """Validate option tokens and the optional display metavar."""
    _raise_first(
        (
            (not declarations, "option must declare at least one CLI token"),
            (len(set(declarations)) != len(declarations), "option declarations must be unique"),
            (
                any(not declaration.startswith("-") for declaration in declarations),
                "option declarations must begin with '-'",
            ),
        )
    )
    for declaration in declarations:
        require_token(declaration, field="option declaration")
    if metavar is not None:
        require_token(metavar, field="option metavar")


def validate_option_flags(count: bool, is_flag: bool, multiple: bool, flag_value: Any) -> None:
    """Validate count and explicit flag-value combinations."""
    _raise_first(
        (
            (count and (not is_flag or multiple), "counting options must be singular flags"),
            (flag_value is not None and not is_flag, "flag values require is_flag"),
        )
    )


def validate_option_environment(envvar: tuple[str, ...]) -> None:
    """Validate unique environment variable names and their token shape."""
    _raise_first(((len(set(envvar)) != len(envvar), "option environment variables must be unique"),))
    for variable in envvar:
        require_token(variable, field="option environment variable")


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _target_matches(annotation: object, module: str, qualname: str) -> bool:
    """Match a deferred target without importing the command declaration module."""
    return (
        annotation.__class__.__name__ == "DeferredTarget"
        and getattr(annotation, "module", None) == module
        and getattr(annotation, "qualname", None) == qualname
    )


def validate_machine_secret_option_channel(channel: object, annotation: object) -> None:
    """Validate the value type required by a machine-secret channel."""
    channel_value = _enum_value(channel)
    _raise_first(
        (
            (
                channel_value == "stdin" and not _target_matches(annotation, "builtins", "bool"),
                "stdin machine-secret channel must be boolean",
            ),
            (
                channel_value == "file-descriptor" and not _target_matches(annotation, "builtins", "int"),
                "file-descriptor machine-secret channel must be integer",
            ),
        )
    )


def validate_secret_channel_scope(
    machine_secret_channel: object,
    profile_secret_channel: object,
) -> None:
    """Refuse assigning one option to both secret-channel scopes."""
    _raise_first(
        (
            (
                machine_secret_channel is not None and profile_secret_channel is not None,
                "one option cannot belong to both secret-channel scopes",
            ),
        )
    )


def validate_profile_secret_option_channel(channel: object, annotation: object) -> None:
    """Validate the value type required by a profile-secret channel."""
    channel_value = _enum_value(channel)
    _raise_first(
        (
            (
                channel_value == "stdin" and not _target_matches(annotation, "builtins", "bool"),
                "stdin profile-secret channel must be boolean",
            ),
            (
                channel_value == "file-descriptor" and not _target_matches(annotation, "builtins", "int"),
                "file-descriptor profile-secret channel must be integer",
            ),
        )
    )


def validate_target_schema(target: object, reason_key: object, identity: str | None) -> None:
    """Require a target schema identity and target without an unavailable reason."""
    _raise_first(
        (
            (
                target is None or reason_key is not None or identity is None,
                "schema target state requires an identity and target",
            ),
        )
    )
    parts = cast(str, identity).split(".")
    _raise_first(
        (
            (
                any(not part or any(character.isspace() for character in part) for part in parts),
                "schema identity must be a non-empty dotted token sequence",
            ),
        )
    )


def validate_not_supported_schema(target: object, reason_key: object, identity: str | None) -> None:
    """Require a not-supported schema to carry no target, reason, or identity."""
    _raise_first(
        (
            (
                target is not None or reason_key is not None or identity is not None,
                "unsupported schema state carries no identity, target, or reason",
            ),
        )
    )


def validate_unavailable_schema(target: object, reason_key: object, identity: str | None) -> None:
    """Require an unavailable schema to carry only its localized reason."""
    _raise_first(
        (
            (
                target is not None or reason_key is None or identity is not None,
                "unavailable schema state requires only a localized reason",
            ),
        )
    )


def validate_unique_parameter_names(parameters: tuple[Any, ...]) -> tuple[str, ...]:
    """Return parameter names after refusing duplicate command fields."""
    parameter_names = tuple(parameter.name for parameter in parameters)
    _raise_first(((len(parameter_names) != len(set(parameter_names)), "command parameter names must be unique"),))
    return parameter_names


def validate_profile_target_parameter(profile_target_parameter: str | None, parameter_names: tuple[str, ...]) -> None:
    """Require a configured profile target to identify a declared parameter."""
    if profile_target_parameter is not None:
        require_identifier(profile_target_parameter, field="profile target parameter")
        _raise_first(
            (
                (
                    profile_target_parameter not in parameter_names,
                    "profile target parameter must reference a declared command parameter",
                ),
            )
        )


def validate_unique_option_tokens(parameters: tuple[Any, ...]) -> None:
    """Refuse aliases reused by more than one command option."""
    option_tokens = [
        declaration
        for parameter in parameters
        if _enum_value(getattr(parameter, "kind", None)) == "option"
        for declaration in parameter.declarations
    ]
    _raise_first(((len(option_tokens) != len(set(option_tokens)), "command option tokens must be unique"),))


def validate_search_terms(search_terms: tuple[str, ...]) -> None:
    """Require every semantic command-search term to contain non-whitespace text."""
    _raise_first(((any(not term.strip() for term in search_terms), "command search terms must be non-empty"),))


def validate_parameter_declarations(
    parameters: tuple[Any, ...],
    profile_target_parameter: str | None,
    search_terms: tuple[str, ...],
) -> tuple[str, ...]:
    """Validate parameter identity, option tokens, profile target, and search terms."""
    parameter_names = validate_unique_parameter_names(parameters)
    validate_profile_target_parameter(profile_target_parameter, parameter_names)
    validate_unique_option_tokens(parameters)
    validate_search_terms(search_terms)
    return parameter_names


def validate_machine_secret_presence(machine_secret: object, secret_channels: tuple[object, ...]) -> None:
    """Require a machine-secret contract when options expose its channels."""
    _raise_first(
        (
            (
                machine_secret is None and bool(secret_channels),
                "machine-secret channel parameters require a machine-secret spec",
            ),
        )
    )


def validate_machine_secret_shape(
    kind: object,
    machine_secret: object,
    secret_channels: tuple[object, ...],
) -> None:
    """Require machine-secret contracts to belong to leaves with both channels."""
    if machine_secret is None:
        return
    values = tuple(_enum_value(channel) for channel in secret_channels)
    _raise_first(
        (
            (_enum_value(kind) != "leaf", "machine-secret specs belong only to command leaves"),
            (
                values.count("stdin") != 1 or values.count("file-descriptor") != 1,
                "machine-secret spec requires exactly one stdin and file-descriptor channel",
            ),
        )
    )


def validate_machine_secret_conditions(parameters: tuple[Any, ...], machine_secret: object) -> None:
    """Require every machine-secret variant condition to name a command option."""
    if machine_secret is None:
        return
    declared_names = {parameter.name for parameter in parameters}
    variants = cast(Any, machine_secret).variants
    _raise_first(
        (
            (
                any(
                    variant.condition is not None and variant.condition.option_name not in declared_names
                    for variant in variants
                ),
                "machine-secret condition must reference a command parameter",
            ),
        )
    )


def validate_machine_secret_contract(
    kind: object,
    parameters: tuple[Any, ...],
    machine_secret: object,
    secret_channels: tuple[object, ...],
) -> None:
    """Validate leaf machine-secret ownership and channel references."""
    validate_machine_secret_presence(machine_secret, secret_channels)
    validate_machine_secret_shape(kind, machine_secret, secret_channels)
    validate_machine_secret_conditions(parameters, machine_secret)


def validate_profile_secret_contract(
    kind: object,
    machine_secret: object,
    profile_secret: object,
    profile_secret_channels: tuple[object, ...],
) -> None:
    """Validate root profile-secret ownership and channel cardinality."""
    if profile_secret is None:
        _raise_first(
            ((bool(profile_secret_channels), "profile-secret channel parameters require a profile-secret spec"),)
        )
        return
    values = tuple(_enum_value(channel) for channel in profile_secret_channels)
    _raise_first(
        (
            (_enum_value(kind) != "root", "profile-secret specs belong only to the executable root"),
            (machine_secret is not None, "root profile-secret channels cannot own a leaf machine-secret spec"),
            (
                values.count("stdin") != 1 or values.count("file-descriptor") != 1,
                "root profile-secret contract requires exactly one stdin and file-descriptor channel",
            ),
        )
    )


__all__ = [
    "require_coherent_transport",
    "require_identifier",
    "require_token",
    "validate_machine_secret_conditions",
    "validate_machine_secret_contract",
    "validate_machine_secret_option_channel",
    "validate_machine_secret_presence",
    "validate_machine_secret_shape",
    "validate_not_supported_schema",
    "validate_option_declarations",
    "validate_option_environment",
    "validate_option_flags",
    "validate_parameter_declarations",
    "validate_profile_secret_contract",
    "validate_profile_secret_option_channel",
    "validate_profile_target_parameter",
    "validate_search_terms",
    "validate_secret_channel_scope",
    "validate_target_schema",
    "validate_unavailable_schema",
    "validate_unique_option_tokens",
    "validate_unique_parameter_names",
]
