"""Unit tests for the ``aeat auth`` CLI (#285)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar

import pytest
from pydantic_settings import SettingsConfigDict
from typer.testing import CliRunner

from ...auth import AuthProviderKind
from ...config import Settings
from .. import app
from . import _registry, _session
from ._paths import storage_state_paths
from ._render import render_status_line

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


_runner = CliRunner()


# ── Test fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_token_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a temp token dir and make ``Settings()`` use it.

    Clears every env var Settings reads so a dev's real ``env/.env``
    cannot leak into the test.
    """
    for name in Settings.env_var_names():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path))
    return tmp_path


def _seed_persisted_session(
    tmp_path: Path,
    *,
    authenticated_at: datetime,
    idle_deadline: datetime,
    identity_nif: str = "12345678Z",
    provider_kind: AuthProviderKind | None = AuthProviderKind.CERTIFICATE,
) -> Path:
    """Write a fake storage-state + metadata pair matching the authenticator layout."""
    storage = tmp_path / "default-storage.json"
    storage.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")

    meta = tmp_path / "default-storage.meta.json"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "certificate_nif": identity_nif,
        "identity_nif": identity_nif,
        "authenticated_at": authenticated_at.isoformat(),
        "idle_deadline": idle_deadline.isoformat(),
        "storage_state_sha256": "0" * 64,
    }
    if provider_kind is not None:
        payload["provider_kind"] = provider_kind.value
    if provider_kind == AuthProviderKind.CERTIFICATE:
        payload["certificate_thumbprint"] = "aa" * 32
        payload["certificate_subject"] = "CN=Test"
        payload["handshake"] = {
            "success": True,
            "status_code": 200,
            "tls_version": "TLSv1.3",
            "cipher": "TLS_AES_256_GCM_SHA384",
            "server_cert_chain": (),
            "attempted_at": authenticated_at.isoformat(),
            "elapsed_ms": 10,
            "target_url": "https://sede.agenciatributaria.gob.es/",
            "error_message": None,
        }
    meta.write_text(json.dumps(payload), encoding="utf-8")
    return meta


# ── list-providers ───────────────────────────────────────────────────────────


