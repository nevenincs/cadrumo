"""Shape, delegation and idempotency of the notification-document service.

Three claims are gated here, and none of them is about whether the bytes
survive a roundtrip — that is the custody suite's job and is not repeated.

**Shape.** The custody record is a POINTER plus provenance. It must never grow
a filesystem path, because a path is exactly how sensitive financial bytes
leave encrypted storage, and it must never quietly grow any other field either:
a new defaultable field is invisible to a fixture that leaves it defaulted, and
would silently widen what a re-store is allowed to discard.

**Delegation.** The bytes reach custody through the shared ``add_attachment``
primitive and through nothing else. The store is injected at the port the
service already declares, wrapped so that what crossed the boundary can be
read off directly rather than inferred from what landed on disk.

**Idempotency.** This CLI's operator is an autonomous agent that retries, and
the AEAT act behind one certificado was served once and cannot change. So a
retry carrying the same document is a no-op returning what is already held,
and a retry carrying anything different refuses rather than overwriting a
taxpayer's served act with another one.

Nothing here is a test double. The injected store delegates every call to the
real encrypted :class:`AttachmentStore`; the recording is an observation of a
real write, never a substitute for one. The one store that refuses is refusing
on purpose — a port that cannot write is the only way to ask whether a second
write path exists.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Union, get_args, get_origin, override

import pytest
from pydantic import BaseModel, ValidationError

from ....adapters.inbound.notificacion import NotificationDocumentReader
from ....adapters.persistence.storage import AttachmentStore
from ....adapters.persistence.storage.crypto import encrypt_secure_object_payload
from ....core.i18n import tr
from ....domain.attachments import Attachment, AttachmentKind
from ....domain.notifications import SancionLiquidacion
from ....tests.aeat_literal_fixtures import NOTIFICATION_DETALLE_SEDE_URL_FIXTURE
from ....tests.secure_sql import isolated_runtime_profile
from ..errors import LiveApplicationInputError
from ..notification_documents import (
    _BYTE_DERIVED_FIELDS,
    _CALLER_SUPPLIED_FIELDS,
    _NON_IDENTITY_FIELDS,
    NotificationDocumentRecord,
)
from ._notification_document_support import (
    BUCKET_ID,
    CERT_READ,
    DETAIL_URL,
    build_service,
    read_row,
    sancion_pdf_bytes,
    served_document,
    stored_document_row,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CONFLICT_KEY = "application.live.notifications.errors.document_conflict"

#: The record's complete persisted surface. Written out rather than counted:
#: a count tells the next author to bump a number, a set tells them to decide
#: which side of the re-store match their new field falls on.
_DECLARED_FIELDS = frozenset(
    {
        "certificado_id",
        "bucket_id",
        "attachment_id",
        "document_sha256",
        "byte_size",
        "source_url",
        "fetched_at",
        "sancion",
        "parse_refusal",
        "mode",
    },
)

#: Substrings that name a place on a filesystem. ``url`` is deliberately absent:
#: ``source_url`` is the AEAT endpoint the document was served from, which is
#: provenance, not a location the bytes were written to.
_FILESYSTEM_PATH_TOKENS = ("path", "dir", "folder", "filename", "file", "disk", "tmp", "temp", "location")


def _annotation_types(annotation: object) -> Iterator[type]:
    """Yield every concrete type reachable inside ``annotation``, unions included."""
    if isinstance(annotation, type):
        yield annotation
    origin = get_origin(annotation)
    if origin is Union or origin is not None:
        for argument in get_args(annotation):
            yield from _annotation_types(argument)


def _path_named_fields(model: type[BaseModel]) -> tuple[str, ...]:
    """Return every field whose NAME carries a filesystem-path concept."""
    offenders: list[str] = [
        name for name in model.model_fields if any(token in name.lower() for token in _FILESYSTEM_PATH_TOKENS)
    ]
    return tuple(offenders)


def _path_typed_fields(model: type[BaseModel]) -> tuple[str, ...]:
    """Return every field whose ANNOTATION is, or contains, a filesystem path type."""
    offenders: list[str] = []
    for name, field in model.model_fields.items():
        for candidate in _annotation_types(field.annotation):
            if issubclass(candidate, PurePath | os.PathLike):
                offenders.append(name)
                break
    return tuple(offenders)


class _RecordingAttachmentStore:
    """A REAL encrypted attachment store with every port call recorded.

    Every method delegates to a concrete :class:`AttachmentStore`, so the bytes
    genuinely reach encrypted custody and the recording only observes what
    crossed the port. A stand-in answering from memory would prove the opposite
    of what these tests are for.

    :meth:`put_file` raises rather than delegating. Nothing on this path may
    hand the store a filesystem path, so the honest implementation of that
    method here is a refusal that would fail loudly if one ever appeared.
    """

    def __init__(self) -> None:
        self._inner = AttachmentStore()
        self.put_bytes_calls: list[bytes] = []
        self.write_manifest_calls: list[Attachment] = []

    def put_bytes(self, data: bytes) -> str:
        self.put_bytes_calls.append(data)
        return self._inner.put_bytes(data)

    def put_file(self, source: Path) -> tuple[str, int]:
        raise AssertionError(f"the notification custody path handed the store a filesystem path: {source!r}")

    def read_bytes(self, sha256: str) -> bytes:
        return self._inner.read_bytes(sha256)

    def write_manifest(self, attachment: Attachment) -> None:
        self.write_manifest_calls.append(attachment)
        self._inner.write_manifest(attachment)

    def load_manifest(self, attachment_id: str) -> Attachment:
        return self._inner.load_manifest(attachment_id)

    def iter_manifests(self) -> Iterator[Attachment]:
        return self._inner.iter_manifests()

    def verify_blob(self, attachment_id: str) -> None:
        self._inner.verify_blob(attachment_id)


class _ByteWriteRefusedError(RuntimeError):
    """Raised by the refusing port so a fallback write path cannot swallow it."""


class _RefusingAttachmentStore(_RecordingAttachmentStore):
    """A custody port that cannot accept bytes, to ask whether a second one exists."""

    @override
    def put_bytes(self, data: bytes) -> str:
        raise _ByteWriteRefusedError("the injected custody port refuses byte writes")


# ── The record's shape ─────────────────────────────────────────────────────


def test_the_record_declares_exactly_the_custody_fields_and_no_others() -> None:
    """A field added without a decision here is a field nothing has classified.

    The strict roundtrip in the custody suite populates every defaultable field
    with a non-default value, but it can only do that for fields it knows about
    — a new one added later would default silently through both the save and
    the load, and would also fall outside the re-store match below. Pinning the
    exact set forces the author of the eleventh field to make both decisions.
    """
    assert set(NotificationDocumentRecord.model_fields) == set(_DECLARED_FIELDS)


def test_the_record_names_no_filesystem_path() -> None:
    """The bytes live in encrypted custody; a path field is how they escape it."""
    assert _path_named_fields(NotificationDocumentRecord) == ()


def test_the_record_is_annotated_with_no_filesystem_path_type() -> None:
    """A path can arrive by type as easily as by name, including inside a union."""
    assert _path_typed_fields(NotificationDocumentRecord) == ()


def test_the_path_detectors_catch_a_path_field_when_one_is_present() -> None:
    """Anti-vacuity: both detectors above pass trivially over a model with no fields.

    Proved against a probe declared here rather than by breaking the record,
    so the assertion holds without any tracked file being edited.
    """

    class _Probe(BaseModel):
        document_path: Path
        cached_at: PurePath | None = None
        certificado_id: str = "x"

    assert _path_named_fields(_Probe) == ("document_path",)
    assert _path_typed_fields(_Probe) == ("document_path", "cached_at")


def test_every_persisted_field_is_classified_by_the_re_store_match() -> None:
    """No field may sit outside the match without a stated reason.

    The three sets are the whole argument for why comparing five fields is
    comparing all ten: five are supplied by the caller and compared, three are
    derived from bytes whose digest is itself compared, and two are declared
    non-identity. An unclassified field would be silently discarded by a no-op,
    which is the exact failure the match exists to prevent.
    """
    assert set(_DECLARED_FIELDS) == _CALLER_SUPPLIED_FIELDS | _BYTE_DERIVED_FIELDS | _NON_IDENTITY_FIELDS
    assert not _CALLER_SUPPLIED_FIELDS & _BYTE_DERIVED_FIELDS
    assert not _CALLER_SUPPLIED_FIELDS & _NON_IDENTITY_FIELDS
    assert not _BYTE_DERIVED_FIELDS & _NON_IDENTITY_FIELDS
    assert "fetched_at" in _NON_IDENTITY_FIELDS


def _record_fields() -> dict[str, object]:
    """Return every field of a valid record except the two under test."""
    return {
        "certificado_id": CERT_READ,
        "bucket_id": BUCKET_ID,
        "attachment_id": "a" * 64,
        "document_sha256": "a" * 64,
        "byte_size": 12,
        "source_url": DETAIL_URL,
        "fetched_at": datetime(2026, 2, 13, tzinfo=UTC),
    }


def _a_real_reading() -> SancionLiquidacion:
    """Parse a real sanción out of real bytes with the real reader.

    The reading is genuine rather than hand-built so the both-populated case
    below is refused for carrying a reading AND a refusal, never for carrying
    something that was never a valid reading in the first place.
    """
    sancion, refusal = NotificationDocumentReader().read(served_document(data=sancion_pdf_bytes()))
    assert refusal is None, refusal
    assert sancion is not None
    return sancion


def test_a_record_carrying_both_a_reading_and_a_refusal_is_refused() -> None:
    """A reading the reader simultaneously declined to vouch for is incoherent.

    Whichever of the two a later consumer believed, the other says it is
    wrong, and nothing in the record decides between them.
    """
    with pytest.raises(ValidationError, match="both a reading and a refusal"):
        NotificationDocumentRecord(
            **_record_fields(),
            sancion=_a_real_reading(),
            parse_refusal="SancionParseError: no text layer",
        )


def test_a_record_carrying_neither_a_reading_nor_a_refusal_is_refused() -> None:
    """The dangerous state: it reads as "no figures" when nobody looked.

    An operator meeting a document with no reading and no stated reason has
    nothing telling them to go read the served act themselves, and a sanción
    they never read is one they never answer.
    """
    with pytest.raises(ValidationError, match="neither a reading nor a refusal"):
        NotificationDocumentRecord(**_record_fields(), sancion=None, parse_refusal=None)


def test_a_record_carrying_exactly_one_of_the_two_is_accepted() -> None:
    """Anti-vacuity: the validator refuses the two states, not the field pair."""
    reading = NotificationDocumentRecord(**_record_fields(), sancion=_a_real_reading())
    refused = NotificationDocumentRecord(**_record_fields(), parse_refusal="SancionParseError: no text layer")

    assert reading.parse_refusal is None
    assert refused.sancion is None


# ── Delegation to the single-writer primitive ──────────────────────────────


def test_the_injected_custody_port_receives_the_served_bytes(tmp_path: Path) -> None:
    """What crossed the port is the document itself, once, unmodified."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID):
        store = _RecordingAttachmentStore()
        document = served_document()

        build_service(attachment_store=store).persist_document(
            bucket_id=BUCKET_ID,
            row=read_row(),
            document=document,
        )

        assert store.put_bytes_calls == [document.pdf_bytes]


