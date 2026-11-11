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
    :func:`cadrumo.application.modelo.binding_resolution.resolve_borrador_source_tier`
        Binding-resolution tier that inserts this resolver before backend mesh
        and caller-value overlay.
    :class:`cadrumo.application.aggregation.source_mesh.CalculationSourceResolution`
        Typed source-resolution envelope carrying the resolved borrador values.
    :class:`cadrumo.application.aggregation.source_mesh.BorradorSourceProvenance`
        Snapshot id and sourced-binding trace persisted onto the calculation
        revision.
    :class:`cadrumo.application.live.borrador_100.Borrador100SnapshotRepository`
        Secure snapshot repository used to load the explicitly selected
        borrador capture.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, Field

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.filing_year import FilingYear
from ...core.hashing import prefixed_digest
from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import (
    BindingDefinition,
    RegistrySnapshot,
)
from ...domain.modelos.errors import ModeloError
from ..aggregation.source_mesh import (
    BorradorSourceProvenance,
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from ..aggregation.source_resolution_operations import storage_degradation_resolution
from ..calculations.revision_carry_gate import revision_carry_outcome
from ..live.borrador_100_keys import borrador_admitted_bindings
from ..persistence_errors import PersistenceDegradationError
from .action_errors import ModeloPreconditionErrorMixin
from .decimal_parsing import decimal_from_string
from .preconditions import build_modelo_calculate_refusal_failure, build_modelo_precondition_failure

if TYPE_CHECKING:
    from ..live.borrador_100 import Borrador100Snapshot, Borrador100SnapshotRepository


class Modelo100BorradorBindingError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when borrador values cannot be consumed for a calculation."""


class Modelo100BorradorBindingCommand(BaseModel):
    """Command contract for resolving one optional borrador snapshot.

    The typed :class:`Period` and bucket/modelo axes are checked against both
    the selected :class:`RegistrySnapshot` and the loaded live borrador snapshot
    before any binding values are emitted.
    """

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    modelo: str = Field(min_length=1, max_length=16)
    filing_year: FilingYear
    period: Period
    borrador_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)


def _borrador_snapshot_load_failure(
    command: Modelo100BorradorBindingCommand,
    *,
    snapshot_id: str,
) -> Modelo100BorradorBindingError:
    """Build the shared refusal for a snapshot that cannot be used."""
    return Modelo100BorradorBindingError(
        translated_message="application.modelo.borrador_binding.errors.snapshot_load_failed",
        context={"borrador_snapshot_id": snapshot_id},
        precondition_failure=build_modelo_precondition_failure(
            subject_leaf_key="modelo.work.calculate",
            condition_id="modelo.work.calculate.borrador_snapshot.active",
            scenario_id="modelo.work.calculate.borrador_snapshot.load_failed",
            evidence_id="modelo.work.calculate.borrador_snapshot",
            evidence_values={
                "borrador_snapshot_id": snapshot_id,
                "modelo": command.modelo,
                "year": command.filing_year,
                "period": command.period.registry_token,
            },
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        ),
    )


def _borrador_snapshot_inactive_failure(
    command: Modelo100BorradorBindingCommand,
    snapshot: Borrador100Snapshot,
    *,
    snapshot_id: str,
) -> Modelo100BorradorBindingError:
    """Build the refusal for a snapshot that is no longer active."""
    return Modelo100BorradorBindingError(
        translated_message="application.modelo.borrador_binding.errors.snapshot_not_active",
        precondition_failure=build_modelo_precondition_failure(
            subject_leaf_key="modelo.work.calculate",
            condition_id="modelo.work.calculate.borrador_snapshot.active",
            scenario_id="modelo.work.calculate.borrador_snapshot.inactive",
            evidence_id="modelo.work.calculate.borrador_snapshot",
            evidence_values={
                "borrador_snapshot_id": snapshot_id,
                "modelo": command.modelo,
                "year": command.filing_year,
                "period": command.period.registry_token,
                "lifecycle_state": snapshot.state.value,
            },
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        ),
    )


def _load_active_borrador_snapshot(
    command: Modelo100BorradorBindingCommand,
    *,
    snapshot_id: str,
    snapshot_repository: Borrador100SnapshotRepository | None,
    operation: PinnedAuthorityOperation,
) -> Borrador100Snapshot:
    """Load the selected snapshot and enforce its axis and active lifecycle."""
    from ..live.borrador_100 import BorradorSnapshotNotFoundError
    from ..live.errors import LiveApplicationInputError
    from ..live.snapshot_base import SnapshotLifecycleState

    if snapshot_repository is None:
        raise _borrador_snapshot_load_failure(command, snapshot_id=snapshot_id)
    repository = snapshot_repository
    try:
        snapshot = repository.load(snapshot_id)
    except (LiveApplicationInputError, BorradorSnapshotNotFoundError) as exc:
        raise _borrador_snapshot_load_failure(command, snapshot_id=snapshot_id) from exc
    _assert_same_axis(
        bucket_id=command.bucket_id,
        filing_year=command.filing_year,
        period=command.period,
        snapshot=snapshot,
    )
    if revision_carry_outcome(snapshot.registry_snapshot_ref, operation=operation).refused:
        raise _borrador_snapshot_load_failure(command, snapshot_id=snapshot_id)
    if snapshot.state is not SnapshotLifecycleState.ACTIVE:
        raise _borrador_snapshot_inactive_failure(command, snapshot, snapshot_id=snapshot_id)
    return snapshot


def _assert_borrador_bindings_allowed(
    snapshot: Borrador100Snapshot,
    eligible_bindings: dict[BindingId, BindingDefinition],
) -> None:
    """Refuse stored keys the revision does not admit, free casilla keys included."""
    unknown_or_forbidden = sorted(set(snapshot.binding_values) - set(eligible_bindings))
    if unknown_or_forbidden:
        raise Modelo100BorradorBindingError(
            translated_message="application.modelo.borrador_binding.errors.forbidden_bindings",
            context={"bindings": unknown_or_forbidden},
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="borrador_snapshot.bindings_forbidden",
                evidence_values={
                    "forbidden_binding_count": len(unknown_or_forbidden),
                    "forbidden_binding_ids": "|".join(unknown_or_forbidden),
                },
            ),
        )


def _resolve_borrador_binding_values(
    snapshot: Borrador100Snapshot,
    *,
    eligible_bindings: dict[BindingId, BindingDefinition],
) -> tuple[dict[BindingId, Decimal], dict[BindingId, str]]:
    """Project every eligible snapshot value; the precedence overlay decides which tier's value is used.

    A ``cross_check_only`` binding is held by the snapshot for comparison and
    never enters this tier, so the borrador cannot fill a value that the
    binding's own evidence leaves missing.
    """
    decimal_values: dict[BindingId, Decimal] = {}
    enum_values: dict[BindingId, str] = {}
    for binding_id, raw_value in snapshot.binding_values.items():
        binding = eligible_bindings[binding_id]
        if binding.value.typed_enum is not None:
            if binding.borrador_supplies_value:
                enum_values[binding_id] = str(raw_value).strip()
            continue
        # Parsed even when only compared, so a malformed stored value is refused rather than ignored.
        value = decimal_value(binding_id, raw_value)
        if binding.borrador_supplies_value:
            decimal_values[binding_id] = value
    return decimal_values, enum_values


def _borrador_resolution(
    snapshot: Borrador100Snapshot,
    *,
    decimal_values: dict[BindingId, Decimal],
    enum_values: dict[BindingId, str],
) -> CalculationSourceResolution:
    """Build the typed source resolution and both provenance projections."""
    sourced = tuple(sorted(set(decimal_values) | set(enum_values)))
    snapshot_fingerprint = prefixed_digest(snapshot.snapshot_id.encode("utf-8"))
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
                terminal_origin=TerminalOriginClass.AEAT_THIRD_PARTY_DATA,
                fingerprint=snapshot_fingerprint,
            )
            for binding_id in sourced
        ),
    )


def resolve_modelo_100_borrador_bindings(
    command: Modelo100BorradorBindingCommand,
    *,
    registry_snapshot: RegistrySnapshot,
    snapshot_repository: Borrador100SnapshotRepository | None = None,
    operation: PinnedAuthorityOperation,
) -> CalculationSourceResolution:
    """Resolve eligible borrador values into a :class:`CalculationSourceResolution` for one Modelo 100 calculation.

    Args:
        command: The borrador binding command carrying the modelo and bucket axes.
        registry_snapshot: The :class:`RegistrySnapshot` used to verify the
            borrador capability and select ``aeat_prefilled`` bindings.
        snapshot_repository: Optional borrador snapshot repository override.
        operation: Caller-owned authority operation used for all governed
            revision reads and revision-carry re-confirmation.

    The function is deliberately inert when no snapshot is supplied:
    borrador values are never consumed implicitly. When a snapshot is
    supplied, the snapshot may only contribute bindings explicitly marked
    ``aeat_prefilled`` by the registry revision passed to the service and not
    declared ``cross_check_only``; a snapshot may still hold those, for
    comparison. Caller values take precedence in the overlay, which still sees
    every value the snapshot states.

    Returns:
        A :class:`CalculationSourceResolution` with ``owned_sources`` set to
        ``borrador`` and, when values participate, typed
        :class:`BorradorSourceProvenance` plus generic
        :class:`CalculationSourceProvenance` rows for each sourced binding.
    """
    snapshot_id = command.borrador_snapshot_id
    if snapshot_id is None:
        return CalculationSourceResolution(
            resolver_id=_BORRADOR_RESOLVER_ID,
            owned_sources=(BindingSourceKind.BORRADOR,),
        )

    if not registry_snapshot.modelo.has_capability("borrador"):
        target_modelo = command.modelo.strip()
        raise Modelo100BorradorBindingError(
            translated_message="application.modelo.borrador_binding.errors.unsupported_modelo",
            context={"modelo": target_modelo},
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="borrador_snapshot.modelo_unsupported",
                evidence_values={"modelo": target_modelo, "borrador_capability": False},
            ),
        )
    _assert_registry_snapshot_axis(command=command, registry_snapshot=registry_snapshot)
    snapshot = _load_active_borrador_snapshot(
        command,
        snapshot_id=snapshot_id,
        snapshot_repository=snapshot_repository,
        operation=operation,
    )
    eligible_bindings = borrador_admitted_bindings(registry_snapshot.revision)
    _assert_borrador_bindings_allowed(snapshot, eligible_bindings)
    decimal_values, enum_values = _resolve_borrador_binding_values(snapshot, eligible_bindings=eligible_bindings)
    return _borrador_resolution(snapshot, decimal_values=decimal_values, enum_values=enum_values)


def borrador_cross_check_values(
    command: Modelo100BorradorBindingCommand,
    *,
    registry_snapshot: RegistrySnapshot,
    snapshot_repository: Borrador100SnapshotRepository | None,
    operation: PinnedAuthorityOperation,
) -> dict[BindingId, Decimal]:
    """Return the amounts a selected borrador snapshot holds for its ``cross_check_only`` bindings.

    These are the values the borrador states for credits it may only compare:
    they never enter a calculation. Empty when no snapshot is selected, which a
    credit reconciliation reads as a cross-check with nothing to compare.

    ``registry_snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    snapshot_id = command.borrador_snapshot_id
    if snapshot_id is None:
        return {}
    _assert_registry_snapshot_axis(command=command, registry_snapshot=registry_snapshot)
    snapshot = _load_active_borrador_snapshot(
        command,
        snapshot_id=snapshot_id,
        snapshot_repository=snapshot_repository,
        operation=operation,
    )
    eligible_bindings = borrador_admitted_bindings(registry_snapshot.revision)
    _assert_borrador_bindings_allowed(snapshot, eligible_bindings)
    return {
        binding_id: decimal_value(binding_id, raw_value)
        for binding_id, raw_value in snapshot.binding_values.items()
        if eligible_bindings[binding_id].value.typed_enum is None
        and not eligible_bindings[binding_id].borrador_supplies_value
    }


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
        registry_snapshot: RegistrySnapshot | None = None,
        snapshot_repository: Borrador100SnapshotRepository | None = None,
        operation: PinnedAuthorityOperation,
    ) -> None:
        """Bind the borrador snapshot this tier reads."""
        self._borrador_snapshot_id = borrador_snapshot_id
        self._registry_snapshot = registry_snapshot
        self._snapshot_repository = snapshot_repository
        self._operation = operation

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve the optional borrador tier for ``context``.

        Secure-storage degradation while loading the selected borrador snapshot
        returns an empty :class:`CalculationSourceResolution` carrying diagnostics
        instead of raising, matching the source-mesh resolver contract.
        """
        snapshot = self._registry_snapshot
        if snapshot is None:
            snapshot = self._operation.reading_snapshot(
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
                ),
                registry_snapshot=snapshot,
                snapshot_repository=self._snapshot_repository,
                operation=self._operation,
            )
        except PersistenceDegradationError as exc:
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
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="borrador_snapshot.bucket_mismatch",
                evidence_values={"snapshot_in_active_bucket": False},
            ),
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
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="borrador_snapshot.axis_mismatch",
                evidence_values={
                    "snapshot_year": snapshot.filing_year,
                    "snapshot_period": snapshot.period.registry_token,
                    "year": filing_year,
                    "period": period.registry_token,
                },
            ),
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
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="borrador_snapshot.registry_modelo_mismatch",
                evidence_values={
                    "registry_modelo": registry_snapshot.modelo.id,
                    "requested_modelo": command.modelo.strip(),
                },
            ),
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
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="borrador_snapshot.registry_axis_mismatch",
                evidence_values={
                    "registry_year": registry_snapshot.filing_year,
                    "registry_period": registry_snapshot.period,
                    "year": command.filing_year,
                    "period": command.period.registry_token,
                },
            ),
        )


def decimal_value(binding_id: BindingId, value: Decimal | str) -> Decimal:
    """Parse a decimal string for a borrador binding or refuse with a binding error."""
    return decimal_from_string(
        binding_id,
        value,
        error_factory=lambda _message: Modelo100BorradorBindingError(
            translated_message="application.modelo.borrador_binding.errors.decimal_value_invalid",
            context={"binding_id": binding_id},
            precondition_failure=build_modelo_calculate_refusal_failure(
                scenario="borrador_snapshot.value_invalid",
                evidence_values={"binding_id": binding_id},
            ),
        ),
        pipeline_label="borrador value",
    )


__all__ = [
    "Modelo100BorradorBindingCommand",
    "Modelo100BorradorBindingError",
    "Modelo100BorradorSourceResolver",
    "borrador_cross_check_values",
    "resolve_modelo_100_borrador_bindings",
]
