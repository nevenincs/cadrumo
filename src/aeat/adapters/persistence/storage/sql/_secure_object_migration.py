"""Bootstrap migrations for SQL secure-object persistence."""

from __future__ import annotations

from logging import Logger

from sqlalchemy import Engine, text
from sqlalchemy.engine import RowMapping

from ..crypto._encrypted_columns import HashedLookup, decrypt_encrypted_string_column
from ..errors import DecryptionError
from ._secure_object_schema import (
    coerce_raw_bytes,
    copy_row_to_quarantine,
    ensure_quarantine_table,
    quarantine_timestamp,
)
from .session import session_scope


def ensure_deterministic_object_keys(engine: Engine, *, logger: Logger) -> None:
    """Migrate legacy randomized object-key ciphertexts to HMAC digests."""
    with session_scope(engine) as session:
        rows = (
            session.execute(
                text(
                    "SELECT id, namespace, object_key, classification, schema_version, written_at, "
                    "revision_id, previous_revision_id, revision_ancestor_ids, "
                    "previous_payload_hash, payload_hash, "
                    "ciphertext_hash, revision_written_at, write_provenance, source_event_id, "
                    "conflict_policy, payload "
                    "FROM secure_objects ORDER BY namespace, id"
                )
            )
            .mappings()
            .all()
        )
        if not rows:
            return

        grouped: dict[tuple[str, bytes], list[tuple[RowMapping, bytes]]] = {}
        unmigratable: list[tuple[RowMapping, bytes]] = []
        for raw in rows:
            namespace = str(raw["namespace"])
            raw_key = coerce_raw_bytes(raw["object_key"])
            try:
                natural_key = decrypt_encrypted_string_column(raw_key)
            except DecryptionError:
                if len(raw_key) == 32:
                    grouped.setdefault((namespace, raw_key), []).append((raw, raw_key))
                else:
                    unmigratable.append((raw, raw_key))
                continue
            target_key = HashedLookup.compute(natural_key)
            grouped.setdefault((namespace, target_key), []).append((raw, raw_key))

        if unmigratable or any(len(entries) > 1 for entries in grouped.values()):
            ensure_quarantine_table(engine)
        quarantined_at = quarantine_timestamp()
        for raw, raw_key in unmigratable:
            logger.debug("secure_objects: quarantining unmigratable legacy object key id=%s", int(raw["id"]))
            copy_row_to_quarantine(session, raw, object_key=raw_key, quarantined_at=quarantined_at)
            session.execute(text("DELETE FROM secure_objects WHERE id = :id"), {"id": int(raw["id"])})

        for (_namespace, target_key), entries in grouped.items():
            winner, winner_key = max(entries, key=_lookup_migration_sort_key)
            for raw, raw_key in entries:
                if int(raw["id"]) == int(winner["id"]):
                    continue
                copy_row_to_quarantine(session, raw, object_key=raw_key, quarantined_at=quarantined_at)
                session.execute(text("DELETE FROM secure_objects WHERE id = :id"), {"id": int(raw["id"])})
            if winner_key != target_key:
                session.execute(
                    text("UPDATE secure_objects SET object_key = :object_key WHERE id = :id"),
                    {"object_key": target_key, "id": int(winner["id"])},
                )


def _lookup_migration_sort_key(entry: tuple[RowMapping, bytes]) -> tuple[str, str, int]:
    raw, _raw_key = entry
    revision_written_at = raw["revision_written_at"] or ""
    written_at = raw["written_at"] or ""
    return (str(revision_written_at), str(written_at), int(raw["id"]))
