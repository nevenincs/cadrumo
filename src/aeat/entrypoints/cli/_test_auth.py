"""CLI tests for the Kent-facing Google auth entrypoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from . import auth as auth_module

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


def test_desktop_auth_init_imports_client_and_prepares_mcp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module, "PROJECT_ROOT", tmp_path)
    (tmp_path / "env").mkdir(parents=True, exist_ok=True)
    (tmp_path / "env" / ".env.example").write_text("GOOGLE_CLOUD_PROJECT=test-project\n", encoding="utf-8")
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
    oauth_json = tmp_path / "downloads" / "oauth-client.json"
    oauth_json.parent.mkdir(parents=True, exist_ok=True)
    oauth_json.write_text(
        (
            '{"installed": {"client_id": "client-id", "client_secret": "client-secret", '
            '"redirect_uris": ["http://localhost:8080"]}}'
        ),
        encoding="utf-8",
    )

    result = _RUNNER.invoke(
        auth_module.app,
        [
            "init",
            "--path",
            "desktop-oauth-local-dev",
            "--json",
            str(oauth_json),
            "--no-acquire-cli-token",
            "--no-doctor",
        ],
    )

    assert result.exit_code == 0
    assert "Next: uv run aeat doctor" in result.output
    env_text = (tmp_path / "env" / ".env").read_text(encoding="utf-8")
    assert "GOOGLE_AUTH_PATH=desktop-oauth-local-dev" in env_text
    assert "GOOGLE_OAUTH_CLIENT_ID=client-id" in env_text
    assert (tmp_path / "env" / "oauth-client.json").exists()
    assert (tmp_path / "env" / "workspace-mcp-credentials").exists()


def test_service_account_auth_init_imports_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module, "PROJECT_ROOT", tmp_path)
    (tmp_path / "env").mkdir(parents=True, exist_ok=True)
    (tmp_path / "env" / ".env.example").write_text("GOOGLE_CLOUD_PROJECT=test-project\n", encoding="utf-8")
    service_account_json = tmp_path / "downloads" / "service-account.json"
    service_account_json.parent.mkdir(parents=True, exist_ok=True)
    service_account_json.write_text("{}", encoding="utf-8")

    result = _RUNNER.invoke(
        auth_module.app,
        [
            "init",
            "--path",
            "service-account-automation",
            "--service-account-json",
            str(service_account_json),
            "--no-doctor",
        ],
    )

    assert result.exit_code == 0
    env_text = (tmp_path / "env" / ".env").read_text(encoding="utf-8")
    assert "GOOGLE_AUTH_PATH=service-account-automation" in env_text
    assert "GOOGLE_APPLICATION_CREDENTIALS=" in env_text
    assert (tmp_path / "env" / "service-account.json").exists()
    assert (tmp_path / "env" / "workspace-mcp-credentials").exists()


def test_failed_path_switch_does_not_persist_blocking_auth_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_module, "PROJECT_ROOT", tmp_path)
    (tmp_path / "env").mkdir(parents=True, exist_ok=True)
    (tmp_path / "env" / ".env.example").write_text(
        "\n".join(
            (
                "GOOGLE_CLOUD_PROJECT=test-project",
                "GOOGLE_AUTH_PATH=desktop-oauth-local-dev",
                "GOOGLE_OAUTH_CLIENT_ID=client-id",
                "GOOGLE_OAUTH_CLIENT_SECRET=client-secret",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "env" / ".env").write_text(
        (tmp_path / "env" / ".env.example").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = _RUNNER.invoke(
        auth_module.app,
        [
            "init",
            "--path",
            "service-account-automation",
            "--no-doctor",
        ],
    )

    assert result.exit_code == 1
    env_text = (tmp_path / "env" / ".env").read_text(encoding="utf-8")
    assert "GOOGLE_AUTH_PATH=desktop-oauth-local-dev" in env_text
