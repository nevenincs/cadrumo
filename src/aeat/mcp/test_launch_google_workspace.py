"""Unit tests for the google-workspace MCP launcher."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from ..config import PROJECT_ROOT, Settings
from ..env_io import write_env_vars
from ..errors import AeatError
from .launch_google_workspace import (
    PROJECT_WORKSPACE_MCP_CREDENTIALS_DIR,
    WORKSPACE_MCP_CREDENTIALS_DIR_ENV,
    WORKSPACE_MCP_USER_EMAIL_ENV,
    build_launch_spec,
    ensure_credentials_dir,
)


class IsolatedSettings(Settings):
    """Settings variant that does not read the on-disk env file."""

    model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")


@pytest.mark.unit
class TestBuildLaunchSpec:
    """Behaviour of the pure launch-spec builder."""

    def test_oauth_env_passthrough(self) -> None:
        settings = IsolatedSettings(
            google_oauth_client_id="oauth-client-id",
            google_oauth_client_secret="oauth-client-secret",  # noqa: S106 - test-only placeholder
            google_oauth_redirect_uri="http://localhost:8787/oauth2callback",
        )

        spec = build_launch_spec(settings, base_env={"PATH": "test-path"}, extra_args=("--read-only",))

        assert spec.argv == ("uvx", "workspace-mcp", "--tool-tier", "core", "--read-only")
        assert spec.env["PATH"] == "test-path"
        assert spec.env["google_oauth_client_id".upper()] == "oauth-client-id"
        assert spec.env["google_oauth_client_secret".upper()] == "oauth-client-secret"
        assert spec.env["google_oauth_redirect_uri".upper()] == "http://localhost:8787/oauth2callback"
        assert spec.env[WORKSPACE_MCP_CREDENTIALS_DIR_ENV] == str(PROJECT_WORKSPACE_MCP_CREDENTIALS_DIR)
        assert WORKSPACE_MCP_CREDENTIALS_DIR_ENV in spec.env

    def test_missing_both_auth_paths_raises(self) -> None:
        settings = IsolatedSettings()

        with pytest.raises(AeatError, match="requires local Google credentials"):
            build_launch_spec(settings, base_env={})

    def test_partial_oauth_without_service_account_raises(self) -> None:
        settings = IsolatedSettings(google_oauth_client_id="oauth-client-id")

        with pytest.raises(AeatError, match="complete OAuth desktop client"):
            build_launch_spec(settings, base_env={})

    def test_service_account_path_maps_to_upstream_env(self, tmp_path: Path) -> None:
        service_account_key = tmp_path / "service-account.json"
        service_account_key.write_text("{}", encoding="utf-8")
        settings = IsolatedSettings(
            google_application_credentials=str(service_account_key),
            google_impersonate_email="operator@example.com",
        )

        spec = build_launch_spec(settings, base_env={"PATH": "test-path"})

        assert spec.env["PATH"] == "test-path"
        assert spec.env["GOOGLE_SERVICE_ACCOUNT_KEY_FILE"] == str(service_account_key.resolve())
        assert spec.env["google_application_credentials".upper()] == str(service_account_key.resolve())
        assert spec.env["google_impersonate_email".upper()] == "operator@example.com"
        assert spec.env[WORKSPACE_MCP_USER_EMAIL_ENV] == "operator@example.com"
        assert "google_oauth_client_id".upper() not in spec.env
        assert spec.credentials_dir == PROJECT_WORKSPACE_MCP_CREDENTIALS_DIR

    def test_missing_service_account_file_raises(self, tmp_path: Path) -> None:
        missing_key = tmp_path / "missing-service-account.json"
        settings = IsolatedSettings(
            google_application_credentials=str(missing_key),
            google_impersonate_email="operator@example.com",
        )

        with pytest.raises(AeatError, match="does not exist"):
            build_launch_spec(settings, base_env={})

    def test_relative_service_account_path_resolves_from_project_root(self) -> None:
        settings = IsolatedSettings(
            google_application_credentials="env/.env.example",
            google_impersonate_email="operator@example.com",
        )

        spec = build_launch_spec(settings, base_env={"PATH": "test-path"})

        assert spec.env["PATH"] == "test-path"
        assert spec.env["GOOGLE_SERVICE_ACCOUNT_KEY_FILE"] == str((PROJECT_ROOT / "env/.env.example").resolve())
        assert spec.env["google_application_credentials".upper()] == str((PROJECT_ROOT / "env/.env.example").resolve())
        assert spec.env[WORKSPACE_MCP_USER_EMAIL_ENV] == "operator@example.com"

    def test_service_account_without_impersonated_user_passes_through(self, tmp_path: Path) -> None:
        service_account_key = tmp_path / "service-account.json"
        service_account_key.write_text("{}", encoding="utf-8")
        settings = IsolatedSettings(google_application_credentials=str(service_account_key))

        spec = build_launch_spec(settings, base_env={"PATH": "test-path"})

        assert spec.env["PATH"] == "test-path"
        assert spec.env["GOOGLE_SERVICE_ACCOUNT_KEY_FILE"] == str(service_account_key.resolve())
        assert spec.env["google_application_credentials".upper()] == str(service_account_key.resolve())
        assert WORKSPACE_MCP_USER_EMAIL_ENV not in spec.env

    def test_missing_service_account_file_falls_back_to_oauth(self, tmp_path: Path) -> None:
        missing_key = tmp_path / "missing-service-account.json"
        settings = IsolatedSettings(
            google_application_credentials=str(missing_key),
            google_oauth_client_id="oauth-client-id",
            google_oauth_client_secret="oauth-client-secret",  # noqa: S106 - test-only placeholder
            google_oauth_redirect_uri="http://localhost:8787/oauth2callback",
        )

        spec = build_launch_spec(settings, base_env={"PATH": "test-path"})

        assert spec.env["PATH"] == "test-path"
        assert spec.env["GOOGLE_OAUTH_CLIENT_ID"] == "oauth-client-id"
        assert spec.env["GOOGLE_OAUTH_CLIENT_SECRET"] == "oauth-client-secret"  # noqa: S105
        assert spec.env["GOOGLE_OAUTH_REDIRECT_URI"] == "http://localhost:8787/oauth2callback"
        assert "GOOGLE_SERVICE_ACCOUNT_KEY_FILE" not in spec.env
        assert "GOOGLE_APPLICATION_CREDENTIALS" not in spec.env


@pytest.mark.unit
class TestEnsureCredentialsDir:
    """The credential-cache hardening path is explicit and creatable."""

    def test_creates_requested_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "env" / "workspace-mcp-credentials"

        created = ensure_credentials_dir(target)

        assert created == target
        assert target.exists()
        assert target.is_dir()
        assert str(created).endswith(str(Path("env") / "workspace-mcp-credentials"))

    def test_project_credentials_dir_is_repo_local(self) -> None:
        assert PROJECT_WORKSPACE_MCP_CREDENTIALS_DIR == PROJECT_ROOT / "env" / "workspace-mcp-credentials"


@pytest.mark.unit
class TestLauncherBoundary:
    """Fresh-clone boundary checks for env loading and MCP handoff."""

    def test_mcp_json_points_google_workspace_to_launcher(self) -> None:
        mcp_config = json.loads((PROJECT_ROOT / ".mcp.json").read_text(encoding="utf-8"))

        google_workspace = mcp_config["mcpServers"]["google-workspace"]
        assert google_workspace == {
            "command": "uv",
            "args": ["run", "python", "-m", "aeat.mcp.launch_google_workspace"],
        }

    def test_dump_launch_spec_reads_env_file_and_creates_repo_local_cache(self) -> None:
        env_path = PROJECT_ROOT / "env" / ".env"
        env_path.parent.mkdir(parents=True, exist_ok=True)
        previous_env = env_path.read_text(encoding="utf-8") if env_path.exists() else None
        credentials_dir = PROJECT_ROOT / "env" / "workspace-mcp-credentials"
        uv_executable = shutil.which("uv")
        assert uv_executable is not None
        expected_secret = "oauth-client-secret"  # noqa: S105 - test-only placeholder

        try:
            write_env_vars(
                env_path,
                {
                    "GOOGLE_OAUTH_CLIENT_ID": "oauth-client-id",
                    "GOOGLE_OAUTH_CLIENT_SECRET": expected_secret,
                    "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:8787/oauth2callback",
                },
            )

            result = subprocess.run(  # noqa: S603 - trusted repo-local test command
                [
                    uv_executable,
                    "run",
                    "python",
                    "-m",
                    "aeat.mcp.launch_google_workspace",
                    "--dump-launch-spec",
                    "--read-only",
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            if previous_env is None:
                env_path.unlink(missing_ok=True)
            else:
                env_path.write_text(previous_env, encoding="utf-8")
            if credentials_dir.exists():
                for child in credentials_dir.iterdir():
                    if child.is_file():
                        child.unlink()
                credentials_dir.rmdir()

        payload = json.loads(result.stdout.strip())
        assert payload["argv"] == ["uvx", "workspace-mcp", "--tool-tier", "core", "--read-only"]
        assert Path(payload["executable"]).exists()
        assert Path(payload["executable"]).stem.lower() == "uvx"
        assert payload["env"]["GOOGLE_OAUTH_CLIENT_ID"] == "oauth-client-id"
        assert payload["env"]["GOOGLE_OAUTH_CLIENT_SECRET"] == "<redacted>"  # noqa: S105
        assert payload["env"]["GOOGLE_OAUTH_REDIRECT_URI"] == "http://localhost:8787/oauth2callback"
        assert payload["env"][WORKSPACE_MCP_CREDENTIALS_DIR_ENV] == str(PROJECT_WORKSPACE_MCP_CREDENTIALS_DIR)
        assert payload["credentials_dir"] == str(PROJECT_WORKSPACE_MCP_CREDENTIALS_DIR)
