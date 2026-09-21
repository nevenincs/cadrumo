"""Installed command-tree evidence for activity-asset operations."""

from __future__ import annotations

import pytest

from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_activity_asset_group_exposes_the_shared_operation_set() -> None:
    result = invoke_cached_cli(["app", "ledger", "actividad-asset", "--help"])

    assert result.exit_code == 0
    for token in ("create", "inspect", "correct", "forecast", "claim", "filing-handoff"):
        assert token in result.output


def test_activity_asset_inspect_dispatches_to_profile_resolution() -> None:
    result = invoke_cached_cli(["app", "ledger", "actividad-asset", "inspect", "missing-asset"])

    assert result.exit_code != 0
    assert "No hay un perfil activo" in result.output


def test_activity_asset_forecast_refuses_a_caller_authored_rate_envelope() -> None:
    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "actividad-asset",
            "forecast",
            "asset-1",
            "--authority-json",
            '{"annual_rate":"1"}',
            "--covered-from",
            "2025-01-01",
            "--covered-until",
            "2026-01-01",
        ],
    )

    assert result.exit_code != 0
    assert "--authority-json" in result.output
