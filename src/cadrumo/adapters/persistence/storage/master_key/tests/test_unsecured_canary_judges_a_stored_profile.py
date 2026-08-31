"""The canary judges a profile row it can actually read.

``refuse_unsecured_bucket_with_real_profile`` is the guard between a real
taxpayer's records and a PUBLISHED deterministic key. Its early exits were
covered -- no database, no rows, an unreadable file, an undecryptable payload,
the ``unsecured`` label bucket -- and every one of those ends before the
function reaches a tax id.

The branch that decides was unexecuted. Coverage put ``_master_key`` at 62%
with the extraction and refusal lines among the gaps, so what stood behind the
guard was a structural gate asserting the call EXISTS and unit tests of the
predicate in isolation. Neither runs the path where a stored profile is
decrypted and judged.

These do. A profile envelope is encrypted through the same ``EncryptedBytes``
column the repository writes with, stored as a real row in a real bucket
database, and read back by the canary under an active unsecured session. The
only difference between the two cases is the tax id in the payload.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.engine.default import DefaultDialect

from ......core import StorageCategory, bucket_scoped_storage_path
from ......core.config import load_settings, override_settings
from ..._secure_object_namespaces import USER_PROFILE_VALUE_NAMESPACE
from ...crypto.encrypted_columns import EncryptedBytes
from ...errors import UnsecuredModeRefusedError
from .._active_session import activate_session
from .._bucket_session import BucketSession
from .._master_key import refuse_unsecured_bucket_with_real_profile

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "7c7c7c7c-7c7c-47c7-8c7c-7c7c7c7c7c7c"
_REAL_TAX_ID = "12345678Z"
_SYNTHETIC_TAX_ID = "00000000T"


def _unsecured_session(root: Path) -> BucketSession:
    """Open a session flagged as running on the published deterministic key."""
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=b"k" * 32,
        dek=b"d" * 32,
        idle_minutes=5,
        opened_at=datetime.now(UTC),
        unsecured_backend=True,
        storage_root=root,
    )


def _store_profile_row(tax_id: str) -> None:
    """Encrypt a profile envelope and store it as a real secure-objects row.

    Encryption goes through the same column type the repository binds with, so
    the bytes on disk are produced the way production produces them rather
    than by a fixture's own idea of the format.
    """
    document = json.dumps({"payload": {"facts": [{"path": "identity.tax_id", "value": tax_id}]}})
    wire = EncryptedBytes().process_bind_param(document.encode("utf-8"), DefaultDialect())

    database = bucket_scoped_storage_path(StorageCategory.BUCKET_DATABASE_FILE, _BUCKET_ID, settings=load_settings())
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS secure_objects (namespace TEXT, payload BLOB)")
        connection.execute(
            "INSERT INTO secure_objects (namespace, payload) VALUES (?, ?)",
            (USER_PROFILE_VALUE_NAMESPACE.namespace, wire),
        )
        connection.commit()
    finally:
        connection.close()


def test_a_stored_real_tax_id_refuses_the_published_key(tmp_path: Path) -> None:
    """DISCRIMINATING: the case the whole guard exists for.

    A bucket already holding a real NIF must not be opened under a key anyone
    can read. Everything covered before this ended earlier in the function, so
    this is the first execution of the judgement itself.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path):
        session = _unsecured_session(tmp_path)
        with activate_session(session):
            _store_profile_row(_REAL_TAX_ID)

            with pytest.raises(UnsecuredModeRefusedError, match="real tax id"):
                refuse_unsecured_bucket_with_real_profile(session)
        session.close()


def test_a_stored_synthetic_tax_id_is_admitted(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the guard must not refuse every readable profile.

    Without this, a canary that raised on ANY decryptable row would satisfy
    the refusal above while making the unsecured backend unusable for the
    throwaway data it exists to serve -- and the refusal would prove only that
    something failed, not that a NIF was recognised.

    The two cases differ in one value: the tax id in the payload.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path):
        session = _unsecured_session(tmp_path)
        with activate_session(session):
            _store_profile_row(_SYNTHETIC_TAX_ID)

            refuse_unsecured_bucket_with_real_profile(session)
        session.close()
