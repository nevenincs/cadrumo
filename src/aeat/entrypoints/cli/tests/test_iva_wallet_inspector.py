"""CLI surface tests for aeat app modelo iva-wallet balance and seed."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from ....application.calculations._iva_compensation_history import (
    IvaCompensationHistoryRepository,
    seed_iva_compensation_period,
)
from ....application.calculations._iva_wallet_balance import query_iva_wallet_balance

# Import the wizard catalogue + persistence so register_wizard_catalogue()
# and register_project_answers() run before any domain module under
# ``aeat app modelo work`` queries SETUP_FLOW or projects answers.  The
# CLI command tree is lazy-loaded, so ``aeat app modelo`` alone does not
# trigger these imports (only ``aeat config`` does).
from ....application.wizard import _catalogue as _wizard_catalogue
from ....application.wizard import _persistence as _wizard_persistence
from ....domain.iva_compensation._carry_forward import (
    IvaCompensationCarryForwardLot,
    IvaCompensationExpiryReviewState,
    IvaCompensationPeriodState,
)
from ....domain.iva_compensation._errors import IvaCompensationSeedConflictError
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_runtime_profile, isolated_runtime_profile
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_WIZARD_REGISTRATION_MODULES = (_wizard_catalogue, _wizard_persistence)
_RUNNER = CliRunner()
_NIF = "12345678Z"


def _unwrap_envelope(payload: object) -> dict[str, object]:
    """Return the inner ``result`` payload from a CLI emit envelope.

    Every CLI verb now emits ``{schema_version, command, result, warnings}``
    via the centralised output schema.  Tests assert against the
    operator-visible payload, which lives under ``result``.  Raw payloads
    (pre-envelope) are returned unchanged so this helper is safe to apply
    unconditionally.
    """
    if isinstance(payload, dict) and "result" in payload and "schema_version" in payload:
        payload_dict = cast(dict[str, object], payload)
        result_obj = payload_dict["result"]
        if isinstance(result_obj, dict):
            return cast(dict[str, object], result_obj)
        raise AssertionError(f"result field is not a dict: {type(result_obj).__name__}")
    if not isinstance(payload, dict):
        raise AssertionError(f"unexpected JSON shape: {type(payload).__name__}")
    return cast(dict[str, object], payload)


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
# contract: iva-wallet seed verb
# ---------------------------------------------------------------------------


def _store_profile_with_nif(nif: str) -> None:
    """Persist a minimal UserProfileRecord carrying identity.tax_id.

    The display_name must match the bucket manifest label written by
    ``isolated_runtime_profile`` so the post-load integrity check
    (manifest.label vs record.display_name) does not refuse the read.
    """
    from datetime import UTC, datetime

    from ....application.user_profile import UserProfileLifecycleRepository
    from ....domain.user_profile import UserProfileFact, UserProfileRecord

    _created_at = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    UserProfileLifecycleRepository(bucket_id="seed-test").save(
        UserProfileRecord(
            profile_id="seed-test",
            display_name="Test runtime profile",
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


def test_seeded_state_surfaces_as_a_wallet_lot(tmp_path: Path) -> None:
    """A seeded opening balance shows up in iva-wallet balance (#50 lot_count fix).

    Before the carry-forward lot builder learned about seeded states, a seed
    populated ``available_end_amount`` / ``pending_for_later_amount`` with
    ``generated_amount == 0``, so the lot builder (which only counted
    ``generated_amount > 0``) produced zero lots: ``iva-wallet seed`` reported
    ``status=seeded`` but ``iva-wallet balance`` showed ``lot_count 0`` and
    ``total_balance 0`` — the seeded carry-forward was invisible. The fix
    surfaces the seeded balance as a lot. This is the real-behaviour regression
    fence: seed a non-zero balance, then assert the balance report reflects it.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="wallet-test"):
        seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            filing_year=2025,
            period="4T",
            amount=Decimal("1500.00"),
        )
        report = query_iva_wallet_balance(as_of_year=2025)

    assert report.lot_count == 1, "seeded carry-forward must surface as exactly one wallet lot"
    assert report.total_balance == Decimal("1500.00"), "balance must reflect the seeded amount, not zero"
    # The seed's own filing year is the lot's source year for the four-year window.
    assert report.next_expiry_year == 2025 + 4


