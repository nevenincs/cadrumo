"""Storage route derivation helpers for core settings.

This module implements the public :func:`~core.config.classify_storage_route`
and :func:`~core.config.settings_for_active_profile_bucket` facades. It
classifies :class:`~core.config.Settings` into a
:class:`~core.config.StorageRouteClassification` whose
:class:`~core.config.StorageRouteKind` distinguishes explicit database
URLs, root-fallback SQLite databases, and active-profile bucket databases.

Application write guards such as
:func:`~application.storage_write_policy.inspect_storage_write_policy`
consume that route classification rather than re-parsing database URLs.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote

from ._config_state_root import PRODUCT_DATABASE_FILENAME
from ._storage_taxonomy import StorageCategory, storage_location, storage_path
from .errors.hierarchy import CoreValidationError

if TYPE_CHECKING:
    from .config import Settings, StorageRouteClassification


def classify_storage_route_for_settings(settings: Settings) -> StorageRouteClassification:
    """Classify the effective primary SQL route.

    Args:
        settings: The :class:`~core.config.Settings` instance whose
            ``cadrumo_database_url`` and ``cadrumo_local_storage_root`` define the
            route.

    Returns:
        A :class:`~core.config.StorageRouteClassification` carrying the
        effective :class:`~core.config.StorageRouteKind`, database URL,
        filesystem path when SQLite-backed, and active bucket id when present.
    """
    from .config import StorageRouteClassification, StorageRouteKind

    database_url = settings.cadrumo_database_url
    database_path = _sqlite_database_path(database_url)
    if "cadrumo_database_url" in settings.model_fields_set:
        return StorageRouteClassification(
            kind=StorageRouteKind.EXPLICIT_DATABASE_URL,
            database_url=database_url,
            database_path=database_path,
        )
    root_fallback = _normalized_path(storage_path(StorageCategory.ROOT_FALLBACK_DATABASE, settings=settings))
    if database_path is not None and _normalized_path(database_path) == root_fallback:
        return StorageRouteClassification(
            kind=StorageRouteKind.ROOT_FALLBACK_DATABASE,
            database_url=database_url,
            database_path=database_path,
        )
    bucket_id = _bucket_id_for_route(
        database_path=database_path,
        storage_root=settings.cadrumo_local_storage_root,
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
    """Return settings routed to ``bucket_id``'s active-profile database.

    Args:
        bucket_id: Active-profile bucket id to embed in the returned
            :class:`~core.config.Settings`.
        source: Source :class:`~core.config.Settings` whose non-route
            fields are preserved.

    Returns:
        A :class:`~core.config.Settings` instance equivalent to ``source``
        but deriving ``cadrumo_database_url`` from ``bucket_id``.

    Raises:
        CoreValidationError: When ``bucket_id`` is blank or ``source`` already
            carries an explicit database URL.
    """
    from .config import Settings

    trimmed = bucket_id.strip()
    if not trimmed:
        raise CoreValidationError("bucket_id must not be blank")
    if "cadrumo_database_url" in source.model_fields_set:
        raise CoreValidationError("cannot derive an active profile bucket route from an explicit database URL")
    values = source.model_dump()
    values.pop("cadrumo_database_url", None)
    values["cadrumo_active_profile"] = trimmed
    derived = Settings.model_validate(values)
    explicit_fields = (source.model_fields_set - {"cadrumo_database_url"}) | {"cadrumo_active_profile"}
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
    # Read from the one core storage authority rather than re-typing the two
    # names here. This classifier used to carry its own copy of ``buckets`` and
    # ``db``, unpinned against the layout that actually provisions them, so a
    # rename would leave it silently classifying every bucket database as an
    # explicit URL -- the branch below returns "" and the caller reads that as
    # "not a bucket route" rather than as a failure to recognise one.
    buckets_dirname = storage_location(StorageCategory.BUCKETS).subpath
    bucket_db_dirname = storage_location(StorageCategory.BUCKET_DATABASE).subpath
    parts = relative.parts
    if len(parts) == 4 and parts[0] == buckets_dirname and parts[2:] == (bucket_db_dirname, PRODUCT_DATABASE_FILENAME):
        return parts[1]
    return ""


__all__ = ["classify_storage_route_for_settings", "settings_for_bucket_route"]
