"""End-to-end read-side schema upgrade through the secure-object repository.

Proves the durability contract on the real substrate: a row
written under an older ``schema_version`` decrypts under its written
version and is chain-upgraded to the consumer's current version on read —
through the real repository, real engine, real crypto, and the real
module-level upgrader registry — while the on-disk row (ciphertext,
version stamp, revision lineage) is left untouched.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...schema_lineage import (
    deregister_secure_object_schema_upgrader,
    register_secure_object_schema_upgrader,
)
from ._secure_objects_support import (
    EnvelopeVersionError,
    SensitivityClass,
    _ephemeral_secure_repo,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_older_row_upgrades_through_registered_chain_on_read(tmp_path: Path) -> None:
    """A v1 row reads as a v2 record once the 1-to-2 upgrader is registered."""
    with _ephemeral_secure_repo(tmp_path, "lineage-upgrade.db") as (db_path, _engine, repo):
        namespace = "cadrumo-test.lineage.upgrade"
        natural_key = "record-key"
        repo.save(
            namespace=namespace,
            object_key=natural_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime(2026, 7, 8, 9, 0, 0, tzinfo=UTC),
            payload=b"written-at-v1",
        )

        register_secure_object_schema_upgrader(
            namespace,
            1,
            lambda payload: payload + b"|upgraded-1to2",
        )
        try:
            record = repo.load(
                namespace,
                natural_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=2,
            )
            listed = list(
                repo.list_records(
                    namespace,
                    expected_class=SensitivityClass.FINANCIAL,
                    max_supported_version=2,
                ),
            )
        finally:
            deregister_secure_object_schema_upgrader(namespace, 1)

        assert record is not None
        assert record.payload == b"written-at-v1|upgraded-1to2"
        assert record.schema_version == 2
        assert [item.payload for item in listed] == [b"written-at-v1|upgraded-1to2"]
        assert [item.schema_version for item in listed] == [2]

        # The read-side upgrade is in-memory only: the stored row keeps its
        # written version stamp so its AEAD binding and revision lineage
        # remain verifiable.
        with sqlite3.connect(db_path) as con:
            (stored_version,) = con.execute(
                "SELECT schema_version FROM secure_objects WHERE namespace = ?",
                (namespace,),
            ).fetchone()
        assert stored_version == 1

        # With the upgrader gone the same row refuses loudly again, naming
        # the missing hop — never a silent blank or a stale-shaped payload.
        with pytest.raises(EnvelopeVersionError) as raised:
            repo.load(
                namespace,
                natural_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=2,
            )
        assert raised.value.translated_message == "errors.storage.namespace.schema_upgrade_path_missing"
        assert raised.value.context == {
            "namespace": namespace,
            "schema_version": 1,
            "expected": 2,
            "missing_from_version": 1,
        }
