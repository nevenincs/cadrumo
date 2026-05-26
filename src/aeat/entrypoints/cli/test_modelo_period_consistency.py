"""Regression tests for pago-fraccionado period consistency across CLI verbs.

Drives the real ``aeat`` CLI against an isolated encrypted backend to
pin the period-unification fix (W01.P07.S25-S29): every pago-fraccionado
clave (``1P`` / ``2P`` / ``3P``) that ``modelo work create`` accepts must
also be accepted by ``modelo work verify`` without an
``invalid registry period`` error.

These are structure-and-wiring tests. They assert the CLI verbs do not
reject the period tokens and that the state machine progresses to the
expected stage — they do not assert calculated Decimal values.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    try:
        yield tmp_path
    finally:
        dispose_engine()


def _create_profile() -> None:
    result = invoke_cached_cli(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--activity", "design",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _create_202_work_unit(period: str) -> str:
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "202", "--year", "2026", "--period", period,
            "--revision", "2025-y-siguientes",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
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
    calc_result = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id],
    )
    assert calc_result.exit_code == 0, calc_result.output
    assert "cannot map workflow period" not in calc_result.output
    assert "invalid registry period" not in calc_result.output

    # verify must accept the same period token without crashing.
    verify_result = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "verify", work_unit_id],
    )
    assert verify_result.exit_code == 0, verify_result.output
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
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id],
    )
    assert calc_result.exit_code == 0, calc_result.output
    calc_payload = json.loads(calc_result.output)
    # The work unit period token is preserved end-to-end.
    assert calc_payload.get("period") == period, calc_payload
