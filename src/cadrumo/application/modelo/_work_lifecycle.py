"""Lifecycle mutations for modelo work units.

This module creates, lists, renames, and discards
:class:`cadrumo.domain.modelos.WorkUnit` records in the
:class:`cadrumo.domain.modelos.WorkUnitCatalogueRepository`.
Each mutating action emits a typed event through
:class:`BucketEventHistoryRepository`, giving
:func:`cadrumo.application.modelo.assemble_work_unit_history` a complete
timeline from creation through discard.

The lifecycle layer mutates the work-unit catalogue only. It does not choose
visible filing targets (see :mod:`cadrumo.application.modelo._work_addressing`),
does not decide unsupported-modelo or applicability policy (see
:mod:`cadrumo.application.modelo._work_create_policy`), and does not persist
calculation revisions or filing records. Creation still performs the profile
readiness and registry revision/period gates before inserting the work unit, so
programmatic callers observe the same safety boundary as the CLI.

See Also:
    :mod:`cadrumo.application.modelo._work_addressing`:
        Resolves natural or exact operator targets before lifecycle mutation.
    :func:`cadrumo.application.modelo.assemble_work_unit_history`:
        Reads the emitted bucket events into a chronological work-unit timeline.
    :class:`CalculationRevision`:
        Defines calculation attempts and current/filed pointers under a work unit.
"""

from __future__ import annotations

