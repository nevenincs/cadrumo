"""Storage route derivation helpers for core settings.

This module uses :class:`Settings` and :class:`StorageRouteClassification`
for SQL database route classification.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote

from .errors import CoreValidationError

if TYPE_CHECKING:
    from .config import Settings, StorageRouteClassification


def classify_storage_route_for_settings(settings: Settings) -> StorageRouteClassification:
    """Classify the effective primary SQL route and return a :class:`StorageRouteClassification`."""
    from .config import StorageRouteClassification, StorageRouteKind

    database_url = settings.aeat_database_url
    database_path = _sqlite_database_path(database_url)
    if "aeat_database_url" in settings.model_fields_set:
        return StorageRouteClassification(
            kind=StorageRouteKind.EXPLICIT_DATABASE_URL,
            database_url=database_url,
            database_path=database_path,
        )
    root_fallback = _normalized_path(settings.aeat_local_storage_root / "aeat.db")
    if database_path is not None and _normalized_path(database_path) == root_fallback:
        return StorageRouteClassification(
            kind=StorageRouteKind.ROOT_FALLBACK_DATABASE,
            database_url=database_url,
            database_path=database_path,
        )
    bucket_id = _bucket_id_for_route(
        database_path=database_path,
        storage_root=settings.aeat_local_storage_root,
    )
    if bucket_id:
        return StorageRouteClassification(
            kind=StorageRouteKind.ACTIVE_BUCKET_DATABASE,
            database_url=database_url,
            database_path=database_path,
            bucket_id=bucket_id,
        )
    return StorageRouteClassification(
        kind=StorageRouteKind.EXPLICIT_DATABASE_URL,
        database_url=database_url,
        database_path=database_path,
    )


def settings_for_bucket_route(bucket_id: str, source: Settings) -> Settings:
    """Return a :class:`Settings` instance routed to ``bucket_id``'s active-profile database."""
    from .config import Settings

    trimmed = bucket_id.strip()
    if not trimmed:
        raise CoreValidationError("bucket_id must not be blank")
    if "aeat_database_url" in source.model_fields_set:
        raise CoreValidationError("cannot derive an active profile bucket route from an explicit database URL")
    values = source.model_dump()
    values.pop("aeat_database_url", None)
    values["aeat_active_profile"] = trimmed
    derived = Settings.model_validate(values)
    explicit_fields = (source.model_fields_set - {"aeat_database_url"}) | {"aeat_active_profile"}
    object.__setattr__(derived, "__pydantic_fields_set__", explicit_fields)
    return derived


def _sqlite_database_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None
    return Path(unquote(database_url.removeprefix("sqlite:///")))


def _normalized_path(path: Path) -> Path:
    return path.expanduser().resolve()


def _bucket_id_for_route(*, database_path: Path | None, storage_root: Path) -> str:
    if database_path is None:
        return ""
    try:
        relative = _normalized_path(database_path).relative_to(_normalized_path(storage_root))
    except ValueError:
        return ""
    parts = relative.parts
    if len(parts) == 4 and parts[0] == "buckets" and parts[2:] == ("db", "aeat.db"):
        return parts[1]
    return ""


__all__ = ["classify_storage_route_for_settings", "settings_for_bucket_route"]
