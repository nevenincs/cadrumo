"""Remote-mirror manifest identifiers carry the canonical content-digest shape.

``object_key_hmac``, ``ciphertext_hash``, and the storage revision ids are all
produced by ``core.hashing.sha256_hex`` -- the first via
:func:`remote_mirror_object_key_hmac`, the rest by the secure-object row codec.
Each is therefore a :data:`~core.identity.ContentDigest`, but the manifest
records constrained them by LENGTH only, which admits ``"z" * 64`` and
``"A" * 64``. A tampered or torn remote manifest carrying such a value passed
construction and was compared against real digests, where it could only ever
mismatch -- surfacing as a spurious revision conflict rather than as manifest
corruption.

The refusals below are asserted against :data:`ContentDigest`'s own verdict on
the same values rather than against a restated rule, so the two cannot drift.
The valid case is built from the production key/digest helpers, not from a
hand-written literal, so the constraint cannot be tightened past what the
producer actually emits.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from .....core.hashing import sha256_hex
from .....core.identity import ContentDigest
from ..mirror_manifest import remote_mirror_object_key_hmac
from ..records import RemoteMirrorNamespaceManifest, RemoteMirrorObjectManifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_NAMESPACE = "cadrumo.mirror.digest"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)

#: Pins the manifest shape under test; claims nothing about what production
#: stamps, so this file deliberately does not import the application constant.
_MANIFEST_SCHEMA_VERSION_UNDER_TEST = 1

#: 64 characters, so a length-only constraint admits both; neither is hex.
_NON_HEX = "z" * 64
_UPPERCASE = "A" * 64
_MALFORMED = (_NON_HEX, _UPPERCASE)

_DIGEST_FIELDS = (
    "object_key_hmac",
    "ciphertext_hash",
    "storage_revision_id",
    "previous_storage_revision_id",
)

_digest_adapter: TypeAdapter[str] = TypeAdapter(ContentDigest)


def _accepts_digest(value: str) -> bool:
    try:
        _digest_adapter.validate_python(value)
    except ValidationError:
        return False
    return True


def _object_manifest(**overrides: object) -> RemoteMirrorObjectManifest:
    payload: dict[str, object] = {
        "namespace": _NAMESPACE,
        "object_key_hmac": remote_mirror_object_key_hmac(_NAMESPACE, b"object-key"),
        "classification": "financial",
        "schema_version": 1,
        "byte_length": 12,
        "ciphertext_hash": sha256_hex(b"ciphertext-bytes"),
        "storage_revision_id": sha256_hex(b"revision"),
        "previous_storage_revision_id": None,
        "revision_ancestor_ids": (),
        "row_written_at": _NOW,
    }
    payload.update(overrides)
    return RemoteMirrorObjectManifest.model_validate(payload)


@pytest.mark.parametrize("malformed", _MALFORMED)
def test_canonical_alias_refuses_the_malformed_digests_under_test(malformed: str) -> None:
    """Positive control: the alias refuses both values and accepts a real one."""
    assert not _accepts_digest(malformed)
    assert _accepts_digest(sha256_hex(b"anything"))


@pytest.mark.parametrize("field", _DIGEST_FIELDS)
@pytest.mark.parametrize("malformed", _MALFORMED)
def test_object_manifest_digest_fields_match_canonical_verdict(field: str, malformed: str) -> None:
    """Each manifest identifier refuses exactly what the canonical alias refuses."""
    with pytest.raises(ValidationError):
        _object_manifest(**{field: malformed})


@pytest.mark.parametrize("malformed", _MALFORMED)
def test_object_manifest_ancestor_ids_are_element_wise_validated(malformed: str) -> None:
    """The lineage tuple validates each element, not merely its container."""
    with pytest.raises(ValidationError):
        _object_manifest(revision_ancestor_ids=(sha256_hex(b"root"), malformed))


@pytest.mark.parametrize("malformed", _MALFORMED)
def test_namespace_manifest_latest_revision_matches_canonical_verdict(malformed: str) -> None:
    """The parent manifest's latest-revision pointer is bound by the same shape."""
    with pytest.raises(ValidationError):
        RemoteMirrorNamespaceManifest(
            manifest_schema_version=_MANIFEST_SCHEMA_VERSION_UNDER_TEST,
            namespace=_NAMESPACE,
            object_count=0,
            latest_revision_id=malformed,
            latest_revision_written_at=_NOW,
            objects=(),
        )


def test_producer_output_round_trips_through_the_tightened_manifest() -> None:
    """Values from the real digest producers still construct a manifest.

    Guards the refusals above against over-tightening: every identifier here
    comes from the production helper that mints it, so a constraint stricter
    than the producer's own output fails here rather than in a remote sync.
    """
    entry = _object_manifest()
    manifest = RemoteMirrorNamespaceManifest(
        manifest_schema_version=_MANIFEST_SCHEMA_VERSION_UNDER_TEST,
        namespace=_NAMESPACE,
        object_count=1,
        latest_revision_id=entry.storage_revision_id,
        latest_revision_written_at=_NOW,
        objects=(entry,),
    )

    assert manifest.objects == (entry,)
    assert _accepts_digest(entry.object_key_hmac)
    assert _accepts_digest(entry.ciphertext_hash)
    assert manifest.latest_revision_id == entry.storage_revision_id
