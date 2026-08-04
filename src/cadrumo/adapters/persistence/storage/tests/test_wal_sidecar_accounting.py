"""WAL-sidecar accounting for at-rest scans and the sealed-archive export.

The bucket databases run in WAL mode with ``synchronous=NORMAL``, so a
just-committed row lives in the ``<db>-wal`` sidecar until a checkpoint folds it
into the main ``.db`` file. Two surfaces must account for the sidecar or they
silently miss committed-but-uncheckpointed rows:

Every at-rest plaintext-scan surface. The shared ``read_db_at_rest_bytes``
helper concatenates the main file with its ``-wal`` sidecar; a scan that read
only the main file would pass *tautologically* (no plaintext leaked because the
data is not in the file being scanned). This test writes a REAL committed row,
leaves it uncheckpointed, and proves the helper's combined view carries bytes a
main-file-only read misses.

The sealed-archive export. The export payload is built by
``serialize_profile_bundle``, which reads every secure object through the SQL
query layer (not a raw file copy), so a committed-but-uncheckpointed WAL row is
inherently included. This test proves the query layer returns a row that the raw
main ``.db`` file does not yet carry, so a sealed bundle built from it carries
every committed row regardless of checkpoint state.

Real active-profile runtime, real encrypted SQLite, no mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....tests.secure_sql import isolated_runtime_profile, read_db_at_rest_bytes
from ..attachment import AttachmentStore

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_ROW_BLOB = b"committed-but-uncheckpointed financial payload for the WAL accounting test"


def test_at_rest_scan_reads_a_committed_row_from_the_wal_sidecar(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        # A real committed secure-object write. In WAL mode with no checkpoint,
        # the row's ciphertext lands in the -wal sidecar, not the main .db file.
        AttachmentStore(objects=profile.repository).put_bytes(_ROW_BLOB)

        db_path = profile.paths.database_file
        wal_path = db_path.with_name(db_path.name + "-wal")

        # The sidecar exists and carries the committed delta.
        assert wal_path.exists(), "expected a -wal sidecar for the uncheckpointed row"
        assert wal_path.stat().st_size > 0

        main_only = db_path.read_bytes()
        combined = read_db_at_rest_bytes(db_path)

        # Anti-tautology: a main-file-only read is strictly smaller than the
        # combined view — the committed row lives in the sidecar the helper
        # folds in. An at-rest scan over the main file alone would miss it.
        assert len(combined) > len(main_only), (
            "the at-rest scan helper did not fold in the -wal sidecar; committed rows would be missed"
        )
        assert combined.startswith(main_only)
        assert combined.endswith(wal_path.read_bytes())


def test_sql_read_layer_carries_an_uncheckpointed_row_for_the_sealed_export(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        store = AttachmentStore(objects=profile.repository)
        digest = store.put_bytes(_ROW_BLOB)

        db_path = profile.paths.database_file
        wal_path = db_path.with_name(db_path.name + "-wal")

        # The committed row is in the WAL sidecar, not yet folded into main.
        assert wal_path.exists() and wal_path.stat().st_size > 0

        # The SQL read layer — the same layer ``serialize_profile_bundle`` uses
        # to build the sealed-archive payload — returns the committed row even
        # though no checkpoint has folded it into the main .db file. A sealed
        # bundle built from this read therefore carries every committed row.
        assert store.read_bytes(digest) == _ROW_BLOB

        # Anti-tautology: the sealed export reads through SQL precisely because a
        # raw main-file copy would be insufficient — the combined at-rest view
        # (main + sidecar) is strictly larger than the main file alone, proving
        # the row is not yet in the copy-able main file.
        assert len(read_db_at_rest_bytes(db_path)) > len(db_path.read_bytes())
