"""Application-owned borrador binding resolution.

The CLI may parse a snapshot id, but the decision to consume values from
a captured borrador belongs here: the application layer checks the
work-unit axis, snapshot state, registry eligibility, and precedence
against caller-supplied binding overrides before the calculation engine
receives any values. Eligibility is determined by inspecting the
:class:`RegistrySnapshot` for the ``"borrador"`` capability declaration.

Only modelos that declare the ``"borrador"`` capability in their registry
manifest are eligible. Adding support for a new modelo requires only a
TOML edit — no code change.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from ...adapters.persistence.storage.errors import ClassificationError, DecryptionError, EnvelopeVersionError
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...core.hashing import sha256_hex
from ...core.identity import BucketId
from ...domain.calculations.registry import BindingId, DataBindingDefinition, RegistrySnapshot
from ...domain.modelos._errors import ModeloError
from ..aggregation._source_mesh import (
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from ..live import (
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    BorradorSnapshotNotFoundError,
    LiveApplicationInputError,
    SnapshotLifecycleState,
)
from ._decimal_parsing import decimal_from_string

_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)


class Modelo100BorradorBindingError(ModeloError):
    """Raised when borrador values cannot be consumed for a calculation."""


class Modelo100BorradorBindingCommand(BaseModel):
    """Command contract for resolving one optional borrador snapshot."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=1900, le=9999)
    period: Period
    borrador_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    caller_binding_values: Mapping[BindingId, Decimal] = Field(default_factory=dict)
    caller_enum_binding_values: Mapping[BindingId, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_binding_key_shape(self) -> Modelo100BorradorBindingCommand:
        blank_decimal_keys = sorted(key for key in self.caller_binding_values if not key.strip())
        blank_enum_keys = sorted(key for key in self.caller_enum_binding_values if not key.strip())
        if blank_decimal_keys or blank_enum_keys:
            raise Modelo100BorradorBindingError(
                translated_message="application.modelo.borrador_binding.errors.caller_binding_keys_blank",
            )
        return self


class Modelo100BorradorBindingResult(BaseModel):
    """Values from a borrador snapshot that survived precedence checks.

    Fills the shared binding source-resolution role (see
    :class:`~aeat.application.modelo._binding_resolution.BindingSourceResolution`):
    the AEAT borrador snapshot is one source that resolves registry bindings onto
    the engine ``binding_values`` / ``enum_binding_values`` channels.
    """

    model_config = _STRICT_FROZEN

    borrador_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    binding_values: Mapping[BindingId, Decimal] = Field(default_factory=dict)
    enum_binding_values: Mapping[BindingId, str] = Field(default_factory=dict)
    bindings_sourced_from_borrador: tuple[BindingId, ...] = ()

    @model_validator(mode="after")
    def _enforce_snapshot_trace(self) -> Modelo100BorradorBindingResult:
        if self.borrador_snapshot_id is None:
            if self.binding_values or self.enum_binding_values or self.bindings_sourced_from_borrador:
                raise Modelo100BorradorBindingError(
                    translated_message="application.modelo.borrador_binding.errors.snapshot_id_required",
                )
            return self
        sourced = set(self.bindings_sourced_from_borrador)
        resolved = set(self.binding_values) | set(self.enum_binding_values)
        if sourced != resolved:
            raise Modelo100BorradorBindingError(
                translated_message="application.modelo.borrador_binding.errors.source_trace_mismatch",
            )
        return self


def resolve_modelo_100_borrador_bindings(
    command: Modelo100BorradorBindingCommand,
    *,
    registry_snapshot: RegistrySnapshot,
    snapshot_repository: Borrador100SnapshotRepository | None = None,
) -> Modelo100BorradorBindingResult:
    """Resolve eligible borrador values into a :class:`Modelo100BorradorBindingResult` for one Modelo 100 calculation.

    Args:
        command: The borrador binding command carrying the modelo and bucket axes.
        registry_snapshot: The :class:`RegistrySnapshot` used to verify the
            borrador capability and select ``aeat_prefilled`` bindings.
        snapshot_repository: Optional borrador snapshot repository override.

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
            translated_message="application.modelo.borrador_binding.errors.unsupported_modelo",
            context={"modelo": target_modelo},
        )
    _assert_registry_snapshot_axis(command=command, registry_snapshot=registry_snapshot)
    repository = snapshot_repository or Borrador100SnapshotRepository(bucket_id=command.bucket_id)
    try:
        snapshot = repository.load(command.borrador_snapshot_id)
    except (LiveApplicationInputError, BorradorSnapshotNotFoundError) as exc:
        raise Modelo100BorradorBindingError(
            translated_message="application.modelo.borrador_binding.errors.snapshot_load_failed",
            context={"borrador_snapshot_id": command.borrador_snapshot_id},
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
            translated_message="application.modelo.borrador_binding.errors.snapshot_not_active",
            suggestion="aeat app live borrador 100 list",
        )

    eligible_bindings = _borrador_capable_bindings(registry_snapshot)
    unknown_or_forbidden = sorted(set(snapshot.binding_values) - set(eligible_bindings))
    if unknown_or_forbidden:
        raise Modelo100BorradorBindingError(
            translated_message="application.modelo.borrador_binding.errors.forbidden_bindings",
            context={"bindings": unknown_or_forbidden},
        )

    caller_owned = set(command.caller_binding_values) | set(command.caller_enum_binding_values)
    decimal_values: dict[BindingId, Decimal] = {}
    enum_values: dict[BindingId, str] = {}
    for binding_id, raw_value in snapshot.binding_values.items():
        key = binding_id
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


class Modelo100BorradorSourceResolver:
    """Source mesh adapter for explicitly selected Modelo 100 borrador snapshots."""

    resolver_id = "modelo_100_borrador"
    owned_sources = ("borrador",)

    def __init__(
        self,
        *,
        borrador_snapshot_id: str | None,
        caller_binding_values: Mapping[BindingId, Decimal],
        caller_enum_binding_values: Mapping[BindingId, str],
        registry_snapshot: RegistrySnapshot | None = None,
        snapshot_repository: Borrador100SnapshotRepository | None = None,
    ) -> None:
        self._borrador_snapshot_id = borrador_snapshot_id
        self._caller_binding_values = caller_binding_values
        self._caller_enum_binding_values = caller_enum_binding_values
        self._registry_snapshot = registry_snapshot
        self._snapshot_repository = snapshot_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        snapshot = self._registry_snapshot
        if snapshot is None:
            from ...core.resources import resources

            snapshot = resources().modelos.authority.snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period.registry_token,
            )
        try:
            result = resolve_modelo_100_borrador_bindings(
                Modelo100BorradorBindingCommand(
                    bucket_id=context.bucket_id,
                    modelo=context.modelo,
                    filing_year=context.filing_year,
                    period=context.period,
                    borrador_snapshot_id=self._borrador_snapshot_id,
                    caller_binding_values=self._caller_binding_values,
                    caller_enum_binding_values=self._caller_enum_binding_values,
                ),
                registry_snapshot=snapshot,
                snapshot_repository=self._snapshot_repository,
            )
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        fingerprint = (
            f"sha256:{sha256_hex(result.borrador_snapshot_id.encode('utf-8'))}"
            if result.borrador_snapshot_id is not None
            else None
        )
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=result.binding_values,
            enum_binding_values=result.enum_binding_values,
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="borrador",
                    source_ref=f"borrador:{result.borrador_snapshot_id}:binding:{binding_id}",
                    fingerprint=fingerprint,
                )
                for binding_id in result.bindings_sourced_from_borrador
                if result.borrador_snapshot_id is not None
            ),
        )


def _assert_same_axis(
    *,
    bucket_id: str,
    filing_year: int,
    period: Period,
    snapshot: Borrador100Snapshot,
) -> None:
    expected_bucket = bucket_id.strip()
    if snapshot.bucket_id != expected_bucket:
        raise Modelo100BorradorBindingError(
            translated_message="application.modelo.borrador_binding.errors.snapshot_bucket_mismatch",
        )
    if snapshot.filing_year != filing_year or snapshot.period != period:
        raise Modelo100BorradorBindingError(
            translated_message="application.modelo.borrador_binding.errors.snapshot_axis_mismatch",
            context={
                "snapshot_year": snapshot.filing_year,
                "snapshot_period": snapshot.period.registry_token,
                "filing_year": filing_year,
                "period": period.registry_token,
            },
        )


def _assert_registry_snapshot_axis(
    *,
    command: Modelo100BorradorBindingCommand,
    registry_snapshot: RegistrySnapshot,
) -> None:
    if registry_snapshot.modelo.id != command.modelo.strip():
        raise Modelo100BorradorBindingError(
            translated_message="application.modelo.borrador_binding.errors.registry_snapshot_modelo_mismatch",
            context={
                "snapshot_modelo": registry_snapshot.modelo.id,
                "command_modelo": command.modelo.strip(),
            },
        )
    if (
        registry_snapshot.filing_year != command.filing_year
        or registry_snapshot.period != command.period.registry_token
    ):
        raise Modelo100BorradorBindingError(
            translated_message="application.modelo.borrador_binding.errors.registry_snapshot_axis_mismatch",
            context={
                "snapshot_year": registry_snapshot.filing_year,
                "snapshot_period": registry_snapshot.period,
                "filing_year": command.filing_year,
                "period": command.period.registry_token,
            },
        )


def _borrador_capable_bindings(registry_snapshot: RegistrySnapshot) -> dict[BindingId, DataBindingDefinition]:
    return {
        binding.id: binding for binding in registry_snapshot.revision.bindings if binding.aeat_prefilled is True
    }


def _decimal_value(binding_id: BindingId, value: Decimal | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return decimal_from_string(
        binding_id,
        value,
        error_factory=lambda _message: Modelo100BorradorBindingError(
            translated_message="application.modelo.borrador_binding.errors.decimal_value_invalid",
            context={"binding_id": binding_id},
        ),
        pipeline_label="borrador value",
    )


__all__ = [
    "Modelo100BorradorBindingCommand",
    "Modelo100BorradorBindingError",
    "Modelo100BorradorBindingResult",
    "Modelo100BorradorSourceResolver",
    "resolve_modelo_100_borrador_bindings",
]
