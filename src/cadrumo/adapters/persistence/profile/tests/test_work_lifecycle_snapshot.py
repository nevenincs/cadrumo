"""Modelo metadata writers cannot overwrite a newer encrypted catalogue snapshot."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import override

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.errors import SecureObjectRevisionConflictError
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.action_errors import WorkUnitMutationRefusedError
from cadrumo.application.modelo.work_lifecycle import discard_work_unit, rename_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.period import Period
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "9a9a9a9a-9a9a-49a9-89a9-9a9a9a9a9a9a"
_START = datetime(2026, 9, 1, 9, tzinfo=UTC)


class _AfterSnapshotRepository(WorkUnitCatalogueRepository):
    """Delegate to real encrypted persistence, then land one real competing write."""

    def __init__(
        self,
        *,
        objects: SecureObjectRepository,
        after_snapshot: Callable[[], None],
    ) -> None:
        super().__init__(bucket_id=_BUCKET_ID, objects=objects)
        self._after_snapshot = after_snapshot
        self.triggered = False

    @override
    def load_revisioned(self) -> tuple[WorkUnitCatalogue, str]:
        snapshot = super().load_revisioned()
        if not self.triggered:
            self.triggered = True
            self._after_snapshot()
        return snapshot


def _unit() -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id="2019-y-siguientes",
        ),
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id="2019-y-siguientes",
        name="Original display",
        created_at=_START,
        updated_at=_START,
    )


def test_rename_rejects_stale_observation_without_new_encrypted_write_or_event(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        repository = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        events = BucketEventHistoryRepository(objects=objects)
        ports = WorkLifecyclePorts(work_unit_repository=repository, bucket_event_repository=events)
        original = _unit()
        repository.save(upsert_work_unit(repository.load(), original))

        competing = rename_work_unit(
            original.work_unit_id,
            "Competing display",
            actor="other operator",
            ports=ports,
            clock=_START + timedelta(minutes=1),
        )
        committed_catalogue, committed_events = repository.load(), events.load()

        with pytest.raises(WorkUnitMutationRefusedError):
            rename_work_unit(
                original.work_unit_id,
                "Stale display",
                actor="first operator",
                ports=ports,
                clock=_START + timedelta(minutes=2),
                expected=original,
            )
        assert repository.load() == committed_catalogue
        assert events.load() == committed_events

        accepted = rename_work_unit(
            original.work_unit_id,
            "Approved display",
            actor="first operator",
            ports=ports,
            clock=_START + timedelta(minutes=2),
            expected=competing,
        )
        assert accepted.name == "Approved display"
        assert repository.load().work_units[accepted.work_unit_id] == accepted
        assert len(events.load().events) == len(committed_events.events) + 1


@pytest.mark.parametrize("competing_change", ["discard", "rename"])
def test_stale_metadata_snapshot_cannot_undo_the_competing_write(tmp_path: Path, competing_change: str) -> None:
    """A race after the first read preserves the second writer's state and event."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        initial = _unit()
        repository = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        repository.save(upsert_work_unit(repository.load(), initial))
        events = BucketEventHistoryRepository(objects=objects)
        competing_ports = WorkLifecyclePorts(
            work_unit_repository=WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
            bucket_event_repository=events,
        )
        landed: list[tuple[WorkUnitCatalogue, object]] = []

        def after_snapshot() -> None:
            if competing_change == "discard":
                discard_work_unit(
                    initial.work_unit_id,
                    actor="competing operator",
                    ports=competing_ports,
                    clock=_START + timedelta(minutes=1),
                )
            else:
                rename_work_unit(
                    initial.work_unit_id,
                    "Newer display",
                    actor="competing operator",
                    ports=competing_ports,
                    clock=_START + timedelta(minutes=1),
                )
            landed.append((repository.load(), events.load()))

        racing = _AfterSnapshotRepository(objects=objects, after_snapshot=after_snapshot)
        first_ports = WorkLifecyclePorts(work_unit_repository=racing, bucket_event_repository=events)
        with pytest.raises(SecureObjectRevisionConflictError):
            if competing_change == "discard":
                rename_work_unit(
                    initial.work_unit_id,
                    "Stale display",
                    actor="first operator",
                    ports=first_ports,
                    clock=_START + timedelta(minutes=2),
                )
            else:
                discard_work_unit(
                    initial.work_unit_id,
                    actor="first operator",
                    ports=first_ports,
                    expected=initial,
                    clock=_START + timedelta(minutes=2),
                )

        assert racing.triggered and len(landed) == 1
        assert repository.load() == landed[0][0]
        assert events.load() == landed[0][1]
        final = next(unit for unit in repository.load() if unit.work_unit_id == initial.work_unit_id)
        if competing_change == "discard":
            assert final.state is WorkUnitState.DESCARTADO
            assert final.name == "Original display"
        else:
            assert final.state is WorkUnitState.BORRADOR
            assert final.name == "Newer display"
