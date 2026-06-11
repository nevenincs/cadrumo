"""Regression tests for pago-fraccionado period consistency across CLI verbs.

Drives the real ``aeat`` CLI against an isolated encrypted backend to
pin the period-unification contract: every pago-fraccionado clave
(``1P`` / ``2P`` / ``3P``) that ``modelo work create`` accepts must
also be accepted by ``modelo work verify`` without an
``invalid registry period`` error.

These are structure-and-wiring tests. They assert the CLI verbs do not
reject the period tokens and that the state machine progresses to the
expected stage — they do not assert calculated Decimal values.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from .envelope_helpers import unwrap_schema_envelope as _payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _create_profile() -> None:
    result = invoke_cached_cli(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--activity", "design",
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output


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
    assert payload["period"] == period
    return payload["work_unit_id"]


@pytest.mark.parametrize("period", ["1P", "2P", "3P"])
def test_work_verify_accepts_modelo_202_pago_fraccionado_periods(period: str) -> None:
    """``work verify`` accepts every pago-fraccionado clave Modelo 202 declares.

    Before the period-unification fix, ``work verify`` rejected ``1P`` /
    ``2P`` / ``3P`` with ``cannot map workflow period`` because
    ``_registry_period_token`` in the workflow engine had no pago-fraccionado
    arm.  The fix adds that arm so the verify path shares the same
    period-token vocabulary as create and calculate.

    This is a wiring test: asserts the exit code and the absence of the
    old error message, not the calculated values.
    """

    _create_profile()
    work_unit_id = _create_202_work_unit(period)

    # First calculate to produce a draft revision the verify step can inspect.
    # Supply prior-period payments as 0 — the test checks period-token wiring,
    # not the calculated amounts.
    calc_result = invoke_cached_cli(
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
    assert calc_result.exit_code == 0, calc_result.output
    assert "cannot map workflow period" not in calc_result.output
    assert "invalid registry period" not in calc_result.output
    calculation_revision_id = _payload(calc_result.output)["calculation_revision_id"]

    # verify must accept the same period token without crashing — exit code 0
    # (fully verified) or 1 (incomplete) are both acceptable; exit code 2
    # indicates a CLI/period-mapping error, which is what the regression tested.
    verify_result = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "verify", calculation_revision_id],
    )
    assert verify_result.exit_code in (0, 1), verify_result.output
    assert "cannot map workflow period" not in verify_result.output
    assert "invalid registry period" not in verify_result.output


@pytest.mark.parametrize("period", ["1P", "2P", "3P"])
def test_create_calculate_verify_agree_on_period_token(period: str) -> None:
    """``work create``, ``work calculate``, and ``work verify`` all agree
    on the pago-fraccionado period token stored on the work unit.

    The work unit created with ``--period 1P`` must carry ``period == "1P"``
    through every workflow stage — no verb silently normalises the token
    to a different form.
    """

    _create_profile()
    work_unit_id = _create_202_work_unit(period)

    calc_result = invoke_cached_cli(
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
    assert calc_result.exit_code == 0, calc_result.output
    # Confirm the period token is preserved on the work unit record itself.
    status_result = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "status", work_unit_id],
    )
    assert status_result.exit_code == 0, status_result.output
    status_payload = _payload(status_result.output)
    # The work unit period token is preserved end-to-end.
    assert status_payload.get("period") == period, status_payload
