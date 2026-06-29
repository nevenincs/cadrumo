"""CLI surface tests for aeat app modelo iva-wallet balance."""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.calculations._iva_compensation_history import IvaCompensationHistoryRepository
from ....application.calculations._iva_wallet_balance import query_iva_wallet_balance
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_runtime_profile
from ._iva_wallet_inspector_support import _state, _unwrap_envelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture()
def _runtime_profile(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="wallet-test"):
        yield


def test_balance_totals_remaining_after_fifo_applications(
    _runtime_profile: None,
) -> None:
    """Q1 2024 +1200, Q2 2024 -300, Q1 2025 -500 → total_balance=400 at as_of_year=2028."""
    repo = IvaCompensationHistoryRepository()
    repo.save_period(_state(filing_year=2024, period="1T", generated=Decimal("1200.00")))
    repo.save_period(_state(filing_year=2024, period="2T", applied=Decimal("300.00")))
    repo.save_period(_state(filing_year=2025, period="1T", applied=Decimal("500.00")))

    report = query_iva_wallet_balance(as_of_year=2028)

    assert report.total_balance == Decimal("400.00")
    assert report.lot_count == 1
    # source_filing_year=2024 + 4 = 2028; expiry_review_state=EXPIRY_REVIEW_DUE at age 4
    assert report.next_expiry_year == 2028
    assert report.as_of_year == 2028
    assert report.unallocated_applied_amount == Decimal("0.00")


def test_next_expiry_year_is_earliest_active_lot_plus_four(
    _runtime_profile: None,
) -> None:
    """Two lots: 2020 (expired) and 2023 (active). next_expiry_year from 2023 lot."""
    expired_lot = Decimal("100.00")
    active_lot = Decimal("200.00")
    repo = IvaCompensationHistoryRepository()
    repo.save_period(_state(filing_year=2020, period="4T", generated=expired_lot))
    repo.save_period(_state(filing_year=2023, period="2T", generated=active_lot))

    report = query_iva_wallet_balance(as_of_year=2026)

    # 2020 lot is EXPIRED_REVIEW_REQUIRED (age=6), excluded from next_expiry_year
    # 2023 lot is ACTIVE (age=3), next_expiry_year = 2023 + 4 = 2027
    assert report.next_expiry_year == 2027
    assert report.total_balance == expired_lot + active_lot
    assert report.lot_count == 2


def test_next_expiry_year_none_when_no_active_lots_with_balance(
    _runtime_profile: None,
) -> None:
    """All remaining balance is in expired lots: next_expiry_year is None."""
    repo = IvaCompensationHistoryRepository()
    repo.save_period(_state(filing_year=2019, period="4T", generated=Decimal("100.00")))

    report = query_iva_wallet_balance(as_of_year=2026)

    # age=7, EXPIRED_REVIEW_REQUIRED — not ACTIVE
    assert report.next_expiry_year is None
    assert report.total_balance == Decimal("100.00")


def test_empty_history_returns_zero_balance(
    _runtime_profile: None,
) -> None:
    report = query_iva_wallet_balance(as_of_year=2026)

    assert report.total_balance == Decimal("0")
    assert report.lot_count == 0
    assert report.next_expiry_year is None
    assert report.unallocated_applied_amount == Decimal("0")


def test_cli_balance_verb_emits_expected_keys(
    tmp_path: Path,
) -> None:
    """The CLI surface emits operation, as_of_year, total_balance, lot_count, next_expiry_year."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cli-wallet-test"):
        repo = IvaCompensationHistoryRepository()
        repo.save_period(_state(filing_year=2024, period="1T", generated=Decimal("1200.00")))
        repo.save_period(_state(filing_year=2024, period="2T", applied=Decimal("300.00")))
        repo.save_period(_state(filing_year=2025, period="1T", applied=Decimal("500.00")))

        result = invoke_cached_cli(
            ["--format", "json", "app", "modelo", "iva-wallet", "balance", "--as-of-year", "2028"],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code == 0, result.output
    payload = _unwrap_envelope(json.loads(result.output))
    assert payload["total_balance"] == "400.00"
    assert payload["lot_count"] == 1
    assert payload["next_expiry_year"] == 2028
    assert payload["as_of_year"] == 2028


def test_cli_balance_verb_text_output_lines(
    tmp_path: Path,
) -> None:
    """Text-mode output includes tab-separated metric lines."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cli-text-test"):
        repo = IvaCompensationHistoryRepository()
        repo.save_period(_state(filing_year=2024, period="1T", generated=Decimal("1200.00")))
        repo.save_period(_state(filing_year=2024, period="2T", applied=Decimal("300.00")))
        repo.save_period(_state(filing_year=2025, period="1T", applied=Decimal("500.00")))

        result = invoke_cached_cli(
            ["app", "modelo", "iva-wallet", "balance", "--as-of-year", "2028"],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code == 0, result.output
    assert "operation\tmodelo.iva-wallet.balance" in result.output
    assert "total_balance\t400.00" in result.output
    assert "next_expiry_year\t2028" in result.output
