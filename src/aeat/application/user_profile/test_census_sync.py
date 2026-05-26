"""Real-behavior tests for the operator-facing CensoSyncService.

Exercises each of the four verbs (refresh / show / compare / apply)
against a real runtime profile backend with a real
CensoSnapshotService and UserProfileLifecycleRepository.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.application.live._censo import CensoSnapshotService, SnapshotLifecycleState
from aeat.application.user_profile import (
    CENSUS_SOURCE_TAG,
    CensoApplyConflictError,
    CensoComparisonStatus,
    CensoNotAvailableError,
    CensoSyncService,
    UserProfileLifecycleRepository,
)
from aeat.domain.user_profile import UserProfileFact, UserProfileRecord
from aeat.tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_G313 = "https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G313.shtml"


@pytest.fixture
def secure_store(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="b1") as profile:
        yield profile.repository


def _facts() -> dict[str, str]:
    return {
        "census.activity_start_date": "2024-01-15",
        "census.establecimiento_type": "propio",
        "census.elected_withholding_pct": "15",
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


def test_refresh_captures_active_snapshot(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)

    snapshot = service.refresh_census(
        profile_id="operator",
        source_url=_G313,
        fact_source=_facts,
    )

    assert snapshot.state is SnapshotLifecycleState.ACTIVE
    assert snapshot.censo_facts["census.establecimiento_type"] == "propio"


def test_refresh_refuses_when_sede_returns_no_facts(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)

    with pytest.raises(CensoNotAvailableError):
        service.refresh_census(profile_id="operator", source_url=_G313, fact_source=dict)


def test_show_returns_latest_active(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)
    captured = service.refresh_census(profile_id="operator", source_url=_G313, fact_source=_facts)

    shown = service.show_census(profile_id="operator")

    assert shown.snapshot_id == captured.snapshot_id


def test_show_refuses_when_no_snapshot_exists(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)

    with pytest.raises(CensoNotAvailableError):
        service.show_census(profile_id="operator")


def test_compare_diffs_per_field_against_profile(secure_store: SecureObjectRepository) -> None:
    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    profiles.save(
        UserProfileRecord(
            profile_id="operator",
            display_name="Operator",
            facts=(
                UserProfileFact(path="census.establecimiento_type", value="arrendado"),
                UserProfileFact(path="census.activity_start_date", value="2024-01-15"),
                UserProfileFact(path="manual.only.path", value="kept"),
            ),
        ),
    )
    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_census(profile_id="operator", source_url=_G313, fact_source=_facts)

    comparison = service.compare_census_with_profile(profile_id="operator")

    statuses = {row.path: row.status for row in comparison.rows}
    assert statuses["census.activity_start_date"] is CensoComparisonStatus.MATCHES
    assert statuses["census.establecimiento_type"] is CensoComparisonStatus.DIVERGES
    assert statuses["manual.only.path"] is CensoComparisonStatus.PROFILE_ONLY
    assert statuses["vivienda_office.total_m2"] is CensoComparisonStatus.CENSUS_ONLY


def test_apply_stamps_censo_facts_with_provenance_tag(secure_store: SecureObjectRepository) -> None:
    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    profiles.save(
        UserProfileRecord(
            profile_id="operator",
            display_name="Operator",
            facts=(
                UserProfileFact(path="manual.only.path", value="kept", source="manual_cli"),
                UserProfileFact(path="census.establecimiento_type", value="arrendado", source=CENSUS_SOURCE_TAG),
            ),
        ),
    )
    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_census(profile_id="operator", source_url=_G313, fact_source=_facts)

    result = service.apply_census_to_profile(profile_id="operator")

    reloaded = profiles.load("operator")
    by_path = {fact.path: fact for fact in reloaded.facts}
    assert by_path["census.establecimiento_type"].value == "propio"
    assert by_path["census.establecimiento_type"].source == CENSUS_SOURCE_TAG
    assert by_path["manual.only.path"].value == "kept"
    assert by_path["manual.only.path"].source == "manual_cli"
    assert "census.establecimiento_type" in result.written_paths


def test_apply_refuses_when_profile_does_not_exist(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)
    service.refresh_census(profile_id="operator", source_url=_G313, fact_source=_facts)

    with pytest.raises(CensoApplyConflictError):
        service.apply_census_to_profile(profile_id="operator")


def _facts_clean_ratio() -> dict[str, str]:
    """Fixture with 100/20 m² so the derived suministros ratio is the
    legally-clean 0.06 (=0.20 * 0.30) and ownership is exactly 0.20.
    Avoids the truncation artefacts the 24.50/120.00 fixture produces."""

    return {
        "vivienda_office.total_m2": "100",
        "vivienda_office.office_m2": "20",
    }


def test_apply_seeds_home_office_usage_ratios_from_census(
    secure_store: SecureObjectRepository,
) -> None:
    """Closes the #495 orphan: apply now drives derive_home_office_ratios_from_census
    via the snapshot's vivienda_office facts. Suministros entries land at
    raw * 0.30 (LIRPF Art. 30.2 rule 5), ownership at raw afectación.

    Fixture: 100 m² total, 20 m² office → raw = 0.20 → suministros = 0.060,
    ownership = 0.20. Witnesses the actual numeric output, not the helper
    signature."""

    from decimal import Decimal

    from aeat.domain.categories import SpendingCategory
    from aeat.domain.usage_ratios import load_usage_ratios

    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    profiles.save(
        UserProfileRecord(profile_id="operator", display_name="Operator"),
    )
    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_census(
        profile_id="operator", source_url=_G313, fact_source=_facts_clean_ratio,
    )

    result = service.apply_census_to_profile(profile_id="operator")

    assert "suministros_home_office_luz" in result.seeded_home_office_categories
    assert "amortizacion_vivienda_afecto" in result.seeded_home_office_categories
    ratios_profile = load_usage_ratios(bucket_id="b1")
    assert ratios_profile.ratios[SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ] == Decimal("0.060")
    assert ratios_profile.ratios[SpendingCategory.AMORTIZACION_VIVIENDA_AFECTO] == Decimal("0.20")


def test_apply_seeding_idempotent_on_repeat(secure_store: SecureObjectRepository) -> None:
    """Second apply with the same census produces no fresh seeded entries —
    the merge skips paths whose persisted value already matches the
    derived value."""

    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_store)
    profiles.save(UserProfileRecord(profile_id="operator", display_name="Operator"))
    service = CensoSyncService(
        bucket_id="b1",
        snapshots=CensoSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_census(
        profile_id="operator", source_url=_G313, fact_source=_facts_clean_ratio,
    )
    service.apply_census_to_profile(profile_id="operator")

    second = service.apply_census_to_profile(profile_id="operator")

    assert second.seeded_home_office_categories == ()


def test_apply_preserves_windowed_manual_facts(secure_store: SecureObjectRepository) -> None:
    """Persistence-audit follow-up: UserProfileFact carries valid_from /
    valid_to date windows that the prior census-apply roundtrip never
    exercised. A save-path that silently dropped either window field on
    non-census facts would have been invisible. This pins that operator-
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
    service.refresh_census(profile_id="operator", source_url=_G313, fact_source=_facts)

    service.apply_census_to_profile(profile_id="operator")

    reloaded = profiles.load("operator")
    by_path = {fact.path: fact for fact in reloaded.facts}
    preserved = by_path["manual.window.fact"]
    assert preserved.valid_from == valid_from
    assert preserved.valid_to == valid_to
    assert preserved.value == "2024-fiscal"
    assert preserved.source == "manual_cli"
