"""Immutable positional and option declarations with validated transport and secret channels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ...application.operator_surface.command_ports import (
    ParameterKind,
)
from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from ._command_parameter_validation import (
    require_coherent_transport,
    require_identifier,
    require_token,
    validate_machine_secret_option_channel,
    validate_option_declarations,
    validate_option_environment,
    validate_option_flags,
    validate_profile_secret_option_channel,
    validate_secret_channel_scope,
)
from ._command_secret_contracts import MachineSecretChannelKind, ProfileSecretChannelKind
from .command_shared_contracts import (
    LiteralValue,
    ParameterConstraint,
    ParameterDefault,
    TranslationKey,
    ValueContract,
)

_ARGUMENT_CONSTRAINT_DEFAULT: Final[ParameterConstraint] = ParameterConstraint()
_OPTION_CONSTRAINT_DEFAULT: Final[ParameterConstraint] = ParameterConstraint()


@dataclass(frozen=True, slots=True)
class ArgumentSpec:
    """One positional argument declaration, in command tuple order."""

    name: str
    value: ValueContract
    default: ParameterDefault
    help_key: TranslationKey | None
    metavar: str | None = None
    show_default: bool = True
    hidden: bool = False
    constraint: ParameterConstraint = _ARGUMENT_CONSTRAINT_DEFAULT
    transport_locus: TransportLocus = TransportLocus.NONE
    transport_shape: TransportShape = TransportShape.NOT_APPLICABLE
    transport_role: TransportRole = TransportRole.NOT_APPLICABLE

    kind: ParameterKind = ParameterKind.ARGUMENT

    def __post_init__(self) -> None:
        """Validate the argument's name, metavar, and transport coherence, or raise."""
        require_identifier(self.name, field="argument name")
        if self.metavar is not None:
            require_token(self.metavar, field="argument metavar")
        require_coherent_transport(
            self.transport_locus,
            self.transport_shape,
            self.transport_role,
            field="argument transport",
        )


@dataclass(frozen=True, slots=True)
class OptionSpec:
    """One named option declaration including aliases and flag pairing."""

    name: str
    declarations: tuple[str, ...]
    value: ValueContract
    default: ParameterDefault
    help_key: TranslationKey | None
    metavar: str | None = None
    show_default: bool = True
    hidden: bool = False
    is_flag: bool = False
    flag_value: LiteralValue = None
    multiple: bool = False
    count: bool = False
    prompt_key: TranslationKey | None = None
    confirmation_prompt_key: TranslationKey | None = None
    envvar: tuple[str, ...] = ()
    eager: bool = False
    constraint: ParameterConstraint = _OPTION_CONSTRAINT_DEFAULT
    machine_secret_channel: MachineSecretChannelKind | None = None
    profile_secret_channel: ProfileSecretChannelKind | None = None
    transport_locus: TransportLocus = TransportLocus.NONE
    transport_shape: TransportShape = TransportShape.NOT_APPLICABLE
    transport_role: TransportRole = TransportRole.NOT_APPLICABLE

    kind: ParameterKind = ParameterKind.OPTION

    def __post_init__(self) -> None:
        """Validate the option's declarations, flags, secret channels, and transport coherence, or raise."""
        require_identifier(self.name, field="option name")
        validate_option_declarations(self.declarations, self.metavar)
        validate_option_flags(self.count, self.is_flag, self.multiple, self.flag_value)
        validate_option_environment(self.envvar)
        validate_machine_secret_option_channel(self.machine_secret_channel, self.value.annotation)
        validate_secret_channel_scope(self.machine_secret_channel, self.profile_secret_channel)
        validate_profile_secret_option_channel(self.profile_secret_channel, self.value.annotation)
        require_coherent_transport(
            self.transport_locus,
            self.transport_shape,
            self.transport_role,
            field="option transport",
        )


type ParameterSpec = ArgumentSpec | OptionSpec
