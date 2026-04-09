"""Tests that Settings and .env.example stay fully aligned.

The Settings model in ``aeat.config`` is the single source of truth for every
environment variable the application reads.  These tests enforce that:

1. Every Settings field has a matching line in ``.env.example``.
2. Every variable in ``.env.example`` has a matching Settings field.
3. Settings can be instantiated with no env vars at all (all fields have defaults).
"""

from __future__ import annotations

import re

from aeat.config import PROJECT_ROOT, Settings


def _parse_env_example_vars() -> set[str]:
    """Extract variable names from ``.env.example``."""
    env_file = PROJECT_ROOT / ".env.example"
    names: set[str] = set()
    for line in env_file.read_text().splitlines():
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
        """.env.example must exist in the project root."""
        assert (PROJECT_ROOT / ".env.example").exists(), ".env.example not found at project root"

    def test_settings_fields_documented_in_env_example(self) -> None:
        """Every Settings field must have a corresponding entry in .env.example."""
        settings_vars = Settings.env_var_names()
        example_vars = _parse_env_example_vars()
        missing = sorted(settings_vars - example_vars)
        assert not missing, (
            f"Settings fields not documented in .env.example: {missing}. "
            "Add an entry for each to .env.example."
        )

    def test_env_example_vars_defined_in_settings(self) -> None:
        """Every .env.example variable must have a corresponding Settings field."""
        settings_vars = Settings.env_var_names()
        example_vars = _parse_env_example_vars()
        extra = sorted(example_vars - settings_vars)
        assert not extra, (
            f".env.example variables with no Settings field: {extra}. "
            "Add a corresponding field to Settings in config.py."
        )

    def test_settings_instantiate_without_env(self) -> None:
        """Settings must load with all defaults when no env vars are set."""
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
        )
        assert settings.aeat_base_url == "https://sede.agenciatributaria.gob.es"
