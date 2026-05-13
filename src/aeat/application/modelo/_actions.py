"""Modelo work-unit lifecycle actions.

Each action loads the catalogue, applies a single mutation in
memory (or returns a read view), and writes the catalogue back.
The catalogue is content-addressed by ``work_unit_id`` so
deterministic deriveation lets ``create_work_unit`` be idempotent:
calling it twice with the same four-axis key returns the same
record without producing a duplicate.

The action signatures take an explicit ``bucket_id`` so the
service layer is unit-testable without a workflow-state fixture.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

from ...domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ...domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...domain.modelos._codes import ModeloCode
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._filing_record import (
    FilingRecord,
    FilingRecordCatalogue,
    FilingRecordStatus,
    derive_filing_record_id,
)
from ...domain.modelos._filing_repository import (
    FilingRecordCatalogueRepository,
    upsert_filing_record,
)
from ...domain.modelos._repository import (
    WorkUnitCatalogueRepository,
    upsert_work_unit,
)
from ...domain.modelos._work_unit import (
    WorkUnit,
    WorkUnitCatalogue,
    WorkUnitState,
    derive_work_unit_id,
)


class WorkUnitNotFoundError(ModeloError, KeyError):
    """Raised when a work-unit lookup or mutation targets a missing id."""


class WorkUnitAlreadyDiscardedError(ModeloError):
    """Raised when discard is invoked on a work unit already discarded."""


class WorkUnitMutationRefusedError(ModeloError):
    """Raised when a mutation targets a discarded work unit."""


class CalculationRevisionNotFoundError(ModeloError, KeyError):
    """Raised when a calculation revision lookup fails."""


class CalculationRevisionStateError(ModeloError):
    """Raised when a state transition is requested from an incompatible source state.

    Examples: marking a non-draft revision as verified-complete;
    filing a revision that is not verified-complete; verifying a
    revision that has already been filed.
    """


class FilingRecordNotFoundError(ModeloError, KeyError):
    """Raised when a filing record lookup fails."""


def _default_name(*, modelo: str, filing_year: int, period: str) -> str:
    """Return the default display name for a fresh work unit.

    Shape: ``<modelo>-<year>-<period>`` (e.g. ``303-2026-Q1``).
    Callers may supply their own name; this helper exists so the
    domain shape stays predictable when the operator does not
    care to name the unit.
    """
    return f"{modelo}-{filing_year}-{period}"


def create_work_unit(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    revision_id: str,
    name: str | None = None,
    repository: WorkUnitCatalogueRepository | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Create or load a work unit for the four-axis key.

    Idempotent: when a work unit already exists under the
    deterministic id, the existing record is returned unchanged.
    A subsequent call with a different ``name`` does NOT mutate the
    persisted name; ``rename_work_unit`` is the dedicated mutation
    surface for that.

    Args:
        bucket_id: Stable bucket the work unit belongs to.
        modelo: AEAT modelo code (e.g. ``"303"``).
        filing_year: Tax year for the filing.
        period: Filing period token (e.g. ``"Q1"``).
        revision_id: Stable id of the targeted modelo revision.
        name: Optional display name; defaults to
            ``<modelo>-<year>-<period>``.
        repository: Repository override for testing; defaults to
            the canonical ``WorkUnitCatalogueRepository``.
        clock: ``datetime`` override for testing the created /
            updated timestamps. Defaults to ``datetime.now(UTC)``.

    Returns:
        The persisted :class:`aeat.domain.modelos.WorkUnit`.
    """

    repo = repository or WorkUnitCatalogueRepository()
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
    now = clock or datetime.now(UTC)
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
    )
    updated = upsert_work_unit(catalogue, unit)
    repo.save(updated)
    return unit


