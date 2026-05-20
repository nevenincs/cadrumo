"""Read-only loader for the centralized user-profile schema TOML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from ...core._toml import freeze_toml, read_toml
from ...core.resources import bundled_path
from ._errors import UserProfileSchemaLoadError
from ._schema import ProfileSchemaDefinition


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
    data = freeze_toml(read_toml(source_path, error_factory=UserProfileSchemaLoadError))
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
