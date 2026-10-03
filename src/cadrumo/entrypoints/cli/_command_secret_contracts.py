"""Immutable secret-channel and recovery-handoff command contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from ...application.operator_surface.command_ports import (
    MachineSecretPresenceValue,
)
from ._command_parameter_validation import require_identifier as _require_identifier
from ._command_policy_validation import validate_machine_secret as _validate_machine_secret
from ._command_policy_validation import validate_machine_secret_condition as _validate_machine_secret_condition
from ._command_policy_validation import validate_machine_secret_field as _validate_machine_secret_field
from ._command_policy_validation import validate_machine_secret_variant as _validate_machine_secret_variant
from ._command_policy_validation import validate_profile_secret as _validate_profile_secret
from ._command_shared_contracts import DeferredTarget
from ._command_structure_validation import validate_recovery_bootstrap as _validate_recovery_bootstrap
from ._command_structure_validation import validate_recovery_directions as _validate_recovery_directions
from ._command_structure_validation import validate_recovery_json_fields as _validate_recovery_json_fields
from ._command_structure_validation import validate_recovery_limits as _validate_recovery_limits
from ._command_structure_validation import validate_recovery_parameters as _validate_recovery_parameters
from ._command_structure_validation import (
    validate_recovery_reserved_descriptors as _validate_recovery_reserved_descriptors,
)


class MachineSecretChannelKind(Enum):
    """Value-free semantic role of a canonical secret transport option."""

    STDIN = "stdin"
    FILE_DESCRIPTOR = "file-descriptor"


class ProfileSecretChannelKind(Enum):
    """Semantic role of a root profile-authentication transport option."""

    STDIN = "stdin"
    FILE_DESCRIPTOR = "file-descriptor"


@dataclass(frozen=True, slots=True)
class MachineSecretFieldSpec:
    """One value-free string field in a strict machine-secret payload."""

    name: str
    json_type: Literal["string"] = "string"

    def __post_init__(self) -> None:
        _validate_machine_secret_field(self.name, require_identifier=_require_identifier)


@dataclass(frozen=True, slots=True)
class MachineSecretConditionSpec:
    """Public option-presence condition selecting a payload variant."""

    option_name: str
    presence: MachineSecretPresenceValue

    def __post_init__(self) -> None:
        _validate_machine_secret_condition(self.option_name, require_identifier=_require_identifier)


@dataclass(frozen=True, slots=True)
class MachineSecretVariantSpec:
    """One strict payload shape and its lazily resolved public model."""

    key: str
    fields: tuple[MachineSecretFieldSpec, ...]
    model: DeferredTarget
    condition: MachineSecretConditionSpec | None = None

    def __post_init__(self) -> None:
        _validate_machine_secret_variant(self.key, self.fields, require_identifier=_require_identifier)


@dataclass(frozen=True, slots=True)
class MachineSecretSpec:
    """Complete immutable machine-secret authority for one command leaf."""

    variants: tuple[MachineSecretVariantSpec, ...]

    def __post_init__(self) -> None:
        _validate_machine_secret(self.variants)


@dataclass(frozen=True, slots=True)
class ProfileSecretSpec:
    """Strict value-free payload authority for root profile authentication."""

    fields: tuple[MachineSecretFieldSpec, ...]
    model: DeferredTarget

    def __post_init__(self) -> None:
        """Validate that fields are declared and their names are unique, or raise."""
        _validate_profile_secret(self.fields)


@dataclass(frozen=True, slots=True)
class RecoveryHandoffSpec:
    """Strict two-way recovery possession protocol owned by one command leaf."""

    handoff_parameter: str
    handoff_direction: Literal["write"]
    verification_parameter: str
    verification_direction: Literal["read"]
    required_together: bool
    json_fields: tuple[str, ...]
    maximum_bytes: int
    strict_utf8_object: bool
    duplicate_extra_missing_fields_refused: bool
    descriptors_closed: bool
    reserved_descriptors: tuple[int, ...]
    descriptors_must_differ: bool
    collides_with_parameters: tuple[str, ...]
    windows_handle_bootstrap: str

    def __post_init__(self) -> None:
        """Validate the recovery handoff protocol's parameters and flag invariants, or raise."""
        _validate_recovery_directions(self.handoff_direction, self.verification_direction)
        _validate_recovery_parameters(
            self.handoff_parameter,
            self.verification_parameter,
            self.collides_with_parameters,
            require_identifier=_require_identifier,
        )
        _validate_recovery_json_fields(self.json_fields, require_identifier=_require_identifier)
        _validate_recovery_limits(
            self.maximum_bytes,
            self.required_together,
            self.strict_utf8_object,
            self.duplicate_extra_missing_fields_refused,
            self.descriptors_closed,
            self.descriptors_must_differ,
        )
        _validate_recovery_reserved_descriptors(self.reserved_descriptors)
        _validate_recovery_bootstrap(self.windows_handle_bootstrap)
