"""Unit tests for the pure helpers in :mod:`aeat.cli.doctor`.

The orchestrator and individual check functions are exercised against
real APIs in the live smoke suite. Here we cover only the deterministic
helpers — ADC scope parsing, well-known path resolution, scope display,
and the Row/State primitives.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ..config import Settings
from .doctor import (
    REQUIRED_ADC_SCOPES,
    Row,
    State,
    adc_scopes_from_file,
    adc_well_known_path,
    check_auth_provider_path,
    check_live_access_gate,
    render_table,
    short_scope,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


class TestAdcWellKnownPath:
    """Behaviour of ``adc_well_known_path``."""

    def test_uses_cloudsdk_config_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path))
        assert adc_well_known_path() == tmp_path / "application_default_credentials.json"

    def test_windows_default_uses_appdata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLOUDSDK_CONFIG", raising=False)
        if sys.platform != "win32":
            pytest.skip("windows-only default")
        monkeypatch.setenv("APPDATA", "C:/fake-appdata")
        result = adc_well_known_path()
        assert "gcloud" in result.parts
        assert result.name == "application_default_credentials.json"

    def test_unix_default_uses_home_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLOUDSDK_CONFIG", raising=False)
        if sys.platform == "win32":
            pytest.skip("unix-only default")
        result = adc_well_known_path()
        assert ".config" in result.parts
        assert "gcloud" in result.parts


class TestAdcScopesFromFile:
    """Behaviour of ``adc_scopes_from_file``."""

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert adc_scopes_from_file(tmp_path / "nope.json") == []

    def test_unparseable_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("not json", encoding="utf-8")
        assert adc_scopes_from_file(path) == []

    def test_top_level_scopes_field(self, tmp_path: Path) -> None:
        path = tmp_path / "adc.json"
        path.write_text(
            json.dumps(
                {
                    "type": "authorized_user",
                    "scopes": [
                        "https://www.googleapis.com/auth/drive",
                        "https://www.googleapis.com/auth/spreadsheets",
                        "https://www.googleapis.com/auth/drive",  # dedup
                    ],
                }
            ),
            encoding="utf-8",
        )
        assert adc_scopes_from_file(path) == sorted(
            {
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets",
            }
        )

    def test_no_scopes_field_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "adc.json"
        path.write_text(json.dumps({"type": "authorized_user"}), encoding="utf-8")
        assert adc_scopes_from_file(path) == []


class TestShortScope:
    """Behaviour of ``short_scope``."""

    def test_full_uri(self) -> None:
        assert short_scope("https://www.googleapis.com/auth/drive") == "drive"

    def test_already_short(self) -> None:
        assert short_scope("openid") == "openid"


class TestRequiredScopes:
    """The required ADC scope set must include every Workspace surface."""

    def test_includes_drive(self) -> None:
        assert "https://www.googleapis.com/auth/drive" in REQUIRED_ADC_SCOPES

    def test_includes_sheets(self) -> None:
        assert "https://www.googleapis.com/auth/spreadsheets" in REQUIRED_ADC_SCOPES

    def test_includes_docs(self) -> None:
        assert "https://www.googleapis.com/auth/documents" in REQUIRED_ADC_SCOPES

    def test_includes_cloud_platform(self) -> None:
        assert "https://www.googleapis.com/auth/cloud-platform" in REQUIRED_ADC_SCOPES


class TestRenderTable:
    """``render_table`` must produce a non-empty table for at least one row."""

    def test_renders_with_one_row(self) -> None:
        table = render_table(
            [
                Row(section="env file", required=True, state=State.OK, detail="env/.env"),
            ]
        )
        # Table object truthiness is hard to assert, so we go on column count.
        assert len(table.columns) == 4

    def test_renders_with_mixed_states(self) -> None:
        rows = [
            Row(section="a", required=True, state=State.OK, detail="ok"),
            Row(section="b", required=True, state=State.MISSING, detail="bad"),
            Row(section="c", required=False, state=State.SKIP, detail="skip"),
            Row(section="d", required=False, state=State.WARN, detail="warn"),
        ]
        table = render_table(rows)
        assert len(table.columns) == 4


class TestLiveAccessGateRow:
    """Behaviour of ``check_live_access_gate``."""

    def test_reports_enabled_reads(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "1")
        monkeypatch.delenv("AEAT_LIVE_SUBMIT_ENABLED", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        row = check_live_access_gate(Settings())
        assert row.section == "live access gate"
        assert row.state == State.OK
        assert "ENABLED" in row.detail
        assert "unset" in row.detail

    def test_reports_skipped_when_reads_not_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AEAT_LIVE_TESTS_ENABLED", raising=False)
        monkeypatch.delenv("AEAT_LIVE_SUBMIT_ENABLED", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        row = check_live_access_gate(Settings())
        assert row.state == State.SKIP
        assert "skipped" in row.detail

    def test_warns_when_submit_var_is_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "1")
        monkeypatch.setenv("AEAT_LIVE_SUBMIT_ENABLED", "true")
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        row = check_live_access_gate(Settings())
        assert row.state == State.WARN
        assert "charter #116" in row.detail


class TestAuthProviderPathRow:
    """Behaviour of ``check_auth_provider_path``."""

    def test_skips_when_no_provider_is_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AEAT_CERTIFICATE_PATH", raising=False)
        monkeypatch.delenv("AEAT_CERTIFICATE_PASSWORD_SECRET", raising=False)
        row = check_auth_provider_path(Settings())
        assert row.section == "aeat auth path"
        assert row.state == State.SKIP
        assert "produce, verify, and export" in row.detail

    def test_warns_when_provider_is_configured_but_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AEAT_CERTIFICATE_PATH", "C:/missing/cert.p12")
        monkeypatch.delenv("AEAT_CERTIFICATE_PASSWORD_SECRET", raising=False)
        row = check_auth_provider_path(Settings())
        assert row.state == State.WARN
        assert "auth is fixed" in row.detail
