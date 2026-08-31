"""CLI surface tests for IVA wallet seed and override verbs."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....application.calculations import (
    IvaCompensationHistoryRepository,
    query_iva_wallet_balance,
    seed_iva_compensation_period,
)
from ....core.iva_compensation_provenance import IvaCompensationStateProvenance
from ....core.period import Period
from ....domain.iva_compensation.carry_forward import IvaCompensationCarryForwardLot, IvaCompensationExpiryReviewState
from ....domain.iva_compensation.errors import IvaCompensationSeedConflictError
from ....tests.cli_envelope import require_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_runtime_profile
from ._iva_wallet_inspector_support import _NIF, _SEED_BUCKET_ID, _store_profile_with_nif

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_seed_iva_compensation_persists_available_end_amount(tmp_path: Path) -> None:
    """seed_iva_compensation_period stores state so prefill resolves the balance."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="58072ef9-4b9f-42b3-9f46-38f4239b1510"):
        state = seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            period=Period.from_year_and_code(2024, "4T"),
            amount=Decimal("1200.00"),
        )

        repo = IvaCompensationHistoryRepository()
        loaded = repo.load_period(Period.from_year_and_code(2024, "4T"))

    assert loaded is not None
    assert loaded.available_end_amount == Decimal("1200.00")
    assert loaded.provenance is IvaCompensationStateProvenance.OPERATOR_SEED
    assert loaded.status is None
    assert loaded.taxpayer_nif == _NIF
    assert loaded == state


def test_seeded_state_surfaces_as_a_wallet_lot(tmp_path: Path) -> None:
    """A seeded opening balance shows up in iva-wallet balance."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f699b704-4c17-4682-ab50-7a2051ce4c52"):
        seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            period=Period.from_year_and_code(2025, "4T"),
            amount=Decimal("1500.00"),
        )
        report = query_iva_wallet_balance(as_of_year=2025)

    assert report.lot_count == 1, "seeded carry-forward must surface as exactly one wallet lot"
    assert report.total_balance == Decimal("1500.00"), "balance must reflect the seeded amount, not zero"
    assert report.active_balance == Decimal("1500.00")
    assert report.expired_balance == Decimal("0")
    assert report.next_expiry_year == 2025 + 4


def test_zero_seed_surfaces_no_lot_anti_tautology(tmp_path: Path) -> None:
    """Anti-tautology: a zero-amount seed produces no lot."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f699b704-4c17-4682-ab50-7a2051ce4c52"):
        seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            period=Period.from_year_and_code(2025, "1T"),
            amount=Decimal("0"),
        )
        report = query_iva_wallet_balance(as_of_year=2025)

    assert report.lot_count == 0, "a zero seed must not fabricate a wallet lot"
    assert report.total_balance == Decimal("0")
    assert report.active_balance == Decimal("0")
    assert report.expired_balance == Decimal("0")


