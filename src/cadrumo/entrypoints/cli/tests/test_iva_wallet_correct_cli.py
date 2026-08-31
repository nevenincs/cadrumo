"""CLI surface tests for the IVA wallet correction verb."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....application.calculations.iva_compensation_history import (
    IvaCompensationHistoryRepository,
    seed_iva_compensation_period,
)
from ....core.period import Period
from ....tests.cli_envelope import require_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_runtime_profile
from ._iva_wallet_inspector_support import _NIF, _SEED_BUCKET_ID, _store_profile_with_nif

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_cli_correct_verb_requires_confirm(tmp_path: Path) -> None:
    """Correct verb requires --confirm; without it, exit code is non-zero."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SEED_BUCKET_ID):
        _store_profile_with_nif(_NIF)
        seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            period=Period.from_year_and_code(2024, "4T"),
            amount=Decimal("500.00"),
        )
        result = invoke_cached_cli(
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
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0, result.output


def test_cli_correct_verb_happy_path_overwrites_seed(tmp_path: Path) -> None:
    """Correct verb with --confirm overwrites the seeded amount and reports it."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SEED_BUCKET_ID):
        _store_profile_with_nif(_NIF)
        seed_iva_compensation_period(
            taxpayer_nif=_NIF,
            period=Period.from_year_and_code(2024, "4T"),
            amount=Decimal("500.00"),
        )
        result = invoke_cached_cli(
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
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

        stored = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2024, "4T"))

    assert result.exit_code == 0, result.output
    payload = require_schema_envelope(result.output)
    assert payload["operation"] == "modelo.iva_wallet.correct"
    assert payload["amount"] == "1200.50"
    assert payload["previous_amount"] == "500.00"
    assert payload["reason"] == "typo in opening balance"
    assert stored is not None
    assert stored.available_end_amount == Decimal("1200.50")


def test_cli_correct_verb_refuses_when_no_record(tmp_path: Path) -> None:
    """Correct verb refuses a period that has no seeded record (seed first)."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SEED_BUCKET_ID):
        _store_profile_with_nif(_NIF)
        result = invoke_cached_cli(
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
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0, result.output
    assert "seed" in result.output.lower()
