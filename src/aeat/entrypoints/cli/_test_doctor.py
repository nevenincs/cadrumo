"""Unit tests for the pure helpers in :mod:`aeat.entrypoints.cli.doctor`.

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
from pydantic_settings import SettingsConfigDict

from ...adapters.outbound.google import GoogleAuthPath
from ...core.config import Settings
from . import doctor as doctor_module
from .doctor import (
    REQUIRED_ADC_SCOPES,
    Row,
    State,
    adc_scopes_from_file,
    adc_well_known_path,
    check_active_google_auth_path,
    check_auth_provider_path,
    check_cli_oauth_cache,
    check_desktop_oauth_client_material,
    check_google_auth_readiness,
    check_inactive_google_auth_drift,
    check_kdf_version,
    check_live_access_gate,
    check_master_key_readiness,
    check_mcp_credentials_cache,
    check_secret_store_backend,
    check_secret_store_directory,
    check_service_account,
    render_table,
    short_scope,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_OAUTH_CLIENT_SECRET = "client-secret"  # noqa: S105 - test-only placeholder


class IsolatedSettings(Settings):
    """Settings variant that does not read the on-disk env file."""

    model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")


class TestAdcWellKnownPath:
    """Behaviour of ``adc_well_known_path``."""

    def test_uses_cloudsdk_config_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path))
        assert adc_well_known_path() == tmp_path / "application_default_credentials.json"

    def test_windows_default_uses_appdata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLOUDSDK_CONFIG", raising=False)
        if sys.platform != "win32":
            pytest.skip("windows-only default")
        monkeypatch.setenv("APPDATA", "C:/test-appdata")
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
            Row(section="bp", required=True, state=State.PARTIAL, detail="partial"),
            Row(section="c", required=False, state=State.SKIP, detail="skip"),
            Row(section="d", required=False, state=State.WARN, detail="warn"),
        ]
        table = render_table(rows)
        assert len(table.columns) == 4


class TestGoogleAuthDoctorRows:
    """Doctor rows for the new auth contract must stay deterministic."""

    def test_active_path_row_blocks_on_ambiguous_configuration(self, tmp_path: Path) -> None:
        service_account = tmp_path / "service-account.json"
        service_account.write_text("{}", encoding="utf-8")
        settings = IsolatedSettings(
            google_oauth_client_id="client-id",
            google_oauth_client_secret=_OAUTH_CLIENT_SECRET,
            google_application_credentials=str(service_account),
        )

        row = check_active_google_auth_path(settings)

        assert row.state == State.MISSING
        assert "Set GOOGLE_AUTH_PATH" in row.detail

    def test_desktop_rows_show_partial_readiness_when_cli_token_missing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(doctor_module, "PROJECT_ROOT", tmp_path)
        settings = IsolatedSettings(
            google_auth_path=GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV,
            google_oauth_client_id="client-id",
            google_oauth_client_secret=_OAUTH_CLIENT_SECRET,
            aeat_token_dir=tmp_path / ".tokens",
        )

        path_row = check_active_google_auth_path(settings)
        readiness_row = check_google_auth_readiness(settings)
        client_row = check_desktop_oauth_client_material(settings)
        token_row = check_cli_oauth_cache(settings)
        mcp_row = check_mcp_credentials_cache(settings)

        assert path_row.state == State.OK
        assert readiness_row.state == State.MISSING
        assert client_row.state == State.OK
        assert token_row.state == State.MISSING
        assert mcp_row.state == State.MISSING

    def test_readiness_is_partial_when_only_mcp_directory_exists(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(doctor_module, "PROJECT_ROOT", tmp_path)
        (tmp_path / "env" / "workspace-mcp-credentials").mkdir(parents=True, exist_ok=True)
        token_dir = tmp_path / ".tokens"
        token_dir.mkdir(parents=True, exist_ok=True)
        (token_dir / "google_oauth_token.json").write_text(
            (
                '{"refresh_token": "refresh", "scopes": ['
                '"https://www.googleapis.com/auth/drive",'
                '"https://www.googleapis.com/auth/spreadsheets",'
                '"https://www.googleapis.com/auth/documents",'
                '"https://www.googleapis.com/auth/cloud-platform",'
                '"https://www.googleapis.com/auth/userinfo.email",'
                '"openid"'
                "]}"
            ),
            encoding="utf-8",
        )
        settings = IsolatedSettings(
            google_auth_path=GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV,
            google_oauth_client_id="client-id",
            google_oauth_client_secret=_OAUTH_CLIENT_SECRET,
            aeat_token_dir=token_dir,
        )

        row = check_google_auth_readiness(settings)

        assert row.state == State.PARTIAL
        assert "MCP credentials cache still needs preparation" in row.detail

    def test_mcp_cache_row_stays_partial_until_credentials_exist(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(doctor_module, "PROJECT_ROOT", tmp_path)
        (tmp_path / "env" / "workspace-mcp-credentials").mkdir(parents=True, exist_ok=True)
        token_dir = tmp_path / ".tokens"
        token_dir.mkdir(parents=True, exist_ok=True)
        (token_dir / "google_oauth_token.json").write_text(
            (
                '{"refresh_token": "refresh", "scopes": ['
                '"https://www.googleapis.com/auth/drive",'
                '"https://www.googleapis.com/auth/spreadsheets",'
                '"https://www.googleapis.com/auth/documents",'
                '"https://www.googleapis.com/auth/cloud-platform",'
                '"https://www.googleapis.com/auth/userinfo.email",'
                '"openid"'
                "]}"
            ),
            encoding="utf-8",
        )
        settings = IsolatedSettings(
            google_auth_path=GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV,
            google_oauth_client_id="client-id",
            google_oauth_client_secret=_OAUTH_CLIENT_SECRET,
            aeat_token_dir=token_dir,
        )

        row = check_mcp_credentials_cache(settings)

        assert row.state == State.PARTIAL
        assert "no cached MCP credentials exist yet" in row.detail

    def test_desktop_material_row_is_skipped_when_service_account_path_is_active(self, tmp_path: Path) -> None:
        service_account = tmp_path / "service-account.json"
        service_account.write_text("{}", encoding="utf-8")
        settings = IsolatedSettings(
            google_auth_path=GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION,
            google_application_credentials=str(service_account),
            google_oauth_client_id="client-id",
            google_oauth_client_secret=_OAUTH_CLIENT_SECRET,
        )

        row = check_desktop_oauth_client_material(settings)

        assert row.state == State.SKIP
        assert "inactive-path drift" in row.detail

    def test_service_account_row_is_required_for_service_account_path(self, tmp_path: Path) -> None:
        service_account = tmp_path / "service-account.json"
        service_account.write_text("{}", encoding="utf-8")
        settings = IsolatedSettings(
            google_auth_path=GoogleAuthPath.SERVICE_ACCOUNT_AUTOMATION,
            google_application_credentials=str(service_account),
        )

        row = check_service_account(settings)

        assert row.required is True
        assert row.state == State.OK

    def test_service_account_row_is_skipped_when_desktop_path_is_active(self, tmp_path: Path) -> None:
        service_account = tmp_path / "service-account.json"
        service_account.write_text("{}", encoding="utf-8")
        settings = IsolatedSettings(
            google_auth_path=GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV,
            google_application_credentials=str(service_account),
            google_oauth_client_id="client-id",
            google_oauth_client_secret=_OAUTH_CLIENT_SECRET,
        )

        row = check_service_account(settings)

        assert row.state == State.SKIP
        assert "inactive-path drift" in row.detail

    def test_inactive_path_drift_reports_ignored_missing_service_account(self, tmp_path: Path) -> None:
        settings = IsolatedSettings(
            google_auth_path=GoogleAuthPath.DESKTOP_OAUTH_LOCAL_DEV,
            google_oauth_client_id="client-id",
            google_oauth_client_secret=_OAUTH_CLIENT_SECRET,
            google_application_credentials=str(tmp_path / "missing.json"),
        )

        row = check_inactive_google_auth_drift(settings)

        assert row.state == State.WARN
        assert "ignored stale service-account path" in row.detail


class TestLiveAccessGateRow:
    """Behaviour of ``check_live_access_gate``."""

    def test_reports_enabled_reads(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "1")
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        row = check_live_access_gate(Settings())
        assert row.section == "live access gate"
        assert row.state == State.OK
        assert "ENABLED" in row.detail
        assert "writes: permanently forbidden" in row.detail

    def test_reports_skipped_when_reads_not_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AEAT_LIVE_TESTS_ENABLED", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        row = check_live_access_gate(Settings())
        assert row.state == State.SKIP
        assert "skipped" in row.detail

    def test_warns_when_running_inside_pytest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AEAT_LIVE_TESTS_ENABLED", "1")
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test-path")
        row = check_live_access_gate(Settings())
        assert row.state == State.WARN
        assert "PYTEST_CURRENT_TEST present" in row.detail


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


def _settings_with_secret_dir(
    tmp_path: Path,
    *,
    backend: str | None = None,
    allow_unencrypted: bool | None = None,
) -> Settings:
    """Build a Settings bound to a tmp secret-store directory."""
    overrides: dict[str, object] = {"aeat_secret_store_dir": tmp_path / "secrets"}
    if backend is not None:
        overrides["aeat_secret_store_backend"] = backend
    if allow_unencrypted is not None:
        overrides["aeat_allow_unencrypted"] = allow_unencrypted
    return IsolatedSettings.model_validate(overrides)


class TestSecretStoreDirectoryRow:
    """The secret-store directory row reports presence + writability."""

    def test_missing_dir_is_a_remediation_hint(self, tmp_path: Path) -> None:
        row = check_secret_store_directory(_settings_with_secret_dir(tmp_path))
        assert row.section == "secret-store dir"
        assert row.state == State.MISSING
        assert "aeat security provision" in row.detail

    def test_writable_dir_is_ok(self, tmp_path: Path) -> None:
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        row = check_secret_store_directory(_settings_with_secret_dir(tmp_path))
        assert row.state == State.OK
        assert str(secret_dir) in row.detail


class TestSecretStoreBackendRow:
    """The active backend row warns loudly on the unsecured path."""

    def test_keyring_backend_is_ok(self, tmp_path: Path) -> None:
        from ...core.config import SecretStoreBackend

        row = check_secret_store_backend(
            _settings_with_secret_dir(
                tmp_path,
                backend=SecretStoreBackend.KEYRING.value,
            ),
        )
        assert row.state == State.OK
        assert "backend=keyring" in row.detail

    def test_unsecured_without_allow_flag_is_missing(self, tmp_path: Path) -> None:
        from ...core.config import SecretStoreBackend

        row = check_secret_store_backend(
            _settings_with_secret_dir(
                tmp_path,
                backend=SecretStoreBackend.UNSECURED.value,
                allow_unencrypted=False,
            ),
        )
        assert row.state == State.MISSING
        assert "AEAT_ALLOW_UNENCRYPTED" in row.detail

    def test_unsecured_with_allow_flag_is_warn(self, tmp_path: Path) -> None:
        from ...core.config import SecretStoreBackend

        row = check_secret_store_backend(
            _settings_with_secret_dir(
                tmp_path,
                backend=SecretStoreBackend.UNSECURED.value,
                allow_unencrypted=True,
            ),
        )
        assert row.state == State.WARN
        assert "ZERO confidentiality" in row.detail


class TestMasterKeyReadinessRow:
    """The master-key readiness row checks file-fallback artefacts."""

    def test_file_backend_with_no_artefacts_is_missing(self, tmp_path: Path) -> None:
        from ...core.config import SecretStoreBackend

        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        row = check_master_key_readiness(
            _settings_with_secret_dir(
                tmp_path,
                backend=SecretStoreBackend.FILE.value,
            ),
        )
        assert row.state == State.MISSING
        assert "aeat security provision" in row.detail

    def test_file_backend_with_complete_artefacts_is_ok(self, tmp_path: Path) -> None:
        from ...core.config import SecretStoreBackend

        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        for name in ("master.key", "master.kdf", "salt"):
            (secret_dir / name).write_bytes(b"placeholder")
        row = check_master_key_readiness(
            _settings_with_secret_dir(
                tmp_path,
                backend=SecretStoreBackend.FILE.value,
            ),
        )
        assert row.state == State.OK

    def test_file_backend_with_partial_artefacts_is_partial(self, tmp_path: Path) -> None:
        from ...core.config import SecretStoreBackend

        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        # Only master.kdf — the other two are missing.
        (secret_dir / "master.kdf").write_bytes(b"placeholder")
        row = check_master_key_readiness(
            _settings_with_secret_dir(
                tmp_path,
                backend=SecretStoreBackend.FILE.value,
            ),
        )
        assert row.state == State.PARTIAL
        assert "partial file-fallback state" in row.detail


class TestKdfVersionRow:
    """The KDF-version row gates on the post-Argon2id parameter shape."""

    def test_no_master_kdf_is_skipped(self, tmp_path: Path) -> None:
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        row = check_kdf_version(_settings_with_secret_dir(tmp_path))
        assert row.state == State.SKIP

    def test_v2_kdf_is_ok(self, tmp_path: Path) -> None:
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        (secret_dir / "master.kdf").write_text(
            json.dumps({"version": 2, "algorithm": "argon2id"}),
            encoding="utf-8",
        )
        row = check_kdf_version(_settings_with_secret_dir(tmp_path))
        assert row.state == State.OK
        assert "Argon2id" in row.detail

    def test_v1_kdf_is_warn_with_migration_hint(self, tmp_path: Path) -> None:
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        (secret_dir / "master.kdf").write_text(
            json.dumps({"version": 1, "algorithm": "scrypt"}),
            encoding="utf-8",
        )
        row = check_kdf_version(_settings_with_secret_dir(tmp_path))
        assert row.state == State.WARN
        assert "migrate-master-key-kdf" in row.detail

    def test_unparseable_master_kdf_is_partial(self, tmp_path: Path) -> None:
        secret_dir = tmp_path / "secrets"
        secret_dir.mkdir()
        (secret_dir / "master.kdf").write_text("{not json", encoding="utf-8")
        row = check_kdf_version(_settings_with_secret_dir(tmp_path))
        assert row.state == State.PARTIAL
