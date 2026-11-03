"""Publish a later authority generation into a private root, for tests of what a publication leaves unchanged.

A full publication compiles and proves the whole registry and writes a database
of over a hundred megabytes, so a test that needs several generations derives
each from the one before it. A derived generation is a real published pair: its
database is the previous generation's with the named revision components
rewritten through the registry's own JSON frame, a new logical generation in its
manifest and a descriptor that names it by its digest. The reader admits it by
that digest and decodes every rewritten component through the typed codec, so a
declaration that no longer parses is refused at load rather than accepted here.

Only the private root is written. The bundled registry tree and the shared
authority are read, never changed.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from collections.abc import Callable, Mapping
from contextlib import closing
from pathlib import Path
from typing import Any, Final

from ....core.hashing import canonical_json_bytes, hash_file, sha256_hex
from ....domain.calculations.registry.authority_store import AUTHORITY_DESCRIPTOR_FILENAME, AuthorityDescriptor

__all__ = ["RevisionEdit", "publish_derived_generation"]

type RevisionEdit = Callable[[dict[str, Any]], None]
"""Rewrites one decoded revision payload in place."""

_REVISION_KIND: Final = "modelo_revision"
_KEY_SEPARATOR: Final = "\x1f"


def publish_derived_generation(
    root: Path, *, label: str, revision_edits: Mapping[tuple[str, str], RevisionEdit] | None = None
) -> AuthorityDescriptor:
    """Publish a generation derived from the one ``root`` currently selects, and return its descriptor.

    Args:
        root: A private authority root holding a descriptor and the database it selects.
        label: Names the new generation; the same label over the same predecessor derives the same identity.
        revision_edits: Per ``(modelo, revision id)``, the edit applied to that revision's payload. Every
            other component is carried over unchanged.

    Raises:
        LookupError: An edit names a revision the predecessor does not hold.
    """
    descriptor_path = root / AUTHORITY_DESCRIPTOR_FILENAME
    predecessor = AuthorityDescriptor.read(descriptor_path)
    staged = root / f"candidate-{label}.sqlite3"
    shutil.copyfile(root / predecessor.database, staged)
    logical_generation = sha256_hex(f"{predecessor.logical_generation}:{label}".encode("ascii"))
    with closing(sqlite3.connect(staged)) as connection:
        connection.execute("PRAGMA journal_mode = DELETE")
        for (modelo, revision_id), edit in (revision_edits or {}).items():
            _rewrite_revision(connection, f"{modelo}{_KEY_SEPARATOR}{revision_id}", edit)
        connection.execute(
            "UPDATE authority_manifest SET logical_generation = ? WHERE singleton = 1", (logical_generation,)
        )
        connection.commit()
    digest, size = hash_file(staged)
    database = f"authority-{digest}.sqlite3"
    staged.replace(root / database)
    descriptor = AuthorityDescriptor(
        database=database, database_size=size, database_sha256=digest, logical_generation=logical_generation
    )
    pending = root / f"{AUTHORITY_DESCRIPTOR_FILENAME}.{label}.pending"
    pending.write_bytes(descriptor.to_bytes())
    os.replace(pending, descriptor_path)
    return descriptor


def _rewrite_revision(connection: sqlite3.Connection, key: str, edit: RevisionEdit) -> None:
    row = connection.execute(
        "SELECT payload, retained_weight FROM components WHERE kind = ? AND key = ?", (_REVISION_KIND, key)
    ).fetchone()
    if row is None:
        raise LookupError(f"the predecessor generation holds no revision {key!r}")
    payload, weight = row
    frame = json.loads(payload)
    edit(frame["payload"])
    rewritten = canonical_json_bytes(frame)
    connection.execute(
        "UPDATE components SET payload = ?, payload_sha256 = ?, retained_weight = ? WHERE kind = ? AND key = ?",
        (rewritten, sha256_hex(rewritten), weight + max(0, len(rewritten) - len(payload)), _REVISION_KIND, key),
    )
