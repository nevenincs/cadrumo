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

See Also:
    :func:`cadrumo.application.modelo._binding_resolution.resolve_borrador_source_tier`
        Binding-resolution tier that inserts this resolver before backend mesh
        and caller-value overlay.
    :class:`cadrumo.application.aggregation._source_mesh.CalculationSourceResolution`
        Typed source-resolution envelope carrying the resolved borrador values.
    :class:`cadrumo.application.aggregation._source_mesh.BorradorSourceProvenance`
        Snapshot id and sourced-binding trace persisted onto the calculation
        revision.
    :class:`cadrumo.application.live.borrador_100.Borrador100SnapshotRepository`
        Secure snapshot repository used to load the explicitly selected
        borrador capture.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, Field, model_validator

from ...adapters.persistence.storage import ClassificationError, DecryptionError, EnvelopeVersionError
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import ActionEvidenceProvenance, Period
from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.filing_year import FilingYear
from ...core.hashing import sha256_hex
from ...core.identity import BucketId
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import (
    DataBindingDefinition,
    RegistrySnapshot,
)
from ...domain.modelos.errors import ModeloError
from ..aggregation import (
    BorradorSourceProvenance,
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from ._action_errors import ModeloPreconditionErrorMixin
from ._decimal_parsing import decimal_from_string
from ._preconditions import build_modelo_precondition_failure

if TYPE_CHECKING:
    from ..live.borrador_100 import Borrador100Snapshot, Borrador100SnapshotRepository

_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)


class Modelo100BorradorBindingError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when borrador values cannot be consumed for a calculation."""


class Modelo100BorradorBindingCommand(BaseModel):
    """Command contract for resolving one optional borrador snapshot.

    The typed :class:`Period` and bucket/modelo axes are checked against both
    the selected :class:`RegistrySnapshot` and the loaded live borrador snapshot
    before any binding values are emitted.
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
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


def resolve_modelo_100_borrador_bindings(
    command: Modelo100BorradorBindingCommand,
    *,
    registry_snapshot: RegistrySnapshot,
    snapshot_repository: Borrador100SnapshotRepository | None = None,
) -> CalculationSourceResolution:
    """Resolve eligible borrador values into a :class:`CalculationSourceResolution` for one Modelo 100 calculation.

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

    Returns:
        A :class:`CalculationSourceResolution` with ``owned_sources`` set to
        ``borrador`` and, when values participate, typed
        :class:`BorradorSourceProvenance` plus generic
        :class:`CalculationSourceProvenance` rows for each sourced binding.
    """
    if command.borrador_snapshot_id is None:
        return CalculationSourceResolution(
            resolver_id=_BORRADOR_RESOLVER_ID,
            owned_sources=(BindingSourceKind.BORRADOR,),
        )

    from ..live.borrador_100 import Borrador100SnapshotRepository, BorradorSnapshotNotFoundError
    from ..live.errors import LiveApplicationInputError
    from ..live.snapshot_base import SnapshotLifecycleState

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
            precondition_failure=build_modelo_precondition_failure(
                subject_leaf_key="modelo.work.calculate",
                condition_id="modelo.work.calculate.borrador_snapshot.active",
                scenario_id="modelo.work.calculate.borrador_snapshot.load_failed",
                evidence_id="modelo.work.calculate.borrador_snapshot",
                evidence_values={
                    "borrador_snapshot_id": command.borrador_snapshot_id,
                    "modelo": command.modelo,
                    "year": command.filing_year,
                    "period": command.period.registry_token,
                },
                provenance=ActionEvidenceProvenance.PERSISTED_STATE,
            ),
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
            precondition_failure=build_modelo_precondition_failure(
                subject_leaf_key="modelo.work.calculate",
                condition_id="modelo.work.calculate.borrador_snapshot.active",
                scenario_id="modelo.work.calculate.borrador_snapshot.inactive",
                evidence_id="modelo.work.calculate.borrador_snapshot",
                evidence_values={
                    "borrador_snapshot_id": command.borrador_snapshot_id,
                    "modelo": command.modelo,
                    "year": command.filing_year,
                    "period": command.period.registry_token,
                    "lifecycle_state": snapshot.state.value,
                },
                provenance=ActionEvidenceProvenance.PERSISTED_STATE,
            ),
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
    snapshot_fingerprint = f"sha256:{sha256_hex(snapshot.snapshot_id.encode('utf-8'))}"
    return CalculationSourceResolution(
        resolver_id=_BORRADOR_RESOLVER_ID,
        owned_sources=(BindingSourceKind.BORRADOR,),
        binding_values=decimal_values,
        enum_binding_values=enum_values,
        borrador_provenance=BorradorSourceProvenance(
            snapshot_id=snapshot.snapshot_id,
            bindings_sourced=sourced,
        ),
        provenance=tuple(
            CalculationSourceProvenance(
                resolver_id="modelo_100_borrador",
                resolved_binding_source=BindingSourceKind.BORRADOR,
                contributor_source_kind="borrador",
                contributor_binding_source=BindingSourceKind.BORRADOR,
                lineage_role=CalculationSourceLineageRole.PRIMARY,
                source_ref=f"borrador:{snapshot.snapshot_id}:binding:{binding_id}",
                parent_source_ref=None,
                fingerprint=snapshot_fingerprint,
            )
            for binding_id in sourced
        ),
    )


_BORRADOR_RESOLVER_ID = "modelo_100_borrador"


class Modelo100BorradorSourceResolver:
    """Source mesh adapter for explicitly selected Modelo 100 borrador snapshots.

    The adapter lets the general source mesh call
    :func:`resolve_modelo_100_borrador_bindings` with a
    :class:`CalculationSourceContext`. When no :class:`RegistrySnapshot` was
    supplied at construction, the context selects one from the registry authority.
    """

    resolver_id: ClassVar[str] = "modelo_100_borrador"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.BORRADOR,)

    def __init__(
        self,
        *,
        borrador_snapshot_id: str | None,
        caller_binding_values: Mapping[BindingId, Decimal],
        caller_enum_binding_values: Mapping[BindingId, str],
        registry_snapshot: RegistrySnapshot | None = None,
        snapshot_repository: Borrador100SnapshotRepository | None = None,
    ) -> None:
        """Bind the borrador snapshot and the caller-supplied binding values."""
        self._borrador_snapshot_id = borrador_snapshot_id
        self._caller_binding_values = caller_binding_values
        self._caller_enum_binding_values = caller_enum_binding_values
        self._registry_snapshot = registry_snapshot
        self._snapshot_repository = snapshot_repository

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve the optional borrador tier for ``context``.

        Secure-storage degradation while loading the selected borrador snapshot
        returns an empty :class:`CalculationSourceResolution` carrying diagnostics
        instead of raising, matching the source-mesh resolver contract.
        """
        snapshot = self._registry_snapshot
        if snapshot is None:
            snapshot = bundled_authority().snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period.registry_token,
            )
        try:
            return resolve_modelo_100_borrador_bindings(
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
    return {binding.id: binding for binding in registry_snapshot.revision.bindings if binding.aeat_prefilled is True}


def _decimal_value(binding_id: BindingId, value: Decimal | str) -> Decimal:
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
    "Modelo100BorradorSourceResolver",
    "resolve_modelo_100_borrador_bindings",
]
