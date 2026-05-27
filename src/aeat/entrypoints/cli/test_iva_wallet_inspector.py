"""CLI surface tests for aeat app modelo iva-wallet balance."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from aeat.application.calculations._iva_compensation_history import (
    IvaCompensationCarryForwardLot,
    IvaCompensationExpiryReviewState,
    IvaCompensationHistoryRepository,
    IvaCompensationPeriodState,
)
from aeat.application.calculations._iva_wallet_balance import (
    IvaWalletBalanceReport,
    build_iva_wallet_balance_report,
    query_iva_wallet_balance,
)
from aeat.application.calculations._iva_compensation_history import (
    build_iva_compensation_carry_forward_report,
)
from aeat.entrypoints.cli import app
from aeat.tests.secure_sql import isolated_runtime_profile
from typer.testing import CliRunner

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()
_NIF = "12345678Z"


def _state(
    *,
    filing_year: int,
    period: str,
    generated: Decimal = Decimal("0.00"),
    applied: Decimal = Decimal("0.00"),
) -> IvaCompensationPeriodState:
    return IvaCompensationPeriodState(
        taxpayer_nif=_NIF,
        filing_year=filing_year,
        period=period,
        expediente_id=f"EXP-{filing_year}-{period}",
        status="filed",
        presented_at=datetime(filing_year + 1, 1, 20, 12, 0, tzinfo=UTC),
        prior_pending_amount=None,
        applied_amount=applied,
        pending_for_later_amount=None,
        period_result_amount=None,
        final_result_amount=None,
        generated_amount=generated,
        available_end_amount=generated,
        source_observation_key=f"303:{filing_year}:{period}:EXP",
    )


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
    repo = IvaCompensationHistoryRepository()
    repo.save_period(_state(filing_year=2020, period="4T", generated=Decimal("100.00")))
    repo.save_period(_state(filing_year=2023, period="2T", generated=Decimal("200.00")))

    report = query_iva_wallet_balance(as_of_year=2026)

    # 2020 lot is EXPIRED_REVIEW_REQUIRED (age=6), excluded from next_expiry_year
    # 2023 lot is ACTIVE (age=3), next_expiry_year = 2023 + 4 = 2027
    assert report.next_expiry_year == 2027
    assert report.total_balance == Decimal("300.00")
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI surface emits operation, as_of_year, total_balance, lot_count, next_expiry_year."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cli-wallet-test"):
        repo = IvaCompensationHistoryRepository()
        repo.save_period(_state(filing_year=2024, period="1T", generated=Decimal("1200.00")))
        repo.save_period(_state(filing_year=2024, period="2T", applied=Decimal("300.00")))
        repo.save_period(_state(filing_year=2025, period="1T", applied=Decimal("500.00")))

        result = _RUNNER.invoke(
            app,
            ["--format", "json", "app", "modelo", "iva-wallet", "balance", "--as-of-year", "2028"],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
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

        result = _RUNNER.invoke(
            app,
            ["app", "modelo", "iva-wallet", "balance", "--as-of-year", "2028"],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code == 0, result.output
    assert "operation\tmodelo.iva-wallet.balance" in result.output
    assert "total_balance\t400.00" in result.output
    assert "next_expiry_year\t2028" in result.output


# Anti-tautology proof: mutated applied_amount in a lot triggers model_validator
def test_carry_forward_lot_rejects_unbalanced_amounts_anti_tautology() -> None:
    """Verifies that the roundtrip contract enforces amount balance."""
    with pytest.raises(ValidationError, match="must equal generated_amount"):
        IvaCompensationCarryForwardLot(
            taxpayer_nif=_NIF,
            source_filing_year=2024,
            source_period="1T",
            generated_amount=Decimal("1200.00"),
            applied_amount=Decimal("800.00"),   # should be 800, remaining should be 400
            remaining_amount=Decimal("500.00"),  # but 800+500 != 1200 → validator fires
            age_years=2,
            expiry_review_state=IvaCompensationExpiryReviewState.ACTIVE,
            source_observation_key="303:2024:1T:EXP",
        )
