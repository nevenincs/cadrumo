"""Schema and row-shape helpers for SQL secure-object persistence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Final

from sqlalchemy import Engine, inspect, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .....core.external_constants import UTF_8_ENCODING
from .....core.time import now as _utc_now
from ..errors import StorageValidationError

VARCHAR_64: Final[str] = "VARCHAR(64)"
SECURE_OBJECT_REVISION_METADATA_COLUMNS: tuple[tuple[str, str], ...] = (
    ("revision_id", VARCHAR_64),
    ("previous_revision_id", VARCHAR_64),
    ("revision_ancestor_ids", "TEXT"),
    ("previous_payload_hash", VARCHAR_64),
    ("payload_hash", VARCHAR_64),
    ("ciphertext_hash", VARCHAR_64),
    ("revision_written_at", "DATETIME"),
    ("write_provenance", "VARCHAR(255)"),
    ("source_event_id", "VARCHAR(128)"),
    ("conflict_policy", "VARCHAR(32)"),
)


def ensure_table_revision_metadata_columns(engine: Engine, table_name: str) -> tuple[str, ...]:
    """Add nullable revision metadata columns to a pre-existing table."""
    existing = {column["name"] for column in inspect(engine).get_columns(table_name)}
    missing = tuple(
        (name, column_type) for name, column_type in SECURE_OBJECT_REVISION_METADATA_COLUMNS if name not in existing
    )
    for name, column_type in missing:
        try:
            with engine.begin() as connection:
                connection.execute(
                    # Identifiers come from local revision-metadata constants.
                    text(  # nosemgrep
                        f"ALTER TABLE {table_name} ADD COLUMN {name} {column_type}"
                    )
                )
        except OperationalError as exc:
            if is_duplicate_column_race(engine, table_name, name, exc):
                continue
            raise
    return tuple(name for name, _column_type in missing)


def is_duplicate_column_race(
    engine: Engine,
    table_name: str,
    column_name: str,
    exc: OperationalError,
) -> bool:
    """Return whether ``ALTER TABLE ADD COLUMN`` failed after a concurrent add."""
    if "duplicate column" not in str(exc.orig).lower():
        return False
    existing = {column["name"] for column in inspect(engine).get_columns(table_name)}
    return column_name in existing


def ensure_quarantine_table(engine: Engine) -> None:
    """Create the quarantine archive table with the secure-object metadata shape."""
    with engine.begin() as connection:
        connection.execute(
            # Static bootstrap DDL; no user-controlled SQL reaches this statement.
            text(  # nosemgrep
                "CREATE TABLE IF NOT EXISTS secure_objects_quarantine ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  source_id INTEGER NOT NULL,"
                "  namespace VARCHAR(128) NOT NULL,"
                "  object_key BLOB NOT NULL,"
                "  classification VARCHAR(32) NOT NULL,"
                "  schema_version INTEGER NOT NULL,"
                "  written_at DATETIME NOT NULL,"
                f"  revision_id {VARCHAR_64},"
                f"  previous_revision_id {VARCHAR_64},"
                "  revision_ancestor_ids TEXT,"
                f"  previous_payload_hash {VARCHAR_64},"
                f"  payload_hash {VARCHAR_64},"
                f"  ciphertext_hash {VARCHAR_64},"
                "  revision_written_at DATETIME,"
                "  write_provenance VARCHAR(255),"
                "  source_event_id VARCHAR(128),"
                "  conflict_policy VARCHAR(32),"
                "  payload BLOB NOT NULL,"
                "  quarantined_at DATETIME NOT NULL"
                ")"
            )
        )
    ensure_table_revision_metadata_columns(engine, "secure_objects_quarantine")


def copy_row_to_quarantine(
    session: Session,
    raw: RowMapping,
    *,
    object_key: bytes,
    quarantined_at: str,
) -> None:
    """Copy one raw secure-object row into the quarantine table."""
    payload_bytes = coerce_raw_bytes(raw["payload"])
    session.execute(
        text(
            "INSERT INTO secure_objects_quarantine "
            "(source_id, namespace, object_key, classification, schema_version, "
            " written_at, revision_id, previous_revision_id, revision_ancestor_ids, previous_payload_hash, "
            " payload_hash, ciphertext_hash, revision_written_at, write_provenance, "
            " source_event_id, conflict_policy, payload, quarantined_at) "
            "VALUES (:source_id, :namespace, :object_key, :classification, "
            "        :schema_version, :written_at, :revision_id, "
            "        :previous_revision_id, :revision_ancestor_ids, :previous_payload_hash, :payload_hash, "
            "        :ciphertext_hash, :revision_written_at, :write_provenance, "
            "        :source_event_id, :conflict_policy, :payload, :quarantined_at)"
        ),
        {
            "source_id": int(raw["id"]),
            "namespace": str(raw["namespace"]),
            "object_key": object_key,
            "classification": str(raw["classification"]),
            "schema_version": int(raw["schema_version"]),
            "written_at": raw["written_at"],
            "revision_id": raw["revision_id"],
            "previous_revision_id": raw["previous_revision_id"],
            "revision_ancestor_ids": raw["revision_ancestor_ids"],
            "previous_payload_hash": raw["previous_payload_hash"],
            "payload_hash": raw["payload_hash"],
            "ciphertext_hash": raw["ciphertext_hash"],
            "revision_written_at": raw["revision_written_at"],
            "write_provenance": raw["write_provenance"],
            "source_event_id": raw["source_event_id"],
            "conflict_policy": raw["conflict_policy"],
            "payload": payload_bytes,
            "quarantined_at": quarantined_at,
        },
    )


def coerce_raw_bytes(value: object) -> bytes:
    """Coerce SQLite BLOB/TEXT return values into bytes."""
    if isinstance(value, bytes | bytearray | memoryview):
        return bytes(value)
    if isinstance(value, str):
        return value.encode(UTF_8_ENCODING)
    raise StorageValidationError(
        context={"value_type": type(value).__name__},
        translated_message="errors.integrity.integrity_storage_secure_object_raw_bytes",
    )


def parse_revision_ancestor_ids(raw_value: object) -> tuple[str, ...]:
    """Parse stored secure-object revision ancestry JSON."""
    if raw_value in (None, ""):
        return ()
    if isinstance(raw_value, bytes | bytearray | memoryview):
        text_value = bytes(raw_value).decode(UTF_8_ENCODING)
    else:
        text_value = str(raw_value)
    try:
        parsed = json.loads(text_value)
    except json.JSONDecodeError as exc:
        raise StorageValidationError(
            translated_message="errors.integrity.integrity_storage_secure_object_revision_ancestry_json",
        ) from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) and len(item) == 64 for item in parsed):
        raise StorageValidationError(
            translated_message="errors.integrity.integrity_storage_secure_object_revision_ancestry_shape",
        )
    return tuple(parsed)


def build_revision_ancestor_ids(
    previous_revision_id: str | None,
    previous_revision_ancestor_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Prepend the direct parent revision to the ancestry chain."""
    if previous_revision_id is None:
        return ()
    return (
        previous_revision_id,
        *tuple(item for item in previous_revision_ancestor_ids if item != previous_revision_id),
    )


def database_bytes(value: object) -> bytes:
    """Normalise SQLite bytes-ish values returned through text queries."""
    if isinstance(value, bytes | bytearray | memoryview):
        return bytes(value)
    if isinstance(value, str):
        return value.encode(UTF_8_ENCODING)
    raise TypeError(f"database_bytes: expected bytes-like or str, found {type(value).__name__}")


def database_datetime(value: object) -> datetime:
    """Normalise SQLite datetime values returned through text queries."""
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def quarantine_timestamp() -> str:
    """Return the timestamp format used by secure-object quarantine rows."""
    return _utc_now().isoformat()