def test_the_bytes_are_written_through_the_shared_ingestion_primitive(tmp_path: Path) -> None:
    """The manifest carries the full ingestion request, which only the primitive builds.

    A service that re-implemented the write would call ``put_bytes`` and
    ``write_manifest`` itself and would have to reproduce every provenance
    field by hand. Asserting the manifest is fully populated is how this test
    distinguishes delegation from a convincing imitation of it.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID):
        store = _RecordingAttachmentStore()
        document = served_document()

        record = (
            build_service(attachment_store=store)
            .persist_document(
                bucket_id=BUCKET_ID,
                row=read_row(),
                document=document,
            )
            .record
        )

        assert len(store.write_manifest_calls) == 1
        manifest = store.write_manifest_calls[0]
        assert manifest.attachment_id == record.attachment_id
        assert manifest.kind is AttachmentKind.AEAT_NOTIFICATION_PDF
        assert manifest.mime_type == "application/pdf"
        assert manifest.bucket_id == BUCKET_ID
        assert manifest.source_command == "app.live.notifications.document.pull"
        assert manifest.source_reference == DETAIL_URL
        assert manifest.bytes_size == len(document.pdf_bytes)
        assert manifest.metadata["certificado_id"] == CERT_READ


def test_a_custody_port_that_refuses_leaves_no_record_behind(tmp_path: Path) -> None:
    """There is no second write path, and no record survives a failed byte write.

    If the service held any route to storage other than the injected port, the
    refusal below would be routed around and a record would appear anyway.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID):
        service = build_service(attachment_store=_RefusingAttachmentStore())

        with pytest.raises(_ByteWriteRefusedError):
            service.persist_document(bucket_id=BUCKET_ID, row=read_row(), document=served_document())

        assert build_service().list_documents(bucket_id=BUCKET_ID) == ()


