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

from datetime import UTC, datetime

from ...domain.modelos._codes import ModeloCode
from ...domain.modelos._errors import ModeloError
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
    """Raised when discard is invoked on a work unit already discarded.

    Idempotent retries are not supported because the discard verb
    emits an audit event; repeating the event for the same unit
    would create a misleading trail.
    """


class WorkUnitMutationRefusedError(ModeloError):
    """Raised when a mutation targets a discarded work unit.

    Once discarded, a work unit's metadata is frozen. Renames and
    other mutations against a discarded unit are rejected; the
    operator must create a fresh work unit on the same modelo /
    year / period to continue.
    """


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


__all__ = [
    "WorkUnitAlreadyDiscardedError",
    "WorkUnitMutationRefusedError",
    "WorkUnitNotFoundError",
    "create_work_unit",
    "discard_work_unit",
    "get_work_unit",
    "list_work_units",
    "rename_work_unit",
]
