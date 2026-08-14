"""Real-behavior tests for the surviving CensoSyncService surface.

The live Modelo 036 censo scrape and the refresh / show / compare / apply
verbs were retired (censal facts are operator-supplied through
``config profile edit``). What remains is the read-only home-office
afectación ratio the ledger proportional-deduction path consumes; these
tests exercise it against the operator-declared ``vivienda_office`` m²
facts persisted on a real encrypted profile record.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from .. import CensoSyncError, CensoSyncService, ProfileRecordRepository
from .._censo_sync import _raw_afectacion_ratio

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "35353535-3535-4535-8535-353535353535"


@pytest.fixture
def secure_store(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _declare_vivienda_office(facts: Mapping[str, str]) -> None:
    """Persist ``vivienda_office`` m² facts on the active profile record.

    Mirrors what ``config profile edit`` writes: a real encrypted
    ``UserProfileRecord`` carrying the operator-declared m² facts.
    """
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Censo sync test profile",
        facts=tuple(UserProfileFact(path=path, value=Decimal(value)) for path, value in facts.items()),
    )
    ProfileRecordRepository(bucket_id=_BUCKET_ID).save(record)


def test_service_refuses_blank_bucket_id_with_translated_error() -> None:
    with pytest.raises(CensoSyncError):
        CensoSyncService(bucket_id="  ")


def test_bound_raw_afectacion_ratio_returns_none_without_profile_record(
    secure_store: SecureObjectRepository,
) -> None:
    service = CensoSyncService(bucket_id=_BUCKET_ID)
    assert service.bound_raw_afectacion_ratio(profile_id=_BUCKET_ID) is None


def test_bound_raw_afectacion_ratio_derives_from_operator_declared_facts(
    secure_store: SecureObjectRepository,
) -> None:
    _declare_vivienda_office(
        {"vivienda_office.total_m2": "120.00", "vivienda_office.office_m2": "24.00"},
    )
    service = CensoSyncService(bucket_id=_BUCKET_ID)
    ratio = service.bound_raw_afectacion_ratio(profile_id=_BUCKET_ID)
    assert ratio is not None
    assert ratio == Decimal("24") / Decimal("120")


def test_bound_raw_afectacion_ratio_none_when_m2_facts_absent(
    secure_store: SecureObjectRepository,
) -> None:
    _declare_vivienda_office({"vivienda_office.total_m2": "120.00"})
    service = CensoSyncService(bucket_id=_BUCKET_ID)
    assert service.bound_raw_afectacion_ratio(profile_id=_BUCKET_ID) is None


def test_raw_afectacion_ratio_rejects_office_exceeding_total() -> None:
    assert (
        _raw_afectacion_ratio(
            {"vivienda_office.total_m2": "50", "vivienda_office.office_m2": "80"},
        )
        is None
    )


def test_raw_afectacion_ratio_rejects_non_positive_total() -> None:
    assert (
        _raw_afectacion_ratio(
            {"vivienda_office.total_m2": "0", "vivienda_office.office_m2": "0"},
        )
        is None
    )


def test_raw_afectacion_ratio_rejects_non_decimal_surface() -> None:
    assert (
        _raw_afectacion_ratio(
            {"vivienda_office.total_m2": "not-a-number", "vivienda_office.office_m2": "24"},
        )
        is None
    )