from datetime import datetime

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...core import Period
from ...core.time import now as _utc_now
from ...domain.buckets import BucketEventHistoryRepositoryProtocol, BucketEventObjectType, BucketEventType
from ...domain.contribuyente import CCAA
from ...domain.modelos import (
    ModeloCode,
    WorkUnit,
    WorkUnitCatalogue,
    WorkUnitCatalogueRepositoryProtocol,
    WorkUnitState,
    derive_work_unit_id,
    upsert_work_unit,
)
from ._action_errors import WorkUnitAlreadyDiscardedError, WorkUnitMutationRefusedError, WorkUnitNotFoundError
from ._registry_resources import reject_unknown_period_for_revision, reject_unknown_revision
from ._revision_persistence import build_modelo_bucket_event as _build_bucket_event
from ._revision_persistence import modelo_bucket_event_write as _bucket_event_write


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

    If the derived work-unit id already exists and is still active, the existing
    record is returned without emitting another creation event. Otherwise a
    BORRADOR work unit is inserted and a ``MODELO_WORK_UNIT_CREATED`` bucket
    event is appended.

    A DESCARTADO unit is REFUSED rather than returned. Because the id is
    content-addressed over exactly the coordinates this function is given, a
    retry after a discard re-derives the same id, so returning the record handed
    the caller a unit every downstream verb then reports as absent — stranding
    that filing target. The refusal states the dead end instead of restating the
    command that produced it. Recovery needs a supersede transition, which does
    not exist yet.
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
        if existing.state is WorkUnitState.DESCARTADO:
            raise WorkUnitMutationRefusedError(
                f"work unit {work_unit_id!r} for {modelo} {filing_year} "
                f"{period.registry_token} is discarded, and creating it again "
                "resolves to that same discarded unit because the id is "
                "content-addressed over exactly these coordinates",
                translated_message="application.modelo.errors.work_unit_create_discarded",
                context={
                    "work_unit_id": work_unit_id,
                    "state": existing.state.value,
                    "modelo": modelo,
                    "filing_year": str(filing_year),
                    "period": period.registry_token,
                    "discarded_at": str(existing.discarded_at),
                    "discarded_by": existing.discarded_by or "",
                },
            )
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
    # One unit of work: the new work unit and MODELO_WORK_UNIT_CREATED. Emitted
    # through a separate write, an event-storage failure left the unit durable
    # while the history had no record that it was ever created.
    created_event = _build_bucket_event(
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
    repo.save_with_secure_object_writes(
        upsert_work_unit(catalogue, unit),
        (_bucket_event_write(bv_repo, (created_event,)),),
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


def _work_unit_in_repository_bucket(
    work_unit_id: str,
    *,
    repository: WorkUnitCatalogueRepositoryProtocol,
) -> WorkUnit:
    """Return the work unit addressed by ``work_unit_id`` within this bucket.

    :class:`WorkUnitCatalogue` may hold rows for more than one bucket -- which is
    why :func:`list_work_units` takes a bucket filter -- but the single-subject
    surfaces looked units up by id alone. A caller bound to bucket A could
    therefore read, rename, or discard a valid bucket-B unit and emit a
    lifecycle event scoped to B, bypassing the bucket authority at the command
    boundary entirely.

    A unit belonging to another bucket is reported as NOT FOUND rather than as a
    refusal: from this repository's scope it genuinely is not addressable, and a
    distinct refusal would confirm the existence of a work unit in a bucket the
    caller has no claim on.

    The check is skipped only when the repository resolved no bucket of its own,
    where there is no scope to compare against.
    """
    catalogue = repository.load()
    unit = catalogue.get(work_unit_id)
    repository_bucket = repository.bucket_id
    if unit is None or (repository_bucket is not None and unit.bucket_id != repository_bucket):
        raise WorkUnitNotFoundError(
            translated_message="application.modelo.errors.work_unit_not_found",
            context={"work_unit_id": work_unit_id},
        )
    return unit


def get_work_unit(
    work_unit_id: str,
    *,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
) -> WorkUnit:
    """Return one :class:`WorkUnit` by id or raise :class:`WorkUnitNotFoundError`.

    Scoped to the repository's own bucket: a unit belonging to another bucket is
    not addressable here and reads as not found.
    """
    repo = repository or WorkUnitCatalogueRepository()
    return _work_unit_in_repository_bucket(work_unit_id, repository=repo)


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

    Scoped to the repository's own bucket: a unit belonging to another bucket is
    not addressable here, so an A-bound caller cannot rename a B unit and emit a
    B-scoped rename event.
    """
    repo = repository or WorkUnitCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    existing = _work_unit_in_repository_bucket(work_unit_id, repository=repo)
    catalogue: WorkUnitCatalogue = repo.load()
    if existing.state is WorkUnitState.DESCARTADO:
        raise WorkUnitMutationRefusedError(
            f"work unit {work_unit_id!r} is discarded, and re-creating the same "
            "modelo / year / period resolves to this same discarded unit rather "
            "than a fresh one",
            translated_message="application.modelo.errors.work_unit_mutation_refused",
        )
    now = clock or _utc_now()
    cleaned_name = new_name.strip()
    cleaned_actor = actor.strip()
    renamed = existing.model_copy(update={"name": cleaned_name, "updated_at": now})
    # One unit of work: the renamed unit and MODELO_WORK_UNIT_RENAMED.
    renamed_event = _build_bucket_event(
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
    repo.save_with_secure_object_writes(
        upsert_work_unit(catalogue, renamed),
        (_bucket_event_write(bv_repo, (renamed_event,)),),
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

    Scoped to the repository's own bucket: a unit belonging to another bucket is
    not addressable here, so an A-bound caller cannot discard a B unit and emit a
    B-scoped discard event.
    """
    repo = repository or WorkUnitCatalogueRepository()
    bv_repo = bucket_event_repository or BucketEventHistoryRepository()
    existing = _work_unit_in_repository_bucket(work_unit_id, repository=repo)
    catalogue: WorkUnitCatalogue = repo.load()
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
    # One unit of work: the discarded unit and MODELO_WORK_UNIT_DISCARDED.
    discarded_event = _build_bucket_event(
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
    repo.save_with_secure_object_writes(
        upsert_work_unit(catalogue, discarded),
        (_bucket_event_write(bv_repo, (discarded_event,)),),
    )
    return discarded
