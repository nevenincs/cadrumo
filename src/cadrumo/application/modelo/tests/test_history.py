"""Tests for the per-work-unit history assembler."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import Period
from ....domain.buckets import BucketEventObjectType, BucketEventType
from ....domain.modelos import ModeloError
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    WorkUnitNotFoundError,
    assemble_work_unit_history,
    create_work_unit,
    discard_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
]

_BUCKET_ID = "17171717-1717-4171-8171-171717171717"


def _seed_ready_profile() -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            ),
        ),
    )


def _seed_sociedad_profile() -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="B12345674"),
                UserProfileFact(path="identity.legal_name", value="History Test Sociedad Limitada"),
                UserProfileFact(path="activities.description", value="corporate tax activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
                UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
                UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
                UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
            ),
        ),
    )


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        _seed_ready_profile()
        yield (
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            ModeloRecordCatalogueRepository(objects=objects),
            VerificationReportCatalogueRepository(objects=objects),
            BucketEventHistoryRepository(objects=objects),
        )


def test_create_rejects_unknown_period_for_modelo_revision(repos: _Repos) -> None:
    """``create_work_unit`` must refuse a period the revision's
    ``filing_schedules`` do not declare.

    Persona-testimonial finding: M202 previously accepted ``--period 1T``
    at create then failed calculate with no-revision-for-period. The
    boundary now catches the modelo-202 quarterly-token typo at
    create-time with the declared-period listing (``1P``, ``2P``, ``3P``).
    """
    wu_repo, _, _, _, bv_repo = repos
    _seed_sociedad_profile()
    with pytest.raises(ModeloError) as exc:
        create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="202",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id="2025-y-siguientes",
            repository=wu_repo,
            bucket_event_repository=bv_repo,
        )
    message = str(exc.value)
    assert "1T" in message
    assert "modelo '202'" in message
    assert "Available periods:" in message
    assert "1P" in message


def test_create_rejects_unknown_revision_with_helpful_list(repos: _Repos) -> None:
    """``create_work_unit`` must refuse a revision id the modelo registry does
    not declare, naming the modelo and listing the available revisions so the
    operator can re-issue the command with a valid id.

    Passing ``--revision "bad-revision"`` previously created a content-addressed
    work unit that was unreachable on subsequent ``work calculate`` (snapshot
    miss). The boundary now catches the typo at create-time.
    """
    wu_repo, _, _, _, bv_repo = repos
    with pytest.raises(ModeloError) as exc:
        create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id="bad-revision",
            repository=wu_repo,
            bucket_event_repository=bv_repo,
        )
    message = str(exc.value)
    assert "bad-revision" in message
    assert "modelo '130'" in message
    assert "Available revisions:" in message
    assert "2019-y-siguientes" in message


def test_history_for_missing_work_unit_raises(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    with pytest.raises(WorkUnitNotFoundError) as exc_info:
        assemble_work_unit_history(
            "no-such-work-unit",
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            verification_repository=vr_repo,
            bucket_event_repository=bv_repo,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.work_unit_not_found"
    assert exc_info.value.context == {"work_unit_id": "no-such-work-unit"}


def test_history_records_creation_event(repos: _Repos) -> None:
    """``create_work_unit`` emits a ``modelo.work_unit.created`` event so
    the work-unit history is complete from its first moment. The
    creation event names when and by whom the unit was provisioned."""
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    t0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
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

    assert history.bucket_id == _BUCKET_ID
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


def test_history_idempotent_create_does_not_duplicate_creation_event(repos: _Repos) -> None:
    """Re-running ``create_work_unit`` on the same four-axis key reloads
    the existing unit and emits no second creation event - the original
    creation event already stands."""
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    t0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)
    first = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=t0,
    )
    reloaded = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
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


def test_history_records_discard_event(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    t0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)

    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
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


def test_history_excludes_events_from_other_work_units(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, vr_repo, bv_repo = repos
    t0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 15, 13, 0, tzinfo=UTC)

    target = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=t0,
    )
    other = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "2T"),
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
