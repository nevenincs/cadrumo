"""Schema and row-shape helpers for SQL secure-object persistence."""

from __future__ import annotations

import json
import re
from typing import Final

from sqlalchemy import Engine, text

from .....core.external_constants import UTF_8_ENCODING
from .....core.hex import HEX_PATTERN_64
from .....core.time.clock import now as _utc_now
from ..errors import StorageValidationError

VARCHAR_64: Final[str] = "VARCHAR(64)"

_REVISION_ID_RE: Final[re.Pattern[str]] = re.compile(HEX_PATTERN_64)
"""Revision ids are :func:`sha256_hex` output, so lowercase hex is the whole shape."""


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
                ")",
            ),
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
    if not isinstance(parsed, list):
        raise StorageValidationError(
            translated_message="errors.integrity.integrity_storage_secure_object_revision_ancestry_shape",
        )
    revision_ids: list[str] = []
    for item in parsed:
        if not isinstance(item, str) or _REVISION_ID_RE.fullmatch(item) is None:
            raise StorageValidationError(
                translated_message="errors.integrity.integrity_storage_secure_object_revision_ancestry_shape",
            )
        revision_ids.append(item)
    return tuple(revision_ids)


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


def quarantine_timestamp() -> str:
    """Return the timestamp format used by secure-object quarantine rows."""
    return _utc_now().isoformat()
