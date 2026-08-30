"""Attachment iteration binds each manifest to the row it is stored under.

``load_manifest`` passes the row key into the manifest decoder, so a manifest
whose embedded ``sha256`` has drifted from the key it is filed under is
refused. ``iter_manifests`` had no key to pass and derived the identity from
that same embedded ``sha256`` instead, which is self-consistent by
construction -- so the one surface that could not detect the drift was the one
that enumerates the whole corpus.

The tamper that matters is **substitution onto a digest the store really
holds**. Iteration already refused a drift to a digest with no blob behind it,
via its blob-presence check, so a test that drifted to ``"f" * 64`` passes
whether or not the key binding exists -- verified empirically: with the
binding removed, that form of the test stayed green. Pointing manifest A at
manifest B's digest satisfies presence and isolates the binding as the only
thing that can object. It is also the sharper defect: iteration then lists two
manifests claiming one identity while ``load_manifest`` refuses the tampered
row, so an audit and a direct read disagree about the evidence corpus.

The binding is checked from a recomputed :class:`HashedLookup` digest. The row
key is stored hashed, so the natural key cannot be read back off the row, but
it can be recomputed from the identity the manifest claims -- one HMAC, which
keeps iteration away from the blob decryption it deliberately avoids.

Real active profile, real SQLite, real AES-GCM; the tamper re-encrypts under
the row's own AAD so the row stays genuinely readable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from .....domain.attachments.enums import AttachmentKind, AttachmentSource
from .....domain.attachments.errors import AttachmentValidationError
from .....domain.attachments.models import Attachment
from .....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ..attachment import _ATTACHMENT_MANIFEST_NAMESPACE, AttachmentStore
from ..sql import SecureObjectRow
from ..sql.engine import get_engine

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_CAPTURED_AT = datetime(2026, 5, 25, 13, 45, 0, tzinfo=UTC)
_PAYLOAD_A = b"%PDF-1.4\n%attachment-iteration-binding-A\n" + b"\x00" * 32
_PAYLOAD_B = b"%PDF-1.4\n%attachment-iteration-binding-B\n" + b"\x11" * 48
#: A well-formed digest with no blob behind it. Refused by the pre-existing
#: presence check, so it cannot discriminate the key binding.
_ABSENT_DIGEST = "f" * 64


def _attachment(*, sha256: str, bytes_size: int, bucket_id: str) -> Attachment:
    """Build a manifest owned by ``bucket_id``.

    The bucket is the store's own, taken from the test profile rather than a
    literal: ``write_manifest`` refuses a manifest naming a foreign bucket and
    stamps its own onto one naming none, so a hardcoded value would make these
    tests fail (or silently mutate) for a reason that has nothing to do with
    the digest binding under test.
    """
    return Attachment(
        attachment_id=sha256,
        kind=AttachmentKind.INVOICE_PDF,
        source=AttachmentSource.LOCAL_FILE,
        source_reference="/local/path/to/invoice.pdf",
        sha256=sha256,
        mime_type="application/pdf",
        bytes_size=bytes_size,
        captured_at=_CAPTURED_AT,
        bucket_id=bucket_id,
    )


def _manifest_row_statement(attachment_id: str):
    """Select one manifest row while the caller owns the content mutation."""
    return select(SecureObjectRow).where(
        SecureObjectRow.namespace == _ATTACHMENT_MANIFEST_NAMESPACE,
        SecureObjectRow.object_key == attachment_id,
    )


def _seed_two_attachments(store: AttachmentStore, *, bucket_id: str) -> tuple[Attachment, Attachment]:
    """Persist two distinct attachments and return their manifests."""
    digest_a = store.put_bytes(_PAYLOAD_A)
    digest_b = store.put_bytes(_PAYLOAD_B)
    attachment_a = _attachment(sha256=digest_a, bytes_size=len(_PAYLOAD_A), bucket_id=bucket_id)
    attachment_b = _attachment(sha256=digest_b, bytes_size=len(_PAYLOAD_B), bucket_id=bucket_id)
    store.write_manifest(attachment_a)
    store.write_manifest(attachment_b)
    return attachment_a, attachment_b


def test_untampered_manifests_load_and_list_identically(tmp_path: Path) -> None:
    """Positive control: both surfaces agree on sound manifests."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        store = AttachmentStore()
        attachment_a, attachment_b = _seed_two_attachments(store, bucket_id=profile.bucket_id)

        assert store.load_manifest(attachment_a.attachment_id) == attachment_a
        assert store.load_manifest(attachment_b.attachment_id) == attachment_b
        assert tuple(store.iter_manifests()) == tuple(
            sorted((attachment_a, attachment_b), key=lambda item: item.attachment_id),
        )