# ── Re-storing an act that is already in custody ───────────────────────────


def test_a_matching_re_store_returns_what_is_held_and_writes_nothing(tmp_path: Path) -> None:
    """The no-op: same certificado, same document, one write in total."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID):
        store = _RecordingAttachmentStore()
        service = build_service(attachment_store=store)

        first = service.persist_document(bucket_id=BUCKET_ID, row=read_row(), document=served_document())
        second = service.persist_document(bucket_id=BUCKET_ID, row=read_row(), document=served_document())

        assert first.already_in_custody is False
        assert second.already_in_custody is True
        assert second.record == first.record
        assert second.record.fetched_at == first.record.fetched_at
        assert store.put_bytes_calls == [served_document().pdf_bytes]
        assert len(store.write_manifest_calls) == 1
        assert len(service.list_documents(bucket_id=BUCKET_ID)) == 1


def test_a_matching_re_store_leaves_the_encrypted_row_byte_identical(tmp_path: Path) -> None:
    """No second lifecycle write, proved against the ciphertext on disk.

    The secure-object payload is encrypted with a fresh nonce on every save, so
    a re-save of even an identical record produces different bytes. Unchanged
    ciphertext is therefore proof that ``save`` was never called a second time,
    which a returned-value comparison alone could not establish.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID) as profile:
        service = build_service()
        service.persist_document(bucket_id=BUCKET_ID, row=read_row(), document=served_document())
        with stored_document_row(profile) as row:
            before = bytes(row.payload)

        service.persist_document(bucket_id=BUCKET_ID, row=read_row(), document=served_document())
        with stored_document_row(profile) as row:
            after = bytes(row.payload)

        assert after == before
        # Anti-vacuity: the comparison above only means something because the
        # cipher is nondeterministic. Two encryptions of one plaintext differ.
        plaintext = b"the same payload twice"
        aad = b"notification-document-anti-tautology"
        assert encrypt_secure_object_payload(plaintext, associated_data=aad) != encrypt_secure_object_payload(
            plaintext,
            associated_data=aad,
        )


