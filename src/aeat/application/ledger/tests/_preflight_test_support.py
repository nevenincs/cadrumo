"""Shared support for ledger preflight tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.config import Settings
from ....domain.categories import SpendingCategory
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....domain.user_profile import UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...live._censo import CensoSnapshotService
from ...user_profile import CensoSyncService, UserProfileLifecycleRepository

_SEDE_ORIGIN = Settings.external_constants().aeat.domains.sede
_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_OTHER_BUCKET_ID = "23232323-2323-4323-8323-232323232323"
_HOME_OFFICE_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_Q2_2026 = _period(2026, "2T")
_AD_HOC_2026 = _period(2026, "AD-HOC")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 4, 5),
    amount: Decimal = Decimal("121.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency=currency,
        counterparty="Cliente o proveedor",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(
    provider_id: str,
    *,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    amount: Decimal = Decimal("121.00"),
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    category_id: str | None = SpendingCategory.MATERIAL_OFICINA.value,
    taxable_base: Decimal | None = Decimal("100.00"),
    iva_rate: Decimal | None = Decimal("0.21"),
    iva_amount: Decimal | None = Decimal("21.00"),
    irpf_category: str | None = None,
    usage_ratio_id: str | None = None,
    booked_date: date = date(2026, 4, 5),
    currency: str = "EUR",
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, booked_date=booked_date, amount=amount, currency=currency),
            "direction": direction,
            "group_label": None,
            "business_classification": business_classification,
            "source_jurisdiction": "ES",
            "business_pct": business_pct,
            "category_id": category_id,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "irpf_category": irpf_category,
            "usage_ratio_id": usage_ratio_id,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _home_office_censo_facts() -> dict[str, str]:
    return {
        "vivienda_office.total_m2": "100",
        "vivienda_office.office_m2": "20",
    }


def _apply_home_office_censo(bucket_id: str) -> None:
    profiles = UserProfileLifecycleRepository(bucket_id=bucket_id)
    profiles.save(UserProfileRecord(profile_id=bucket_id, display_name="Ledger preflight profile"))
    service = CensoSyncService(
        bucket_id=bucket_id,
        snapshots=CensoSnapshotService(bucket_id=bucket_id),
        profiles=profiles,
    )
    service.refresh_censo(
        profile_id=bucket_id,
        source_url=f"{_SEDE_ORIGIN}/",
        fact_source=_home_office_censo_facts,
    )
    service.apply_censo_to_profile(profile_id=bucket_id)
