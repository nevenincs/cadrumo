"""CLI surface tests for IVA wallet seed and override verbs."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....application.calculations._iva_compensation_history import (
    IvaCompensationHistoryRepository,
    seed_iva_compensation_period,
)
from ....application.calculations._iva_wallet_balance import query_iva_wallet_balance
from ....core import Period
from ....domain.iva_compensation._carry_forward import (
    IvaCompensationCarryForwardLot,
    IvaCompensationExpiryReviewState,
)
from ....domain.iva_compensation._errors import IvaCompensationSeedConflictError
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_runtime_profile
from ._iva_wallet_inspector_support import _NIF, _store_profile_with_nif, _unwrap_envelope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_seed_iva_compensation_persists_available_end_amount(tmp_path: Path) -> None:
    """seed_iva_compensation_period stores state so prefill resolves the balance."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        state = seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            period=Period.from_year_and_code(2024, "4T"),
            amount=Decimal("1200.00"),
        )

        repo = IvaCompensationHistoryRepository()
        loaded = repo.load_period(Period.from_year_and_code(2024, "4T"))

    assert loaded is not None
    assert loaded.available_end_amount == Decimal("1200.00")
    assert loaded.status == "seeded"
    assert loaded.taxpayer_nif == _NIF
    assert loaded == state


def test_seeded_state_surfaces_as_a_wallet_lot(tmp_path: Path) -> None:
    """A seeded opening balance shows up in iva-wallet balance."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="wallet-test"):
        seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            period=Period.from_year_and_code(2025, "4T"),
            amount=Decimal("1500.00"),
        )
        report = query_iva_wallet_balance(as_of_year=2025)

    assert report.lot_count == 1, "seeded carry-forward must surface as exactly one wallet lot"
    assert report.total_balance == Decimal("1500.00"), "balance must reflect the seeded amount, not zero"
    assert report.next_expiry_year == 2025 + 4


def test_zero_seed_surfaces_no_lot_anti_tautology(tmp_path: Path) -> None:
    """Anti-tautology: a zero-amount seed produces no lot."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="wallet-test"):
        seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            period=Period.from_year_and_code(2025, "1T"),
            amount=Decimal("0"),
        )
        report = query_iva_wallet_balance(as_of_year=2025)

    assert report.lot_count == 0, "a zero seed must not fabricate a wallet lot"
    assert report.total_balance == Decimal("0")


def test_seed_iva_compensation_anti_tautology_different_amounts(tmp_path: Path) -> None:
    """Anti-tautology: seeding X vs Y produces different available_end_amount."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        state_a = seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            period=Period.from_year_and_code(2024, "3T"),
            amount=Decimal("500.00"),
        )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test-b"):
        state_b = seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            period=Period.from_year_and_code(2024, "3T"),
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
            period=Period.from_year_and_code(2024, "2T"),
            amount=Decimal("800.00"),
        )

        with pytest.raises(IvaCompensationSeedConflictError) as excinfo:
            seed_iva_compensation_period(
                taxpayer_nif=_NIF,
                period=Period.from_year_and_code(2024, "2T"),
                amount=Decimal("100.00"),
            )

    assert excinfo.value.translated_message == "application.calculations.iva_compensation.errors.seed_conflict"
    assert excinfo.value.context == {"filing_year": 2024, "period": "2T", "existing_status": "seeded"}


def test_cli_seed_verb_refuses_without_confirm(tmp_path: Path) -> None:
    """Seed verb requires --confirm; without it, exit code is non-zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        result = invoke_cached_cli(
            ["app", "modelo", "iva-wallet", "seed", "--filing-year", "2024", "--period", "4T", "--amount", "1200.00"],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0


def test_cli_seed_verb_happy_path(tmp_path: Path) -> None:
    """Seed verb with --confirm creates the state and emits the correct fields."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        result = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "iva-wallet",
                "seed",
                "--filing-year",
                "2024",
                "--period",
                "4T",
                "--amount",
                "1200.50",
                "--confirm",
            ],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

        repo = IvaCompensationHistoryRepository()
        stored = repo.load_period(Period.from_year_and_code(2024, "4T"))

    assert result.exit_code == 0, result.output
    payload = _unwrap_envelope(json.loads(result.output))
    assert payload["operation"] == "modelo.iva_wallet.seed"
    assert payload["filing_year"] == 2024
    assert payload["period"] == {"filing_year": 2024, "code": "4T"}
    assert payload["amount"] == "1200.50"
    assert payload["status"] == "seeded"
    assert stored is not None
    assert stored.available_end_amount == Decimal("1200.50")


def test_cli_override_verb_records_taxpayer_override_decision(tmp_path: Path) -> None:
    """The override verb records a non-blocking taxpayer_override decision."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        result = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "iva-wallet",
                "override",
                "--filing-year",
                "2025",
                "--period",
                "2T",
                "--amount",
                "210.00",
                "--reason",
                "1T 2025 credit a compensar carried forward",
                "--evidence-locator",
                "local M303 1T-2025 filed revision",
                "--confirm",
            ],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code == 0, result.output
    payload = _unwrap_envelope(json.loads(result.output))
    assert payload["operation"] == "modelo.iva_wallet.override"
    assert payload["filing_year"] == 2025
    assert payload["period"] == {"filing_year": 2025, "code": "2T"}
    assert payload["amount"] == "210.00"
    assert payload["selected_authority"] == "taxpayer_override"
    assert payload["divergence"] == "override"
    assert payload["reason"] == "1T 2025 credit a compensar carried forward"
    assert payload["evidence_locator"] == "local M303 1T-2025 filed revision"


