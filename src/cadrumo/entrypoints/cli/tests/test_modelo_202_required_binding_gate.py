"""CLI regression for Modelo 202 missing required-binding hard-stop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ._modelo_empty_profile_fixture import _isolated_backend
from ._profile_cli_support import seed_profile

__all__ = ["_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_M202_INCN_BINDING = "modelo-202-2025-y-siguientes-incn-prior-12-months"
_M202_CUOTA_BASE_BINDING = "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior"
_M202_PRIOR_PAYMENTS_BINDING = "modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores"
_M202_2023_2024_PRIOR_PAYMENTS_BINDING = "modelo-202-2023-2024-pagos-fraccionados-anteriores"
_MISSING_M202_BINDINGS = {
    _M202_INCN_BINDING,
    _M202_CUOTA_BASE_BINDING,
}


# The natural-person placeholders the shared seeding door applies are blanked
# for a legal entity, which has no business carrying them.
_LEGAL_ENTITY_FACTS = {
    "taxpayer_type.entity_type": "legal_entity",
    "taxpayer_type.legal_entity_form": "sl",
    "identity.tax_id": "B12345674",
    "identity.name": "",
    "identity.surnames": "",
    "taxpayer_type.irpf_income_categories": "",
    "irpf.estimation_regime": "",
}


def _create_laura_taller_sol_profile() -> None:
    seed_profile(
        "laura-taller-sol",
        **_LEGAL_ENTITY_FACTS,
        **{
            "identity.legal_name": "Taller Sol SL",
            "activities.description": "taller mecanico",
        },
    )


def _create_lorentz_irene_profile() -> None:
    seed_profile(
        "lorentz-irene",
        **_LEGAL_ENTITY_FACTS,
        **{
            "identity.legal_name": "Lorentz Irene SL",
            "activities.description": "IVA corporate run",
            "taxpayer_type.incn_prior_12_months": "500000",
            "censo.activity_start_date": "2024-01-15",
            "tax_residence.ccaa": "madrid",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )


def test_laura_m202_not_ready_refuses_calculate_and_no_zero_artifact_is_reachable(tmp_path: Path) -> None:
    """Laura/Taller Sol cannot turn a not-ready M202 state into a zero draft/export/file."""
    _create_laura_taller_sol_profile()

    readiness = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "readiness",
            "--modelo",
            "202",
            "--revision-id",
            "2025-y-siguientes",
            "--year",
            "2025",
            "--period",
            "1P",
        ],
    )
    assert readiness.exit_code == 0, readiness.output
    readiness_payload = _payload(readiness.output)
    assert readiness_payload["ready"] is False
    assert readiness_payload["binding_ready"] is False
    assert {row["binding_id"] for row in readiness_payload["missing_bindings"]} == _MISSING_M202_BINDINGS

    created = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
        ],
    )
    assert created.exit_code == 0, created.output
    work_unit_id = _payload(created.output)["work_unit_id"]

    calculated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
        ],
    )
    assert calculated.exit_code != 0, calculated.output
    error_payload = json.loads(calculated.output)
    error = error_payload["error"]
    assert error["code"] == "REFUSED_MODELO_REQUIRED_BINDINGS_MISSING"
    # The error-envelope context funnel renders collection values as a
    # comma-joined string (dict[str, str] contract), so the missing-binding
    # ids arrive as one string and are split back to compare the set.
    assert {
        binding_id.strip() for binding_id in error["context"]["missing_bindings"].split(",")
    } == _MISSING_M202_BINDINGS
    assert "saved" not in calculated.output
    assert "Traceback" not in calculated.output

    status = invoke_cached_cli(["--format", "json", "app", "modelo", "work", "status", work_unit_id])
    assert status.exit_code == 0, status.output
    status_payload = _payload(status.output)
    assert status_payload["current_calculation_revision_id"] is None
    assert status_payload["filed_calculation_revision_id"] is None

    verify = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "verify",
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
        ],
    )
    assert verify.exit_code != 0, verify.output
    assert "granted_verificado_completo" not in verify.output

    filed = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "file",
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
        ],
    )
    assert filed.exit_code != 0, filed.output
    assert "presentado" not in filed.output

    export_path = tmp_path / "modelo-202-2025-1P.txt"
    exported = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "export",
            "--modelo",
            "202",
            "--year",
            "2025",
            "--period",
            "1P",
            "--output",
            str(export_path),
        ],
    )
    assert exported.exit_code != 0, exported.output
    assert export_path.exists() is False


def test_lorentz_m202_2024_1p_calculates_with_first_period_prior_payments_zero() -> None:
    _create_lorentz_irene_profile()

    created = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "202",
            "--year",
            "2024",
            "--period",
            "1P",
            "--revision",
            "2023-2024",
        ],
    )
    assert created.exit_code == 0, created.output

    calculated = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "calculate",
            "--modelo",
            "202",
            "--year",
            "2024",
            "--period",
            "1P",
            "--revision",
            "2023-2024",
        ],
    )
    assert calculated.exit_code == 0, calculated.output
    payload = _payload(calculated.output)
    assert payload["binding_overrides"][_M202_2023_2024_PRIOR_PAYMENTS_BINDING] == "0"
    assert payload["casilla_values"]["30"] == "0"
    assert payload["relation_overrides"] == {}
