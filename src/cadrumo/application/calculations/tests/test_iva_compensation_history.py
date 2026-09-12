"""IVA compensation carry-forward modelling tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage.errors import SecureObjectRowIdentityError
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....core.period import Period
from ....domain.iva_compensation.carry_forward import (
    IvaCompensationCarryForwardLot,
    IvaCompensationExpiryReviewState,
    build_iva_compensation_carry_forward_report,
)
from ....domain.iva_compensation.reconciliation import IvaCompensationAuthoritySource, reconcile_iva_compensation_wallet
from ..iva_compensation_history import IvaCompensationHistoryRepository, iva_compensation_period_key
from ._iva_compensation_history_support import _TAXPAYER_REF, _state, _wallet, m303_registry_snapshot_ref

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HISTORY_BUCKET_ID = "30330300-0000-4000-8000-000000000305"


def _local_recurrence_source_for_test(
    amount: Decimal,
    *,
    source_filing_year: int,
    source_period: str,
) -> IvaCompensationAuthoritySource:
    return IvaCompensationAuthoritySource(
        source_kind="local_recurrence",
        amount=amount,
        source_locator="local-recurrence:modelo-303-compensacion-pendiente-anteriores",
        captured_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
        source_modelo="303",
        source_filing_year=source_filing_year,
        source_periods=(Period.from_year_and_code(source_filing_year, source_period),),
        registry_snapshot_refs=(m303_registry_snapshot_ref(source_filing_year, source_period),),
    )


def test_iva_compensation_carry_forward_report_tracks_source_age_application_and_remaining_balance() -> None:
    report = build_iva_compensation_carry_forward_report(
        (
            _state(filing_year=2022, period="4T", generated=Decimal("113.00")),
            _state(filing_year=2023, period="2T", applied=Decimal("31.00")),
            _state(filing_year=2024, period="1T", generated=Decimal("47.00")),
        ),
        as_of_year=2026,
    )

    assert report.unallocated_applied_amount == Decimal("0")
    assert [(lot.source_filing_year, lot.source_period) for lot in report.lots] == [
        (2022, Period.from_year_and_code(2022, "4T")),
        (2024, Period.from_year_and_code(2024, "1T")),
    ]
    first, second = report.lots
    assert first.applied_amount == Decimal("31.00")
    assert first.remaining_amount == Decimal("82.00")
    assert first.age_years == 4
    assert first.expiry_review_state is IvaCompensationExpiryReviewState.EXPIRY_REVIEW_DUE
    assert second.applied_amount == Decimal("0")
    assert second.remaining_amount == Decimal("47.00")
    assert second.age_years == 2
    assert second.expiry_review_state is IvaCompensationExpiryReviewState.ACTIVE


def test_iva_compensation_carry_forward_report_marks_expired_review_required() -> None:
    report = build_iva_compensation_carry_forward_report(
        (_state(filing_year=2022, period="4T", generated=Decimal("100.00")),),
        as_of_year=2027,
    )

    assert report.lots[0].age_years == 5
    assert report.lots[0].expiry_review_state is IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED


def test_iva_compensation_carry_forward_report_preserves_unallocated_applications() -> None:
    report = build_iva_compensation_carry_forward_report(
        (_state(filing_year=2025, period="2T", applied=Decimal("25.00")),),
        as_of_year=2026,
    )

    assert report.lots == ()
    assert report.unallocated_applied_amount == Decimal("25.00")


def test_multiyear_compensation_flow_covers_expiry_boundary_wallet_divergence_and_blocked_local_fallback() -> None:
    report = build_iva_compensation_carry_forward_report(
        (
            _state(filing_year=2022, period="4T", generated=Decimal("100.00")),
            _state(filing_year=2024, period="2T", applied=Decimal("40.00")),
        ),
        as_of_year=2026,
    )
    source_lot = report.lots[0]
    assert source_lot.source_filing_year == 2022
    assert source_lot.applied_amount == Decimal("40.00")
    assert source_lot.remaining_amount == Decimal("60.00")
    assert source_lot.expiry_review_state is IvaCompensationExpiryReviewState.EXPIRY_REVIEW_DUE

    divergent = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        target_registry_snapshot_ref=m303_registry_snapshot_ref(2026, "2T"),
        wallet=_wallet(Decimal("80.00")),
        local_recurrence_amount=source_lot.remaining_amount,
        local_recurrence_source=_local_recurrence_source_for_test(
            source_lot.remaining_amount,
            source_filing_year=source_lot.source_filing_year,
            source_period=source_lot.source_period.registry_token,
        ),
        decided_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    )
    assert divergent.divergence == "wallet_higher"
    assert divergent.blocked is True

    fallback = reconcile_iva_compensation_wallet(
        taxpayer_nif=_TAXPAYER_REF,
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        target_registry_snapshot_ref=m303_registry_snapshot_ref(2026, "2T"),
        wallet=None,
        local_recurrence_amount=source_lot.remaining_amount,
        local_recurrence_source=_local_recurrence_source_for_test(
            source_lot.remaining_amount,
            source_filing_year=source_lot.source_filing_year,
            source_period=source_lot.source_period.registry_token,
        ),
        decided_at=datetime(2026, 5, 19, 10, 0, tzinfo=UTC),
    )
    assert fallback.selected_authority == "local_recurrence"
    assert fallback.selected_amount == Decimal("60.00")
    assert fallback.blocked is True


def test_iva_compensation_carry_forward_lot_rejects_unbalanced_amounts() -> None:
    with pytest.raises(ValidationError, match="must equal generated_amount"):
        IvaCompensationCarryForwardLot(
            taxpayer_nif=_TAXPAYER_REF,
            source_filing_year=2026,
            source_period=Period.from_year_and_code(2026, "1T"),
            generated_amount=Decimal("100.00"),
            applied_amount=Decimal("20.00"),
            remaining_amount=Decimal("90.00"),
            age_years=0,
            expiry_review_state=IvaCompensationExpiryReviewState.ACTIVE,
            source_observation_key="303:2026:1T:EXP",
        )


def test_iva_compensation_history_round_trips_a_period_bound_encrypted_payload(tmp_path: Path) -> None:
    state = _state(filing_year=2026, period="2T", generated=Decimal("47.00"))

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HISTORY_BUCKET_ID):
        repository = IvaCompensationHistoryRepository()
        repository.save_period(state)
        loaded = repository.load_period(state.period)
        listed = repository.list_periods()

    assert loaded == state
    assert listed == (state,)


def test_iva_compensation_history_refuses_a_period_payload_rekeyed_under_foreign_storage_key(tmp_path: Path) -> None:
    state = _state(filing_year=2026, period="2T", generated=Decimal("47.00"))
    foreign_period = Period.from_year_and_code(2025, "1T")
    foreign_key = iva_compensation_period_key(foreign_period)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HISTORY_BUCKET_ID):
        repository = IvaCompensationHistoryRepository()
        write = repository.to_secure_object_write(state)
        repository.secure_object_repository.save(
            namespace=write.namespace,
            object_key=foreign_key,
            classification=write.classification,
            schema_version=write.schema_version,
            written_at=write.written_at,
            payload=write.payload,
        )

        with pytest.raises(SecureObjectRowIdentityError) as load_error:
            repository.load_period(foreign_period)
        with pytest.raises(SecureObjectRowIdentityError) as list_error:
            repository.list_periods()

    assert load_error.value.expected_identifier == foreign_key
    assert list_error.value.expected_identifier == iva_compensation_period_key(state.period)