def test_zero_seed_surfaces_no_lot_anti_tautology(tmp_path: Path) -> None:
    """Anti-tautology: a zero-amount seed produces NO lot (lot_count stays 0).

    The #50 fix surfaces a seeded balance only when it is positive; a true
    first-period zero seed (LIVA art. 99.5) carries no balance, so it must not
    fabricate a lot. If this test ever shows lot_count > 0 for a zero seed, the
    fix is over-counting (manufacturing balance from nothing).
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="wallet-test"):
        seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            filing_year=2025,
            period="1T",
            amount=Decimal("0"),
        )
        report = query_iva_wallet_balance(as_of_year=2025)

    assert report.lot_count == 0, "a zero seed must not fabricate a wallet lot"
    assert report.total_balance == Decimal("0")


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

        with pytest.raises(IvaCompensationSeedConflictError) as excinfo:
            seed_iva_compensation_period(
                taxpayer_nif=_NIF,
                filing_year=2024,
                period="2T",
                amount=Decimal("100.00"),
            )

    assert excinfo.value.translated_message == "application.calculations.iva_compensation.errors.seed_conflict"
    assert excinfo.value.context == {"filing_year": 2024, "period": "2T", "existing_status": "seeded"}


def test_cli_seed_verb_refuses_without_confirm(tmp_path: Path) -> None:
    """Seed verb requires --confirm; without it, exit code is non-zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        result = _RUNNER.invoke(
            app,
            ["app", "modelo", "iva-wallet", "seed", "--filing-year", "2024", "--period", "4T", "--amount", "1200.00"],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0


def test_cli_seed_verb_happy_path(tmp_path: Path) -> None:
    """Seed verb with --confirm creates the state and emits the correct fields."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        result = _RUNNER.invoke(
            app,
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
        stored = repo.load_period(2024, "4T")

    assert result.exit_code == 0, result.output
    payload = _unwrap_envelope(json.loads(result.output))
    # IvaWalletSeedResult.operation default is the underscore form; the
    # tab-separated text-mode emit uses the hyphen form for operator legibility.
    assert payload["operation"] == "modelo.iva_wallet.seed"
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
        first_result = _RUNNER.invoke(
            app,
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
        result = _RUNNER.invoke(
            app,
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


# Anti-tautology proof: mutated applied_amount in a lot triggers model_validator
def test_carry_forward_lot_rejects_unbalanced_amounts_anti_tautology() -> None:
    """Verifies that the roundtrip contract enforces amount balance."""
    with pytest.raises(ValidationError, match="must equal generated_amount"):
        IvaCompensationCarryForwardLot(
            taxpayer_nif=_NIF,
            source_filing_year=2024,
            source_period="1T",
            generated_amount=Decimal("1200.00"),
            applied_amount=Decimal("800.00"),  # should be 800, remaining should be 400
            remaining_amount=Decimal("500.00"),  # but 800+500 != 1200 → validator fires
            age_years=2,
            expiry_review_state=IvaCompensationExpiryReviewState.ACTIVE,
            source_observation_key="303:2024:1T:EXP",
        )


# ---------------------------------------------------------------------------
# M303 wallet-seed error guidance regression (Pedro round-18 finding)
# ---------------------------------------------------------------------------
#
# Fresh-profile M303 calculate with a caller compensation-binding override
# must surface the iva-wallet seed verb — NOT the obsolete --mode modelo flag.
# After seeding the same calculate must succeed.
# ---------------------------------------------------------------------------

_GUIDANCE_PROFILE = "guidance-test"
_GUIDANCE_NIF = "87654321Y"


def _seed_full_autónomo_profile_for_guidance(bucket_id: str) -> None:
    """Persist a minimal autónomo profile sufficient for M303 work-unit applicability."""
    from datetime import UTC, datetime

    from ....application.user_profile import UserProfileLifecycleRepository
    from ....domain.user_profile import UserProfileFact, UserProfileRecord, UserProfileStatus

    _created_at = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    UserProfileLifecycleRepository(bucket_id=bucket_id).save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name="Test runtime profile",
            status=UserProfileStatus.ACTIVE,
            facts=(
                UserProfileFact(path="identity.name", value="Guidance Test Autónomo"),
                UserProfileFact(path="identity.tax_id", value=_GUIDANCE_NIF),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(
                    path="taxpayer_type.irpf_income_categories",
                    value="actividad_economica",
                ),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
            ),
        )
    )


def test_m303_fresh_profile_binding_override_surfaces_seed_verb_not_mode_flag(
    tmp_path: Path,
) -> None:
    """Pedro round-18 regression: compensation binding override on fresh profile names seed verb.

    A fresh profile with no persisted IVA wallet decision attempting
    ``aeat app modelo work calculate`` with a binding override for
    ``modelo-303-compensacion-pendiente-anteriores`` must:
    - exit with a non-zero exit code
    - name the iva-wallet seed verb in the error output
    - NOT reference the obsolete ``--mode modelo`` flag

    This is derived from the spec: the error message must contain the exact
    verb ``aeat app modelo iva-wallet seed`` so the operator can unblock.
    """
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_GUIDANCE_PROFILE,
    ):
        _seed_full_autónomo_profile_for_guidance(_GUIDANCE_PROFILE)
        work_unit_result = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                "303",
                "--year",
                "2024",
                "--period",
                "1T",
                "--revision",
                "2023-y-siguientes",
            ]
        )
        assert work_unit_result.exit_code == 0, work_unit_result.output
        import json as _json

        raw = _json.loads(work_unit_result.output)
        if "schema_version" in raw and "result" in raw:
            work_unit_id = raw["result"]["work_unit_id"]
        else:
            work_unit_id = raw["work_unit_id"]

        result = invoke_cached_cli(
            [
                "app",
                "modelo",
                "work",
                "calculate",
                work_unit_id,
                "--binding",
                "modelo-303-compensacion-pendiente-anteriores=500",
            ],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0, "Expected non-zero exit when compensation binding is supplied without a seeded wallet"
    assert "iva-wallet seed" in result.output, f"Error output must name the iva-wallet seed verb; got:\n{result.output}"
    assert "--mode" not in result.output, (
        f"Error output must NOT reference the obsolete --mode flag; got:\n{result.output}"
    )


def test_m303_fresh_profile_calculate_without_binding_override_does_not_raise_wallet_error(
    tmp_path: Path,
) -> None:
    """Anti-tautology: fresh-profile M303 calculate without binding override does not error on wallet.

    When no compensation binding is supplied by the caller, M303 calculate
    proceeds with zero prior compensation (a valid first-filing state).
    The wallet-seed guidance error must NOT appear without provocation.
    This proves the error is not spuriously emitted on every M303 calculate.
    """
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_GUIDANCE_PROFILE,
    ):
        _seed_full_autónomo_profile_for_guidance(_GUIDANCE_PROFILE)

        work_unit_result = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                "303",
                "--year",
                "2024",
                "--period",
                "1T",
                "--revision",
                "2023-y-siguientes",
            ]
        )
        assert work_unit_result.exit_code == 0, work_unit_result.output
        import json as _json

        raw = _json.loads(work_unit_result.output)
        if "schema_version" in raw and "result" in raw:
            work_unit_id = raw["result"]["work_unit_id"]
        else:
            work_unit_id = raw["work_unit_id"]

        # Calculate WITHOUT a compensation binding override — fresh profile
        # with no prior filings should succeed with zero compensation.
        result = invoke_cached_cli(
            ["app", "modelo", "work", "calculate", work_unit_id],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    # The wallet-seed error must not appear when no binding override is supplied.
    assert "iva_wallet_not_seeded" not in result.output, (
        "Wallet-seed error must not fire when no compensation binding is supplied"
    )
    # An empty-ledger M303 may refuse for other reasons (e.g. missing bindings),
    # but it must never emit the seed-verb guidance without a compensation binding conflict.
    assert "iva-wallet seed" not in result.output or result.exit_code == 0, (
        "Wallet-seed guidance must not appear without a compensation binding conflict; "
        f"got exit_code={result.exit_code}:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# seed help text — legal grounding phrase coverage
# ---------------------------------------------------------------------------


def test_cli_seed_help_text_contains_liva_art_99_legal_grounding(tmp_path: Path) -> None:
    """The iva-wallet seed --help output must cite LIVA art. 99.5.

    The help text distinguishes --amount 0 (true first-period, legally certain
    under LIVA art. 99.5) from --amount X (carry-in from prior filings).
    This test asserts the legal grounding phrase survives locale rendering
    so operators can verify the basis for non-blocking zero treatment.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="help-text-test"):
        result = _RUNNER.invoke(
            app,
            ["app", "modelo", "iva-wallet", "seed", "--help"],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code == 0, result.output
    help_text = result.output
    assert "99.5" in help_text, "seed --help must cite LIVA art. 99.5 for the zero-first-period legal grounding"
    assert "Ley 37/1992" in help_text or "LIVA" in help_text, (
        "seed --help must reference the legal source (Ley 37/1992 or LIVA)"
    )


# ---------------------------------------------------------------------------
# contract: iva-wallet correct verb (guarded correction path, W04.P10 / D7)
# ---------------------------------------------------------------------------


def test_cli_correct_verb_requires_confirm(tmp_path: Path) -> None:
    """Correct verb requires --confirm; without it, exit code is non-zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        seed_iva_compensation_period(taxpayer_nif=_NIF, filing_year=2024, period="4T", amount=Decimal("500.00"))
        result = _RUNNER.invoke(
            app,
            [
                "app",
                "modelo",
                "iva-wallet",
                "correct",
                "--filing-year",
                "2024",
                "--period",
                "4T",
                "--amount",
                "1200.00",
                "--reason",
                "fix",
            ],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0, result.output


def test_cli_correct_verb_happy_path_overwrites_seed(tmp_path: Path) -> None:
    """Correct verb with --confirm overwrites the seeded amount and reports it."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        seed_iva_compensation_period(taxpayer_nif=_NIF, filing_year=2024, period="4T", amount=Decimal("500.00"))
        result = _RUNNER.invoke(
            app,
            [
                "--format",
                "json",
                "app",
                "modelo",
                "iva-wallet",
                "correct",
                "--filing-year",
                "2024",
                "--period",
                "4T",
                "--amount",
                "1200.50",
                "--reason",
                "typo in opening balance",
                "--confirm",
            ],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

        stored = IvaCompensationHistoryRepository().load_period(2024, "4T")

    assert result.exit_code == 0, result.output
    payload = _unwrap_envelope(json.loads(result.output))
    assert payload["operation"] == "modelo.iva_wallet.correct"
    assert payload["amount"] == "1200.50"
    assert payload["previous_amount"] == "500.00"
    assert payload["reason"] == "typo in opening balance"
    assert stored is not None
    assert stored.available_end_amount == Decimal("1200.50")


def test_cli_correct_verb_refuses_when_no_record(tmp_path: Path) -> None:
    """Correct verb refuses a period that has no seeded record (seed first)."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="seed-test"):
        _store_profile_with_nif(_NIF)
        result = _RUNNER.invoke(
            app,
            [
                "app",
                "modelo",
                "iva-wallet",
                "correct",
                "--filing-year",
                "2024",
                "--period",
                "4T",
                "--amount",
                "1200.50",
                "--reason",
                "no record",
                "--confirm",
            ],
            env={"AEAT_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0, result.output
    assert "seed" in result.output.lower()
