"""Shared support for ledger preflight tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....domain.categories.spending_category import SpendingCategory
from ....domain.iva.schema import EUMemberState, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ...user_profile.censo_sync import CensoSyncService

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_OTHER_BUCKET_ID = "23232323-2323-4323-8323-232323232323"
_HOME_OFFICE_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_Q2_2026 = _period(2026, "2T")
_AD_HOC_2026 = _period(2026, "AD-HOC")


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 4, 5),
    amount: Decimal = Decimal("121.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
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
        raw_fields={"source_kind": BindingSourceKind.LEDGER_TRANSACTION.value},
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
    iva_category: IvaCategory | None = None,
    counterparty_country: str | None = None,
    counterparty_identification_state: EUMemberState | None = None,
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
            "iva_category": iva_category,
            "counterparty_country": counterparty_country,
            "counterparty_identification_state": counterparty_identification_state,
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


def _declare_home_office_m2(bucket_id: str) -> None:
    """Persist only the operator-declared ``vivienda_office`` m² facts.

    Mirrors ``config profile edit``: a real encrypted profile record
    carrying the afectación m² so ``bound_raw_afectacion_ratio`` resolves
    from the operator-declared facts, with no usage-ratio overrides.
    """
    m2_facts = tuple(
        UserProfileFact(path=path, value=Decimal(value)) for path, value in _home_office_censo_facts().items()
    )
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=m2_facts,
        ),
    )


def _apply_home_office_censo(bucket_id: str) -> None:
    """Declare the operator's ``vivienda_office`` m² facts and derived HOME_OFFICE ratios.

    Reproduces what the retired ``censo apply`` verb did for the ledger
    preflight tests: persist the operator-declared ``vivienda_office``
    afectación m² onto the profile record (so ``bound_raw_afectacion_ratio``
    resolves from the profile facts, as ``config profile edit`` would write
    them) and persist the derived HOME_OFFICE ratios so the operator's
    override agrees with the bound afectación ratio.
    """
    from ....adapters.persistence.profile.usage_ratios import load_usage_ratios, save_usage_ratios
    from ....domain.usage_ratios._model import UsageRatioProfile
    from ....domain.usage_ratios._service import derive_home_office_ratios_from_censo

    _declare_home_office_m2(bucket_id)
    raw = CensoSyncService(bucket_id=bucket_id).bound_raw_afectacion_ratio(profile_id=bucket_id)
    assert raw is not None
    derived = derive_home_office_ratios_from_censo(raw, year=2025)
    merged = dict(load_usage_ratios(bucket_id=bucket_id).ratios)
    merged.update(derived.ratios)
    save_usage_ratios(UsageRatioProfile(ratios=merged), bucket_id=bucket_id)