def list_work_units(
    *,
    bucket_id: str | None = None,
    include_discarded: bool = False,
    repository: WorkUnitCatalogueRepository | None = None,
) -> tuple[WorkUnit, ...]:
    """Return work units, optionally filtered to one bucket.

    Discarded work units are excluded by default; pass
    ``include_discarded=True`` to see them. The result is sorted
    by ``(bucket_id, filing_year, modelo, period)`` so consumers
    see a stable ordering across calls without re-sorting.
    """

    repo = repository or WorkUnitCatalogueRepository()
    catalogue = repo.load()
    units = tuple(
        unit
        for unit in catalogue.values()
        if (bucket_id is None or unit.bucket_id == bucket_id)
        and (include_discarded or unit.state is WorkUnitState.DRAFT)
    )
    return tuple(
        sorted(
            units,
            key=lambda u: (
                u.bucket_id,
                u.filing_year,
                str(u.modelo),
                u.period,
            ),
        )
    )


def get_work_unit(
    work_unit_id: str,
    *,
    repository: WorkUnitCatalogueRepository | None = None,
) -> WorkUnit:
    """Return one work unit by id.

    Raises:
        WorkUnitNotFoundError: When no work unit lives under
            ``work_unit_id``. ``KeyError`` is in the base classes
            so callers that prefer the Python idiom can still
            ``except KeyError``.
    """

    repo = repository or WorkUnitCatalogueRepository()
    catalogue = repo.load()
    unit = catalogue.get(work_unit_id)
    if unit is None:
        raise WorkUnitNotFoundError(f"no modelo work unit with work_unit_id={work_unit_id!r}")
    return unit


