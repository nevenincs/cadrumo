"""M303 IVA wallet guidance regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.resources import resources
from ....tests.cli_envelope import require_schema_envelope
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_runtime_profile
from ._iva_wallet_inspector_support import (
    _GUIDANCE_PROFILE,
    _seed_full_autonomo_profile_for_guidance,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _m303_revision_id(*, filing_year: int, period: str) -> str:
    return str(resources().modelos.authority.snapshot("303", filing_year=filing_year, period=period).revision.id)


def test_m303_fresh_profile_binding_override_is_a_terminal_typed_refusal(
    tmp_path: Path,
) -> None:
    """No seed inference is made when a compensation record is absent."""
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_GUIDANCE_PROFILE,
    ):
        _seed_full_autonomo_profile_for_guidance(_GUIDANCE_PROFILE)
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
                "2T",
                "--revision",
                _m303_revision_id(filing_year=2024, period="2T"),
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
                "--binding",
                "modelo-303-compensacion-pendiente-anteriores=500",
            ],
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0, "Expected non-zero exit when compensation binding is supplied without a seeded wallet"
    assert "iva-wallet seed" not in result.output, f"Refusal must not infer a seed command; got:\n{result.output}"


def test_m303_in_scope_missing_wallet_surfaces_override_verb_not_seed(
    tmp_path: Path,
) -> None:
    """In-scope missing wallet/local authority is unblocked with explicit override, not seed."""
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_GUIDANCE_PROFILE,
    ):
        _seed_full_autonomo_profile_for_guidance(_GUIDANCE_PROFILE)
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
                "2T",
                "--revision",
                _m303_revision_id(filing_year=2024, period="2T"),
            ],
        )
        assert work_unit_result.exit_code == 0, work_unit_result.output
        work_unit_payload = require_schema_envelope(work_unit_result.output)
        work_unit_id = str(work_unit_payload["work_unit_id"])

        result = invoke_cached_cli(
            ["app", "modelo", "work", "calculate", work_unit_id],
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0, "Expected non-zero exit when in-scope prior IVA authority is missing"
    assert "iva-wallet override" in result.output, f"Error output must name the override verb; got:\n{result.output}"
    assert "--amount 0" in result.output, (
        f"Missing-authority guidance must make the zero override explicit:\n{result.output}"
    )
    assert "iva-wallet seed" not in result.output, (
        f"Blocked decisions must not send the operator back to seed; got:\n{result.output}"
    )


def test_m303_fresh_profile_calculate_without_binding_override_does_not_raise_wallet_error(
    tmp_path: Path,
) -> None:
    """Anti-tautology: fresh-profile M303 calculate without binding override does not error on wallet."""
    with isolated_cli_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_GUIDANCE_PROFILE,
    ):
        _seed_full_autonomo_profile_for_guidance(_GUIDANCE_PROFILE)

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
                _m303_revision_id(filing_year=2024, period="1T"),
            ],
        )
        assert work_unit_result.exit_code == 0, work_unit_result.output
        work_unit_payload = require_schema_envelope(work_unit_result.output)
        work_unit_id = str(work_unit_payload["work_unit_id"])

        result = invoke_cached_cli(
            ["app", "modelo", "work", "calculate", work_unit_id],
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert "iva_wallet_not_seeded" not in result.output, (
        "Wallet-seed error must not fire when no compensation binding is supplied"
    )
    assert "iva-wallet seed" not in result.output or result.exit_code == 0, (
        "Wallet-seed guidance must not appear without a compensation binding conflict; "
        f"got exit_code={result.exit_code}:\n{result.output}"
    )
