"""Read-only loader for the centralized user-profile schema TOML."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from ...core.resources import bundled_path
from ._errors import UserProfileSchemaLoadError
from ._schema import ProfileSchemaDefinition

def _read_toml(path: Path) -> dict[str, object]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise UserProfileSchemaLoadError(f"{path}: invalid TOML: {exc}") from exc
    except OSError as exc:
        raise UserProfileSchemaLoadError(f"{path}: cannot read TOML: {exc}") from exc


def _freeze_toml_value(value: object) -> object:
    if isinstance(value, list):
        return tuple(_freeze_toml_value(item) for item in value)
    if isinstance(value, dict):
        return {key: _freeze_toml_value(item) for key, item in value.items()}
    return value


def _freeze_toml(data: dict[str, object]) -> dict[str, object]:
    return {key: _freeze_toml_value(value) for key, value in data.items()}


def load_user_profile_schema(path: Path | None = None) -> ProfileSchemaDefinition:
    """Load the centralized user-profile schema.

    Args:
        path: TOML schema path. Defaults to the bundled registry schema.

    Returns:
        A strict, frozen :class:`ProfileSchemaDefinition`.

    Raises:
        UserProfileSchemaLoadError: If the file is missing, invalid TOML, or
            fails strict schema validation.
    """

    target = path if path is not None else bundled_path("registry", "aeat", "user_profile", "schema.toml")
    resolved = target.resolve()
    stat = resolved.stat()
    return _load_user_profile_schema_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=16)
def _load_user_profile_schema_cached(path: str, byte_count: int, modified_ns: int) -> ProfileSchemaDefinition:
    del byte_count, modified_ns
    source_path = Path(path)
    data = _freeze_toml(_read_toml(source_path))
    raw_schema = data.get("schema")
    if not isinstance(raw_schema, dict):
        raise UserProfileSchemaLoadError(f"{source_path}: missing [schema] table")
    raw_sections = data.get("sections")
    if not isinstance(raw_sections, tuple) or not raw_sections:
        raise UserProfileSchemaLoadError(f"{source_path}: missing [[sections]] tables")
    try:
        return ProfileSchemaDefinition.model_validate({**raw_schema, "sections": raw_sections})
    except ValidationError as exc:
        raise UserProfileSchemaLoadError(f"{source_path}: invalid user-profile schema: {exc}") from exc
