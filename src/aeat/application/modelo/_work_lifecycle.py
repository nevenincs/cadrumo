"""Lifecycle mutations for modelo work units.

This module creates, lists, renames, and discards
:class:`aeat.domain.modelos.WorkUnit` records in the
:class:`aeat.domain.modelos.WorkUnitCatalogueRepository`.
Each mutating action emits a typed event through
:class:`BucketEventHistoryRepository`, giving
:func:`aeat.application.modelo.assemble_work_unit_history` a complete
timeline from creation through discard.

The lifecycle layer mutates the work-unit catalogue only. It does not choose
visible filing targets (see :mod:`aeat.application.modelo._work_addressing`),
does not decide unsupported-modelo or applicability policy (see
:mod:`aeat.application.modelo._work_create_policy`), and does not persist
calculation revisions or filing records. Creation still performs the profile
readiness and registry revision/period gates before inserting the work unit, so
programmatic callers observe the same safety boundary as the CLI.

See Also:
    :mod:`aeat.application.modelo._work_addressing`:
        Resolves natural or exact operator targets before lifecycle mutation.
    :func:`aeat.application.modelo.assemble_work_unit_history`:
        Reads the emitted bucket events into a chronological work-unit timeline.
    :class:`CalculationRevision`:
        Defines calculation attempts and current/filed pointers under a work unit.
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
    enforce_applicability: bool = True,
) -> WorkUnit:
    """Create or load the :class:`WorkUnit` for an exact filing target key.

    The key is ``bucket_id`` + ``modelo`` + ``filing_year`` + ``period`` +
    ``revision_id``. The revision id must be known to the bundled registry and
    the period must be declared for that revision. The active profile must also
    be ready for the requested modelo work before any record is inserted.

    If the derived work-unit id already exists, the existing record is returned
    without emitting another creation event. Otherwise a BORRADOR work unit is
    inserted and a ``MODELO_WORK_UNIT_CREATED`` bucket event is appended.
    """
    if period.filing_year != filing_year:
        raise WorkUnitMutationRefusedError(
            f"filing_year {filing_year!r} does not match period year {period.filing_year!r}",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period_year": period.filing_year,
                "period": period.registry_token,
                "revision_id": revision_id,
            },
            suggestion="pass a Period whose filing year matches the filing_year argument",
        )
    from ._profile_readiness_gate import (
        require_existing_profile_baseline_ready_for_modelo_work,
        require_profile_ready_for_modelo_work,
    )

    require_existing_profile_baseline_ready_for_modelo_work(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        enforce_applicability=enforce_applicability,
    )
    reject_unknown_revision(modelo=modelo, revision_id=revision_id)
    reject_unknown_period_for_revision(modelo=modelo, revision_id=revision_id, period=period)

    require_profile_ready_for_modelo_work(
        bucket_id=bucket_id,
        modelo=modelo,
        revision_id=revision_id,
        filing_year=filing_year,
        period=period,
        enforce_applicability=enforce_applicability,
    )
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
    """Return :class:`WorkUnit` records, optionally filtered to one bucket.

    Discarded work units are hidden by default so operator-facing discovery sees
    only active draft roots. Pass ``include_discarded=True`` for audit/history
    views that need the abandoned records.
    """
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
    """Return one :class:`WorkUnit` by id or raise :class:`WorkUnitNotFoundError`."""
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
    """Update a :class:`WorkUnit` display name and emit a rename event.

    Discarded work units are immutable through this lifecycle surface; callers
    must create a fresh work unit for renewed work on the same filing target.
    Successful renames preserve the content-addressed work-unit id and update
    only display metadata plus ``updated_at``.
    """
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
    """Transition a :class:`WorkUnit` to ``DESCARTADO`` and emit a discard event.

    Discard is a durable state transition, not a physical delete. The work-unit
    record remains available for history/audit reads, repeated discards refuse
    with :class:`WorkUnitAlreadyDiscardedError`, and active-listing callers must
    opt in with ``include_discarded=True`` to see the abandoned root.
    """
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