def test_cli_override_verb_refuses_without_confirm(tmp_path: Path) -> None:
    """Override verb requires --confirm; without it, exit code is non-zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        result = invoke_cached_cli(
            [
                "app",
                "modelo",
                "iva-wallet",
                "override",
                "--filing-year",
                "2025",
                "--period",
                "2T",
                "--amount",
                "210.00",
                "--reason",
                "x",
                "--evidence-locator",
                "y",
            ],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0


def test_cli_override_verb_requires_evidence_locator(tmp_path: Path) -> None:
    """A blank --evidence-locator is refused: provenance is mandatory, not optional."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        result = invoke_cached_cli(
            [
                "app",
                "modelo",
                "iva-wallet",
                "override",
                "--filing-year",
                "2025",
                "--period",
                "2T",
                "--amount",
                "210.00",
                "--reason",
                "valid reason",
                "--evidence-locator",
                "   ",
                "--confirm",
            ],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0


def test_cli_seed_verb_refuses_duplicate(tmp_path: Path) -> None:
    """Seed verb refuses a second seed for the same period."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        first_result = invoke_cached_cli(
            [
                "app",
                "modelo",
                "iva-wallet",
                "seed",
                "--filing-year",
                "2024",
                "--period",
                "4T",
                "--amount",
                "1200.00",
                "--confirm",
            ],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )
        assert first_result.exit_code == 0, first_result.output
        result = invoke_cached_cli(
            [
                "app",
                "modelo",
                "iva-wallet",
                "seed",
                "--filing-year",
                "2024",
                "--period",
                "4T",
                "--amount",
                "500.00",
                "--confirm",
            ],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0


def test_carry_forward_lot_rejects_unbalanced_amounts_anti_tautology() -> None:
    """Verifies that the roundtrip contract enforces amount balance."""
    with pytest.raises(ValidationError, match="must equal generated_amount"):
        IvaCompensationCarryForwardLot(
            taxpayer_nif=_NIF,
            source_filing_year=2024,
            source_period=Period.from_year_and_code(2024, "1T"),
            generated_amount=Decimal("1200.00"),
            applied_amount=Decimal("800.00"),
            remaining_amount=Decimal("500.00"),
            age_years=2,
            expiry_review_state=IvaCompensationExpiryReviewState.ACTIVE,
            source_observation_key="303:2024:1T:EXP",
        )


def test_cli_seed_help_text_contains_liva_art_99_legal_grounding(tmp_path: Path) -> None:
    """The iva-wallet seed --help output must cite LIVA art. 99.5."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="help-text-test"):
        result = invoke_cached_cli(
            ["app", "modelo", "iva-wallet", "seed", "--help"],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code == 0, result.output
    help_text = result.output
    assert "99.5" in help_text, "seed --help must cite LIVA art. 99.5 for the zero-first-period legal grounding"
    assert "Ley 37/1992" in help_text or "LIVA" in help_text, (
        "seed --help must reference the legal source (Ley 37/1992 or LIVA)"
    )
