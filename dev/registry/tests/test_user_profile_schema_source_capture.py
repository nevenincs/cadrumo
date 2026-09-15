"""The development capture refuses an unavailable or envelope-less user-profile schema source."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from dev.registry.compiler.profile_schema import capture_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_missing_user_profile_schema_path_is_refused_by_development_capture(tmp_path: Path) -> None:
    missing = tmp_path / "missing-schema.toml"

    with pytest.raises(RegistryValidationError, match="unavailable") as exc_info:
        capture_profile_schema(missing)

    assert isinstance(exc_info.value.__cause__, FileNotFoundError)


def test_user_profile_schema_missing_tables_are_refused_by_development_parser(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text("[not_schema]\nid = 'wrong'\n", encoding="utf-8")

    with pytest.raises(RegistryValidationError, match="invalid envelope"):
        capture_profile_schema(schema_path)
