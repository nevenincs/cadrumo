"""Concurrent work-unit writes do not discard each other.

The work-unit catalogue is a SINGLETON row, so touching one unit rewrites all of
them. Performed unguarded, a unit another operator created or advanced in the
interim is discarded by whichever write lands second, and nothing reports it:
every surviving entry is individually intact and the missing one leaves no hole.

The path that made this concrete is the verification repair that stamps a work
unit's current-revision pointer. It reads the catalogue, changes one field on one
unit, and rewrites the whole thing -- so a repair meant to fill in a single
pointer could drop an unrelated work unit somebody else had just created.

Observed deterministically, by landing the interloping write inside the guarded
unit of work's read-to-write window rather than by racing threads.

Real behaviour throughout: a real isolated bucket runtime, the real encrypted SQL
backend, independent repository instances. Nothing is mocked.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from .....core.modelo import Modelo
from .....core.period import Period
from .....domain.modelos.repository import upsert_work_unit
from .....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..modelos_work_units import WorkUnitCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "6d6d6d6d-6d6d-46d6-8d6d-6d6d6d6d6d6d"
_INSTANT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


#: Work-unit identity is DERIVED from (bucket, modelo, year, period, revision),
#: so two units in one bucket are distinguished by their coordinates rather than
#: by a label. Each case's units differ only by period, which is the cheapest
#: axis that yields distinct ids.
_PERIOD_BY_LABEL = {"first": "1T", "interloper": "2T", "target": "3T"}


def _work_unit(label: str) -> WorkUnit:
    """Build one minimal work unit attributed to this test's bucket."""
    period = Period.from_year_and_code(2026, _PERIOD_BY_LABEL[label])
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=Modelo.M303.value,
            filing_year=2026,
            period=period,
            revision_id="2026",
        ),
        bucket_id=_BUCKET_ID,
        modelo=Modelo.M303.value,
        filing_year=2026,
        period=period,
        revision_id="2026",
        name=label,
        created_at=_INSTANT,
        updated_at=_INSTANT,
    )


def _id_of(label: str) -> str:
    """Return the derived id for ``label``'s coordinates."""
    return _work_unit(label).work_unit_id


def _names() -> list[str]:
    """Return the readable names, since the ids themselves are hashes."""
    return sorted(unit.name for unit in WorkUnitCatalogueRepository().load())


def test_sequential_writes_through_independent_instances_accumulate() -> None:
    """Baseline: two repository instances do not lose a work unit on their own."""
    for identifier in ("first", "interloper"):
        unit = _work_unit(identifier)
        WorkUnitCatalogueRepository().mutate(
            lambda current, unit=unit: upsert_work_unit(current, unit),
        )

    assert _names() == ["first", "interloper"]


def test_a_concurrent_write_does_not_discard_the_other_work_unit() -> None:
    """DISCRIMINATING: the interleaving that used to lose a work unit.

    The interloper creates a SECOND work unit inside the first mutation's
    read-to-write window. Unguarded, the first write rebuilds from the catalogue
    it read before the interloper existed and overwrites it away.

    This covers the verification repair's shape too. That path changes ONE field
    on ONE unit -- the change most easily assumed harmless to the rest -- and
    rewrites every other entry with it, so what it needs proving is exactly this:
    a concurrent write inside the window survives.
    """
    repository = WorkUnitCatalogueRepository()
    interloper_written = False

    def _add_one_while_another_lands(current: WorkUnitCatalogue) -> WorkUnitCatalogue:
        nonlocal interloper_written
        if not interloper_written:
            interloper_written = True
            interloper = _work_unit("interloper")
            WorkUnitCatalogueRepository().mutate(
                lambda inner: upsert_work_unit(inner, interloper),
            )
        return upsert_work_unit(current, _work_unit("first"))

    repository.mutate(_add_one_while_another_lands)

    assert _names() == ["first", "interloper"]
