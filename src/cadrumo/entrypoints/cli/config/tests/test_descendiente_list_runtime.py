"""Installed descendant-list reads from one authorized, complete profile view."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....tests.cli_envelope import unwrap_schema_envelope
from ...tests.cli_runner import invoke_cached_cli
from .isolated_storage_fixture import CREDENTIAL_INPUT, native_profile_view_server
from .isolated_storage_fixture import live_cli_profile as live_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.windows_only]


def test_registered_profile_lists_declared_rows_in_order_through_native_runtime(
    live_cli_profile: None, tmp_path: Path
) -> None:
    """The protected view round-trips real rows without a local read fallback."""
    with native_profile_view_server(tmp_path / "cadrumo-storage"):
        added = invoke_cached_cli(
            [
                "--format",
                "json",
                "--profile",
                "Editor",
                "--profile-secrets-stdin",
                "config",
                "profile",
                "descendiente",
                "add",
                "--descendiente",
                "NACIMIENTO=2015-04-01",
                "--descendiente",
                "NACIMIENTO=2021-04-15,GASTOS_GUARDERIA_MENSUAL=1-4:150;5-7:200,MESES_TRABAJO=1-12,SEGUNDO_CICLO_INFANTIL_INICIO_MES=8",
            ],
            input=json.dumps({"profile_passphrase": CREDENTIAL_INPUT}),
        )
        assert added.exit_code == 0, added.output
        assert unwrap_schema_envelope(added.output)["total"] == 2

        listed = invoke_cached_cli(
            [
                "--format",
                "json",
                "--profile",
                "Editor",
                "--profile-secrets-stdin",
                "config",
                "profile",
                "descendiente",
                "list",
            ],
            input=json.dumps({"profile_passphrase": CREDENTIAL_INPUT}),
        )
    assert listed.exit_code == 0, listed.output
    assert CREDENTIAL_INPUT not in listed.output
    result = unwrap_schema_envelope(listed.output)
    assert result["profile"] == "Editor"
    assert result["total"] == 2
    rows = result["descendientes"]
    assert [row["birth_date"] for row in rows] == ["2015-04-01", "2021-04-15"]
    assert rows[1]["segundo_ciclo_infantil_inicio_mes"] == 8
    assert [(month["month"], month["amount_euros"]) for month in rows[1]["gastos_guarderia_mensuales"]] == [
        (1, 150),
        (2, 150),
        (3, 150),
        (4, 150),
        (5, 200),
        (6, 200),
        (7, 200),
    ]
