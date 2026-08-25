"""Read-only loader for the centralized user-profile schema TOML.

:func:`load_user_profile_schema` reads the bundled schema TOML into a
:class:`ProfileSchemaDefinition` and raises :class:`UserProfileSchemaLoadError`
when the file cannot be read or validated.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from ...core import freeze_toml, read_toml
from ...core.paths import path_stat_fingerprint
from ...core.resources import bundled_path
from .errors import UserProfileSchemaLoadError
from .schema import ProfileSchemaDefinition

#: The stage of the load that refused, as a locale-neutral machine fact. These
#: are condition identities, not prose: they stay stable when the operator text
#: is retranslated and they are what a reader greps for when a schema stops
#: loading. Distinct from ``operation``, which names the coarse phase (stat,
#: read, validate) that the refusal has always reported.
CONDITION_SCHEMA_PATH_STAT: Final[str] = "schema_path_stat"
CONDITION_SCHEMA_TOML_PARSE: Final[str] = "schema_toml_parse"
CONDITION_SCHEMA_TABLE_PRESENT: Final[str] = "schema_table_present"
CONDITION_SECTIONS_TABLE_PRESENT: Final[str] = "sections_table_present"
CONDITION_DERIVED_SELECTORS_ARRAY: Final[str] = "derived_selectors_array"
CONDITION_SCHEMA_MODEL_VALID: Final[str] = "schema_model_valid"

_OPERATION_STAT: Final[str] = "stat"
_OPERATION_READ: Final[str] = "read"
_OPERATION_VALIDATE: Final[str] = "validate"


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
        raise _schema_load_error(
            resolved,
            operation=_OPERATION_STAT,
            condition=CONDITION_SCHEMA_PATH_STAT,
        ) from exc
    return _load_user_profile_schema_cached(*fingerprint)


@lru_cache(maxsize=16)
def _load_user_profile_schema_cached(path: str, byte_count: int, modified_ns: int) -> ProfileSchemaDefinition:
    del byte_count, modified_ns
    source_path = Path(path)
    data = freeze_toml(
        read_toml(
            source_path,
            # The parser hands back an authored sentence describing the decode
            # failure. It is discarded rather than forwarded: it is prose this
            # layer does not own and cannot translate, and forwarding it would
            # put an English sentence into a refusal that resolves through a
            # registered key. Nothing is lost -- ``read_toml`` chains the
            # underlying parse error as the cause, which carries the line and
            # column this sentence only restates.
            error_factory=lambda _message: _schema_load_error(
                source_path,
                operation=_OPERATION_READ,
                condition=CONDITION_SCHEMA_TOML_PARSE,
            ),
        ),
    )
    raw_schema = data.get("schema")
    if not isinstance(raw_schema, dict):
        raise _schema_load_error(
            source_path,
            operation=_OPERATION_VALIDATE,
            condition=CONDITION_SCHEMA_TABLE_PRESENT,
        )
    raw_sections = data.get("sections")
    if not isinstance(raw_sections, tuple) or not raw_sections:
        raise _schema_load_error(
            source_path,
            operation=_OPERATION_VALIDATE,
            condition=CONDITION_SECTIONS_TABLE_PRESENT,
        )
    # ``freeze_toml`` turns TOML arrays into tuples, so the guard mirrors the
    # sections guard above. The key is passed through explicitly because
    # ``model_validate`` receives only the keys named here -- an array left out
    # of this call is parsed and then silently dropped.
    raw_derived_selectors = data.get("derived_selectors", ())
    if not isinstance(raw_derived_selectors, tuple):
        raise _schema_load_error(
            source_path,
            operation=_OPERATION_VALIDATE,
            condition=CONDITION_DERIVED_SELECTORS_ARRAY,
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
        raise _schema_load_error(
            source_path,
            operation=_OPERATION_VALIDATE,
            condition=CONDITION_SCHEMA_MODEL_VALID,
            violation_count=len(exc.errors()),
        ) from exc


def _schema_load_error(
    path: Path,
    *,
    operation: str,
    condition: str,
    violation_count: int | None = None,
) -> UserProfileSchemaLoadError:
    """Build a structured schema-load refusal from facts alone.

    Every caller reaches the refusal through this one factory, so the fact set
    is uniform and the class is never constructed with an authored sentence.
    The failing count is attached only where a count exists; the underlying
    failure survives as the exception's cause rather than being flattened into
    the refusal.
    """
    context: dict[str, object] = {
        "operation": operation,
        "condition": condition,
        "path": str(path),
        "schema": "user_profile",
    }
    if violation_count is not None:
        context["violation_count"] = violation_count
    return UserProfileSchemaLoadError(context=context)
