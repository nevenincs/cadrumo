"""The local backend never invents a content hash it did not verify against.

``get`` used to build its metadata with
``content_hash=stored_hash or f"sha256-{actual_hash}"``. When the sidecar
carried no digest that fallback computed one from whatever bytes were on disk
and returned it as the object's content hash -- a value the caller cannot
distinguish from one that had actually been checked. Nothing verified those
bytes; the hash simply described them.

That is a misreport by construction, independent of how the empty state
arises: it is a function returning a value it made up. Because
``ProviderObjectMetadata.content_hash`` is ``min_length=1`` there is no
"carry the empty hash" option, so the read refuses instead.

Reachability, measured rather than assumed: ``put`` refuses a blank
``content_hash``, so the application cannot produce this state through its own
write path -- reaching it means the sidecar was truncated or edited outside
the application. The refusal is therefore about not lying, not about defending
a hole the app can open.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....core.directory_scan import DirectoryEntryKind, iter_directory
from .....core.hashing import sha256_hex
from .._local import LocalFileSystemProvider
from ..errors import OutboundStorageIntegrityError, OutboundStorageValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_NAMESPACE = "ns"
_HMAC = "abcdef0123"


def _stored(tmp_path: Path, payload: bytes) -> tuple[LocalFileSystemProvider, Path, Path]:
    """Write one real object and return its provider, payload path and sidecar."""
    provider = LocalFileSystemProvider(tmp_path / "vault")
    provider.put(_NAMESPACE, _HMAC, payload, content_hash=f"sha256-{sha256_hex(payload)}", label="obj")
    root = tmp_path / "vault"
    sidecar = next(iter_directory(root, pattern="*.json", recursive=True))
    blob = next(p for p in iter_directory(root, recursive=True, select=DirectoryEntryKind.FILES) if p.suffix != ".json")
    return provider, blob, sidecar


def _blank_the_digest(sidecar: Path) -> None:
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["content_hash"] = ""
    sidecar.write_text(json.dumps(payload), encoding="utf-8")


def test_a_sidecar_with_no_digest_is_refused_rather_than_papered_over(tmp_path: Path) -> None:
    """The read refuses instead of returning unverified bytes."""
    provider, _blob, sidecar = _stored(tmp_path, b"original")
    _blank_the_digest(sidecar)

    with pytest.raises(OutboundStorageIntegrityError, match="carries no content_hash"):
        provider.get(_NAMESPACE, _HMAC)


def test_tampered_bytes_are_no_longer_returned_with_a_hash_describing_them(tmp_path: Path) -> None:
    """The exact defect, end to end: blank the digest, tamper the payload, read.

    Before the fix this returned ``b"TAMPERED"`` alongside
    ``content_hash=sha256(b"TAMPERED")`` -- a self-consistent pair that no
    caller could tell from a verified one.
    """
    provider, blob, sidecar = _stored(tmp_path, b"original")
    _blank_the_digest(sidecar)
    blob.write_bytes(b"TAMPERED")

    with pytest.raises(OutboundStorageIntegrityError):
        provider.get(_NAMESPACE, _HMAC)


def test_an_intact_object_still_reports_the_hash_that_was_stored(tmp_path: Path) -> None:
    """The refusal is scoped: a normal read is unaffected and carries the STORED digest.

    Guards the direction the fix could have broken -- metadata must keep
    reporting what the sidecar holds, not a recomputed value that would happen
    to agree today.
    """
    payload = b"original"
    provider, _blob, _sidecar = _stored(tmp_path, payload)

    returned, metadata = provider.get(_NAMESPACE, _HMAC)

    assert returned == payload
    assert metadata.content_hash == f"sha256-{sha256_hex(payload)}"


def test_put_refuses_a_blank_content_hash_so_the_app_cannot_reach_the_refusal(tmp_path: Path) -> None:
    """Pins the reachability claim the module docstring rests on.

    If ``put`` ever started accepting a blank digest, the read refusal above
    would become reachable through ordinary use and this fails -- rather than
    the claim quietly going stale in prose.
    """
    provider = LocalFileSystemProvider(tmp_path / "vault")

    with pytest.raises(OutboundStorageValidationError):
        provider.put(_NAMESPACE, _HMAC, b"x", content_hash="", label="obj")