def test_iteration_refuses_a_substitution_onto_another_stored_digest(tmp_path: Path) -> None:
    """The discriminating case: A's manifest retagged with B's real digest.

    B's blob exists, so the pre-existing presence check is satisfied and only
    the row-key binding can object. Before the binding, ``load_manifest(A)``
    refused while iteration listed the substituted record -- two surfaces
    disagreeing about the same stored evidence.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        engine = get_engine(profile.settings)
        store = AttachmentStore()
        attachment_a, attachment_b = _seed_two_attachments(store, bucket_id=profile.bucket_id)

        mutate_encrypted_secure_object_json(
            engine,
            row_statement=_manifest_row_statement(attachment_a.attachment_id),
            mutate=lambda envelope: envelope["payload"].update(
                sha256=attachment_b.attachment_id,
                bytes_size=attachment_b.bytes_size,
            ),
        )

        with pytest.raises(AttachmentValidationError):
            store.load_manifest(attachment_a.attachment_id)
        with pytest.raises(AttachmentValidationError):
            list(store.iter_manifests())


def test_iteration_never_yields_the_substituted_identity(tmp_path: Path) -> None:
    """No listing may report one identity twice, not even before raising.

    Draining the generator defensively: previously it yielded B's digest for
    both rows, so a consumer counting the corpus saw one attachment duplicated
    and the other vanished.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        engine = get_engine(profile.settings)
        store = AttachmentStore()
        attachment_a, attachment_b = _seed_two_attachments(store, bucket_id=profile.bucket_id)

        mutate_encrypted_secure_object_json(
            engine,
            row_statement=_manifest_row_statement(attachment_a.attachment_id),
            mutate=lambda envelope: envelope["payload"].update(
                sha256=attachment_b.attachment_id,
                bytes_size=attachment_b.bytes_size,
            ),
        )

        seen: list[str] = []
        with pytest.raises(AttachmentValidationError):
            for attachment in store.iter_manifests():
                seen.append(attachment.attachment_id)

        assert seen.count(attachment_b.attachment_id) <= 1


def test_iteration_still_refuses_a_drift_to_an_unstored_digest(tmp_path: Path) -> None:
    """The weaker drift stays refused, by the presence check that already caught it.

    Recorded deliberately as the NON-discriminating case: it passes with or
    without the key binding, and is kept only so a future change that removed
    the presence check would be noticed here rather than nowhere.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        engine = get_engine(profile.settings)
        store = AttachmentStore()
        attachment_a, _ = _seed_two_attachments(store, bucket_id=profile.bucket_id)

        mutate_encrypted_secure_object_json(
            engine,
            row_statement=_manifest_row_statement(attachment_a.attachment_id),
            mutate=lambda envelope: envelope["payload"].update(sha256=_ABSENT_DIGEST),
        )

        with pytest.raises(AttachmentValidationError):
            list(store.iter_manifests())


def test_restoring_the_true_digest_restores_both_surfaces(tmp_path: Path) -> None:
    """The refusal tracks the substitution, not the fact of a re-encryption.

    Rewriting the envelope decrypts and re-encrypts the row with a fresh
    nonce. Writing the original digest back through the same helper must
    restore both surfaces, or the refusals above would prove only that the
    rewrite itself broke the record.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        engine = get_engine(profile.settings)
        store = AttachmentStore()
        attachment_a, attachment_b = _seed_two_attachments(store, bucket_id=profile.bucket_id)

        mutate_encrypted_secure_object_json(
            engine,
            row_statement=_manifest_row_statement(attachment_a.attachment_id),
            mutate=lambda envelope: envelope["payload"].update(
                sha256=attachment_b.attachment_id,
                bytes_size=attachment_b.bytes_size,
            ),
        )
        with pytest.raises(AttachmentValidationError):
            list(store.iter_manifests())

        mutate_encrypted_secure_object_json(
            engine,
            row_statement=_manifest_row_statement(attachment_a.attachment_id),
            mutate=lambda envelope: envelope["payload"].update(
                sha256=attachment_a.attachment_id,
                bytes_size=attachment_a.bytes_size,
            ),
        )
        assert store.load_manifest(attachment_a.attachment_id) == attachment_a
        assert tuple(store.iter_manifests()) == tuple(
            sorted((attachment_a, attachment_b), key=lambda item: item.attachment_id),
        )
