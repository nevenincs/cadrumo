"""M303 IVA wallet guidance regressions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.entrypoints.cli.tests.ordinary_m303_scenarios import joint_return_options
from cadrumo.tests.cli_envelope import require_schema_envelope

from .cli_runner import invoke_cached_cli
from .iva_wallet_inspector_support import (
    seed_full_autonomo_profile_for_guidance,
)
from .runtime_profile_backend import runtime_cli_profile

__all__ = ["isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

# A supported exercise after the seeded profile's activity start, so every quarter has a prior one.
_FILING_YEAR = filing_year_envelope().horizon


def test_m303_fresh_profile_binding_override_is_a_terminal_typed_refusal(
    tmp_path: Path,
) -> None:
    """A supplied binding with no wallet record is refused, naming the opening-balance command and inferring no amount."""
    with runtime_cli_profile(tmp_path=tmp_path) as profile:
        seed_full_autonomo_profile_for_guidance(profile.bucket_id)
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
                str(_FILING_YEAR),
                "--period",
                "2T",
            ],
        )
        assert work_unit_result.exit_code == 0, work_unit_result.output
        work_unit_payload = require_schema_envelope(work_unit_result.output)
        work_unit_id = str(work_unit_payload["work_unit_id"])

        result = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "calculate",
                work_unit_id,
                "--binding",
                "modelo-303-compensacion-pendiente-anteriores=500",
                *joint_return_options(),
            ],
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0, "Expected non-zero exit when compensation binding is supplied without a seeded wallet"
    _assert_names_the_opening_balance_command(result.output, filing_year=_FILING_YEAR, period_code="2T")


def test_m303_in_scope_missing_wallet_surfaces_typed_terminal_refusal(
    tmp_path: Path,
) -> None:
    """In-scope missing authority is refused with the command that records the opening balance."""
    filing_year = _FILING_YEAR
    period_code = "2T"
    with runtime_cli_profile(tmp_path=tmp_path) as profile:
        seed_full_autonomo_profile_for_guidance(profile.bucket_id)
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
                str(filing_year),
                "--period",
                period_code,
            ],
        )
        assert work_unit_result.exit_code == 0, work_unit_result.output
        work_unit_payload = require_schema_envelope(work_unit_result.output)
        work_unit_id = str(work_unit_payload["work_unit_id"])

        result = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "calculate",
                work_unit_id,
                *joint_return_options(),
            ],
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0, "Expected non-zero exit when in-scope prior IVA authority is missing"
    _assert_names_the_opening_balance_command(result.output, filing_year=filing_year, period_code=period_code)


def test_m303_fresh_profile_calculate_without_binding_override_does_not_raise_wallet_error(
    tmp_path: Path,
) -> None:
    """Anti-tautology: fresh-profile M303 calculate without binding override does not error on wallet."""
    with runtime_cli_profile(tmp_path=tmp_path) as profile:
        seed_full_autonomo_profile_for_guidance(profile.bucket_id)

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
                str(_FILING_YEAR),
                "--period",
                "1T",
            ],
        )
        assert work_unit_result.exit_code == 0, work_unit_result.output
        work_unit_payload = require_schema_envelope(work_unit_result.output)
        work_unit_id = str(work_unit_payload["work_unit_id"])

        result = invoke_cached_cli(
            [
                "app",
                "modelo",
                "work",
                "calculate",
                work_unit_id,
                *joint_return_options(),
            ],
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert "iva_wallet_not_seeded" not in result.output, (
        "Wallet-seed error must not fire when no compensation binding is supplied"
    )
    assert "iva-wallet seed" not in result.output or result.exit_code == 0, (
        "Wallet-seed guidance must not appear without a compensation binding conflict; "
        f"got exit_code={result.exit_code}:\n{result.output}"
    )


def _assert_names_the_opening_balance_command(output: str, *, filing_year: int, period_code: str) -> None:
    """Require the refusal envelope to serve the command that records the period's opening balance."""
    error = json.loads(output)["error"]
    action = error["action"]
    assert action["failed_condition_id"] == "modelo.work.calculate.iva_wallet.ready", output
    assert action["action"] is not None, f"the wallet refusal names no action: {output}"
    assert action["action"]["action_id"] == "operator.modelo.iva_wallet.seed", output
    assert action["action"]["target_command_key"] == "modelo.iva_wallet.seed", output
    assert action["action"]["cli_path"] == ["aeat", "app", "modelo", "iva-wallet", "seed"], output
    assert action["conditionality"] == "requires_arguments", output
    assert action["no_recovery_outcome"] is None, output
    assert action["missing_argument_names"] == ["amount"], output
    bound = {
        item["argument_name"]: item["value"] for item in action["argument_bindings"] if item["status"] == "resolved"
    }
    assert bound == {"filing_year": filing_year, "period": period_code}, output
