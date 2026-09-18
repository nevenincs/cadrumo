"""Operator-supplied local filed observations for calculation prefill.

This module records local, non-official observations in the pending-local
layer of the cross-period calculation observation store, and clears them again.
Each recorded figure is an audited override: it names the actor, the reason and
what it replaced, and the official layer it may sit above is never destroyed.
It deliberately does not create a
:class:`ModeloRecord` and does not stamp :class:`ExternalEvidence`: the values are
operator-supplied scratch/local inputs that can feed relation and
``previous_filing`` calculation prefill, but they must never satisfy the
filing-grade clean-state proof that requires AEAT-backed evidence.

Each persisted observation is grounded against the law-determined
:class:`ModeloRevision` -- resolved structurally via ``select_revision``,
never a filing-grade snapshot, since recording a non-official local
observation is not itself a filing act -- and stored as provenance-bearing
:class:`CasillaObservation` rows, while the source kind stays explicitly
non-official.

See Also:
    :func:`~application.modelo.filed_revision_observation.persist_filed_revision_observation`:
        Local-filing projection that uses ``app_filing`` rather than
        operator-manual source.
    :mod:`~application.calculations.cross_period_clean_state`:
        Classifies local observations as non-official for filing-grade readiness.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field, ValidationError

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.clock import now as _utc_now
from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import bucket_event_history_write
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.bindings import (
    CasillaObservation,
    RegistryModeloObservation,
)
from ...domain.calculations.registry.casilla_membership import (
    casilla_noncanonical_reference_targets,
    casillas_by_id,
    format_noncanonical_casilla_reference,
    undeclared_casilla_ids,
)
from ...domain.calculations.registry.errors import (
    RegistrySnapshotError,
    RegistryValidationError,
)
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    ObservationOverride,
    ObservationSourceKind,
    member_observation_key,
)
from ._registry_helpers import NUMERIC_CASILLA_DATA_TYPES
from .action_errors import ModeloLocalObservationError
from .revision_persistence import build_modelo_bucket_event
from .work_addressing import ModeloWorkSelectorError
from .work_selection import ModeloWorkSelectionMode, ModeloWorkSelectorRequest, select_modelo_work_resolution

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND: Final = ObservationSourceKind.OPERATOR_MANUAL
"""Non-official source kind for operator-supplied local observations."""


@dataclass(frozen=True, slots=True)
class LocalObservationPorts:
    """Persistence authorities one operator observation override reads and co-commits."""

    bucket_id: str
    observation_repository: CalculationObservationRepositoryProtocol
    bucket_event_repository: BucketEventHistoryRepositoryProtocol
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol


LOCAL_OBSERVATION_ACTION_CARRIES_DETAIL: Mapping[str, bool] = {
    "recorded": True,
    "cleared": False,
}
"""Whether each local-observation outcome carries the observation's own detail.

Recording an override states a revision, a source kind and the values it
overrides; clearing one states none of them, because the layer it removed is
what held them. The two results below are the typed halves of that split, and
this mapping is what a projection of either consults rather than restating it.
"""


class ModeloLocalObservationResult(BaseModel):
    """Result of recording one operator-supplied local observation."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    filing_year: int
    period: Period
    member_nif: str | None = None
    revision_id: RevisionId
    observation_key: str
    source_kind: ObservationSourceKind
    casilla_values: dict[CasillaId, Decimal] = Field(min_length=1)
    captured_at: datetime
    captured_by: str
    override: ObservationOverride
    official_evidence: bool = False
    filing_record_created: bool = False
    aeat_accepted: bool = False


