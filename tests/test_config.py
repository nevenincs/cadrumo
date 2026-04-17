"""Tests that Settings and ``env/.env.example`` stay fully aligned.

The Settings model in ``aeat.config`` is the single source of truth for every
environment variable the application reads.  These tests enforce that:

1. Every Settings field has a matching line in ``env/.env.example``.
2. Every variable in ``env/.env.example`` has a matching Settings field.
3. Settings can be instantiated with no env vars at all (all fields have defaults).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from aeat.config import PROJECT_ROOT, Settings

ENV_EXAMPLE_PATH = PROJECT_ROOT / "env" / ".env.example"

pytestmark = pytest.mark.unit


def _parse_env_example_vars() -> set[str]:
    """Extract variable names from ``env/.env.example``."""
    env_file = ENV_EXAMPLE_PATH
    names: set[str] = set()
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        # Skip blank lines and comments
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Z_][A-Z0-9_]*)=", stripped)
        if match:
            names.add(match.group(1))
    return names


class TestEnvExampleAlignment:
    """Ensure .env.example and Settings stay fully synchronized."""

    def test_env_example_file_exists(self) -> None:
        """``env/.env.example`` must exist at the canonical env container path."""
        assert ENV_EXAMPLE_PATH.exists(), f".env.example not found at {ENV_EXAMPLE_PATH}"

    def test_settings_fields_documented_in_env_example(self) -> None:
        """Every Settings field must have a corresponding entry in env/.env.example."""
        settings_vars = Settings.env_var_names()
        example_vars = _parse_env_example_vars()
        missing = sorted(settings_vars - example_vars)
        assert not missing, (
            f"Settings fields not documented in .env.example: {missing}. Add an entry for each to .env.example."
        )

    def test_env_example_vars_defined_in_settings(self) -> None:
        """Every .env.example variable must have a corresponding Settings field."""
        settings_vars = Settings.env_var_names()
        example_vars = _parse_env_example_vars()
        extra = sorted(example_vars - settings_vars)
        assert not extra, (
            f"env/.env.example variables with no Settings field: {extra}. "
            "Add a corresponding field to Settings in config.py."
        )

    def test_settings_instantiate_without_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings must load with all defaults when no env file and no env vars are present."""
        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)

        class IsolatedSettings(Settings):
            """Settings variant that skips the on-disk env file for test isolation."""

            model_config = SettingsConfigDict(env_file=None, env_file_encoding="utf-8")

        settings = IsolatedSettings()
        assert settings.aeat_base_url == "https://sede.agenciatributaria.gob.es"

    def test_blank_env_values_are_ignored(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Blank values in env/.env must not coerce optional settings into live values."""
        for name in Settings.env_var_names():
            monkeypatch.delenv(name, raising=False)

        env_path = tmp_path / ".env"
        env_path.write_text(
            "\n".join(
                (
                    "AEAT_DEFAULT_PROFILE_PATH=",
                    "AEAT_CERTIFICATE_PATH=",
                    "AEAT_CERTIFICATE_PASSWORD_SECRET=",
                    "GOOGLE_OAUTH_REDIRECT_URI=",
                )
            )
            + "\n",
            encoding="utf-8",
        )

        class BlankEnvSettings(Settings):
            """Settings variant bound to a temp env file that contains blank assignments."""

            model_config = SettingsConfigDict(
                env_file=env_path,
                env_file_encoding="utf-8",
                env_ignore_empty=True,
            )

        settings = BlankEnvSettings()
        assert settings.aeat_default_profile_path is None
        assert settings.aeat_certificate_path is None
        assert settings.aeat_certificate_password_secret is None
        assert settings.google_oauth_redirect_uri == "http://localhost:8080"