def rename_work_unit(
    work_unit_id: str,
    new_name: str,
    *,
    repository: WorkUnitCatalogueRepository | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Update a work unit's display name and bump ``updated_at``.

    The ``work_unit_id`` does not change — the identifier is
    content-addressed by the four-axis key, not by display name.
    """

    repo = repository or WorkUnitCatalogueRepository()
    catalogue: WorkUnitCatalogue = repo.load()
    existing = catalogue.get(work_unit_id)
    if existing is None:
        raise WorkUnitNotFoundError(f"no modelo work unit with work_unit_id={work_unit_id!r}")
    if existing.state is WorkUnitState.DISCARDED:
        raise WorkUnitMutationRefusedError(
            f"work unit {work_unit_id!r} is discarded; "
            "create a fresh work unit on the same modelo / year / period to continue"
        )
    now = clock or datetime.now(UTC)
    renamed = existing.model_copy(update={"name": new_name.strip(), "updated_at": now})
    updated_catalogue = upsert_work_unit(catalogue, renamed)
    repo.save(updated_catalogue)
    return renamed


def discard_work_unit(
    work_unit_id: str,
    *,
    actor: str,
    reason: str | None = None,
    repository: WorkUnitCatalogueRepository | None = None,
    clock: datetime | None = None,
) -> WorkUnit:
    """Transition a work unit to ``DISCARDED`` state.

    Audit metadata (``discarded_at``, ``discarded_by``, optional
    ``discard_reason``) is captured in the same write. Once
    discarded, the work unit cannot be renamed or re-activated;
    the operator must create a fresh work unit on the same modelo
    / year / period.

    Raises:
        WorkUnitNotFoundError: When ``work_unit_id`` is absent.
        WorkUnitAlreadyDiscardedError: When the unit is already
            in ``DISCARDED`` state. Idempotent retries would
            corrupt the audit trail.
    """

    repo = repository or WorkUnitCatalogueRepository()
    catalogue: WorkUnitCatalogue = repo.load()
    existing = catalogue.get(work_unit_id)
    if existing is None:
        raise WorkUnitNotFoundError(f"no modelo work unit with work_unit_id={work_unit_id!r}")
    if existing.state is WorkUnitState.DISCARDED:
        raise WorkUnitAlreadyDiscardedError(
            f"work unit {work_unit_id!r} is already discarded "
            f"(by {existing.discarded_by!r} at {existing.discarded_at!s})"
        )
    now = clock or datetime.now(UTC)
    discarded = existing.model_copy(
        update={
            "state": WorkUnitState.DISCARDED,
            "discarded_at": now,
            "discarded_by": actor.strip(),
            "discard_reason": reason.strip() if reason else None,
            "updated_at": now,
        }
    )
    updated_catalogue = upsert_work_unit(catalogue, discarded)
    repo.save(updated_catalogue)
    return discarded


# ---------------------------------------------------------------------------
# Calculation revision lifecycle: calculate / verify / mark-verified / file
# ---------------------------------------------------------------------------


def calculate_modelo_revision(
    work_unit_id: str,
    *,
    inputs_snapshot: Mapping[str, str] | None = None,
    binding_overrides: Mapping[str, str] | None = None,
    casilla_values: Mapping[str, Decimal],
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    clock: datetime | None = None,
) -> CalculationRevision:
    """Persist a new draft calculation revision for ``work_unit_id``.

    Records the operator-supplied or registry-computed casilla
    values as the snapshot. The revision id is content-addressed
    by the inputs + overrides + outputs, so a structurally
    identical re-run is naturally idempotent (existing revision
    returned, no duplicate persisted). The work unit's
    ``current_calculation_revision_id`` pointer is advanced to the
    newly-persisted revision.

    The work unit must exist and must not be in ``DISCARDED``
    state. The revision starts in ``DRAFT`` state; callers must
    run ``mark_verified_complete`` and ``file_modelo_revision``
    explicitly to move it through the verified and filed states.
    """

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    work_units = wu_repo.load()
    work_unit = work_units.get(work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"no modelo work unit with work_unit_id={work_unit_id!r}"
        )
    if work_unit.state is WorkUnitState.DISCARDED:
        raise WorkUnitMutationRefusedError(
            f"work unit {work_unit_id!r} is discarded; cannot calculate"
        )
    inputs = dict(inputs_snapshot or {})
    overrides = dict(binding_overrides or {})
    outputs = dict(casilla_values)
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot=inputs,
        binding_overrides=overrides,
        casilla_values=outputs,
    )
    revisions = cr_repo.load()
    existing = revisions.get(revision_id)
    if existing is not None:
        # Idempotent: structurally identical re-run, return the
        # existing revision without re-persisting.
        return existing
    now = clock or datetime.now(UTC)
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.DRAFT,
        inputs_snapshot=inputs,
        binding_overrides=overrides,
        casilla_values=outputs,
        created_at=now,
        updated_at=now,
    )
    cr_repo.save(upsert_calculation_revision(revisions, revision))
    # Advance the work unit's current pointer to the new revision.
    wu_repo.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "current_calculation_revision_id": revision_id,
                    "updated_at": now,
                }
            ),
        )
    )
    return revision


def list_calculation_revisions(
    *,
    work_unit_id: str | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
) -> tuple[CalculationRevision, ...]:
    """List calculation revisions, optionally filtered to one work unit.

    Results are sorted by ``(work_unit_id, created_at)`` so the
    chronological revision chain for one work unit is contiguous
    and stable across calls.
    """

    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    revisions = tuple(
        revision
        for revision in catalogue.values()
        if work_unit_id is None or revision.work_unit_id == work_unit_id
    )
    return tuple(sorted(revisions, key=lambda r: (r.work_unit_id, r.created_at)))


def get_calculation_revision(
    calculation_revision_id: str,
    *,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
) -> CalculationRevision:
    """Return one calculation revision by id, or raise."""

    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    revision = catalogue.get(calculation_revision_id)
    if revision is None:
        raise CalculationRevisionNotFoundError(
            f"no calculation revision with id={calculation_revision_id!r}"
        )
    return revision


def mark_revision_verified_complete(
    calculation_revision_id: str,
    *,
    actor: str,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    clock: datetime | None = None,
) -> CalculationRevision:
    """Transition a draft revision to ``VERIFIED_COMPLETE``.

    The revision must currently be in ``DRAFT`` state. After the
    transition the revision is immutable; subsequent calculation
    work on the same work unit must produce a new revision.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is
            absent.
        CalculationRevisionStateError: When the revision is not
            currently in ``DRAFT`` state.
    """

    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    catalogue = cr_repo.load()
    existing = catalogue.get(calculation_revision_id)
    if existing is None:
        raise CalculationRevisionNotFoundError(
            f"no calculation revision with id={calculation_revision_id!r}"
        )
    if existing.state is not CalculationRevisionState.DRAFT:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{existing.state.value!r}; only DRAFT revisions can be marked verified-complete"
        )
    now = clock or datetime.now(UTC)
    verified = existing.model_copy(
        update={
            "state": CalculationRevisionState.VERIFIED_COMPLETE,
            "verified_at": now,
            "verified_by": actor.strip(),
            "updated_at": now,
        }
    )
    cr_repo.save(upsert_calculation_revision(catalogue, verified))
    return verified


def file_modelo_revision(
    calculation_revision_id: str,
    *,
    actor: str,
    notes: str | None = None,
    work_unit_repository: WorkUnitCatalogueRepository | None = None,
    calculation_repository: CalculationRevisionCatalogueRepository | None = None,
    filing_repository: FilingRecordCatalogueRepository | None = None,
    clock: datetime | None = None,
) -> FilingRecord:
    """File a verified-complete revision as the current filed answer.

    State transitions performed atomically (from the caller's
    perspective — each repository save is sequenced):

    1. Verify the revision is in ``VERIFIED_COMPLETE`` state.
    2. Look up any existing current filing record for the same
       (bucket, modelo, year, period) tuple.
    3. If a prior current filing exists:
        * mark the prior filing record ``SUPERSEDED`` with
          ``superseded_at`` and ``superseded_by_filing_record_id``;
        * transition the prior filed calculation revision from
          ``FILED`` to ``FILED_SUPERSEDED``.
    4. Create the new filing record with status ``CURRENT``.
    5. Transition the target calculation revision from
       ``VERIFIED_COMPLETE`` to ``FILED``.
    6. Advance the work unit's ``filed_calculation_revision_id``
       and ``current_filing_record_id`` pointers.

    Raises:
        CalculationRevisionNotFoundError: When the revision id is
            absent.
        CalculationRevisionStateError: When the revision is not in
            ``VERIFIED_COMPLETE`` state.
        WorkUnitNotFoundError: When the revision's parent work
            unit cannot be loaded.
    """

    wu_repo = work_unit_repository or WorkUnitCatalogueRepository()
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository()
    fr_repo = filing_repository or FilingRecordCatalogueRepository()

    revisions = cr_repo.load()
    target = revisions.get(calculation_revision_id)
    if target is None:
        raise CalculationRevisionNotFoundError(
            f"no calculation revision with id={calculation_revision_id!r}"
        )
    if target.state is not CalculationRevisionState.VERIFIED_COMPLETE:
        raise CalculationRevisionStateError(
            f"calculation revision {calculation_revision_id!r} is in state "
            f"{target.state.value!r}; only VERIFIED_COMPLETE revisions can be filed"
        )

    work_units = wu_repo.load()
    work_unit = work_units.get(target.work_unit_id)
    if work_unit is None:
        raise WorkUnitNotFoundError(
            f"calculation revision {calculation_revision_id!r} references missing "
            f"work_unit_id={target.work_unit_id!r}"
        )

    now = clock or datetime.now(UTC)

    new_filing_id = derive_filing_record_id(
        work_unit_id=target.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        filed_at=now,
        filed_by=actor.strip(),
    )

    filing_catalogue = fr_repo.load()
    prior_current = filing_catalogue.current_for(
        bucket_id=work_unit.bucket_id,
        modelo=str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period,
    )

    # 1. Build new current filing record.
    new_filing = FilingRecord(
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
        status=FilingRecordStatus.CURRENT,
    )

    # 2. Supersede prior filing record if present.
    updated_filing_catalogue = filing_catalogue
    if prior_current is not None:
        superseded_prior = prior_current.model_copy(
            update={
                "status": FilingRecordStatus.SUPERSEDED,
                "superseded_at": now,
                "superseded_by_filing_record_id": new_filing_id,
            }
        )
        updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, superseded_prior)

        # Transition prior filed calculation revision to FILED_SUPERSEDED.
        prior_revision = revisions.get(prior_current.calculation_revision_id)
        if prior_revision is not None and prior_revision.state is CalculationRevisionState.FILED:
            superseded_revision = prior_revision.model_copy(
                update={
                    "state": CalculationRevisionState.FILED_SUPERSEDED,
                    "superseded_at": now,
                    "updated_at": now,
                }
            )
            revisions = upsert_calculation_revision(revisions, superseded_revision)

    # 3. Insert new filing record + transition target revision to FILED.
    updated_filing_catalogue = upsert_filing_record(updated_filing_catalogue, new_filing)
    filed_target = target.model_copy(
        update={
            "state": CalculationRevisionState.FILED,
            "filed_at": now,
            "filed_by": actor.strip(),
            "updated_at": now,
        }
    )
    revisions = upsert_calculation_revision(revisions, filed_target)

    # 4. Persist (catalogue saves are sequenced).
    cr_repo.save(revisions)
    fr_repo.save(updated_filing_catalogue)

    # 5. Advance work-unit pointers.
    wu_repo.save(
        upsert_work_unit(
            work_units,
            work_unit.model_copy(
                update={
                    "filed_calculation_revision_id": calculation_revision_id,
                    "current_filing_record_id": new_filing_id,
                    "updated_at": now,
                }
            ),
        )
    )

    return new_filing


def list_filing_records(
    *,
    bucket_id: str | None = None,
    include_superseded: bool = False,
    filing_repository: FilingRecordCatalogueRepository | None = None,
) -> tuple[FilingRecord, ...]:
    """List filing records, optionally filtered to a bucket.

    Superseded records are excluded unless ``include_superseded``
    is true. Results are sorted by ``(bucket_id, filing_year,
    modelo, period, filed_at)``.
    """

    fr_repo = filing_repository or FilingRecordCatalogueRepository()
    catalogue = fr_repo.load()
    records = tuple(
        record
        for record in catalogue.values()
        if (bucket_id is None or record.bucket_id == bucket_id)
        and (include_superseded or record.status is FilingRecordStatus.CURRENT)
    )
    return tuple(
        sorted(
            records,
            key=lambda r: (r.bucket_id, r.filing_year, str(r.modelo), r.period, r.filed_at),
        )
    )


def get_filing_record(
    filing_record_id: str,
    *,
    filing_repository: FilingRecordCatalogueRepository | None = None,
) -> FilingRecord:
    """Return one filing record by id, or raise."""

    fr_repo = filing_repository or FilingRecordCatalogueRepository()
    catalogue = fr_repo.load()
    record = catalogue.get(filing_record_id)
    if record is None:
        raise FilingRecordNotFoundError(
            f"no filing record with id={filing_record_id!r}"
        )
    return record


__all__ = [
    "CalculationRevisionNotFoundError",
    "CalculationRevisionStateError",
    "FilingRecordNotFoundError",
    "WorkUnitAlreadyDiscardedError",
    "WorkUnitMutationRefusedError",
    "WorkUnitNotFoundError",
    "calculate_modelo_revision",
    "create_work_unit",
    "discard_work_unit",
    "file_modelo_revision",
    "get_calculation_revision",
    "get_filing_record",
    "get_work_unit",
    "list_calculation_revisions",
    "list_filing_records",
    "list_work_units",
    "mark_revision_verified_complete",
    "rename_work_unit",
]