class ModeloLocalObservationClearResult(BaseModel):
    """Result of clearing one operator override from the pending-local layer."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    filing_year: int
    period: Period
    member_nif: str | None = None
    observation_key: str
    cleared_override: ObservationOverride
    cleared_at: datetime
    cleared_by: str
    reason: str
    effective_source_kind: ObservationSourceKind | None = None


def record_operator_local_observation[CasillaKey](
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    casilla_values: Mapping[CasillaKey, object],
    reason: str,
    actor: str,
    ports: LocalObservationPorts,
    operation: PinnedAuthorityOperation,
    member_nif: str | None = None,
    clock: datetime | None = None,
) -> ModeloLocalObservationResult:
    """Persist an audited operator figure in the pending-local layer of one coordinate.

    The observation is grounded against the law-determined
    :class:`ModeloRevision` for ``modelo`` / ``filing_year`` /
    ``period``. Every supplied casilla id must be a canonical numeric
    casilla declared by that revision; printed-number aliases and
    unknown ids are refused before the observation store is touched.

    The persisted envelope uses ``source_kind="operator_manual"`` and carries
    the revision id as its stamp plus an :class:`ObservationOverride` naming
    the actor, the reason, and the envelope that was effective before. An
    official layer stays stored underneath. Calculation prefill then resolves
    the operator values, while cross-period clean-state verification still
    treats them as non-official local evidence. The envelope and a
    ``modelo.observation.overridden`` event commit together.

    Returns:
        A :class:`ModeloLocalObservationResult` describing the persisted local
        observation stamp.
    """
    captured_by, stated_reason = _required_audit_text(actor=actor, reason=reason)
    _require_period_year(filing_year=filing_year, period=period)
    if modelo == "303":
        raise ModeloLocalObservationError(
            "Modelo 303 observations require canonical filed or official evidence with a result disposition",
            context={"modelo": modelo, "filing_year": filing_year, "period": period.registry_token},
        )
    revision = _load_revision(modelo=modelo, filing_year=filing_year, period=period, operation=operation)
    canonical_values = _canonical_casilla_values(revision=revision, casilla_values=casilla_values)
    observations = _observation_rows(revision=revision, casilla_values=canonical_values)
    observation = RegistryModeloObservation(
        modelo=modelo,
        filing_year=filing_year,
        period=period.registry_token,
        observations=observations,
    )
    captured_at = clock or _utc_now()
    key = member_observation_key(modelo, period, member_nif)
    repo = ports.observation_repository
    replaced = repo.load_observation_layers(modelo, period, member_nif=member_nif).effective
    override = ObservationOverride(
        actor=captured_by,
        reason=stated_reason,
        recorded_at=captured_at,
        replaced_source_kind=replaced.source_kind if replaced is not None else None,
        replaced_values=(
            {casilla_id: str(value) for casilla_id, value in replaced.observation.casilla_values.items()}
            if replaced is not None
            else {}
        ),
    )
    payload = repo.prepare_observation_envelope(
        observation,
        source_kind=OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND,
        captured_at=captured_at,
        stamped_revision_id=revision.id,
        member_nif=member_nif,
        source_metadata={
            "local_observation_kind": "operator_supplied",
            "captured_by": captured_by,
            "official_evidence": "false",
            "filing_record_created": "false",
        },
        override=override,
    )
    replaced_kind = override.replaced_source_kind
    event = _override_event(
        ports=ports,
        event_type=BucketEventType.MODELO_OBSERVATION_OVERRIDDEN,
        modelo=modelo,
        period=period,
        member_nif=member_nif,
        actor=captured_by,
        occurred_at=captured_at,
        extra={
            "reason": stated_reason,
            "replaced_source_kind": replaced_kind.value if replaced_kind is not None else "",
            "casilla_count": str(len(canonical_values)),
        },
    )
    repo.secure_object_repository.apply_batch(
        (
            repo.to_secure_object_write(payload),
            bucket_event_history_write(ports.bucket_event_repository, (event,)),
        ),
    )
    return ModeloLocalObservationResult(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        member_nif=member_nif,
        revision_id=revision.id,
        observation_key=key,
        source_kind=OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND,
        casilla_values=dict(canonical_values),
        captured_at=captured_at,
        captured_by=captured_by,
        override=override,
    )


def clear_operator_local_observation(
    modelo: str,
    filing_year: int,
    period: Period,
    *,
    member_nif: str | None = None,
    reason: str,
    actor: str,
    ports: LocalObservationPorts,
    clock: datetime | None = None,
) -> ModeloLocalObservationClearResult:
    """Remove the operator override from the pending-local layer of one coordinate.

    The official layer, when stored, becomes effective again. The removal and a
    ``modelo.observation.override_cleared`` event commit together.

    Raises:
        ModeloLocalObservationError: The coordinate holds no operator override
            in its pending-local layer, or the actor or reason is blank.
    """
    cleared_by, stated_reason = _required_audit_text(actor=actor, reason=reason)
    _require_period_year(filing_year=filing_year, period=period)
    repo = ports.observation_repository
    layers = repo.load_observation_layers(modelo, period, member_nif=member_nif)
    pending = layers.pending_local
    if pending is None or pending.override is None:
        raise ModeloLocalObservationError(
            translated_message="application.modelo.errors.local_observation_override_missing",
            context={"modelo": modelo, "filing_year": filing_year, "period": period.registry_token},
        )
    cleared_at = clock or _utc_now()
    event = _override_event(
        ports=ports,
        event_type=BucketEventType.MODELO_OBSERVATION_OVERRIDE_CLEARED,
        modelo=modelo,
        period=period,
        member_nif=member_nif,
        actor=cleared_by,
        occurred_at=cleared_at,
        extra={
            "reason": stated_reason,
            "cleared_override_actor": pending.override.actor,
            "cleared_override_recorded_at": pending.override.recorded_at.isoformat(),
        },
    )
    repo.secure_object_repository.apply_batch(
        (
            *repo.clear_pending_local(modelo, period, member_nif=member_nif),
            bucket_event_history_write(ports.bucket_event_repository, (event,)),
        ),
    )
    return ModeloLocalObservationClearResult(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        member_nif=member_nif,
        observation_key=member_observation_key(modelo, period, member_nif),
        cleared_override=pending.override,
        cleared_at=cleared_at,
        cleared_by=cleared_by,
        reason=stated_reason,
        effective_source_kind=layers.official.source_kind if layers.official is not None else None,
    )


def _required_audit_text(*, actor: str, reason: str) -> tuple[str, str]:
    stated_actor = actor.strip()
    if not stated_actor:
        raise ModeloLocalObservationError(
            translated_message="application.modelo.errors.local_observation_actor_blank",
        )
    stated_reason = reason.strip()
    if not stated_reason:
        raise ModeloLocalObservationError(
            translated_message="application.modelo.errors.local_observation_reason_blank",
        )
    return stated_actor, stated_reason


def _require_period_year(*, filing_year: int, period: Period) -> None:
    if period.filing_year != filing_year:
        raise ModeloLocalObservationError(
            translated_message="application.modelo.errors.external_import_source_period_mismatch",
            context={"filing_year": filing_year, "period": period.registry_token},
        )


def _active_work_unit_id(ports: LocalObservationPorts, *, modelo: str, period: Period) -> str:
    """Return the one active work unit of the coordinate, or ``""`` when there is none or several."""
    try:
        resolution = select_modelo_work_resolution(
            ModeloWorkSelectorRequest(
                bucket_id=ports.bucket_id,
                modelo=ModeloCode(modelo),
                filing_year=period.filing_year,
                period=period,
            ),
            catalogue=ports.work_unit_repository.load(),
            bucket_id=ports.bucket_id,
            mode=ModeloWorkSelectionMode.ACTIVE_NATURAL,
        )
    except ModeloWorkSelectorError:
        return ""
    return resolution.work_unit.work_unit_id if resolution.work_unit is not None else ""


def _override_event(
    *,
    ports: LocalObservationPorts,
    event_type: BucketEventType,
    modelo: str,
    period: Period,
    member_nif: str | None,
    actor: str,
    occurred_at: datetime,
    extra: Mapping[str, str],
) -> BucketEvent:
    work_unit_id = _active_work_unit_id(ports, modelo=modelo, period=period)
    if work_unit_id:
        object_type, object_id = BucketEventObjectType.WORK_UNIT, work_unit_id
    else:
        object_type, object_id = BucketEventObjectType.BUCKET, ports.bucket_id
    return build_modelo_bucket_event(
        bucket_id=ports.bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload={
            "work_unit_id": work_unit_id,
            "modelo": modelo,
            "filing_year": str(period.filing_year),
            "period": period.registry_token,
            "member_scoped": "true" if member_nif is not None else "false",
            **extra,
        },
    )


def _load_revision(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> ModeloRevision:
    try:
        return operation.revision_for_context(modelo, filing_year=filing_year, period=period.registry_token)
    except RegistrySnapshotError as exc:
        raise ModeloLocalObservationError(
            (
                f"local observation cannot be recorded because the registry revision is missing for "
                f"modelo={modelo!r} filing_year={filing_year} period={period.registry_token!r}"
            ),
            context={"modelo": modelo, "filing_year": filing_year, "period": period.registry_token},
        ) from exc


def _require_local_observation_values[CasillaKey](casilla_values: Mapping[CasillaKey, object]) -> None:
    """Require at least one operator value before touching registry state."""
    if not casilla_values:
        raise ModeloLocalObservationError(
            translated_message="errors.error.error_modelos",
            context={"casilla_value_count": 0},
        )


def _canonicalize_local_observation_values[CasillaKey](
    casilla_values: Mapping[CasillaKey, object],
) -> tuple[dict[CasillaId, Decimal], list[str], list[str]]:
    """Separate canonical Decimal rows from malformed input diagnostics."""
    canonical: dict[CasillaId, Decimal] = {}
    malformed: list[str] = []
    non_decimal: list[str] = []
    for key, value in casilla_values.items():
        try:
            casilla_id = validated_casilla_id(key, surface="local observation casilla")
        except ValueError:
            malformed.append(repr(key))
            continue
        if isinstance(value, bool) or not isinstance(value, Decimal):
            non_decimal.append(casilla_id)
            continue
        canonical[casilla_id] = value
    return canonical, malformed, non_decimal


def _raise_local_observation_input_errors(
    *,
    revision: ModeloRevision,
    malformed: list[str],
    non_decimal: list[str],
) -> None:
    """Raise canonical boundary diagnostics in their original precedence."""
    if malformed:
        raise ModeloLocalObservationError(
            translated_message="errors.error.error_modelos",
            context={"casillas": ",".join(sorted(malformed)), "revision_id": revision.id},
        )
    if non_decimal:
        raise ModeloLocalObservationError(
            translated_message="errors.error.error_modelos",
            context={"casillas": ",".join(sorted(non_decimal)), "revision_id": revision.id},
        )


def _raise_unknown_local_observation_casillas(
    *,
    revision: ModeloRevision,
    canonical: Mapping[CasillaId, Decimal],
) -> None:
    """Reject undeclared ids and explain printed-number ambiguity."""
    unknown = undeclared_casilla_ids(revision, canonical)
    if not unknown:
        return
    noncanonical = {
        casilla_id: targets
        for casilla_id in unknown
        if (targets := casilla_noncanonical_reference_targets(revision, casilla_id))
    }
    if noncanonical:
        details = "; ".join(
            format_noncanonical_casilla_reference(casilla_id, targets)
            for casilla_id, targets in sorted(noncanonical.items())
        )
        raise ModeloLocalObservationError(
            translated_message="errors.error.error_modelos",
            context={
                "casillas": ",".join(sorted(noncanonical)),
                "revision_id": revision.id,
                "noncanonical_reference_targets": details,
            },
        )
    raise ModeloLocalObservationError(
        translated_message="errors.error.error_modelos",
        context={"casillas": ",".join(unknown), "revision_id": revision.id},
    )


def _raise_non_numeric_local_observation_casillas(
    *,
    revision: ModeloRevision,
    canonical: Mapping[CasillaId, Decimal],
) -> None:
    """Reject canonical ids whose registry declaration is not numeric."""
    declared = casillas_by_id(revision)
    non_numeric = sorted(
        casilla_id for casilla_id in canonical if declared[casilla_id].data_type not in NUMERIC_CASILLA_DATA_TYPES
    )
    if non_numeric:
        raise ModeloLocalObservationError(
            translated_message="errors.error.error_modelos",
            context={"casillas": ",".join(non_numeric), "revision_id": revision.id},
        )


def _canonical_casilla_values[CasillaKey](
    *,
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaKey, object],
) -> dict[CasillaId, Decimal]:
    """Validate and return registry-canonical numeric local observation values."""
    _require_local_observation_values(casilla_values)
    canonical, malformed, non_decimal = _canonicalize_local_observation_values(casilla_values)
    _raise_local_observation_input_errors(
        revision=revision,
        malformed=malformed,
        non_decimal=non_decimal,
    )
    _raise_unknown_local_observation_casillas(revision=revision, canonical=canonical)
    _raise_non_numeric_local_observation_casillas(revision=revision, canonical=canonical)

    return canonical


def _observation_rows(
    *,
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
) -> tuple[CasillaObservation, ...]:
    declared = casillas_by_id(revision)
    rows: list[CasillaObservation] = []
    for casilla_id, value in casilla_values.items():
        casilla = declared[casilla_id]
        try:
            rows.append(
                CasillaObservation(
                    casilla_id=casilla_id,
                    value=value,
                    legal_refs=casilla.legal_refs,
                    source_refs=casilla.source_refs,
                ),
            )
        except (RegistryValidationError, ValidationError, TypeError, ValueError) as exc:
            raise ModeloLocalObservationError(
                translated_message="errors.error.error_modelos",
                context={"casilla": casilla_id, "revision_id": revision.id},
            ) from exc
    return tuple(rows)


__all__ = [
    "OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND",
    "LocalObservationPorts",
    "ModeloLocalObservationClearResult",
    "ModeloLocalObservationResult",
    "clear_operator_local_observation",
    "record_operator_local_observation",
]
