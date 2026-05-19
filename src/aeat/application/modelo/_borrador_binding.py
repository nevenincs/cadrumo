"""Application-owned borrador binding resolution.

The CLI may parse a snapshot id, but the decision to consume values from
a captured borrador belongs here: the application layer checks the
work-unit axis, snapshot state, registry eligibility, and precedence
against caller-supplied binding overrides before the calculation engine
receives any values.

Only modelos that declare the ``"borrador"`` capability in their registry
manifest are eligible. Adding support for a new modelo requires only a
TOML edit — no code change.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core.i18n import tr
from ...domain.calculations.registry import DataBindingDefinition, RegistrySnapshot
from ...domain.modelos._errors import ModeloError
from ..live import (
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    SnapshotLifecycleState,
    LiveApplicationInputError,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class Modelo100BorradorBindingError(ModeloError):
    """Raised when borrador values cannot be consumed for a calculation."""


class Modelo100BorradorBindingCommand(BaseModel):
    """Command contract for resolving one optional borrador snapshot."""

    model_config = _STRICT_FROZEN

    bucket_id: str = Field(min_length=1, max_length=128)
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=1900, le=9999)
    period: str = Field(min_length=1, max_length=16)
    borrador_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    caller_binding_values: Mapping[str, Decimal] = Field(default_factory=dict)
    caller_enum_binding_values: Mapping[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_binding_key_shape(self) -> Modelo100BorradorBindingCommand:
        blank_decimal_keys = sorted(key for key in self.caller_binding_values if not key.strip())
        blank_enum_keys = sorted(key for key in self.caller_enum_binding_values if not key.strip())
        if blank_decimal_keys or blank_enum_keys:
            raise Modelo100BorradorBindingError(
                tr("application.modelo.borrador_binding.errors.caller_binding_keys_blank")
            )
        return self


class Modelo100BorradorBindingResult(BaseModel):
    """Values from a borrador snapshot that survived precedence checks."""

    model_config = _STRICT_FROZEN

    borrador_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    binding_values: Mapping[str, Decimal] = Field(default_factory=dict)
    enum_binding_values: Mapping[str, str] = Field(default_factory=dict)
    bindings_sourced_from_borrador: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _enforce_snapshot_trace(self) -> Modelo100BorradorBindingResult:
        if self.borrador_snapshot_id is None:
            if self.binding_values or self.enum_binding_values or self.bindings_sourced_from_borrador:
                raise Modelo100BorradorBindingError(
                    tr("application.modelo.borrador_binding.errors.snapshot_id_required")
                )
            return self
        sourced = set(self.bindings_sourced_from_borrador)
        resolved = set(self.binding_values) | set(self.enum_binding_values)
        if sourced != resolved:
            raise Modelo100BorradorBindingError(
                tr("application.modelo.borrador_binding.errors.source_trace_mismatch")
            )
        return self


def resolve_modelo_100_borrador_bindings(
    command: Modelo100BorradorBindingCommand,
    *,
    registry_snapshot: RegistrySnapshot,
    snapshot_repository: Borrador100SnapshotRepository | None = None,
) -> Modelo100BorradorBindingResult:
    """Resolve eligible borrador values for one Modelo 100 calculation.

    The function is deliberately inert when no snapshot is supplied:
    borrador values are never consumed implicitly. When a snapshot is
    supplied, caller values take precedence and the snapshot may only
    contribute bindings explicitly marked ``aeat_prefilled`` by the
    registry revision passed to the service.
    """

    if command.borrador_snapshot_id is None:
        return Modelo100BorradorBindingResult()

    if not registry_snapshot.modelo.has_capability("borrador"):
        target_modelo = command.modelo.strip()
        raise Modelo100BorradorBindingError(
            f"borrador binding is not supported for modelo {target_modelo!r}; "
            f"the modelo registry manifest must declare the 'borrador' capability"
        )
    _assert_registry_snapshot_axis(command=command, registry_snapshot=registry_snapshot)
    repository = snapshot_repository or Borrador100SnapshotRepository(bucket_id=command.bucket_id)
    try:
        snapshot = repository.load(command.borrador_snapshot_id)
    except LiveApplicationInputError as exc:
        raise Modelo100BorradorBindingError(
            str(exc),
            suggestion=exc.suggestion or "aeat app live borrador 100 list",
        ) from exc
    _assert_same_axis(
        bucket_id=command.bucket_id,
        filing_year=command.filing_year,
        period=command.period,
        snapshot=snapshot,
    )
    if snapshot.state is not SnapshotLifecycleState.ACTIVE:
        raise Modelo100BorradorBindingError(
            tr("application.modelo.borrador_binding.errors.snapshot_not_active"),
            suggestion="aeat app live borrador 100 list",
        )

    eligible_bindings = _borrador_capable_bindings(registry_snapshot)
    unknown_or_forbidden = sorted(set(snapshot.binding_values) - set(eligible_bindings))
    if unknown_or_forbidden:
        raise Modelo100BorradorBindingError(
            "borrador snapshot contains values for bindings that are not registry-marked "
            f"aeat_prefilled: {unknown_or_forbidden!r}"
        )

    caller_owned = set(command.caller_binding_values) | set(command.caller_enum_binding_values)
    decimal_values: dict[str, Decimal] = {}
    enum_values: dict[str, str] = {}
    for binding_id, raw_value in snapshot.binding_values.items():
        key = binding_id.strip()
        if key in caller_owned:
            continue
        binding = eligible_bindings[key]
        if binding.typed_enum is not None:
            enum_values[key] = str(raw_value).strip()
            continue
        decimal_values[key] = _decimal_value(key, raw_value)

    sourced = tuple(sorted(set(decimal_values) | set(enum_values)))
    return Modelo100BorradorBindingResult(
        borrador_snapshot_id=snapshot.snapshot_id,
        binding_values=decimal_values,
        enum_binding_values=enum_values,
        bindings_sourced_from_borrador=sourced,
    )


def _assert_same_axis(
    *,
    bucket_id: str,
    filing_year: int,
    period: str,
    snapshot: Borrador100Snapshot,
) -> None:
    expected_bucket = bucket_id.strip()
    expected_period = period.strip()
    if snapshot.bucket_id != expected_bucket:
        raise Modelo100BorradorBindingError(
            f"borrador snapshot bucket_id={snapshot.bucket_id!r} does not match active bucket {expected_bucket!r}"
        )
    if snapshot.filing_year != filing_year or snapshot.period != expected_period:
        raise Modelo100BorradorBindingError(
            "borrador snapshot axis does not match calculation axis: "
            f"snapshot year={snapshot.filing_year} period={snapshot.period!r}; "
            f"calculation year={filing_year} period={expected_period!r}"
        )


def _assert_registry_snapshot_axis(
    *,
    command: Modelo100BorradorBindingCommand,
    registry_snapshot: RegistrySnapshot,
) -> None:
    if registry_snapshot.modelo.id != command.modelo.strip():
        raise Modelo100BorradorBindingError(
            "registry snapshot modelo does not match borrador binding command: "
            f"snapshot modelo={registry_snapshot.modelo.id!r}; command modelo={command.modelo.strip()!r}"
        )
    if registry_snapshot.filing_year != command.filing_year or registry_snapshot.period != command.period.strip():
        raise Modelo100BorradorBindingError(
            "registry snapshot axis does not match borrador binding command: "
            f"snapshot year={registry_snapshot.filing_year} period={registry_snapshot.period!r}; "
            f"command year={command.filing_year} period={command.period.strip()!r}"
        )


def _borrador_capable_bindings(registry_snapshot: RegistrySnapshot) -> dict[str, DataBindingDefinition]:
    return {
        str(binding.id): binding for binding in registry_snapshot.revision.bindings if binding.aeat_prefilled is True
    }


def _decimal_value(binding_id: str, value: Decimal | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(value.strip())
    except (InvalidOperation, ValueError) as exc:
        raise Modelo100BorradorBindingError(
            f"borrador value for numeric binding {binding_id!r} must be decimal-compatible; got {value!r}"
        ) from exc


__all__ = [
    "Modelo100BorradorBindingCommand",
    "Modelo100BorradorBindingError",
    "Modelo100BorradorBindingResult",
    "resolve_modelo_100_borrador_bindings",
]
