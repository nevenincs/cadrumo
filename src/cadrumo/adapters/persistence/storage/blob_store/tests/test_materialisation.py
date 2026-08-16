"""Tests for the route-canonical :class:`SecretStore` factory."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core.classification import SensitivityClass
from ......core.config import Settings
from ......tests import assert_path_matches_grammar
from ......tests.master_key import EphemeralMasterKeyProvider
from ......tests.profile_capsule import open_test_profile_session
from ......tests.secure_sql import isolated_profile_storage_root
from ...secret_store import SecretRecord
from .._blob_store import EncryptedBlobStore
from .._materialisation import get_secret_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

# A bucket id IS a profile UUID: registration is proven by the capsule named
# for it, so a descriptive label can never name a bucket a session can open.
_BUCKET_ID = "3f7b9c21-84ad-4e60-9c15-5a2e6d0b7f38"
_SECRET_CREATED_AT = datetime(2026, 8, 3, 12, 0, 0, tzinfo=UTC)
_SECRET_EXPIRES_AT = datetime(2099, 1, 1, tzinfo=UTC)


def test_secret_store_factory_caches_each_explicit_route_independently(tmp_path: Path) -> None:
    """A second Settings route never inherits the first route's cached store."""
    settings_a = Settings(
        cadrumo_secret_store_dir=tmp_path / "root-a" / "fallback-store",
        cadrumo_blob_store_dir=tmp_path / "root-a" / "blobs",
    )
    settings_b = Settings(
        cadrumo_secret_store_dir=tmp_path / "root-b" / "fallback-store",
        cadrumo_blob_store_dir=tmp_path / "root-b" / "blobs",
    )
    settings_c = Settings(
        cadrumo_secret_store_dir=settings_a.cadrumo_secret_store_dir,
        cadrumo_blob_store_dir=tmp_path / "root-c" / "blobs",
    )
    store_a = get_secret_store(settings=settings_a)
    store_b = get_secret_store(settings=settings_b)
    store_c = get_secret_store(settings=settings_c)

    assert store_a is get_secret_store(settings=settings_a)
    assert store_b is get_secret_store(settings=settings_b)
    assert store_a is not store_b
    assert store_a is not store_c
    assert store_a.store_dir == settings_a.cadrumo_secret_store_dir
    assert store_b.store_dir == settings_b.cadrumo_secret_store_dir
    assert store_c.store_dir == settings_c.cadrumo_secret_store_dir


def _record(key: str = "materialisation-wiring:probe") -> SecretRecord:
    return SecretRecord(
        key=key,
        value=b"wiring-probe-payload",
        classification=SensitivityClass.SECRET,
        metadata={"issued_by": "test-suite"},
        created_at=_SECRET_CREATED_AT,
        expires_at=_SECRET_EXPIRES_AT,
    )


def test_get_secret_store_writes_a_real_blob_at_the_declared_taxonomy_path(tmp_path: Path) -> None:
    """A real write through ``get_secret_store()``'s factory wiring lands where the taxonomy declares.

    Every prior blob-store conformance test constructs :class:`EncryptedBlobStore`
    directly with an arbitrary ``root_dir`` -- exactly the shape that cannot see a
    wiring bug in the factory that replaced it. This drives the REAL factory
    (:func:`get_secret_store`), through a REAL active-bucket master-key session
    (mirroring how ``profile create`` and every other real caller reaches it),
    and asserts the REAL resulting ciphertext file against the declared
    ``blob_content_ciphertext`` grammar, anchored at the real storage root --
    not at whatever the store happened to be constructed with.

    Reproduces and closes the doubled-``blobs/blobs`` factory bug: ``root_dir``
    was constructed from ``cadrumo_blob_store_dir`` (already
    ``<storage_root>/blobs``), and ``EncryptedBlobStore`` appended its own
    ``blobs`` segment again.
    """
    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as storage_root,
        open_test_profile_session(_BUCKET_ID),
    ):
        store = get_secret_store()
        blob_ref = store.put(_record())

        ciphertext_path = (
            storage_root / "blobs" / blob_ref.sha256_plaintext_hex[:2] / f"{blob_ref.sha256_plaintext_hex}.enc"
        )
        assert ciphertext_path.is_file(), (
            "the real write did not land at the single-level blobs/<hex[:2]>/<hash>.enc shape -- "
            "if this fails, the doubled blobs/blobs factory bug has returned"
        )
        assert_path_matches_grammar(key="blob_content_ciphertext", root=storage_root, produced=ciphertext_path)


def test_the_doubled_blobs_wiring_would_have_been_caught_positive_control(tmp_path: Path) -> None:
    """Positive control: reproduces the exact prior bug and proves the grammar check catches it.

    Constructs ``EncryptedBlobStore`` the way the factory did before this fix --
    ``root_dir`` set to the already-``blobs``-suffixed directory -- and shows the
    resulting path does NOT match the declared grammar when anchored at the real
    storage root, proving :func:`get_secret_store`'s corrected wiring (the test
    above) is what makes the real write conform, not an accident of the matcher.
    """
    storage_root = tmp_path / "storage"
    blob_store_dir = storage_root / "blobs"  # what cadrumo_blob_store_dir resolves to by default
    provider = EphemeralMasterKeyProvider()
    # The prior bug: passing the already-suffixed blob_store_dir as root_dir.
    buggy_store = EncryptedBlobStore(root_dir=blob_store_dir, master_key_provider=provider)
    reference = buggy_store.put(b"positive-control-payload", classification=SensitivityClass.SECRET)
    doubled_path = (
        blob_store_dir / "blobs" / reference.sha256_plaintext_hex[:2] / f"{reference.sha256_plaintext_hex}.enc"
    )
    assert doubled_path.is_file(), "fixture assumption: the buggy wiring produces the doubled blobs/blobs path"

    with pytest.raises(AssertionError):
        assert_path_matches_grammar(key="blob_content_ciphertext", root=storage_root, produced=doubled_path)
