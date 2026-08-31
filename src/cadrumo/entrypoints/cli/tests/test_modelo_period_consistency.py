"""Regression tests for pago-fraccionado period consistency across CLI verbs.

Drives the real ``cadrumo`` CLI against an isolated encrypted backend to
pin the period-unification contract: every pago-fraccionado clave
(``1P`` / ``2P`` / ``3P``) that ``modelo work create`` accepts must
also be accepted by ``modelo work verify`` without an
``invalid registry period`` error.

These are structure-and-wiring tests. They assert the CLI verbs do not
reject the period tokens and that the state machine progresses to the
expected stage — they do not assert calculated Decimal values.
"""

from __future__ import annotations

import pytest

from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_cli_backend as _isolated_cli_backend  # noqa: F401 - autouse fixture
from ....tests.user_profile import register_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MODELO_202_PERIODS = ("1P", "2P", "3P")


def _assert_payload_period(payload: dict[str, object], *, year: int, code: str) -> None:
    assert payload["period"] == {"filing_year": year, "code": code}


def _create_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "B12345674",
            "taxpayer_type.entity_type": "legal_entity",
            "taxpayer_type.legal_entity_form": "sl",
            "identity.name": "Operator",
            "identity.surnames": "Operator SL",
            "identity.legal_name": "Operator SL",
            "activities.description": "design",
            "taxpayer_type.incn_prior_12_months": "7500000.00",
        },
    )


def _create_202_work_unit(period: str) -> str:
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "202", "--year", "2026", "--period", period,
            "--revision", "2025-y-siguientes",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    _assert_payload_period(payload, year=2026, code=period)
    work_unit_id = STR_KEYED_MAPPING_ADAPTER.validate_python(payload)["work_unit_id"]
    assert isinstance(work_unit_id, str)
    return work_unit_id


def _calculate_202_work_unit(work_unit_id: str) -> dict[str, object]:
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
            "modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores=0",
            "--binding",
            "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior=0",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "cannot map workflow period" not in result.output
    assert "invalid registry period" not in result.output
    return STR_KEYED_MAPPING_ADAPTER.validate_python(_payload(result.output))


def test_create_calculate_status_verify_agree_on_modelo_202_pago_fraccionado_periods() -> None:
    """``work`` verbs accept and preserve every pago-fraccionado clave Modelo 202 declares.

    Before the period-unification fix, ``work verify`` rejected ``1P`` /
    ``2P`` / ``3P`` with ``cannot map workflow period`` because
    ``_registry_period_token`` in the workflow engine had no pago-fraccionado
    arm.  The fix adds that arm so the verify path shares the same
    period-token vocabulary as create and calculate.

    This is a wiring test: asserts the exit code and the absence of the
    old error message, not the calculated values.
    """
    _create_profile()
    for period in _MODELO_202_PERIODS:
        work_unit_id = _create_202_work_unit(period)

        # First calculate to produce a draft revision the verify step can inspect.
        # Supply prior-period payments as 0; this checks period-token wiring, not amounts.
        calc_payload = _calculate_202_work_unit(work_unit_id)
        calculation_revision_id = calc_payload["calculation_revision_id"]
        assert isinstance(calculation_revision_id, str)

        status_result = invoke_cached_cli(
            ["--format", "json", "app", "modelo", "work", "status", work_unit_id],
        )
        assert status_result.exit_code == 0, f"{period}: {status_result.output}"
        status_payload = _payload(status_result.output)
        _assert_payload_period(status_payload, year=2026, code=period)

        # Verify must accept the same period token without crashing. Exit code 0
        # (fully verified) or 1 (incomplete) are both acceptable; exit code 2
        # indicates a CLI/period-mapping error.
        verify_result = invoke_cached_cli(
            ["--format", "json", "app", "modelo", "work", "verify", calculation_revision_id],
        )
        assert verify_result.exit_code in (0, 1), f"{period}: {verify_result.output}"
        assert "cannot map workflow period" not in verify_result.output
        assert "invalid registry period" not in verify_result.output
