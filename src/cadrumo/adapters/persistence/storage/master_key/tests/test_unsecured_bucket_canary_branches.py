"""What the bucket-level canary does when it cannot prove a profile synthetic.

The sibling module covers the tax-id decision. This one covers the branch
BEFORE it: ``refuse_unsecured_bucket_with_real_profile`` has to reach a
bucket's stored profile at all, and the interesting cases are the ones where it
cannot. An unreadable database or an undecryptable payload leaves the canary
unable to answer the only question it exists to answer, and the safe answer to
"I cannot tell whether this is real tax data" is to refuse the published
zero-confidentiality key.

Its own source says so -- the comment on the sqlite branch records that an
earlier revision returned there, silently downgrading the check and admitting
the published key on profiles that may have held real tax ids. That regression
is precisely what this module pins, and nothing was asserting it.

Both directions again, because a canary that refused every bucket would satisfy
the fail-closed cases while making unsecured mode unusable. The admitting cases
are therefore part of the contract, not filler -- and one of them carries a real
ordering gap, recorded in the campaign audit and named in its own docstring
below.

The refusals are driven by corrupting a REAL bucket database created by the real
runtime, not by a hand-built table: a fabricated schema would keep agreeing with
itself if production moved.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core.config import load_settings, override_settings
from ......core.storage_taxonomy import StorageCategory
from ......core.storage_taxonomy_locations import bucket_scoped_storage_path
from ....tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ...errors import UnsecuredModeRefusedError
from ...secure_object_namespaces import USER_PROFILE_VALUE_NAMESPACE
from .._master_key import refuse_unsecured_bucket_with_real_profile
from ..bucket_session import BucketSession

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "5a5a5a5a-5a5a-45a5-8a5a-5a5a5a5a5a5a"

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _unsecured_session(bucket_id: str, root: Path) -> BucketSession:
    """Open a session flagged as running on the published deterministic key."""
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=b"k" * 32,
        dek=b"d" * 32,
        idle_minutes=5,
        opened_at=datetime.now(UTC),
        unsecured_backend=True,
        storage_root=root,
    )


def _bucket_database(bucket_id: str) -> Path:
    """Resolve the real on-disk database path for ``bucket_id``."""
    return bucket_scoped_storage_path(
        StorageCategory.BUCKET_DATABASE_FILE,
        bucket_id,
        settings=load_settings(),
    )


def test_an_unreadable_bucket_database_refuses(tmp_path: Path) -> None:
    """DISCRIMINATING: the branch whose own comment records the old regression.

    A database that cannot be opened means the canary cannot prove the profile
    synthetic. Returning here -- which an earlier revision did -- admits the
    published key onto a bucket that may hold a real NIF.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path):
        database = _bucket_database(_BUCKET_ID)
        database.parent.mkdir(parents=True, exist_ok=True)
        database.write_bytes(b"this is not a sqlite database")

        with pytest.raises(UnsecuredModeRefusedError):
            refuse_unsecured_bucket_with_real_profile(_unsecured_session(_BUCKET_ID, tmp_path))


def test_an_undecryptable_profile_payload_refuses(tmp_path: Path) -> None:
    """A readable row whose ciphertext will not open is equally unprovable.

    This is the likelier real-world shape of the previous case: the database is
    fine and one payload is not, so a canary that only guarded the connection
    would sail past it.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path):
        database = _bucket_database(_BUCKET_ID)
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database)
        try:
            connection.execute("CREATE TABLE secure_objects (namespace TEXT, payload BLOB)")
            connection.execute(
                "INSERT INTO secure_objects VALUES (?, ?)",
                (USER_PROFILE_VALUE_NAMESPACE.namespace, b"not-a-cipher-envelope"),
            )
            connection.commit()
        finally:
            connection.close()

        with pytest.raises(UnsecuredModeRefusedError):
            refuse_unsecured_bucket_with_real_profile(_unsecured_session(_BUCKET_ID, tmp_path))


def test_the_unsecured_label_bucket_is_admitted(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY, and the fallback the provider itself opens under.

    ``_provider_enter`` uses the literal ``"unsecured"`` as a stable bucket
    label when no active profile resolves. Real profiles are UUID-identified, so
    this label can never name one.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path):
        refuse_unsecured_bucket_with_real_profile(_unsecured_session("unsecured", tmp_path))


def test_a_bucket_with_no_database_yet_is_admitted(tmp_path: Path) -> None:
    """ADMITS, and the ordering gap that follows is deliberate to pin.

    There is nothing stored to judge, so the canary lets activation proceed.
    The consequence worth stating is that the check runs at ACTIVATION only: a
    profile written after this point, in the same unsecured session, is not
    re-examined, so a real NIF typed into a fresh bucket lands under the
    published key and is refused only on the NEXT activation -- after the bytes
    exist.

    That is narrow. Reaching it takes the hostile-named CADRUMO_ALLOW_UNENCRYPTED=1
    plus the unsecured backend, an opt-in whose entire purpose is to declare the
    data disposable. It is pinned rather than closed because closing it means
    re-running the canary on the profile WRITE path, which is a design change to
    that path rather than a fix to this function.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path):
        absent = "9d9d9d9d-9d9d-49d9-8d9d-9d9d9d9d9d9d"
        assert not _bucket_database(absent).exists()

        refuse_unsecured_bucket_with_real_profile(_unsecured_session(absent, tmp_path))


def test_a_bucket_carrying_no_profile_rows_is_admitted(tmp_path: Path) -> None:
    """A real database with nothing in the profile namespace judges nothing."""
    with override_settings(cadrumo_local_storage_root=tmp_path):
        database = _bucket_database(_BUCKET_ID)
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database)
        try:
            connection.execute("CREATE TABLE secure_objects (namespace TEXT, payload BLOB)")
            connection.commit()
        finally:
            connection.close()

        refuse_unsecured_bucket_with_real_profile(_unsecured_session(_BUCKET_ID, tmp_path))
