"""Real-behavior tests for the operator-facing CensoSyncService.

Exercises each of the four verbs (refresh / show / compare / apply)
against a real runtime profile backend with a real
CensoSnapshotService and UserProfileLifecycleRepository.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from ....tests.secure_sql import isolated_runtime_profile
from ...live._censo import CensoSnapshotService, SnapshotLifecycleState
from ...overview import OverviewCalendarRange, build_overview_calendar
from .. import (
    CENSO_DERIVED_SOURCE_TAG,
    CENSO_SOURCE_TAG,
    CensoApplyConflictError,
    CensoComparisonStatus,
    CensoNotAvailableError,
    CensoSyncError,
    CensoSyncService,
    UserProfileLifecycleRepository,
)
from .._projections import projection_for_taxpayer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_G313 = aeat_url("sede", configured_path("sede_paths", "censo_g313_launcher"))


@pytest.fixture
def secure_store(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="b1") as profile:
        yield profile.repository


def _facts() -> dict[str, str]:
    return {
        "censo.activity_start_date": "2024-01-15",
        "censo.establecimiento_type": "propio",
        "censo.elected_withholding_pct": "15",
        "vivienda_office.total_m2": "120.00",
        "vivienda_office.office_m2": "24.50",
    }


def _service(secure_objects: SecureObjectRepository) -> CensoSyncService:
    snapshots = CensoSnapshotService(bucket_id="b1")
    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_objects)
    return CensoSyncService(
        bucket_id="b1",
        snapshots=snapshots,
        profiles=profiles,
    )


def test_service_refuses_blank_bucket_id_with_translated_error(secure_store: SecureObjectRepository) -> None:
    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    snapshots = CensoSnapshotService(bucket_id="b1")

    with pytest.raises(CensoSyncError) as exc_info:
        CensoSyncService(bucket_id=" ", snapshots=snapshots, profiles=profiles)

    assert exc_info.value.translated_message == "errors.censo.bucket_id_blank"


def test_refresh_captures_active_snapshot(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)

    snapshot = service.refresh_censo(
        profile_id="operator",
        source_url=_G313,
        fact_source=_facts,
    )

    assert snapshot.state is SnapshotLifecycleState.ACTIVE
    assert snapshot.censo_facts["censo.establecimiento_type"] == "propio"


def test_refresh_with_production_factory_enrolls_censo_event(secure_store: SecureObjectRepository) -> None:

    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store),
        events=BucketEventHistoryRepository(objects=secure_store),
    )

    snapshot = service.refresh_censo(
        profile_id="operator",
        source_url=_G313,
        fact_source=_facts,
    )

    catalogue = BucketEventHistoryRepository(objects=secure_store).load()
    events = catalogue.for_bucket("b1", event_types=(BucketEventType.CENSO_REFRESHED,))
    assert len(events) == 1
    assert events[0].bucket_id == "b1"
    assert events[0].object_id == "operator"
    assert events[0].payload["snapshot_id"] == snapshot.snapshot_id


def test_refresh_refuses_when_sede_returns_no_facts(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)

    with pytest.raises(CensoNotAvailableError):
        service.refresh_censo(profile_id="operator", source_url=_G313, fact_source=dict)


def test_show_returns_latest_active(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)
    captured = service.refresh_censo(profile_id="operator", source_url=_G313, fact_source=_facts)

    shown = service.show_censo(profile_id="operator")

    assert shown.snapshot_id == captured.snapshot_id


def test_show_refuses_explicit_snapshot_for_another_profile(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)
    other = service.refresh_censo(profile_id="other-profile", source_url=_G313, fact_source=_facts)

    with pytest.raises(CensoNotAvailableError) as exc_info:
        service.show_censo(profile_id="operator", snapshot_id=other.snapshot_id)

    assert exc_info.value.translated_message == "errors.censo.snapshot_profile_mismatch"
    ctx = exc_info.value.context
    assert ctx is not None
    assert ctx["snapshot_id"] == other.snapshot_id
    assert ctx["snapshot_profile_id"] == "other-profile"


def test_show_refuses_when_no_snapshot_exists(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)

    with pytest.raises(CensoNotAvailableError):
        service.show_censo(profile_id="operator")


def test_compare_diffs_per_field_against_profile(secure_store: SecureObjectRepository) -> None:
    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    profiles.save(
        UserProfileRecord(
            profile_id="operator",
            display_name="Operator",
            facts=(
                UserProfileFact(path="censo.establecimiento_type", value="arrendado"),
                UserProfileFact(path="censo.activity_start_date", value="2024-01-15"),
                UserProfileFact(path="manual.only.path", value="kept"),
            ),
        ),
    )
    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_censo(profile_id="operator", source_url=_G313, fact_source=_facts)

    comparison = service.compare_censo_with_profile(profile_id="operator")

    statuses = {row.path: row.status for row in comparison.rows}
    assert statuses["censo.activity_start_date"] is CensoComparisonStatus.MATCHES
    assert statuses["censo.establecimiento_type"] is CensoComparisonStatus.DIVERGES
    assert statuses["manual.only.path"] is CensoComparisonStatus.PROFILE_ONLY
    assert statuses["vivienda_office.total_m2"] is CensoComparisonStatus.CENSO_ONLY


def test_apply_stamps_censo_facts_with_provenance_tag(secure_store: SecureObjectRepository) -> None:
    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    profiles.save(
        UserProfileRecord(
            profile_id="operator",
            display_name="Operator",
            facts=(
                UserProfileFact(path="manual.only.path", value="kept", source="manual_cli"),
                UserProfileFact(path="censo.establecimiento_type", value="arrendado", source=CENSO_SOURCE_TAG),
            ),
        ),
    )
    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_censo(profile_id="operator", source_url=_G313, fact_source=_facts)

    result = service.apply_censo_to_profile(profile_id="operator")

    reloaded = profiles.load("operator")
    by_path = {fact.path: fact for fact in reloaded.facts}
    assert by_path["censo.establecimiento_type"].value == "propio"
    assert by_path["censo.establecimiento_type"].source == CENSO_SOURCE_TAG
    assert by_path["manual.only.path"].value == "kept"
    assert by_path["manual.only.path"].source == "manual_cli"
    assert "censo.establecimiento_type" in result.written_paths


def test_apply_derives_taxpayer_axes_from_nie_and_iae_for_calendar(secure_store: SecureObjectRepository) -> None:
    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    profiles.save(
        UserProfileRecord(
            profile_id="operator",
            display_name="Operator",
            facts=(
                UserProfileFact(path="identity.tax_id", value="X1234567L"),
                UserProfileFact(path="identity.name", value="Operator"),
                UserProfileFact(path="activities.description", value="Servicios profesionales"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            ),
        ),
    )
    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_censo(
        profile_id="operator",
        source_url=_G313,
        fact_source=lambda: {
            "activities.iae_epigraph": "763",
            "censo.activity_start_date": "2024-01-15",
        },
    )

    result = service.apply_censo_to_profile(profile_id="operator")

    reloaded = profiles.load("operator")
    by_path = {fact.path: fact for fact in reloaded.facts}
    assert result.derived_paths == ("taxpayer_type.entity_type", "taxpayer_type.irpf_income_categories")
    assert by_path["taxpayer_type.entity_type"].value == "natural_person"
    assert by_path["taxpayer_type.entity_type"].source == CENSO_DERIVED_SOURCE_TAG
    assert by_path["taxpayer_type.irpf_income_categories"].value == "actividad_economica"
    assert by_path["taxpayer_type.irpf_income_categories"].source == CENSO_DERIVED_SOURCE_TAG

    taxpayer = projection_for_taxpayer(reloaded)
    calendar = build_overview_calendar(
        taxpayer,
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        today=date(2025, 4, 1),
    )
    assert calendar.taxpayer_model_declared is True
    assert {entry.modelo for entry in calendar.entries} >= {"303"}


def test_apply_does_not_infer_income_category_without_iae(secure_store: SecureObjectRepository) -> None:
    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    profiles.save(
        UserProfileRecord(
            profile_id="operator",
            display_name="Operator",
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Operator"),
                UserProfileFact(path="activities.description", value="Servicios profesionales"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
            ),
        ),
    )
    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_censo(
        profile_id="operator",
        source_url=_G313,
        fact_source=lambda: {
            "censo.activity_start_date": "2024-01-15",
        },
    )

    result = service.apply_censo_to_profile(profile_id="operator")

    reloaded = profiles.load("operator")
    by_path = {fact.path: fact for fact in reloaded.facts}
    assert result.derived_paths == ("taxpayer_type.entity_type",)
    assert by_path["taxpayer_type.entity_type"].value == "natural_person"
    assert "taxpayer_type.irpf_income_categories" not in by_path
    calendar = build_overview_calendar(
        projection_for_taxpayer(reloaded),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        today=date(2025, 4, 1),
    )
    assert calendar.taxpayer_model_declared is False


def test_apply_does_not_infer_income_category_without_natural_person_identity(
    secure_store: SecureObjectRepository,
) -> None:
    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    profiles.save(
        UserProfileRecord(
            profile_id="operator",
            display_name="Operator",
            facts=(
                UserProfileFact(path="identity.tax_id", value="B12345678"),
                UserProfileFact(path="identity.name", value="Operator SL"),
                UserProfileFact(path="activities.description", value="Servicios profesionales"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            ),
        ),
    )
    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_censo(
        profile_id="operator",
        source_url=_G313,
        fact_source=lambda: {
            "activities.iae_epigraph": "763",
            "censo.activity_start_date": "2024-01-15",
        },
    )

    result = service.apply_censo_to_profile(profile_id="operator")

    reloaded = profiles.load("operator")
    by_path = {fact.path: fact for fact in reloaded.facts}
    assert result.derived_paths == ()
    assert "taxpayer_type.entity_type" not in by_path
    assert "taxpayer_type.irpf_income_categories" not in by_path
    calendar = build_overview_calendar(
        projection_for_taxpayer(reloaded),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        today=date(2025, 4, 1),
    )
    assert calendar.taxpayer_model_declared is False


def test_apply_refuses_when_profile_does_not_exist(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)
    service.refresh_censo(profile_id="operator", source_url=_G313, fact_source=_facts)

    with pytest.raises(CensoApplyConflictError):
        service.apply_censo_to_profile(profile_id="operator")


def _facts_clean_ratio() -> dict[str, str]:
    """Fixture with 100/20 m² so the derived suministros ratio is the
    legally-clean 0.06 (=0.20 * 0.30) and ownership is exactly 0.20.
    Avoids the truncation artefacts the 24.50/120.00 fixture produces."""

    return {
        "vivienda_office.total_m2": "100",
        "vivienda_office.office_m2": "20",
    }


def test_apply_seeds_home_office_usage_ratios_from_censo(
    secure_store: SecureObjectRepository,
) -> None:
    """Closes the #495 orphan: apply now drives derive_home_office_ratios_from_censo
    via the snapshot's vivienda_office facts. Suministros entries land at
    raw * 0.30 (LIRPF Art. 30.2 rule 5), ownership at raw afectación.

    Fixture: 100 m² total, 20 m² office → raw = 0.20 → suministros = 0.060,
    ownership = 0.20. Witnesses the actual numeric output, not the helper
    signature."""

    from decimal import Decimal

    from ....domain.categories import SpendingCategory
    from ....domain.usage_ratios import load_usage_ratios

    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    profiles.save(
        UserProfileRecord(profile_id="operator", display_name="Operator"),
    )
    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_censo(
        profile_id="operator",
        source_url=_G313,
        fact_source=_facts_clean_ratio,
    )

    result = service.apply_censo_to_profile(profile_id="operator")

    assert "suministros_home_office_luz" in result.seeded_home_office_categories
    assert "amortizacion_vivienda_afecto" in result.seeded_home_office_categories
    ratios_profile = load_usage_ratios(bucket_id="b1")
    assert ratios_profile.ratios[SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ] == Decimal("0.060")
    assert ratios_profile.ratios[SpendingCategory.AMORTIZACION_VIVIENDA_AFECTO] == Decimal("0.20")


def test_apply_seeding_idempotent_on_repeat(secure_store: SecureObjectRepository) -> None:
    """Second apply with the same censo produces no fresh seeded entries —
    the merge skips paths whose persisted value already matches the
    derived value."""

    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    profiles.save(UserProfileRecord(profile_id="operator", display_name="Operator"))
    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_censo(
        profile_id="operator",
        source_url=_G313,
        fact_source=_facts_clean_ratio,
    )
    service.apply_censo_to_profile(profile_id="operator")

    second = service.apply_censo_to_profile(profile_id="operator")

    assert second.seeded_home_office_categories == ()


def test_bound_raw_afectacion_ratio_logs_non_decimal_censo_values(
    secure_store: SecureObjectRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = _service(secure_store)
    service.refresh_censo(
        profile_id="operator",
        source_url=_G313,
        fact_source=lambda: {
            "vivienda_office.total_m2": "not-a-decimal",
            "vivienda_office.office_m2": "20",
        },
    )

    with caplog.at_level(logging.DEBUG, logger="aeat.application.user_profile._censo_sync"):
        ratio = service.bound_raw_afectacion_ratio(profile_id="operator")

    assert ratio is None
    assert any("non-decimal censo surface" in record.message for record in caplog.records)


def test_apply_preserves_windowed_manual_facts(secure_store: SecureObjectRepository) -> None:
    """Persistence-audit follow-up: UserProfileFact carries valid_from /
    valid_to date windows that the prior censo-apply roundtrip never
    exercised. A save-path that silently dropped either window field on
    non-censo facts would have been invisible. This pins that operator-
    entered facts with explicit effective-date windows survive the
    apply path untouched."""

    from datetime import date

    valid_from = date(2024, 1, 1)
    valid_to = date(2024, 12, 31)
    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    profiles.save(
        UserProfileRecord(
            profile_id="operator",
            display_name="Operator",
            facts=(
                UserProfileFact(
                    path="manual.window.fact",
                    value="2024-fiscal",
                    source="manual_cli",
                    valid_from=valid_from,
                    valid_to=valid_to,
                ),
            ),
        ),
    )
    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_censo(profile_id="operator", source_url=_G313, fact_source=_facts)

    service.apply_censo_to_profile(profile_id="operator")

    reloaded = profiles.load("operator")
    by_path = {fact.path: fact for fact in reloaded.facts}
    preserved = by_path["manual.window.fact"]
    assert preserved.valid_from == valid_from
    assert preserved.valid_to == valid_to
    assert preserved.value == "2024-fiscal"
    assert preserved.source == "manual_cli"
