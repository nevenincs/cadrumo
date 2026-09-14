"""Development-only access to the committed user-profile schema."""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition
from dev.registry.compiler.profile_schema import capture_profile_schema


def load_user_profile_schema(path: Path | None = None) -> ProfileSchemaDefinition:
    """Capture and parse the profile schema for tests and development checks.

    Production code does not depend on this helper.  Every call captures one
    source path and delegates validation to the development parser, so tests
    exercise the same typed envelope contract as registry compilation.
    """
    source = path or bundled_path("registry", "cadrumo", "user_profile", "schema.toml")
    _payload, schema = capture_profile_schema(source)
    return schema
