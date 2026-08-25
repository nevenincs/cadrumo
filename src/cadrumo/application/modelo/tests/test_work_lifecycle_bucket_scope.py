"""Single-subject work-unit surfaces stay inside their repository's bucket.

:class:`WorkUnitCatalogue` may hold rows for more than one bucket -- which is why
``list_work_units`` takes a bucket filter -- but ``get``, ``rename``, and
``discard`` looked units up by id alone. An A-bound operator could therefore
read, rename, or discard a valid B work unit and emit a lifecycle event scoped to
B, bypassing the bucket authority at the command boundary.

Real adapters throughout: an encrypted-SQLite runtime, the production
repositories, and the production catalogue mutators. Nothing is stubbed.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import Period
from ....domain.modelos import WorkUnit, WorkUnitState, derive_work_unit_id, upsert_work_unit
from ....tests.secure_sql import isolated_runtime_profile
from .._action_errors import WorkUnitNotFoundError
from .._work_lifecycle import (
    discard_work_unit,
    get_work_unit,
    list_work_units,
    rename_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_A = "5aa00000-0000-4000-8000-0000000000aa"
_BUCKET_B = "5bb00000-0000-4000-8000-0000000000bb"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)


def _unit(bucket_id: str, *, modelo: str = "130") -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=2026,
            period=period,
            revision_id="2019-y-siguientes",
        ),
        bucket_id=bucket_id,
        name=f"{modelo}-2026-1T",
        modelo=modelo,
        filing_year=2026,
        period=period,
        revision_id="2019-y-siguientes",
        created_at=_T0,
        updated_at=_T0,
    )


@pytest.fixture
def a_bound_repository(tmp_path: Path) -> Iterator[tuple[WorkUnitCatalogueRepository, BucketEventHistoryRepository]]:
    """Yield an A-bound catalogue repository holding both an A and a B unit."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_A) as profile:
        repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_A, objects=profile.repository)
        catalogue = repo.load()
        catalogue = upsert_work_unit(catalogue, _unit(_BUCKET_A))
        catalogue = upsert_work_unit(catalogue, _unit(_BUCKET_B))
        repo.save(catalogue)
        assert repo.bucket_id == _BUCKET_A
        yield repo, BucketEventHistoryRepository(objects=profile.repository)


def test_get_refuses_a_unit_owned_by_another_bucket(a_bound_repository) -> None:
    """A B unit is not addressable through an A-bound repository."""
    repo, _ = a_bound_repository
    foreign = _unit(_BUCKET_B)

    with pytest.raises(WorkUnitNotFoundError):
        get_work_unit(foreign.work_unit_id, repository=repo)


def test_rename_refuses_a_unit_owned_by_another_bucket(a_bound_repository) -> None:
    """A foreign rename neither persists a new name nor emits a B-scoped event."""
    repo, events = a_bound_repository
    foreign = _unit(_BUCKET_B)

    with pytest.raises(WorkUnitNotFoundError):
        rename_work_unit(foreign.work_unit_id, "renamed by A", actor="operator-A", repository=repo, clock=_T0)

    stored = repo.load().get(foreign.work_unit_id)
    assert stored is not None
    assert stored.name == foreign.name
    assert events.load().events == {}


def test_discard_refuses_a_unit_owned_by_another_bucket(a_bound_repository) -> None:
    """A foreign discard leaves the B unit active and emits no B-scoped event."""
    repo, events = a_bound_repository
    foreign = _unit(_BUCKET_B)

    with pytest.raises(WorkUnitNotFoundError):
        discard_work_unit(foreign.work_unit_id, actor="operator-A", repository=repo, clock=_T0)

    stored = repo.load().get(foreign.work_unit_id)
    assert stored is not None
    assert stored.state is not WorkUnitState.DESCARTADO
    assert events.load().events == {}


def test_same_bucket_lifecycle_still_works(a_bound_repository) -> None:
    """Positive control: the A unit is readable, renameable, and discardable.

    Without it every refusal above could hold because the guard rejects
    everything, which would break the real single-bucket flow.
    """
    repo, events = a_bound_repository
    own = _unit(_BUCKET_A)

    assert get_work_unit(own.work_unit_id, repository=repo).bucket_id == _BUCKET_A

    renamed = rename_work_unit(own.work_unit_id, "renamed", actor="operator-A", repository=repo, clock=_T0)
    assert renamed.name == "renamed"

    discarded = discard_work_unit(own.work_unit_id, actor="operator-A", repository=repo, clock=_T0)
    assert discarded.state is WorkUnitState.DESCARTADO
    assert {event.bucket_id for event in events.load().events.values()} == {_BUCKET_A}


def test_the_foreign_unit_is_genuinely_present_in_the_catalogue(a_bound_repository) -> None:
    """Anti-tautology: the refusals above are scope, not an empty catalogue.

    If the B unit were simply absent, every not-found assertion would pass while
    proving nothing about bucket isolation.
    """
    repo, _ = a_bound_repository
    foreign = _unit(_BUCKET_B)

    assert repo.load().get(foreign.work_unit_id) is not None
    assert {unit.bucket_id for unit in list_work_units(repository=repo)} == {_BUCKET_A, _BUCKET_B}
