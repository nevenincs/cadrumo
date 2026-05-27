"""Tests for the per-work-unit history assembler."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.application.modelo import (
    WorkUnitNotFoundError,
    assemble_work_unit_history,
    create_work_unit,
    discard_work_unit,
)
from aeat.domain.modelos._errors import ModeloError
from aeat.domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from aeat.domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from aeat.domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository
from aeat.domain.modelos._verification_repository import (
    VerificationReportCatalogueRepository,
)
from aeat.tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def repos(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="default") as profile:
        objects = profile.repository
        yield (
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            ModeloRecordCatalogueRepository(objects=objects),
            VerificationReportCatalogueRepository(objects=objects),
            BucketEventHistoryRepository(objects=objects),
        )


def test_create_rejects_unknown_revision_with_helpful_list(repos) -> None:
    """``create_work_unit`` must refuse a revision id the modelo registry does
    not declare, naming the modelo and listing the available revisions so the
    operator can re-issue the command with a valid id.

    Persona-testimonial finding (MED, 2026-05-20-cli-persona-testimonials-audit):
    passing ``--revision "bad-revision"`` previously created a content-addressed
    work unit that was unreachable on subsequent ``work calculate`` (snapshot
    miss). The boundary now catches the typo at create-time.
    """
    wu_repo, _, _, _, bv_repo = repos
    with pytest.raises(ModeloError) as exc:
        create_work_unit(
            bucket_id="default",
            modelo="130",
            filing_year=2026,
            period="1T",
            revision_id="bad-revision",
            repository=wu_repo,
            bucket_event_repository=bv_repo,
        )
    message = str(exc.value)
    assert "bad-revision" in message
    assert "modelo '130'" in message
    assert "Available revisions:" in message
    assert "2019-y-siguientes" in message


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


def test_history_records_creation_event(repos) -> None:
    """``create_work_unit`` emits a ``modelo.work_unit.created`` event so
    the work-unit history is complete from its first moment. The
    creation event names when and by whom the unit was provisioned."""
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    t0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    work_unit = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        actor="operator@example.test",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=t0,
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
    assert len(history.events) == 1
    event = history.events[0]
    assert event.object_type is BucketEventObjectType.WORK_UNIT
    assert event.object_id == work_unit.work_unit_id
    assert event.event_type is BucketEventType.MODELO_WORK_UNIT_CREATED
    assert event.occurred_at == t0
    assert event.actor == "operator@example.test"
    assert event.payload == {
        "modelo": "130",
        "filing_year": "2026",
        "period": "1T",
        "revision_id": "2019-y-siguientes",
        "name": "130-2026-1T",
    }


def test_history_idempotent_create_does_not_duplicate_creation_event(repos) -> None:
    """Re-running ``create_work_unit`` on the same four-axis key reloads
    the existing unit and emits no second creation event - the original
    creation event already stands."""
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    t0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)
    first = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=t0,
    )
    reloaded = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="1T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=t1,
    )
    assert reloaded.work_unit_id == first.work_unit_id

    history = assemble_work_unit_history(
        first.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
    )
    assert len(history.events) == 1
    assert history.events[0].event_type is BucketEventType.MODELO_WORK_UNIT_CREATED


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
        bucket_event_repository=bv_repo,
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

    # Creation event first, then the discard event - the timeline is
    # complete from provisioning through to discard.
    assert len(history.events) == 2
    assert history.events[0].event_type is BucketEventType.MODELO_WORK_UNIT_CREATED
    event = history.events[1]
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
        bucket_event_repository=bv_repo,
        clock=t0,
    )
    other = create_work_unit(
        bucket_id="default",
        modelo="130",
        filing_year=2026,
        period="2T",
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=t0,
    )
    # Discard *only* the unrelated work unit so it emits an extra event.
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

    # The target was never discarded -> only its own creation event is
    # present; the other unit's creation and discard events must not
    # leak into its history.
    assert len(history.events) == 1
    assert history.events[0].object_id == target.work_unit_id
    assert history.events[0].event_type is BucketEventType.MODELO_WORK_UNIT_CREATED
