"""Persistence helpers for modelo calculation revisions and filing transitions.

Use of :class:`CalculationRevision`, :class:`CasillaObservation`, :class:`ModeloRecord` for compliance.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.hashing import sha256_hex
from ...domain.buckets import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry import BindingId, CasillaId, CasillaObservation, RelationId
from ...domain.modelos._calculation_repository import upsert_calculation_revision
from ...domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...domain.modelos._filing_record import ModeloRecord, ModeloRecordStatus, derive_filing_record_id
from ...domain.modelos._filing_repository import upsert_filing_record
from ...domain.modelos._participation_index import (
    TransactionParticipationIndexRepository,
    TransactionRevisionParticipation,
    upsert_transaction_participation,
)
from ...domain.modelos._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ...domain.modelos._repository import upsert_work_unit
from ...domain.modelos._row_models import ModeloDetailRow
from ...domain.modelos._work_unit import WorkUnit, WorkUnitCatalogue
from ..calculations import CalculationObservationRepository
from ._filed_revision_observation import persist_filed_revision_observation

if TYPE_CHECKING:  # pragma: no cover - typing-only storage boundary import
    from ...adapters.persistence.storage import SecureObjectWrite

_BUCKET_EVENT_PAYLOAD_VERSION = 2
"""Schema version for the bucket-event payload dict emitted by modelo actions."""


def emit_bucket_event(
    *,
    repository: BucketEventHistoryRepositoryProtocol,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_type: BucketEventObjectType,
    object_id: str,
    payload: Mapping[str, str],
) -> BucketEvent:
    """Append one event to the bucket-event-history catalogue and return the persisted :class:`BucketEvent`."""
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor.strip(),
        object_type=object_type,
        object_id=object_id,
        payload=payload,
    )
    event = BucketEvent(
        event_id=event_id,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor.strip(),
        object_type=object_type,
        object_id=object_id,
        payload_version=_BUCKET_EVENT_PAYLOAD_VERSION,
        payload=dict(payload),
    )
    catalogue = repository.load()
    repository.save(append_bucket_event(catalogue, event))
    return event


def persist_calculation_revision(
    *,
    work_unit_id: str,
    work_unit: WorkUnit,
    work_units: WorkUnitCatalogue,
    input_values_by_casilla_id: dict[CasillaId, str],
    binding_overrides: dict[BindingId, str],
    relation_overrides: dict[RelationId, str],
    casilla_values: dict[CasillaId, Decimal],
    source_transaction_ids: tuple[str, ...],
    borrador_snapshot_id: str | None,
    bindings_sourced_from_borrador: tuple[BindingId, ...],
    observations: tuple[CasillaObservation, ...],
    detail_rows: tuple[ModeloDetailRow, ...],
    formula_count: int,
    actor: str,
    now: datetime,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol,
) -> CalculationRevision:
    """Persist a freshly calculated draft revision and return the :class:`CalculationRevision`.

    Returns the existing duplicate when an identical revision is already persisted.
    Uses :class:`CasillaObservation` for provenance.
    """
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        relation_overrides=relation_overrides,
        casilla_values=casilla_values,
        source_transaction_ids=source_transaction_ids,
        borrador_snapshot_id=borrador_snapshot_id,
        bindings_sourced_from_borrador=bindings_sourced_from_borrador,
        detail_rows=detail_rows,
    )
    revisions = calculation_repository.load()
    existing = revisions.get(revision_id)
    if existing is not None:
        if (
            existing.state is CalculationRevisionState.BORRADOR
            and work_unit.current_calculation_revision_id != revision_id
        ):
            work_unit_repository.save(
                upsert_work_unit(
                    work_units,
                    work_unit.model_copy(
                        update={
                            "current_calculation_revision_id": revision_id,
                            "updated_at": now,
                        },
                    ),
                ),
            )
        return existing

    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=input_values_by_casilla_id,
        binding_overrides=binding_overrides,
        relation_overrides=relation_overrides,
        source_transaction_ids=source_transaction_ids,
        borrador_snapshot_id=borrador_snapshot_id,
        bindings_sourced_from_borrador=bindings_sourced_from_borrador,
        casilla_values=casilla_values,
        observations=observations,
        detail_rows=detail_rows,
        created_at=now,
        updated_at=now,
    )
    calculation_repository.save(upsert_calculation_revision(revisions, revision))
    work_unit_repository.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": revision_id,
                    "updated_at": now,
                },
            ),
        ),
    )
    emit_bucket_event(
        repository=bucket_event_repository,
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id=revision_id,
        payload={
            "calculation_revision_id": revision_id,
            "work_unit_id": work_unit_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "input_casilla_count": str(len(input_values_by_casilla_id)),
            "casilla_count": str(len(casilla_values)),
            "formula_count": str(formula_count),
            "source_transaction_count": str(len(source_transaction_ids)),
            "borrador_snapshot_id": borrador_snapshot_id or "",
            "borrador_participated": "true" if bindings_sourced_from_borrador else "false",
            "borrador_binding_count": str(len(bindings_sourced_from_borrador)),
            "borrador_bindings_trace_sha256": sha256_hex(
                "\n".join(bindings_sourced_from_borrador).encode("utf-8"),
            ),
            "has_provenance": "true" if observations else "false",
        },
    )
    return revision


def _build_filed_participation_writes(
    *,
    filed_target: CalculationRevision,
    work_unit: WorkUnit,
    filing_record_id: str,
    participation_index_repository: TransactionParticipationIndexRepository,
) -> tuple[SecureObjectWrite, ...]:
    """Build the per-transaction participation writes for a filed revision.

    For each ``source_transaction_id`` of the filed revision, load that
    transaction's participation index, upsert the ``PRESENTADO`` participation
    carrying the ``filing_record_id`` (replacing the prior verified entry for the
    same revision in place), and return the resulting ``SecureObjectWrite`` so
    the caller co-emits them in the same atomic unit of work as the filing save.
    """
    writes: list[SecureObjectWrite] = []
    for transaction_id in filed_target.source_transaction_ids:
        index = participation_index_repository.load(transaction_id)
        participation = TransactionRevisionParticipation(
            calculation_revision_id=filed_target.calculation_revision_id,
            work_unit_id=work_unit.work_unit_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            revision_state=CalculationRevisionState.PRESENTADO.value,
            filing_record_id=filing_record_id,
        )
        updated = upsert_transaction_participation(index, participation)
        writes.append(participation_index_repository.to_secure_object_write(updated))
    return tuple(writes)


def persist_filed_revision(
    *,
    target: CalculationRevision,
    work_unit: WorkUnit,
    work_units: WorkUnitCatalogue,
    notes: str | None,
    actor: str,
    now: datetime,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol,
    calculation_observation_repository: CalculationObservationRepository | None = None,
    participation_index_repository: TransactionParticipationIndexRepository | None = None,
    refunded: bool = False,
) -> ModeloRecord:
    """Persist the filing transition for a verified-complete calculation revision and return a :class:`ModeloRecord`.

    Uses :class:`CalculationRevision` for the source revision.

    When ``calculation_observation_repository`` is supplied the filed revision's
    casilla observations are additionally persisted into the cross-period
    observation store (via :func:`persist_filed_revision_observation`,
    co-emitted with the ``MODELO_FILED`` event) so a later period's
    ``calculate`` can carry the filed values forward automatically through the
    ``previous_filing`` resolver. The record is stamped with the NON-official
    ``app_filing`` source_kind and therefore never satisfies the cross-period
    clean-state filing gate. This is a second projection of the single-writer
    filing transition, not a parallel write path.

    ``refunded`` is the disposition-determined fact (resolved once at the
    calculate/file boundary by ``resolve_modelo_result_disposition``): when the
    Modelo 303 period is filed as a refund (devolución, Tipo de declaración
    ``D``) the credit is returned by AEAT, so the persisted cross-period carry
    generates ZERO compensación. It is forwarded verbatim to
    :func:`persist_filed_revision_observation`; the default ``False`` preserves
    the standard compensación carry (RD 1624/1992 art. 30 / Ley 37/1992 art. 116).
    """
    calculation_revision_id = target.calculation_revision_id
    new_filing_id = derive_filing_record_id(
        work_unit_id=target.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        filed_at=now,
        filed_by=actor.strip(),
    )

    filing_catalogue = filing_repository.load()
    prior_current = filing_catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    new_filing = ModeloRecord(
        filing_record_id=new_filing_id,
        work_unit_id=target.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=now,
        filed_by=actor.strip(),
        notes=notes.strip() if notes else None,
        aeat_accepted=False,
        status=ModeloRecordStatus.VIGENTE,
        source_transaction_ids=target.source_transaction_ids,
    )

    revisions = calculation_repository.load()
    updated_filing_catalogue = filing_catalogue
    if prior_current is not None:
        superseded_prior = prior_current.model_copy(
            update={
                "status": ModeloRecordStatus.SUPERSEDIDO,
                "superseded_at": now,
                "superseded_by_filing_record_id": new_filing_id,
            },
        )
        updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, superseded_prior)

        prior_revision = revisions.get(prior_current.calculation_revision_id)
        if prior_revision is not None and prior_revision.state is CalculationRevisionState.PRESENTADO:
            superseded_revision = prior_revision.model_copy(
                update={
                    "state": CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
                    "superseded_at": now,
                    "updated_at": now,
                },
            )
            revisions = upsert_calculation_revision(revisions, superseded_revision)

    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)
    filed_target = target.model_copy(
        update={
            "state": CalculationRevisionState.PRESENTADO,
            "filed_at": now,
            "filed_by": actor.strip(),
            "updated_at": now,
        },
    )
    revisions = upsert_calculation_revision(revisions, filed_target)

    participation_repo = participation_index_repository or TransactionParticipationIndexRepository(
        bucket_id=work_unit.bucket_id,
    )
    participation_writes = _build_filed_participation_writes(
        filed_target=filed_target,
        work_unit=work_unit,
        filing_record_id=new_filing_id,
        participation_index_repository=participation_repo,
    )
    # Co-emit the filed revision, filing catalogue, and per-transaction
    # participation index in the filing repository's save_many call. The
    # participation rows gain filing_record_id in the same SQL unit of work as
    # the filing catalogue, so transaction->filing cross-reference cannot drift
    # from the receipt it names.
    filing_repository.save_with_secure_object_writes(
        updated_filing_catalogue,
        (calculation_repository.to_secure_object_write(revisions), *participation_writes),
    )
    work_unit_repository.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "filed_calculation_revision_id": calculation_revision_id,
                    "current_filing_record_id": new_filing_id,
                    "updated_at": now,
                },
            ),
        ),
    )

    if prior_current is not None:
        emit_bucket_event(
            repository=bucket_event_repository,
            bucket_id=work_unit.bucket_id,
            event_type=BucketEventType.MODELO_FILED_SUPERSEDED,
            occurred_at=now,
            actor=actor,
            object_type=BucketEventObjectType.FILING_RECORD,
            object_id=prior_current.filing_record_id,
            payload={
                "superseded_by_filing_record_id": new_filing_id,
                "calculation_revision_id": prior_current.calculation_revision_id,
                "modelo": work_unit.modelo,
                "filing_year": str(work_unit.filing_year),
                "period": work_unit.period.registry_token,
            },
        )

    emit_bucket_event(
        repository=bucket_event_repository,
        bucket_id=work_unit.bucket_id,
        event_type=BucketEventType.MODELO_FILED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id=new_filing_id,
        payload={
            "calculation_revision_id": calculation_revision_id,
            "work_unit_id": target.work_unit_id,
            "modelo": work_unit.modelo,
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
            "supersedes_filing_record_id": prior_current.filing_record_id if prior_current is not None else "",
        },
    )

    # Cross-period carry projection (co-emitted with MODELO_FILED above): record
    # the filed casilla observations under the NON-official app_filing source so
    # a later period's calculate carries them forward through the previous_filing
    # resolver. Runs after the catalogue saves succeed so a failed filing never
    # leaves a carry row behind.
    if calculation_observation_repository is not None:
        persist_filed_revision_observation(
            revision=filed_target,
            work_unit=work_unit,
            repository=calculation_observation_repository,
            captured_at=now,
            refunded=refunded,
        )

    return new_filing


__all__ = [
    "emit_bucket_event",
    "persist_calculation_revision",
    "persist_filed_revision",
]
