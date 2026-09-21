"""M303 IVA wallet guidance regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....tests.cli_envelope import require_schema_envelope
from ._iva_wallet_inspector_support import (
    _GUIDANCE_PROFILE,
    _seed_full_autonomo_profile_for_guidance,
)
from ._m303_ordinary_cli_support import admit_ordinary_m303_secure_evidence
from .cli_runner import invoke_cached_cli

__all__ = ["_isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]


def test_m303_fresh_profile_binding_override_is_a_terminal_typed_refusal(
    tmp_path: Path,
) -> None:
    """No seed inference is made when a compensation record is absent."""
    with isolated_runtime_profile(
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
                "2025",
                "--period",
                "2T",
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
                *admit_ordinary_m303_secure_evidence(period="2T").calculate_options(),
            ],
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0, "Expected non-zero exit when compensation binding is supplied without a seeded wallet"
    assert "iva-wallet seed" not in result.output, f"Refusal must not infer a seed command; got:\n{result.output}"
    assert 'action.failed_condition_id: "modelo.work.calculate.iva_wallet.ready"' in result.output, result.output
    assert "action.action: null" in result.output, result.output
    assert 'action.no_recovery_outcome: "operator_decision"' in result.output, result.output
    assert "NOTICE:" not in result.output, result.output


def test_m303_in_scope_missing_wallet_surfaces_typed_terminal_refusal(
    tmp_path: Path,
) -> None:
    """In-scope missing authority preserves its terminal operator-decision verdict."""
    filing_year = 2025
    period_code = "2T"
    with isolated_runtime_profile(
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
                "app",
                "modelo",
                "work",
                "calculate",
                work_unit_id,
                *admit_ordinary_m303_secure_evidence(period="2T").calculate_options(),
            ],
            env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
        )

    assert result.exit_code != 0, "Expected non-zero exit when in-scope prior IVA authority is missing"
    assert 'action.failed_condition_id: "modelo.work.calculate.iva_wallet.ready"' in result.output, result.output
    assert "action.action: null" in result.output, result.output
    assert 'action.no_recovery_outcome: "operator_decision"' in result.output, result.output
    assert "iva-wallet override" not in result.output, (
        f"A recovery command needs taxpayer-supplied evidence and cannot be inferred:\n{result.output}"
    )
    assert "--amount 0" not in result.output, (
        f"Missing authority cannot be replaced with an invented zero carry:\n{result.output}"
    )
    assert "iva-wallet seed" not in result.output, (
        f"Blocked decisions must not send the operator back to seed; got:\n{result.output}"
    )


def test_m303_fresh_profile_calculate_without_binding_override_does_not_raise_wallet_error(
    tmp_path: Path,
) -> None:
    """Anti-tautology: fresh-profile M303 calculate without binding override does not error on wallet."""
    with isolated_runtime_profile(
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
                "2025",
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
                *admit_ordinary_m303_secure_evidence().calculate_options(),
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
