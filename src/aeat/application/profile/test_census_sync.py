"""Real-behavior tests for the operator-facing CensusSyncService.

Exercises each of the four verbs (refresh / show / compare / apply)
against a real encrypted SQLite backend with a real
CensusSnapshotService and UserProfileLifecycleRepository — no mocks.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from aeat.adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.live._census import CensusSnapshotService, CensusSnapshotState
from aeat.application.profile import (
    CENSUS_SOURCE_TAG,
    CensusApplyConflictError,
    CensusComparisonStatus,
    CensusNotAvailableError,
    CensusSyncService,
)
from aeat.application.user_profile import UserProfileLifecycleRepository
from aeat.core.config import Settings
from aeat.domain.user_profile import UserProfileFact, UserProfileRecord


pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


_G313 = "https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G313.shtml"


@pytest.fixture
def secure_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[SecureObjectRepository]:
    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "census-sync.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    dispose_engine()
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        yield SecureObjectRepository(engine=engine)
    finally:
        engine.dispose()
        dispose_engine()
        override_master_key_provider(None)


def _facts() -> dict[str, str]:
    return {
        "census.activity_start_date": "2024-01-15",
        "census.establecimiento_type": "propio",
        "census.elected_withholding_pct": "15",
        "vivienda_office.total_m2": "120.00",
        "vivienda_office.office_m2": "24.50",
    }


def _service(secure_objects: SecureObjectRepository) -> CensusSyncService:
    snapshots = CensusSnapshotService(bucket_id="b1")
    profiles = UserProfileLifecycleRepository(bucket_id="b1", objects=secure_objects)
    return CensusSyncService(
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

    assert snapshot.state is CensusSnapshotState.ACTIVE
    assert snapshot.census_facts["census.establecimiento_type"] == "propio"


def test_refresh_refuses_when_sede_returns_no_facts(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)

    with pytest.raises(CensusNotAvailableError):
        service.refresh_census(profile_id="operator", source_url=_G313, fact_source=dict)


def test_show_returns_latest_active(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)
    captured = service.refresh_census(profile_id="operator", source_url=_G313, fact_source=_facts)

    shown = service.show_census(profile_id="operator")

    assert shown.snapshot_id == captured.snapshot_id


def test_show_refuses_when_no_snapshot_exists(secure_store: SecureObjectRepository) -> None:
    service = _service(secure_store)

    with pytest.raises(CensusNotAvailableError):
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
    service = CensusSyncService(
        bucket_id="b1",
        snapshots=CensusSnapshotService(bucket_id="b1"),
        profiles=profiles,
    )
    service.refresh_census(profile_id="operator", source_url=_G313, fact_source=_facts)

    comparison = service.compare_census_with_profile(profile_id="operator")

    statuses = {row.path: row.status for row in comparison.rows}
    assert statuses["census.activity_start_date"] is CensusComparisonStatus.MATCHES
    assert statuses["census.establecimiento_type"] is CensusComparisonStatus.DIVERGES
    assert statuses["manual.only.path"] is CensusComparisonStatus.PROFILE_ONLY
    assert statuses["vivienda_office.total_m2"] is CensusComparisonStatus.CENSUS_ONLY


def test_apply_stamps_census_facts_with_provenance_tag(secure_store: SecureObjectRepository) -> None:
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
    service = CensusSyncService(
        bucket_id="b1",
        snapshots=CensusSnapshotService(bucket_id="b1"),
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

    with pytest.raises(CensusApplyConflictError):
        service.apply_census_to_profile(profile_id="operator")
