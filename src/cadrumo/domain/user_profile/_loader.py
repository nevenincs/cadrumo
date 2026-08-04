"""Read-only loader for the centralized user-profile schema TOML.

:func:`load_user_profile_schema` reads the bundled schema TOML into a
:class:`ProfileSchemaDefinition` and raises :class:`UserProfileSchemaLoadError`
when the file cannot be read or validated.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from ...core import freeze_toml, read_toml
from ...core.paths import path_stat_fingerprint
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
        :class:`UserProfileSchemaLoadError`: If the schema file cannot be stated,
            parsed, or validated into :class:`ProfileSchemaDefinition`.
    """
    target = path if path is not None else bundled_path("registry", "cadrumo", "user_profile", "schema.toml")
    resolved = target.resolve()
    try:
        fingerprint = path_stat_fingerprint(resolved)
    except OSError as exc:
        raise _schema_load_error(resolved, "cannot stat user-profile schema", operation="stat") from exc
    return _load_user_profile_schema_cached(*fingerprint)


@lru_cache(maxsize=16)
def _load_user_profile_schema_cached(path: str, byte_count: int, modified_ns: int) -> ProfileSchemaDefinition:
    del byte_count, modified_ns
    source_path = Path(path)
    data = freeze_toml(
        read_toml(
            source_path,
            error_factory=lambda message: _schema_load_error(source_path, message, operation="read"),
        ),
    )
    raw_schema = data.get("schema")
    if not isinstance(raw_schema, dict):
        raise _schema_load_error(source_path, "missing [schema] table", operation="validate")
    raw_sections = data.get("sections")
    if not isinstance(raw_sections, tuple) or not raw_sections:
        raise _schema_load_error(source_path, "missing [[sections]] tables", operation="validate")
    # ``freeze_toml`` turns TOML arrays into tuples, so the guard mirrors the
    # sections guard above. The key is passed through explicitly because
    # ``model_validate`` receives only the keys named here -- an array left out
    # of this call is parsed and then silently dropped.
    raw_derived_selectors = data.get("derived_selectors", ())
    if not isinstance(raw_derived_selectors, tuple):
        raise _schema_load_error(
            source_path,
            "[[derived_selectors]] must be an array of tables",
            operation="validate",
        )
    try:
        return ProfileSchemaDefinition.model_validate(
            {
                **raw_schema,
                "sections": raw_sections,
                "derived_selectors": raw_derived_selectors,
            },
        )
    except ValidationError as exc:
        raise _schema_load_error(source_path, f"invalid user-profile schema: {exc}", operation="validate") from exc


def _schema_load_error(path: Path, message: str, *, operation: str) -> UserProfileSchemaLoadError:
    """Build a structured schema-load error without leaking raw OS exceptions."""
    return UserProfileSchemaLoadError(
        f"{path}: {message}",
        context={
            "operation": operation,
            "path": str(path),
            "schema": "user_profile",
        },
    )
