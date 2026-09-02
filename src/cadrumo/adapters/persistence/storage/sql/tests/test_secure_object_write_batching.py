"""The set-based write funnel: statement budget, in-batch lineage, and guards.

The write funnel executes a batch with set-based SQL — one previous-metadata
read per namespace slice, one ``INSERT`` executemany for absent rows, one
lineage-guarded ``UPDATE`` executemany for present rows. These tests pin the
properties that make that shape safe to keep:

- the statement budget is a COUNT of SQL statements, never a wall-clock
  duration, so the regression gate is deterministic under parallel load;
- a batch repeating one ``(namespace, object_key)`` chains revisions exactly
  as sequential saves would;
- a concurrent writer landing between the batch's lineage read and its
  guarded update is refused loudly instead of being orphaned from the
  revision chain;
- the batch existence read reports exactly the stored subset;
- a row the batch wrote refuses to decrypt once its ciphertext is tampered
  (the anti-tautology proof that the roundtrips above test something real).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event

from ......core.classification.policies import SensitivityClass
from ......core.secure_object_write import SecureObjectWrite
from ...errors import DecryptionError, SecureObjectRevisionConflictError
from ._secure_objects_support import _ephemeral_secure_repo

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo-test.write.batching"
_WRITTEN_AT = datetime(2026, 5, 22, 18, 0, 0, tzinfo=UTC)


def _write(key: str, payload: bytes, *, written_at: datetime = _WRITTEN_AT) -> SecureObjectWrite:
    return SecureObjectWrite(
        namespace=_NAMESPACE,
        object_key=key,
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=written_at,
        payload=payload,
    )


@contextmanager
def _statement_log(engine: Any) -> Generator[list[str]]:
    """Record the first SQL verb of every cursor execution on ``engine``.

    An ``executemany`` batch is one cursor execution regardless of how many
    parameter sets it carries, which is exactly the property the budget gate
    asserts.
    """
    statements: list[str] = []

    def _record(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,  # SQLAlchemy event signature
    ) -> None:
        statements.append(statement.split(None, 1)[0].upper())

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _record)


def test_save_many_statement_budget_is_constant_per_batch(tmp_path: Path) -> None:
    """A fresh batch costs one read plus one insert; an overwrite batch one read plus one update.

    The gate counts statements, not milliseconds: the per-row funnel this
    replaced issued five statements per row, so a regression to per-row SQL
    is a count explosion this assertion catches deterministically.
    """
    with _ephemeral_secure_repo(tmp_path, "statement-budget.db") as (_db_path, engine, repo):
        fresh = tuple(_write(f"budget-{i}", b"payload-%d" % i) for i in range(50))
        with _statement_log(engine) as statements:
            repo.save_many(fresh)
        assert statements == ["SELECT", "INSERT"]

        overwrite = tuple(_write(f"budget-{i}", b"overwrite-%d" % i) for i in range(50))
        with _statement_log(engine) as statements:
            repo.save_many(overwrite)
        assert statements == ["SELECT", "UPDATE"]


def test_in_batch_duplicate_key_chains_revisions_like_sequential_saves(tmp_path: Path) -> None:
    """A batch writing one key twice links the second revision to the first."""
    with _ephemeral_secure_repo(tmp_path, "duplicate-chain.db") as (db_path, _engine, repo):
        repo.save_many(
            (
                _write("dup-key", b"first-payload"),
                _write("dup-key", b"second-payload", written_at=datetime(2026, 5, 22, 18, 5, 0, tzinfo=UTC)),
            ),
        )
        with sqlite3.connect(db_path) as con:
            row = con.execute(
                "SELECT revision_id, previous_revision_id, revision_ancestor_ids, payload_hash, "
                "previous_payload_hash FROM secure_objects WHERE namespace = ?",
                (_NAMESPACE,),
            ).fetchone()
        revision_id, previous_revision_id, ancestor_ids_json, payload_hash, previous_payload_hash = row
        assert previous_revision_id is not None
        assert revision_id != previous_revision_id
        assert json.loads(ancestor_ids_json) == [previous_revision_id]
        assert payload_hash == hashlib.sha256(b"second-payload").hexdigest()
        assert previous_payload_hash == hashlib.sha256(b"first-payload").hexdigest()

        # The chained row must pass its own read-time self-consistency gate.
        record = repo.load(
            _NAMESPACE,
            "dup-key",
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=1,
        )
        assert record is not None
        assert record.payload == b"second-payload"


def test_concurrent_mutation_between_read_and_guarded_update_is_refused(tmp_path: Path) -> None:
    """A writer landing between the lineage read and the update cannot be orphaned.

    The interleaving is driven through SQLAlchemy's real cursor-execution
    event: the moment the batch's UPDATE reaches the cursor, a second raw
    connection moves the stored ``revision_id`` out from under it — the
    guarded update then matches nothing, and the funnel must surface a
    revision conflict rather than silently dropping the concurrent revision
    from the chain.
    """
    with _ephemeral_secure_repo(tmp_path, "guarded-update-race.db") as (db_path, engine, repo):
        repo.save_many((_write("raced-key", b"initial-payload"),))
        forged_revision = "f" * 64
        fired: list[bool] = []

        def _side_write(
            conn: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,  # SQLAlchemy event signature
        ) -> None:
            if fired or not statement.lstrip().upper().startswith("UPDATE"):
                return
            fired.append(True)
            with sqlite3.connect(db_path) as con:
                con.execute(
                    "UPDATE secure_objects SET revision_id = ? WHERE namespace = ?",
                    (forged_revision, _NAMESPACE),
                )

        event.listen(engine, "before_cursor_execute", _side_write)
        try:
            with pytest.raises(SecureObjectRevisionConflictError) as raised:
                repo.save_many((_write("raced-key", b"overwrite-payload"),))
        finally:
            event.remove(engine, "before_cursor_execute", _side_write)

        assert raised.value.context is not None
        assert raised.value.context["current_revision_id"] == forged_revision
        # The refused batch rolled back: the concurrent revision survives.
        with sqlite3.connect(db_path) as con:
            (revision_id, payload_hash) = con.execute(
                "SELECT revision_id, payload_hash FROM secure_objects WHERE namespace = ?",
                (_NAMESPACE,),
            ).fetchone()
        assert revision_id == forged_revision
        assert payload_hash == hashlib.sha256(b"initial-payload").hexdigest()


def test_exists_many_reports_exactly_the_stored_subset(tmp_path: Path) -> None:
    """Batch existence equals per-key existence over stored, absent, and empty inputs."""
    with _ephemeral_secure_repo(tmp_path, "exists-many.db") as (_db_path, _engine, repo):
        repo.save_many((_write("present-a", b"a"), _write("present-b", b"b")))
        present = repo.exists_many(_NAMESPACE, ("present-a", "present-b", "absent-c"))
        assert present == frozenset({"present-a", "present-b"})
        assert repo.exists(_NAMESPACE, "present-a") is True
        assert repo.exists(_NAMESPACE, "absent-c") is False
        assert repo.exists_many(_NAMESPACE, ()) == frozenset()


def test_batch_written_row_refuses_tampered_ciphertext(tmp_path: Path) -> None:
    """Anti-tautology proof: corrupt the stored wire bytes, and the load fails closed."""
    with _ephemeral_secure_repo(tmp_path, "tampered-batch-row.db") as (db_path, _engine, repo):
        repo.save_many((_write("tampered-key", b"authentic-payload"),))
        with sqlite3.connect(db_path) as con:
            (payload_wire,) = con.execute(
                "SELECT payload FROM secure_objects WHERE namespace = ?",
                (_NAMESPACE,),
            ).fetchone()
            corrupted = bytes(payload_wire[:-1]) + bytes([payload_wire[-1] ^ 0x01])
            con.execute(
                "UPDATE secure_objects SET payload = ? WHERE namespace = ?",
                (corrupted, _NAMESPACE),
            )
        with pytest.raises(DecryptionError):
            repo.load(
                _NAMESPACE,
                "tampered-key",
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=1,
            )
