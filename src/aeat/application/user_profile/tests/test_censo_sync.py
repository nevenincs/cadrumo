"""Real-behavior tests for the surviving CensoSyncService surface.

The live Modelo 036 censo scrape and the refresh / show / compare / apply
verbs were retired (censal facts are operator-supplied through
``config profile edit``). What remains is the read-only home-office
afectación ratio the ledger proportional-deduction path consumes; these
tests exercise it against a real ``CensoSnapshotService`` store.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....tests.aeat_literal_fixtures import aeat_url
from ....tests.secure_sql import isolated_runtime_profile
from ...live import CensoSnapshotService
from .. import CensoSyncError, CensoSyncService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "35353535-3535-4535-8535-353535353535"
_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_SOURCE_URL = aeat_url("sede", "/operator-declared")


@pytest.fixture
def secure_store(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _capture(snapshots: CensoSnapshotService, censo_facts: dict[str, str]) -> None:
    snapshots.capture(
        profile_id=_PROFILE_ID,
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_url=_SOURCE_URL,
        censo_facts=censo_facts,
    )


def test_service_refuses_blank_bucket_id_with_translated_error() -> None:
    with pytest.raises(CensoSyncError):
        CensoSyncService(bucket_id="  ")


def test_bound_raw_afectacion_ratio_returns_none_without_snapshot(
    secure_store: SecureObjectRepository,
) -> None:
    service = CensoSyncService(bucket_id=_BUCKET_ID)
    assert service.bound_raw_afectacion_ratio(profile_id=_PROFILE_ID) is None


def test_bound_raw_afectacion_ratio_derives_from_active_snapshot(
    secure_store: SecureObjectRepository,
) -> None:
    snapshots = CensoSnapshotService(bucket_id=_BUCKET_ID)
    _capture(
        snapshots,
        {"vivienda_office.total_m2": "120.00", "vivienda_office.office_m2": "24.00"},
    )
    service = CensoSyncService(bucket_id=_BUCKET_ID, snapshots=snapshots)
    ratio = service.bound_raw_afectacion_ratio(profile_id=_PROFILE_ID)
    assert ratio is not None
    assert ratio == Decimal("24") / Decimal("120")


def test_bound_raw_afectacion_ratio_none_when_m2_facts_absent(
    secure_store: SecureObjectRepository,
) -> None:
    snapshots = CensoSnapshotService(bucket_id=_BUCKET_ID)
    _capture(snapshots, {"censo.establecimiento_type": "propio"})
    service = CensoSyncService(bucket_id=_BUCKET_ID, snapshots=snapshots)
    assert service.bound_raw_afectacion_ratio(profile_id=_PROFILE_ID) is None


def test_bound_raw_afectacion_ratio_logs_non_decimal_censo_values(
    secure_store: SecureObjectRepository,
    caplog: pytest.LogCaptureFixture,
) -> None:
    snapshots = CensoSnapshotService(bucket_id=_BUCKET_ID)
    _capture(
        snapshots,
        {"vivienda_office.total_m2": "not-a-number", "vivienda_office.office_m2": "24.00"},
    )
    service = CensoSyncService(bucket_id=_BUCKET_ID, snapshots=snapshots)
    with caplog.at_level(logging.DEBUG):
        ratio = service.bound_raw_afectacion_ratio(profile_id=_PROFILE_ID)
    assert ratio is None
    assert any("afectacion ratio ignored" in record.message for record in caplog.records)