def test_a_re_store_changing_a_caller_supplied_field_refuses_rather_than_dropping_it(tmp_path: Path) -> None:
    """The subtle failure: a no-op that silently discards a newly-supplied value.

    Same certificado, same bytes, different served-from endpoint. Accepting
    this as a no-op would return the stored record and lose the new provenance
    without a word, so the match covers every caller-supplied field and this
    one refuses.
    """
    other_url = f"{NOTIFICATION_DETALLE_SEDE_URL_FIXTURE}?ncc=2699101808461&v=2"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID):
        store = _RecordingAttachmentStore()
        service = build_service(attachment_store=store)
        first = service.persist_document(bucket_id=BUCKET_ID, row=read_row(), document=served_document()).record

        with pytest.raises(LiveApplicationInputError) as excinfo:
            service.persist_document(
                bucket_id=BUCKET_ID,
                row=read_row(),
                document=served_document(source_url=other_url),
            )

        context = excinfo.value.context
        assert context is not None
        assert excinfo.value.translated_message == _CONFLICT_KEY
        assert context["diverging_fields"] == "source_url"
        assert len(store.put_bytes_calls) == 1
        assert service.show(bucket_id=BUCKET_ID, certificado_id=CERT_READ) == first


def test_a_re_store_of_a_different_document_refuses_and_overwrites_nothing(tmp_path: Path) -> None:
    """A second, different act filed under one certificado is a conflict, not an update.

    Either the stored row or the incoming one is wrong about what AEAT served,
    and overwriting silently would destroy the evidence of which.
    """
    other_bytes = sancion_pdf_bytes(("Clave de liquidacion: A2860024500099999", "Referencia: 2024/0009999"))
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID):
        store = _RecordingAttachmentStore()
        service = build_service(attachment_store=store)
        first = service.persist_document(bucket_id=BUCKET_ID, row=read_row(), document=served_document()).record

        with pytest.raises(LiveApplicationInputError) as excinfo:
            service.persist_document(
                bucket_id=BUCKET_ID,
                row=read_row(),
                document=served_document(data=other_bytes),
            )

        context = excinfo.value.context
        assert context is not None
        assert excinfo.value.translated_message == _CONFLICT_KEY
        assert "document_sha256" in str(context["diverging_fields"])
        assert context["stored_document_sha256"] == first.document_sha256
        assert context["incoming_document_sha256"] != first.document_sha256
        assert len(store.put_bytes_calls) == 1
        assert service.show(bucket_id=BUCKET_ID, certificado_id=CERT_READ) == first


def test_the_conflict_refusal_speaks_every_shipped_language() -> None:
    """The refusal an operator reads names the diverging fields, in their language.

    A conflict the operator cannot act on is a conflict they will resolve by
    deleting something, so the message has to carry the field names rather than
    only announce that a disagreement occurred.
    """
    rendered = {
        locale: tr(_CONFLICT_KEY, locale=locale, diverging_fields="source_url") for locale in ("en", "es", "ca", "hu")
    }

    for locale, text in rendered.items():
        assert "source_url" in text, locale
        assert "{" not in text, locale
    assert len(set(rendered.values())) == len(rendered)
