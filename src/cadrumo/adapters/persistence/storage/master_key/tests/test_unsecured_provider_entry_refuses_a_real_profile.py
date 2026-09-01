"""Opting into the published key on a bucket holding real tax data is refused.

The end-to-end form of the NIF canary. Earlier tests covered
the guard's predicate, then its judgement; what remained unexecuted was the
entry path that CALLS it -- ``_provider_enter``, the whole of which coverage
reported as unrun. Until now the link between "the operator entered the
unsecured provider" and "the canary ran" was asserted structurally, by a gate
checking the call exists in the source.

Two properties, and the second is the one a structural gate could never state.

The refusal: entering with a real NIF already stored raises rather than
handing back a session.

The cleanup: after that refusal NO session remains bound. The canary runs
AFTER the session is opened and activated, so a refusal that skipped its
unwind would leave a published-key session live on the context -- refusing at
the door while leaving the door open, and every later column read in that
context would decrypt under a key anyone can read.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.engine.default import DefaultDialect

from ......core.config import load_settings, override_settings
from ......core.storage_taxonomy import StorageCategory
from ......core.storage_taxonomy_locations import bucket_scoped_storage_path
from ...crypto.encrypted_columns import EncryptedBytes
from ...errors import UnsecuredModeRefusedError
from ...secure_object_namespaces import USER_PROFILE_VALUE_NAMESPACE
from ..active_session import activate_session, current_active_bucket_session
from ..bucket_session import BucketSession
from ..master_key import UnsecuredMasterKeyProvider

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "6b6b6b6b-6b6b-46b6-8b6b-6b6b6b6b6b6b"
_REAL_TAX_ID = "12345678Z"
_SYNTHETIC_TAX_ID = "00000000T"


def _seed_profile_row(tax_id: str, root: Path) -> None:
    """Store a profile row encrypted under the PUBLISHED key the provider uses.

    The row must be readable by the session ``_provider_enter`` opens, whose
    DEK is the published constant -- so the seeding session uses the same key,
    taken from the provider's own accessor rather than restated here.
    """
    published = UnsecuredMasterKeyProvider().get_master_key()
    seeding = BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=published,
        dek=published,
        idle_minutes=5,
        opened_at=datetime.now(UTC),
        unsecured_backend=True,
        storage_root=root,
    )
    document = json.dumps({"payload": {"facts": [{"path": "identity.tax_id", "value": tax_id}]}})
    try:
        with activate_session(seeding):
            wire = EncryptedBytes().process_bind_param(document.encode("utf-8"), DefaultDialect())
    finally:
        seeding.close()

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


def test_entering_the_unsecured_provider_on_a_real_profile_refuses(tmp_path: Path) -> None:
    """DISCRIMINATING: the operator-facing form of the guard.

    Not "the canary refuses a NIF" -- that is already covered -- but "asking
    for the published key on this bucket does not get you a session".
    """
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_BUCKET_ID):
        _seed_profile_row(_REAL_TAX_ID, tmp_path)

        with pytest.raises(UnsecuredModeRefusedError, match="real tax id"), UnsecuredMasterKeyProvider():
            pytest.fail("entry must not yield a session for a bucket carrying a real tax id")


def test_a_synthetic_profile_still_opens(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: entry must not fail for every seeded bucket.

    Without this, a provider that raised on any stored profile -- or an entry
    path broken for an unrelated reason -- would satisfy both refusals above
    while making the unsecured backend unusable for the throwaway data it
    exists to serve.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_BUCKET_ID):
        _seed_profile_row(_SYNTHETIC_TAX_ID, tmp_path)

        with UnsecuredMasterKeyProvider() as session:
            assert session is not None
            assert current_active_bucket_session() is session

        assert current_active_bucket_session() is None


def test_a_refused_entry_closes_the_session_it_had_opened(tmp_path: Path) -> None:
    """DISCRIMINATING: the refusal must not leave a published-key session usable.

    ``_provider_enter`` opens and ACTIVATES before the canary runs, so the
    unwind on refusal is what keeps that session from staying live. A guard
    that refused and left it open would be worse than no guard: the operator is
    told no while every later column read in that context decrypts under a key
    anyone can read.

    ``__enter__`` is called directly, and the provider is held, ON PURPOSE. An
    earlier version of this test used a ``with`` block and asserted the
    context-var was clear -- and it PASSED with the unwind removed, because
    dropping every reference let CPython finalise the activation generator and
    reset the binding as a side effect of refcounting. The test was measuring
    garbage collection, not the guard.

    What only the unwind does is seal the session and detach the bookkeeping,
    so that is what is asserted.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_BUCKET_ID):
        _seed_profile_row(_REAL_TAX_ID, tmp_path)
        provider = UnsecuredMasterKeyProvider()

        with pytest.raises(UnsecuredModeRefusedError):
            provider.__enter__()

        assert provider.session is None, "the refused entry left its session on the provider"
        assert provider._activation_cm is None, "the refused entry left its activation attached"
        assert current_active_bucket_session() is None, "the refused entry left a published-key session bound"
