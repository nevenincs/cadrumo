"""End-to-end CLI tests for the ``aeat config check`` preflight health rows.

Verifies that the workstation doctor surfaces the per-auth-provider certificate /
Cl@ve Móvil health, the secure-storage / bundled-corpus / configuration
preflight, and the registry referential-integrity row through the
typed ``preflight`` channel on the JSON envelope — and that a red preflight row
is reported for operator visibility without crashing the command or leaking into
the capability/dependency ``issues`` contract that owns the exit code. Real CLI
surface, real persistence in an isolated storage root, no mocks.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from .....application.preflight import HealthSeverity
from .....core.config import override_settings
from .....tests.cli_runner import invoke_cached_cli
from .....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path / "storage", cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        yield


def _config_check_payload() -> dict[str, Any]:
    result = invoke_cached_cli(["--format", "json", "config", "check"])
    # A red preflight row (e.g. the registry referential-integrity row) must not
    # crash the doctor: the exit is governed by the capability/dependency
    # contract (0 when clean, 2 on a capability gap), never a bare crash (1).
    assert result.exit_code in (0, 2), result.output
    return json.loads(result.output)["result"]


def test_config_check_emits_typed_preflight_rows() -> None:
    """The doctor reports one typed preflight row per health dimension."""
    payload = _config_check_payload()
    rows = payload["preflight"]
    assert isinstance(rows, list) and rows, "config check must emit preflight rows"
    by_id = {row["check"]: row for row in rows}
    assert {
        "auth-provider:certificate",
        "auth-provider:clave_movil",
        "storage:local-root",
        "corpus:normatives",
        "corpus:manuals",
        "env:configuration",
        "registry:referential-integrity",
    } <= set(by_id)
    for row in rows:
        assert set(row) == {"check", "healthy", "severity", "detail", "remediation"}
        assert isinstance(row["healthy"], bool)
        assert row["severity"] in {"ok", "warn", "error"}


def test_preflight_rows_do_not_leak_into_capability_issues() -> None:
    """A red preflight row is reported but never smuggled into the ``issues`` contract."""
    payload = _config_check_payload()
    issues = payload["issues"]
    # ``issues`` is the capability/dependency gap channel; preflight rows carry
    # their own severity and must not appear as capability issues.
    assert all("registry:" not in str(issue) and "storage:" not in str(issue) for issue in issues)


def test_config_check_flags_missing_corpus_as_red_preflight_row(tmp_path: Path) -> None:
    """A missing bundled corpus surfaces an error preflight row end to end."""
    with override_settings(aeat_normatives_root=tmp_path / "absent-corpus"):
        payload = _config_check_payload()
    by_id = {row["check"]: row for row in payload["preflight"]}
    normatives = by_id["corpus:normatives"]
    assert normatives["healthy"] is False
    assert normatives["severity"] == "error"
    assert normatives["remediation"]


def test_config_check_payload_rows_refuse_empty_ids_and_unknown_severity() -> None:
    """The doctor transport preserves canonical dependency and preflight identifiers."""

    from .._check_payloads import CheckDependencyPayload, CheckPreflightPayload

    with pytest.raises(ValidationError):
        CheckDependencyPayload(service="", available=True)
    with pytest.raises(ValidationError):
        CheckPreflightPayload(check="", healthy=True, severity=HealthSeverity.OK)
    with pytest.raises(ValidationError):
        CheckPreflightPayload(check="storage:local-root", healthy=True, severity="bogus")
