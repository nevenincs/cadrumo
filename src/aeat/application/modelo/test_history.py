"""Tests for the per-work-unit history assembler."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import create_engine_from_settings
from aeat.application.modelo import (
    WorkUnitNotFoundError,
    assemble_work_unit_history,
    create_work_unit,
    discard_work_unit,
)
from aeat.core.config import Settings
from aeat.domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from aeat.domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from aeat.domain.modelos._filing_repository import FilingRecordCatalogueRepository
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository
from aeat.domain.modelos._verification_repository import (
    VerificationReportCatalogueRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def repos(tmp_path: Path):
    provider = EphemeralMasterKeyProvider()
    with provider:
        db_path = tmp_path / "history.db"
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            objects = SecureObjectRepository(engine=engine)
            yield (
                WorkUnitCatalogueRepository(objects=objects),
                CalculationRevisionCatalogueRepository(objects=objects),
                FilingRecordCatalogueRepository(objects=objects),
                VerificationReportCatalogueRepository(objects=objects),
                BucketEventHistoryRepository(objects=objects),
            )
        finally:
            engine.dispose()


def test_history_for_missing_work_unit_raises(repos) -> None:
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    with pytest.raises(WorkUnitNotFoundError):
        assemble_work_unit_history(
            "no-such-work-unit",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
        )


def test_history_for_freshly_created_work_unit_is_empty(repos) -> None:
    """``create_work_unit`` does not emit a bucket event today, so the
    history of a freshly-created work unit is empty. This test pins
    that contract: the assembler returns an empty stream rather than
    fabricating a synthesized creation row."""
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )

    history = assemble_work_unit_history(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
    )

    assert history.bucket_id == "default"
    assert history.work_unit_id == work_unit.work_unit_id
    assert history.events == ()


def test_history_records_discard_event(repos) -> None:
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    t0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)

    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=t0,
    )
    discard_work_unit(
        work_unit.work_unit_id,
        actor="operator@example.test",
        reason="superseded by a fresh draft",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=t1,
    )

    history = assemble_work_unit_history(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
    )

    assert len(history.events) == 1
    event = history.events[0]
    assert event.object_type is BucketEventObjectType.WORK_UNIT
    assert event.object_id == work_unit.work_unit_id
    assert event.event_type is BucketEventType.MODELO_WORK_UNIT_DISCARDED
    assert event.occurred_at == t1
    assert event.actor == "operator@example.test"


def test_history_excludes_events_from_other_work_units(repos) -> None:
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    t0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)

    target = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=t0,
    )
    other = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="2T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=t0,
    )
    # Discard *only* the unrelated work unit so it emits an event.
    discard_work_unit(
        other.work_unit_id,
        actor="other-operator",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=t1,
    )

    history = assemble_work_unit_history(
        target.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
    )

    # The target was never discarded -> the other unit's event must
    # not leak into its history.
    assert history.events == ()
