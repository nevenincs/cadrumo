"""Work-unit lifecycle actions for modelo filings.

Use of :class:`BucketEventHistoryRepository` for compliance.
"""

from __future__ import annotations

from datetime import datetime

from ...core import Period
from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventHistoryRepository, BucketEventObjectType, BucketEventType
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.contribuyente._ccaa import CCAA
from ...domain.modelos._codes import ModeloCode
from ...domain.modelos._protocols import WorkUnitCatalogueRepositoryProtocol
from ...domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ...domain.modelos._work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ._action_errors import WorkUnitAlreadyDiscardedError, WorkUnitMutationRefusedError, WorkUnitNotFoundError
from ._registry_resources import reject_unknown_period_for_revision, reject_unknown_revision
from ._revision_persistence import emit_bucket_event as _emit_bucket_event


def _default_name(*, modelo: str, filing_year: int, period: Period) -> str:
    """Return the default display name for a fresh work unit."""
    return f"{modelo}-{filing_year}-{period.registry_token}"


def create_work_unit(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
    revision_id: str,
    name: str | None = None,
    actor: str = "system",
    causante_ccaa: CCAA | None = None,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Create or load a :class:`WorkUnit` for the filing target key."""
    reject_unknown_revision(modelo=modelo, revision_id=revision_id)
    if period.filing_year != filing_year:
        raise ValueError(f"filing_year {filing_year!r} does not match period year {period.filing_year!r}")
    reject_unknown_period_for_revision(modelo=modelo, revision_id=revision_id, period=period)
    repo = repository or WorkUnitCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    catalogue = repo.load()
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
    )
    existing = catalogue.get(work_unit_id)
    if existing is not None:
        return existing
    now = clock or _utc_now()
    unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=name.strip() if name else _default_name(modelo=modelo, filing_year=filing_year, period=period),
        created_at=now,
        updated_at=now,
        causante_ccaa=causante_ccaa,
    )
    repo.save(upsert_work_unit(catalogue, unit))
    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=unit.bucket_id,
        event_type=BucketEventType.MODELO_WORK_UNIT_CREATED,
        occurred_at=now,
        actor=actor,
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=unit.work_unit_id,
        payload={
            "modelo": str(unit.modelo),
            "filing_year": str(unit.filing_year),
            "period": unit.period.registry_token,
            "revision_id": unit.revision_id,
            "name": unit.name,
        },
    )
    return unit


def list_work_units(
    *,
    bucket_id: str | None = None,
    include_discarded: bool = False,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
) -> tuple[WorkUnit, ...]:
    """Return :class:`WorkUnit` records, optionally filtered to one bucket."""
    repo = repository or WorkUnitCatalogueRepository()
    catalogue = repo.load()
    units = tuple(
        unit
        for unit in catalogue.values()
        if (bucket_id is None or unit.bucket_id == bucket_id)
        and (include_discarded or unit.state is WorkUnitState.BORRADOR)
    )
    return tuple(
        sorted(
            units,
            key=lambda u: (
                u.bucket_id,
                u.filing_year,
                str(u.modelo),
                u.period.registry_token,
            ),
        ),
    )


def get_work_unit(
    work_unit_id: str,
    *,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
) -> WorkUnit:
    """Return one :class:`WorkUnit` by id."""
    repo = repository or WorkUnitCatalogueRepository()
    catalogue = repo.load()
    unit = catalogue.get(work_unit_id)
    if unit is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    return unit


def rename_work_unit(
    work_unit_id: str,
    new_name: str,
    *,
    actor: str,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Update a :class:`WorkUnit` display name, bump ``updated_at``, and return the updated record."""
    repo = repository or WorkUnitCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    catalogue: WorkUnitCatalogue = repo.load()
    existing = catalogue.get(work_unit_id)
    if existing is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    if existing.state is WorkUnitState.DESCARTADO:
        raise WorkUnitMutationRefusedError(
            f"work unit {work_unit_id!r} is discarded; "
            "create a fresh work unit on the same modelo / year / period to continue",
            translated_message="application.modelo.errors.work_unit_mutation_refused",
        )
    now = clock or _utc_now()
    cleaned_name = new_name.strip()
    cleaned_actor = actor.strip()
    renamed = existing.model_copy(update={"name": cleaned_name, "updated_at": now})
    repo.save(upsert_work_unit(catalogue, renamed))
    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=renamed.bucket_id,
        event_type=BucketEventType.MODELO_WORK_UNIT_RENAMED,
        occurred_at=now,
        actor=cleaned_actor,
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=renamed.work_unit_id,
        payload={
            "modelo": str(renamed.modelo),
            "filing_year": str(renamed.filing_year),
            "period": renamed.period.registry_token,
            "previous_name": existing.name,
            "new_name": cleaned_name,
        },
    )
    return renamed


def discard_work_unit(
    work_unit_id: str,
    *,
    actor: str,
    reason: str | None = None,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Transition a :class:`WorkUnit` to ``DISCARDED`` state and return the updated record."""
    repo = repository or WorkUnitCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    catalogue: WorkUnitCatalogue = repo.load()
    existing = catalogue.get(work_unit_id)
    if existing is None:
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    if existing.state is WorkUnitState.DESCARTADO:
        raise WorkUnitAlreadyDiscardedError(
            f"work unit {work_unit_id!r} is already discarded "
            f"(by {existing.discarded_by!r} at {existing.discarded_at!s})",
            translated_message="application.modelo.errors.work_unit_already_discarded",
        )
    now = clock or _utc_now()
    discarded = existing.model_copy(
        update={
            "state": WorkUnitState.DESCARTADO,
            "discarded_at": now,
            "discarded_by": actor.strip(),
            "discard_reason": reason.strip() if reason else None,
            "updated_at": now,
        },
    )
    repo.save(upsert_work_unit(catalogue, discarded))
    _emit_bucket_event(
        repository=bv_repo,
        bucket_id=discarded.bucket_id,
        event_type=BucketEventType.MODELO_WORK_UNIT_DISCARDED,
        occurred_at=now,
        actor=discarded.discarded_by or actor.strip(),
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=discarded.work_unit_id,
        payload={
            "modelo": str(discarded.modelo),
            "filing_year": str(discarded.filing_year),
            "period": discarded.period.registry_token,
            "reason": discarded.discard_reason or "",
        },
    )
    return discarded
