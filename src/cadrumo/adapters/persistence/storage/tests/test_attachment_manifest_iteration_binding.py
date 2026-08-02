"""Attachment iteration binds each manifest to the row it is stored under.

``load_manifest`` passes the row key into the manifest decoder, so a manifest
whose embedded ``sha256`` has drifted from the key it is filed under is
refused. ``iter_manifests`` had no key to pass, and derived the identity from
that same embedded ``sha256`` instead -- which is self-consistent by
construction. The one surface that could not detect the drift was therefore
the one that enumerates the whole corpus: a manifest ``load_manifest``
rejected was listed as though it were sound, so any audit, reconciliation, or
evidence sweep built on iteration saw a record the direct read refuses.

The binding is now checked from a recomputed :class:`HashedLookup` digest.
The row key is stored hashed, so the natural key cannot be read back off the
row, but it can be recomputed from the identity the manifest claims and
compared -- one HMAC, which keeps iteration away from the blob decryption it
deliberately avoids.

The tamper here rewrites only the persisted ``sha256`` inside the encrypted
manifest payload, re-encrypting under the row's own AAD, so the row remains
genuinely readable and the drift is the only thing under test. Real active
profile, real SQLite, real AES-GCM.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import select

from .....core.external_constants import UTF_8_ENCODING
from .....domain.attachments import (
    Attachment,
    AttachmentKind,
    AttachmentSource,
    AttachmentValidationError,
)
from .....tests.secure_sql import isolated_runtime_profile
from ..attachment import _ATTACHMENT_MANIFEST_NAMESPACE, AttachmentStore
from ..crypto import (
    decrypt_secure_object_payload,
    encrypt_secure_object_payload,
    secure_object_payload_aad,
)
from ..sql import SecureObjectRow
from ..sql.engine import get_engine
from ..sql.session import session_scope

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_CAPTURED_AT = datetime(2026, 5, 25, 13, 45, 0, tzinfo=UTC)
_PAYLOAD = b"%PDF-1.4\n%attachment-iteration-binding\n" + b"\x00" * 32
#: A well-formed digest that is simply not this attachment's.
_DRIFTED_DIGEST = "f" * 64


def _attachment(*, sha256: str, bytes_size: int) -> Attachment:
    return Attachment(
        attachment_id=sha256,
        kind=AttachmentKind.INVOICE_PDF,
        source=AttachmentSource.LOCAL_FILE,
        source_reference="/local/path/to/invoice.pdf",
        sha256=sha256,
        mime_type="application/pdf",
        bytes_size=bytes_size,
        captured_at=_CAPTURED_AT,
        bucket_id="b" * 32,
    )


def _rewrite_manifest_envelope(
    engine: Any,
    attachment_id: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    """Rewrite the decrypted manifest envelope in place, under the row's own AAD.

    Re-encrypting under the same associated data keeps the row genuinely
    readable, so the test exercises manifest drift rather than a broken
    ciphertext the substrate would reject for unrelated reasons.
    """
    statement = select(SecureObjectRow).where(
        SecureObjectRow.namespace == _ATTACHMENT_MANIFEST_NAMESPACE,
        SecureObjectRow.object_key == attachment_id,
    )
    with session_scope(engine) as session:
        row = session.execute(statement).scalar_one()
        aad = secure_object_payload_aad(row.namespace, bytes(row.object_key), row.schema_version)
        envelope = cast(
            "dict[str, Any]",
            json.loads(decrypt_secure_object_payload(bytes(row.payload), associated_data=aad).decode(UTF_8_ENCODING)),
        )
        mutate(envelope)
        row.payload = encrypt_secure_object_payload(
            json.dumps(envelope).encode(UTF_8_ENCODING),
            associated_data=aad,
        )


def test_an_untampered_manifest_loads_and_lists_identically(tmp_path: Path) -> None:
    """Positive control: both surfaces agree on a sound manifest."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        store = AttachmentStore()
        digest = store.put_bytes(_PAYLOAD)
        attachment = _attachment(sha256=digest, bytes_size=len(_PAYLOAD))
        store.write_manifest(attachment)

        assert store.load_manifest(digest) == attachment
        assert tuple(store.iter_manifests()) == (attachment,)


def test_iteration_refuses_the_sha_drift_that_direct_load_refuses(tmp_path: Path) -> None:
    """The two read surfaces reach the same verdict on a drifted manifest.

    The discriminating case. Before the binding, ``load_manifest`` raised
    while ``iter_manifests`` yielded the corrupted record -- so the assertion
    that matters is the pair, not either half alone: a fix that merely made
    iteration fail for some other reason would not establish that the two
    surfaces now enforce one invariant.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        engine = get_engine(profile.settings)
        store = AttachmentStore()
        digest = store.put_bytes(_PAYLOAD)
        store.write_manifest(_attachment(sha256=digest, bytes_size=len(_PAYLOAD)))

        def drift_sha256(envelope: dict[str, Any]) -> None:
            envelope["payload"]["sha256"] = _DRIFTED_DIGEST

        _rewrite_manifest_envelope(engine, digest, drift_sha256)

        with pytest.raises(AttachmentValidationError):
            store.load_manifest(digest)
        with pytest.raises(AttachmentValidationError):
            list(store.iter_manifests())


def test_iteration_does_not_yield_the_drifted_identity(tmp_path: Path) -> None:
    """No listing may report the tampered digest, not even before raising.

    ``iter_manifests`` is a generator that collects before yielding, so a
    partial listing is conceivable. This drains it defensively and asserts the
    drifted identity never reaches a consumer -- the corrupted record was
    previously yielded outright under a digest no blob in the store has.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        engine = get_engine(profile.settings)
        store = AttachmentStore()
        digest = store.put_bytes(_PAYLOAD)
        store.write_manifest(_attachment(sha256=digest, bytes_size=len(_PAYLOAD)))

        def drift_sha256(envelope: dict[str, Any]) -> None:
            envelope["payload"]["sha256"] = _DRIFTED_DIGEST

        _rewrite_manifest_envelope(engine, digest, drift_sha256)

        seen: list[str] = []
        with pytest.raises(AttachmentValidationError):
            for attachment in store.iter_manifests():
                seen.append(attachment.attachment_id)

        assert _DRIFTED_DIGEST not in seen


def test_restoring_the_true_digest_restores_both_surfaces(tmp_path: Path) -> None:
    """The refusal tracks the drift, not the fact of a re-encryption.

    Rewriting the envelope at all decrypts and re-encrypts the row with a
    fresh nonce. Writing the original digest back through the same helper must
    restore both surfaces, or the refusals above would prove only that the
    rewrite itself broke the record.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        engine = get_engine(profile.settings)
        store = AttachmentStore()
        digest = store.put_bytes(_PAYLOAD)
        attachment = _attachment(sha256=digest, bytes_size=len(_PAYLOAD))
        store.write_manifest(attachment)

        _rewrite_manifest_envelope(engine, digest, lambda e: e["payload"].update(sha256=_DRIFTED_DIGEST))
        with pytest.raises(AttachmentValidationError):
            list(store.iter_manifests())

        _rewrite_manifest_envelope(engine, digest, lambda e: e["payload"].update(sha256=digest))
        assert tuple(store.iter_manifests()) == (attachment,)
        assert store.load_manifest(digest) == attachment
