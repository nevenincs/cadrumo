"""Persistence-boundary tests for the IVA compensation history adapter."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.storage.errors import SecureObjectRowIdentityError
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.calculations.iva_compensation_history import iva_compensation_period_key
from cadrumo.application.calculations.iva_compensation_history_ports import IvaCompensationHistoryPersistenceError
from cadrumo.core.period import Period
from cadrumo.domain.iva_compensation.carry_forward import build_iva_compensation_carry_forward_report

from ._iva_compensation_history_support import _state

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_HISTORY_BUCKET_ID = "30330300-0000-4000-8000-000000000305"


def test_iva_compensation_history_round_trips_a_period_bound_encrypted_payload(tmp_path: Path) -> None:
    state = _state(filing_year=2026, period="2T", generated=Decimal("47.00"))

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HISTORY_BUCKET_ID):
        repository = IvaCompensationHistoryRepository()
        repository.save_period(state)
        loaded = repository.load_period(state.period)
        listed = repository.list_periods()

    assert loaded == state
    assert listed == (state,)


def test_replaying_the_same_period_state_does_not_duplicate_a_compensation_lot(tmp_path: Path) -> None:
    """An identical recalculation/replay replaces one period key, not the wallet history."""
    state = _state(filing_year=2026, period="2T", generated=Decimal("47.00"))

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HISTORY_BUCKET_ID):
        repository = IvaCompensationHistoryRepository()
        repository.save_period(state)
        repository.save_period(state)

        listed = repository.list_periods()
    report = build_iva_compensation_carry_forward_report(listed, as_of_year=2026)

    assert listed == (state,)
    assert len(report.lots) == 1
    assert report.lots[0].remaining_amount == Decimal("47.00")


def test_iva_compensation_history_refuses_a_period_payload_rekeyed_under_foreign_storage_key(tmp_path: Path) -> None:
    state = _state(filing_year=2026, period="2T", generated=Decimal("47.00"))
    foreign_period = Period.from_year_and_code(2025, "1T")
    foreign_key = iva_compensation_period_key(foreign_period)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_HISTORY_BUCKET_ID) as profile:
        repository = IvaCompensationHistoryRepository(objects=profile.repository)
        write = repository.to_secure_object_write(state)
        profile.repository.save(
            namespace=write.namespace,
            object_key=foreign_key,
            classification=write.classification,
            schema_version=write.schema_version,
            written_at=write.written_at,
            payload=write.payload,
        )

        # The adapter reports the application-owned persistence error; the
        # storage identity refusal it translates is carried as the cause.
        with pytest.raises(IvaCompensationHistoryPersistenceError) as load_error:
            repository.load_period(foreign_period)
        with pytest.raises(IvaCompensationHistoryPersistenceError) as list_error:
            repository.list_periods()

    load_cause = load_error.value.__cause__
    list_cause = list_error.value.__cause__
    assert isinstance(load_cause, SecureObjectRowIdentityError)
    assert isinstance(list_cause, SecureObjectRowIdentityError)
    assert load_cause.expected_identifier == foreign_key
    assert list_cause.expected_identifier == iva_compensation_period_key(state.period)
