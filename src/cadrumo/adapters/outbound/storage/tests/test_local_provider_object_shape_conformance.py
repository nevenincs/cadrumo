"""The local storage provider's namespace fan-out matches its declared grammar.

``LocalFileSystemProvider`` is production's Google-Drive-alternative
backend, constructed by ``factory.py`` against
``bucket_paths(root, profile).blobs_dir`` -- genuinely enrolled
(``BUCKET_BLOBS``) at its own root. But the provider then fans out one
directory per outbound-attachment namespace beneath that root, and nothing
declared that fan-out's shape until now. This drives a real ``put()`` through
the real production layout (root anchored at ``buckets/<bucket_id>/blobs/``,
matching how ``factory.py`` constructs it) and checks the real resulting
paths.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from .....tests import assert_path_matches_grammar
from ....persistence.storage.bucket.directory_layout import bucket_paths
from .._local import LocalFileSystemProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _hash(payload: bytes) -> str:
    return f"sha256-{hashlib.sha256(payload).hexdigest()}"


@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
    return tmp_path / "state"


@pytest.fixture
def provider(storage_root: Path) -> LocalFileSystemProvider:
    # The exact construction factory.py uses for ProviderKind.LOCAL_FILESYSTEM.
    return LocalFileSystemProvider(bucket_paths(storage_root, "primary").blobs_dir)


def test_a_real_put_lands_at_the_declared_namespace_fan_out_shape(
    storage_root: Path,
    provider: LocalFileSystemProvider,
) -> None:
    payload = b"real outbound attachment bytes"
    metadata = provider.put(
        "ledger_transaction",
        "abcdef0123456789",
        payload,
        content_hash=_hash(payload),
        label="payroll-march-batch",
    )

    payload_path = Path(metadata.provider_object_id)
    assert payload_path.is_file(), "the real write did not land where the provider's own metadata says"
    assert_path_matches_grammar(key="local_provider_object", root=storage_root, produced=payload_path)

    sidecar_path = payload_path.with_name(payload_path.stem + ".meta.json")
    assert sidecar_path.is_file(), "the real write's sidecar did not land where the naming convention expects"
    assert_path_matches_grammar(key="local_provider_object_sidecar", root=storage_root, produced=sidecar_path)


def test_a_non_conforming_path_is_rejected_by_the_grammar(
    storage_root: Path, provider: LocalFileSystemProvider
) -> None:
    """Positive control: the matcher can still fail.

    A payload sitting directly under the bucket's blobs directory -- the
    per-namespace fan-out collapsed away -- is exactly the drift this
    grammar exists to catch.
    """
    flattened = provider.root / "abcdef01--payroll-march-batch.bin"

    with pytest.raises(AssertionError):
        assert_path_matches_grammar(key="local_provider_object", root=storage_root, produced=flattened)
