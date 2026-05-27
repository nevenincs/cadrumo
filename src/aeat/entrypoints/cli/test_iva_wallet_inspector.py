"""CLI surface tests for aeat app modelo iva-wallet balance and seed."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from aeat.application.calculations._iva_compensation_history import (
    IvaCompensationCarryForwardLot,
    IvaCompensationExpiryReviewState,
    IvaCompensationHistoryRepository,
    IvaCompensationPeriodState,
    IvaCompensationSeedConflictError,
    seed_iva_compensation_period,
)
from aeat.application.calculations._iva_wallet_balance import query_iva_wallet_balance
from aeat.entrypoints.cli import app
from aeat.tests.secure_sql import isolated_runtime_profile

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


# ---------------------------------------------------------------------------
# S352: iva-wallet seed verb
# ---------------------------------------------------------------------------


def _store_profile_with_nif(nif: str) -> None:
    """Persist a minimal UserProfileRecord carrying identity.tax_id."""
    from datetime import UTC, datetime

    from aeat.application.user_profile import UserProfileLifecycleRepository
    from aeat.domain.user_profile import UserProfileFact, UserProfileRecord

    _created_at = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    UserProfileLifecycleRepository(bucket_id="seed-test").save(
        UserProfileRecord(
            profile_id="seed-test",
            display_name="Seed Tester",
            facts=(UserProfileFact(path="identity.tax_id", value=nif),),
            created_at=_created_at,
            updated_at=_created_at,
        )
    )


def test_seed_iva_compensation_persists_available_end_amount(tmp_path: Path) -> None:
    """seed_iva_compensation_period stores state so prefill resolves the balance.

    Seeds 2024/4T with 1200 EUR, then reads back via the repository.
    The available_end_amount on the stored state is the value that
    _observation_from_iva_compensation_history forwards to the binding resolver
    as iva.compensacion-disponible-fin-periodo.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        state = seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            filing_year=2024,
            period="4T",
            amount=Decimal("1200.00"),
        )

        repo = IvaCompensationHistoryRepository()
        loaded = repo.load_period(2024, "4T")

    assert loaded is not None
    assert loaded.available_end_amount == Decimal("1200.00")
    assert loaded.status == "seeded"
    assert loaded.taxpayer_nif == _NIF
    # The seeded state must round-trip with the same amount that was seeded.
    assert loaded == state


def test_seed_iva_compensation_anti_tautology_different_amounts(tmp_path: Path) -> None:
    """Anti-tautology: seeding X vs Y produces different available_end_amount.

    If seeding were a no-op or if the value were ignored, both scenarios would
    produce the same stored state. The strict inequality below fails if that happens.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        state_a = seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            filing_year=2024,
            period="3T",
            amount=Decimal("500.00"),
        )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test-b"):
        state_b = seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            filing_year=2024,
            period="3T",
            amount=Decimal("999.00"),
        )

    assert state_a.available_end_amount != state_b.available_end_amount, (
        "Anti-tautology failure: both seed amounts produced the same available_end_amount"
    )


def test_seed_iva_compensation_refuses_duplicate(tmp_path: Path) -> None:
    """Seeding a period that already has a stored state raises IvaCompensationSeedConflictError."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            filing_year=2024,
            period="2T",
            amount=Decimal("800.00"),
        )

        with pytest.raises(IvaCompensationSeedConflictError, match="2024/2T"):
            seed_iva_compensation_period(
                taxpayer_nif=_NIF,
                filing_year=2024,
                period="2T",
                amount=Decimal("100.00"),
            )


def test_cli_seed_verb_refuses_without_confirm(tmp_path: Path) -> None:
    """Seed verb requires --confirm; without it, exit code is non-zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        result = _RUNNER.invoke(
            app,
            ["app", "modelo", "iva-wallet", "seed",
             "--filing-year", "2024", "--period", "4T", "--amount", "1200.00"],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0


def test_cli_seed_verb_happy_path(tmp_path: Path) -> None:
    """Seed verb with --confirm creates the state and emits the correct fields."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        result = _RUNNER.invoke(
            app,
            ["--format", "json", "app", "modelo", "iva-wallet", "seed",
             "--filing-year", "2024", "--period", "4T",
             "--amount", "1200.50", "--confirm"],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

        repo = IvaCompensationHistoryRepository()
        stored = repo.load_period(2024, "4T")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["operation"] == "modelo.iva-wallet.seed"
    assert payload["filing_year"] == 2024
    assert payload["period"] == "4T"
    assert payload["amount"] == "1200.50"
    assert payload["status"] == "seeded"
    # Stored state must match the seeded amount.
    assert stored is not None
    assert stored.available_end_amount == Decimal("1200.50")


def test_cli_seed_verb_refuses_duplicate(tmp_path: Path) -> None:
    """Seed verb refuses a second seed for the same period."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        _RUNNER.invoke(
            app,
            ["app", "modelo", "iva-wallet", "seed",
             "--filing-year", "2024", "--period", "4T",
             "--amount", "1200.00", "--confirm"],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )
        result = _RUNNER.invoke(
            app,
            ["app", "modelo", "iva-wallet", "seed",
             "--filing-year", "2024", "--period", "4T",
             "--amount", "500.00", "--confirm"],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0


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