class TestListProviders:
    """`aeat auth list-providers` reports every known provider in canonical order."""

    def test_table_lists_every_kind(self, isolated_token_dir: Path) -> None:
        del isolated_token_dir
        result = _runner.invoke(app, ["auth", "list-providers"])
        assert result.exit_code == 0, result.output
        assert "Certificate (FNMT)" in result.output
        assert "Cl@ve Permanente" in result.output
        assert "Cl@ve Móvil" in result.output
        assert "Cl@ve PIN" in result.output
        # Rich may wrap the status column; the JSON surface is the
        # deterministic placement test for the "not yet implemented" label.

    def test_configured_filter_hides_unshipped_providers(self, isolated_token_dir: Path) -> None:
        del isolated_token_dir
        result = _runner.invoke(app, ["auth", "list-providers", "--configured"])
        assert result.exit_code == 0, result.output
        # No provider is configured with an empty token dir, so the table has no data rows.
        assert "Cl@ve Permanente" not in result.output
        assert "Certificate (FNMT)" not in result.output

    def test_json_round_trips_descriptions(self, isolated_token_dir: Path) -> None:
        del isolated_token_dir
        result = _runner.invoke(app, ["auth", "list-providers", "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert [row["kind"] for row in payload] == [
            AuthProviderKind.CERTIFICATE.value,
            AuthProviderKind.CLAVE_MOVIL.value,
            AuthProviderKind.CLAVE_PERMANENTE.value,
            AuthProviderKind.CLAVE_PIN.value,
        ]
        assert payload[0]["implemented"] is True
        assert payload[1]["implemented"] is True
        assert payload[2]["implemented"] is False
        assert payload[2]["health_summary"] == "not yet implemented"


# ── registry / default resolution ────────────────────────────────────────────


class TestRegistry:
    """Direct tests for ``_registry`` helpers."""

    def test_default_kind_uses_env_var(
        self,
        isolated_token_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        del isolated_token_dir
        monkeypatch.setenv("AEAT_AUTH_PROVIDER", AuthProviderKind.CLAVE_PERMANENTE.value)
        settings = Settings()
        assert _registry.default_kind(settings) == AuthProviderKind.CLAVE_PERMANENTE

    def test_default_kind_falls_back_to_configured(self, isolated_token_dir: Path) -> None:
        del isolated_token_dir
        settings = Settings()
        with pytest.raises(_registry.NoConfiguredProviderError):
            _registry.default_kind(settings)

    def test_build_provider_rejects_unshipped_kinds(self, isolated_token_dir: Path) -> None:
        del isolated_token_dir
        settings = Settings()
        with pytest.raises(_registry.ProviderNotImplementedError):
            _registry.build_provider(AuthProviderKind.CLAVE_PERMANENTE, settings)

    def test_describe_returns_placeholder_for_unshipped_kinds(self, isolated_token_dir: Path) -> None:
        del isolated_token_dir
        settings = Settings()
        description = _registry.describe(AuthProviderKind.CLAVE_PIN, settings)
        assert description.configured is False
        assert description.available is False
        assert description.health_summary == "not yet implemented"


# ── login ─────────────────────────────────────────────────────────────────────


class TestLogin:
    """`aeat auth login` error paths are Kent-readable and exit with code 2."""

    def test_login_unshipped_provider_exits_2(self, isolated_token_dir: Path) -> None:
        del isolated_token_dir
        result = _runner.invoke(app, ["auth", "login", "--provider", "clave_permanente"])
        assert result.exit_code == 2, result.output
        assert "not yet implemented" in result.output
        assert "#279" in result.output

    def test_login_unknown_provider_rejected(self, isolated_token_dir: Path) -> None:
        del isolated_token_dir
        result = _runner.invoke(app, ["auth", "login", "--provider", "nope"])
        assert result.exit_code != 0
        assert "unknown provider" in result.output or "nope" in result.output

    def test_login_without_configured_provider_reports_actionable_error(
        self,
        isolated_token_dir: Path,
    ) -> None:
        del isolated_token_dir
        result = _runner.invoke(app, ["auth", "login"])
        assert result.exit_code != 0
        assert "AEAT_AUTH_PROVIDER" in result.output or "--provider" in result.output

    def test_login_non_interactive_rejects_interactive_kind(self, isolated_token_dir: Path) -> None:
        del isolated_token_dir
        result = _runner.invoke(
            app,
            ["auth", "login", "--provider", "clave_movil", "--non-interactive"],
        )
        assert result.exit_code == 2
        assert "interactive" in result.output


# ── status ────────────────────────────────────────────────────────────────────


class TestStatus:
    """`aeat auth status` maps persisted state into Kent-readable lines."""

    def test_no_session_prints_friendly_hint(self, isolated_token_dir: Path) -> None:
        del isolated_token_dir
        result = _runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0, result.output
        assert "no active session" in result.output
        assert "aeat auth login" in result.output

    def test_fresh_session_reports_identity_and_ttl(self, isolated_token_dir: Path) -> None:
        now = datetime.now(UTC)
        _seed_persisted_session(
            isolated_token_dir,
            authenticated_at=now - timedelta(minutes=5),
            idle_deadline=now + timedelta(minutes=10),
        )
        result = _runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0, result.output
        assert "active provider: certificate" in result.output
        assert "12345678Z" in result.output

    def test_expired_session_reports_expiry(self, isolated_token_dir: Path) -> None:
        now = datetime.now(UTC)
        _seed_persisted_session(
            isolated_token_dir,
            authenticated_at=now - timedelta(hours=2),
            idle_deadline=now - timedelta(minutes=5),
        )
        result = _runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0, result.output
        assert "expired" in result.output
        assert "aeat auth login" in result.output

    def test_json_output_carries_ttl_fields(self, isolated_token_dir: Path) -> None:
        now = datetime.now(UTC)
        _seed_persisted_session(
            isolated_token_dir,
            authenticated_at=now - timedelta(minutes=2),
            idle_deadline=now + timedelta(minutes=15),
        )
        result = _runner.invoke(app, ["auth", "status", "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["identity_nif"] == "12345678Z"
        assert payload["is_expired"] is False
        assert 0 < payload["seconds_remaining"] <= payload["idle_ttl_seconds"]

    def test_mismatched_provider_reports_no_session(self, isolated_token_dir: Path) -> None:
        now = datetime.now(UTC)
        _seed_persisted_session(
            isolated_token_dir,
            authenticated_at=now - timedelta(minutes=1),
            idle_deadline=now + timedelta(minutes=5),
        )
        result = _runner.invoke(app, ["auth", "status", "--provider", "clave_permanente"])
        assert result.exit_code == 0, result.output
        assert "no active session" in result.output


# ── logout ────────────────────────────────────────────────────────────────────


class TestLogout:
    """`aeat auth logout` deletes storage + metadata and supports --all."""

    def test_logout_without_session_is_noop(self, isolated_token_dir: Path) -> None:
        del isolated_token_dir
        result = _runner.invoke(app, ["auth", "logout"])
        assert result.exit_code == 0, result.output
        assert "no active session" in result.output

    def test_logout_removes_persisted_pair(self, isolated_token_dir: Path) -> None:
        now = datetime.now(UTC)
        _seed_persisted_session(
            isolated_token_dir,
            authenticated_at=now - timedelta(minutes=1),
            idle_deadline=now + timedelta(minutes=10),
        )
        settings = Settings()
        paths = storage_state_paths(settings)
        assert paths.storage_state.exists()
        assert paths.metadata.exists()

        result = _runner.invoke(app, ["auth", "logout"])
        assert result.exit_code == 0, result.output
        assert "cleared" in result.output
        assert not paths.storage_state.exists()
        assert not paths.metadata.exists()

    def test_logout_all_iterates_every_registered_kind(self, isolated_token_dir: Path) -> None:
        now = datetime.now(UTC)
        _seed_persisted_session(
            isolated_token_dir,
            authenticated_at=now - timedelta(minutes=1),
            idle_deadline=now + timedelta(minutes=10),
        )
        settings = Settings()
        paths = storage_state_paths(settings)

        result = _runner.invoke(app, ["auth", "logout", "--all"])
        assert result.exit_code == 0, result.output
        assert not paths.storage_state.exists()
        assert not paths.metadata.exists()

    def test_logout_json_reports_removed_paths(self, isolated_token_dir: Path) -> None:
        now = datetime.now(UTC)
        _seed_persisted_session(
            isolated_token_dir,
            authenticated_at=now - timedelta(minutes=1),
            idle_deadline=now + timedelta(minutes=10),
        )
        result = _runner.invoke(app, ["auth", "logout", "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert len(payload["removed_paths"]) == 2

    def test_logout_with_wrong_provider_preserves_session(self, isolated_token_dir: Path) -> None:
        now = datetime.now(UTC)
        _seed_persisted_session(
            isolated_token_dir,
            authenticated_at=now - timedelta(minutes=1),
            idle_deadline=now + timedelta(minutes=10),
        )
        settings = Settings()
        paths = storage_state_paths(settings)

        result = _runner.invoke(app, ["auth", "logout", "--provider", "clave_permanente"])
        assert result.exit_code == 0, result.output
        # Session belongs to certificate, not clave_permanente — keep it.
        assert paths.storage_state.exists()
        assert paths.metadata.exists()


# ── render ────────────────────────────────────────────────────────────────────


class TestRender:
    """Deterministic tests for the render helpers (no Settings / CLI)."""

    def test_status_line_reports_minutes_remaining(self) -> None:
        now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
        session = _session.PersistedAuthSession(
            provider_kind=AuthProviderKind.CERTIFICATE,
            identity_nif="11111111H",
            authenticated_at=now - timedelta(minutes=8),
            idle_deadline=now + timedelta(minutes=10),
        )
        line = render_status_line(session, now=now)
        assert "authenticated 8m ago" in line
        assert "10m remaining" in line
        assert "11111111H" in line


# ── _session corruption paths ─────────────────────────────────────────────────


class TestSessionLoad:
    """`_session.load` fails closed with an actionable message when the sidecar is broken."""

    def test_corrupt_metadata_raises(self, isolated_token_dir: Path) -> None:
        (isolated_token_dir / "default-storage.json").write_text("{}", encoding="utf-8")
        (isolated_token_dir / "default-storage.meta.json").write_text("not json", encoding="utf-8")
        settings = Settings()
        with pytest.raises(_session.CorruptAuthSessionError):
            _session.load(settings)


# ── conformance checks ───────────────────────────────────────────────────────


class TestConfigure:
    """`aeat auth configure` persists Cl@ve Móvil config to env/.env."""

    def test_configure_clave_movil_writes_env_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)
        # Point Settings at a temp env file so the test never touches the real one.
        env_file = tmp_path / "env" / ".env"

        _config_overrides = {**dict(Settings.model_config), "env_file": env_file}

        class _ScopedSettings(Settings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(**_config_overrides)

        monkeypatch.setattr("aeat.cli.auth.Settings", _ScopedSettings)

        result = _runner.invoke(
            app,
            [
                "auth",
                "configure",
                "--provider",
                "clave_movil",
                "--dni-nie",
                "12345678Z",
                "--prefer-qr",
                "--non-interactive",
            ],
        )
        assert result.exit_code == 0, result.output
        content = env_file.read_text(encoding="utf-8")
        assert "AEAT_CLAVE_MOVIL_DNI_NIE=12345678Z" in content
        assert "AEAT_CLAVE_PREFER_NON_QR=false" in content
        assert "AEAT_AUTH_PROVIDER=clave_movil" in content

    def test_configure_rejects_invalid_identity(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)
        env_file = tmp_path / "env" / ".env"

        _config_overrides = {**dict(Settings.model_config), "env_file": env_file}

        class _ScopedSettings(Settings):
            model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(**_config_overrides)

        monkeypatch.setattr("aeat.cli.auth.Settings", _ScopedSettings)

        result = _runner.invoke(
            app,
            [
                "auth",
                "configure",
                "--dni-nie",
                "NOT-A-REAL-ID",
                "--non-interactive",
            ],
        )
        assert result.exit_code != 0
        assert not env_file.exists() or "AEAT_CLAVE_MOVIL_DNI_NIE" not in env_file.read_text(encoding="utf-8")


class TestConformance:
    """Cross-module contracts that keep registry/description wiring correct."""

    def test_registry_covers_every_provider_kind(self) -> None:
        registry_kinds = {entry.kind for entry in _registry.iter_entries()}
        assert registry_kinds == set(AuthProviderKind)

    def test_placeholder_description_model_dump_is_json_safe(self, isolated_token_dir: Path) -> None:
        del isolated_token_dir
        settings = Settings()
        description = _registry.describe(AuthProviderKind.CLAVE_PIN, settings)
        payload = description.model_dump(mode="json")
        assert payload["kind"] == AuthProviderKind.CLAVE_PIN.value
        assert payload["configured"] is False
