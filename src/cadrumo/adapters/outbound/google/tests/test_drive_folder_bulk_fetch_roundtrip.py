"""Bulk-fetch-and-encrypt roundtrip for the Drive-folder sweep (#262, Drive half).

Exercises the exact composition ``aeat app ledger doclink pull-folder``
performs — :func:`list_drive_folder_documents` to enumerate the folder's
PDF/image children, then :func:`resolve_document_link` +
:func:`~cadrumo.domain.attachments.add_attachment` to fetch-and-encrypt
each one — with the storage and manifest path REAL (a real
:class:`AttachmentStore` over real SQLite) and the Drive requests executed
through real ``google-api-python-client`` resources pointed at local HTTP
endpoints (mirroring the single-document
``test_document_link_resolve_roundtrip.py`` gate):

* a folder with N invoice PDFs yields N encrypted evidence records, each
  independently readable and byte-identical to its source, and re-hash
  verification passes (real byte custody, not a link);
* a file inside the sweep that the ``drive.file`` scope cannot reach (a 403)
  is refused individually, is not written as a link-only record, and does
  not abort the fetch of the sweep's other files (the composed pipeline's
  actionable-refusal contract);
* re-running the sweep against the same bytes is idempotent: the same
  content-addressed attachment id is returned rather than a duplicate.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....adapters.persistence.storage.attachment import AttachmentStore
from .....domain.attachments.enums import AttachmentKind, AttachmentSource
from .....domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from .....tests.google_credentials import unused_google_credentials
from .....tests.secure_sql import isolated_runtime_profile
from ...storage.errors import OutboundStorageError, OutboundStoragePermissionError
from ..document_link_resolver import list_drive_folder_documents, resolve_document_link
from .drive_media_server import drive_files_list_endpoint, drive_media_endpoint

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# The attachment store refuses a manifest naming another profile bucket, so
# the fixture names the same bucket the runtime profile provisions.
_BUCKET_ID = "9d4e1a2b-6c70-4f81-8b92-a3c4d5e6f701"

_FOLDER_ID = "1FoldEr12345678901234567890AB"
# Drive file ids must be >=10 chars to match the /d/<id>/ URL pattern the
# resolver's parse_drive_file_id recognises (see
# _document_link_resolver._DRIVE_ID_PATTERNS); short synthetic ids like
# "file-1" would not parse and the resolver would (correctly) refuse them
# as validation errors rather than reach the fake Drive media endpoint.
_FILE_ID_1 = "1FileOne1234567890ABCDEFGH"
_FILE_ID_2 = "1FileTwo1234567890ABCDEFGH"
_FILE_ID_3 = "1FileThree1234567890ABCDEFGH"
_FILE_ID_DENIED = "1FileDenied1234567890ABCDEFGH"
_CAPTURED_AT = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)


def _pull_folder(
    store: AttachmentStore,
    *,
    listing_pages: Sequence[Mapping[str, object]],
    file_payloads: dict[str, bytes],
    refused_file_ids: frozenset[str] = frozenset(),
) -> tuple[list[str], list[str]]:
    """Run the exact list-then-fetch-then-encrypt composition the CLI verb performs.

    Returns ``(fetched_attachment_ids, refused_file_ids)`` in listing order.
    Each file's media fetch is served by its own local HTTP endpoint (a
    refused file's endpoint returns HTTP 403), mirroring how the real Drive
    API refuses an individual file outside the ``drive.file`` scope.
    """
    with drive_files_list_endpoint(pages=listing_pages) as list_endpoint:
        listing = list_drive_folder_documents(
            folder_id=_FOLDER_ID, credentials=unused_google_credentials(), service=list_endpoint.service
        )

    fetched: list[str] = []
    refused: list[str] = []
    for document in listing.documents:
        payload = file_payloads[document.file_id]
        status = 403 if document.file_id in refused_file_ids else 200
        reference = f"https://drive.google.com/file/d/{document.file_id}/view"
        with drive_media_endpoint(payload=payload, status=status) as media_endpoint:
            try:
                data = resolve_document_link(
                    source=AttachmentSource.GOOGLE_DRIVE,
                    reference=reference,
                    credentials=unused_google_credentials(),
                    service=media_endpoint.service,
                )
            except OutboundStorageError:
                refused.append(document.file_id)
                continue
        attachment = add_attachment(
            store,
            content=AttachmentBytesContent(data=data),
            request=AttachmentIngestionRequest(
                kind=AttachmentKind.DRIVE_DOCUMENT,
                source=AttachmentSource.GOOGLE_DRIVE,
                source_reference=reference,
                mime_type=document.mime_type,
                captured_at=_CAPTURED_AT,
                bucket_id=_BUCKET_ID,
                metadata={"source": "GOOGLE_DRIVE", "drive_folder_id": _FOLDER_ID},
            ),
        )
        fetched.append(attachment.attachment_id)
    return fetched, refused


def test_folder_with_n_pdfs_yields_n_encrypted_evidence_records(tmp_path: Path) -> None:
    """A folder with 3 invoice PDFs yields 3 independently-verifiable encrypted attachments."""
    payloads = {
        _FILE_ID_1: b"%PDF-1.4\n%invoice-one\n" + b"\x01" * 32,
        _FILE_ID_2: b"%PDF-1.4\n%invoice-two\n" + b"\x02" * 32,
        _FILE_ID_3: b"%PDF-1.4\n%invoice-three\n" + b"\x03" * 32,
    }
    listing_page = {
        "files": [{"id": file_id, "name": f"{file_id}.pdf", "mimeType": "application/pdf"} for file_id in payloads],
    }
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        fetched, refused = _pull_folder(store, listing_pages=[listing_page], file_payloads=payloads)

        assert refused == []
        assert len(fetched) == 3
        assert len(set(fetched)) == 3, "each distinct PDF must yield a distinct content-addressed attachment id"

        for file_id, attachment_id in zip(payloads, fetched, strict=True):
            payload = payloads[file_id]
            assert attachment_id == hashlib.sha256(payload).hexdigest()
            assert store.read_bytes(attachment_id) == payload
            manifest = store.load_manifest(attachment_id)
            assert manifest.sha256 == attachment_id
            assert manifest.mime_type == "application/pdf"
            assert manifest.source is AttachmentSource.GOOGLE_DRIVE
            store.verify_blob(attachment_id)


def test_permission_denied_file_refuses_individually_without_aborting_sweep(tmp_path: Path) -> None:
    """One out-of-scope file in the sweep refuses without blocking the rest, and stores nothing for it."""
    payloads = {
        _FILE_ID_1: b"%PDF-1.4\n%reachable-one\n" + b"\x01" * 32,
        _FILE_ID_DENIED: b"{}",
        _FILE_ID_2: b"%PDF-1.4\n%reachable-two\n" + b"\x02" * 32,
    }
    listing_page = {
        "files": [
            {"id": _FILE_ID_1, "name": "file-ok-1.pdf", "mimeType": "application/pdf"},
            {"id": _FILE_ID_DENIED, "name": "file-denied.pdf", "mimeType": "application/pdf"},
            {"id": _FILE_ID_2, "name": "file-ok-2.pdf", "mimeType": "application/pdf"},
        ],
    }
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        fetched, refused = _pull_folder(
            store,
            listing_pages=[listing_page],
            file_payloads=payloads,
            refused_file_ids=frozenset({_FILE_ID_DENIED}),
        )

        assert refused == [_FILE_ID_DENIED]
        assert len(fetched) == 2

        # The two reachable files were fetched and encrypted for real.
        for file_id in (_FILE_ID_1, _FILE_ID_2):
            attachment_id = hashlib.sha256(payloads[file_id]).hexdigest()
            assert attachment_id in fetched
            assert store.read_bytes(attachment_id) == payloads[file_id]

        # The refused file wrote nothing to the store — never a link-only record.
        denied_digest = hashlib.sha256(payloads[_FILE_ID_DENIED]).hexdigest()
        assert denied_digest not in tuple(manifest.attachment_id for manifest in store.iter_manifests())


def test_permission_denied_file_raises_scope_named_error_when_isolated() -> None:
    """The single-file refusal surfaces the same scope-named error doclink uses."""
    with (
        drive_media_endpoint(payload=b"{}", status=403) as endpoint,
        pytest.raises(OutboundStoragePermissionError) as excinfo,
    ):
        resolve_document_link(
            source=AttachmentSource.GOOGLE_DRIVE,
            reference=f"https://drive.google.com/file/d/{_FILE_ID_DENIED}/view",
            credentials=unused_google_credentials(),
            service=endpoint.service,
        )
    assert excinfo.value.context is not None
    assert excinfo.value.context["required_scope"] == "https://www.googleapis.com/auth/drive.readonly"


def test_rerunning_sweep_over_same_bytes_is_idempotent(tmp_path: Path) -> None:
    """Re-running the sweep for an unchanged file returns the same attachment id, not a duplicate."""
    payload = b"%PDF-1.4\n%idempotent-invoice\n" + b"\x09" * 32
    listing_page = {"files": [{"id": _FILE_ID_1, "name": "file-1.pdf", "mimeType": "application/pdf"}]}

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        store = AttachmentStore()
        first_fetched, first_refused = _pull_folder(
            store,
            listing_pages=[listing_page],
            file_payloads={_FILE_ID_1: payload},
        )
        second_fetched, second_refused = _pull_folder(
            store,
            listing_pages=[listing_page],
            file_payloads={_FILE_ID_1: payload},
        )

        assert first_refused == second_refused == []
        assert first_fetched == second_fetched
        assert len(tuple(store.iter_manifests())) == 1, "re-fetching unchanged bytes must not duplicate the record"