def test_seed_iva_compensation_anti_tautology_different_amounts(tmp_path: Path) -> None:
    """Anti-tautology: seeding X vs Y produces different available_end_amount."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="58072ef9-4b9f-42b3-9f46-38f4239b1510"):
        state_a = seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            period=Period.from_year_and_code(2024, "3T"),
            amount=Decimal("500.00"),
        )

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="3ba277a9-0812-47c5-9400-64768e433f06"):
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="58072ef9-4b9f-42b3-9f46-38f4239b1510"):
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
    assert excinfo.value.context == {"filing_year": 2024, "period": "2T", "existing_provenance": "operator_seed"}


def test_cli_seed_verb_refuses_without_confirm(tmp_path: Path) -> None:
    """Seed verb requires --confirm; without it, exit code is non-zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SEED_BUCKET_ID):
        _store_profile_with_nif(_NIF)
        result = invoke_cached_cli(
            ["app", "modelo", "iva-wallet", "seed", "--filing-year", "2024", "--period", "4T", "--amount", "1200.00"],
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0


def test_cli_seed_verb_happy_path(tmp_path: Path) -> None:
    """Seed verb with --confirm creates the state and emits the correct fields."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SEED_BUCKET_ID):
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
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

        repo = IvaCompensationHistoryRepository()
        stored = repo.load_period(Period.from_year_and_code(2024, "4T"))

    assert result.exit_code == 0, result.output
    payload = require_schema_envelope(result.output)
    assert payload["operation"] == "modelo.iva_wallet.seed"
    assert payload["filing_year"] == 2024
    assert payload["period"] == {"filing_year": 2024, "code": "4T"}
    assert payload["amount"] == "1200.50"
    assert payload["provenance"] == "operator_seed"
    assert payload["register_status"] is None
    assert stored is not None
    assert stored.available_end_amount == Decimal("1200.50")
    assert stored.provenance is IvaCompensationStateProvenance.OPERATOR_SEED
    assert stored.status is None


def test_wallet_amount_refuses_non_canonical_forms() -> None:
    """The shared wallet amount parser refuses every non-canonical euro form.

    Each form is asserted to be one the bare ``Decimal`` constructor this
    replaced really does accept, so the test proves a genuine tightening rather
    than restating the constructor. The headline case is ``1.000``: previously it
    became ``Decimal("1.0")``, declaring a one-euro carry-forward balance for an
    operator who meant one thousand.
    """
    import typer as _typer

    from .._modelo_iva_wallet_cli import _wallet_amount

    for raw in ("1.000", "1e3", "1E3", "+1200", "1_000", ".5", "1.", "NaN", "-NaN", "Infinity", "-Infinity"):
        assert isinstance(Decimal(raw), Decimal), raw
        with pytest.raises(_typer.BadParameter):
            _wallet_amount(raw)

    for raw in ("1.234,56", "36.500,00", "not-decimal", "1 200"):
        with pytest.raises(_typer.BadParameter):
            _wallet_amount(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1200", Decimal("1200")),
        ("1200.50", Decimal("1200.50")),
        ("0", Decimal("0")),
        ("  1200.50  ", Decimal("1200.50")),
        # A leading '-' still conforms so the domain's own non-negative refusal
        # stays the surface that reports a negative balance.
        ("-1200.50", Decimal("-1200.50")),
    ],
)
def test_wallet_amount_accepts_canonical_forms(raw: str, expected: Decimal) -> None:
    from .._modelo_iva_wallet_cli import _wallet_amount

    assert _wallet_amount(raw) == expected


def test_cli_seed_verb_refuses_spanish_thousands_amount_and_persists_nothing(tmp_path: Path) -> None:
    """``--amount 1.000`` refuses at the boundary instead of seeding one euro."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SEED_BUCKET_ID):
        _store_profile_with_nif(_NIF)
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
                "1.000",
                "--confirm",
            ],
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )
        stored = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2024, "4T"))

    assert result.exit_code != 0, result.output
    assert stored is None, "a refused amount must not persist a carry-forward balance"


def test_cli_override_verb_records_taxpayer_override_decision(tmp_path: Path) -> None:
    """The override verb records a non-blocking taxpayer_override decision."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SEED_BUCKET_ID):
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
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code == 0, result.output
    payload = require_schema_envelope(result.output)
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SEED_BUCKET_ID):
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
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0


def test_cli_override_verb_requires_evidence_locator(tmp_path: Path) -> None:
    """A blank --evidence-locator is refused: provenance is mandatory, not optional."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SEED_BUCKET_ID):
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
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0


def test_cli_seed_verb_refuses_duplicate(tmp_path: Path) -> None:
    """Seed verb refuses a second seed for the same period."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SEED_BUCKET_ID):
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
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
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
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="cb110a91-a9ee-4310-8690-818df2a5df78"):
        result = invoke_cached_cli(
            ["app", "modelo", "iva-wallet", "seed", "--help"],
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code == 0, result.output
    help_text = result.output
    assert "99.5" in help_text, "seed --help must cite LIVA art. 99.5 for the zero-first-period legal grounding"
    assert "Ley 37/1992" in help_text or "LIVA" in help_text, (
        "seed --help must reference the legal source (Ley 37/1992 or LIVA)"
    )
