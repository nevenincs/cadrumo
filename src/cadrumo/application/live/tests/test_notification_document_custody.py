"""Custody, refusal and roundtrip behaviour for fetched notification documents.

Two persistence boundaries are crossed on every capture and both are exercised
here against real adapters — real key provider, real ``SecureObjectRepository``,
real SQLite, real encrypted ``AttachmentStore``. Nothing is mocked, faked or
patched: a store that returns what the test expects is the canonical
false-positive, and this is the path a taxpayer's served sanción travels.

Every defaultable field on the persisted record carries a NON-default value,
because a save-drops-field / load-re-defaults-field regression is invisible when
a fixture leaves the default in place. ``sancion`` and ``parse_refusal`` are
mutually exclusive by construction — a read either parses into a reading or it
does not — so no single record can carry both non-default; the sanción
roundtrip below exercises ``sancion`` and the refusal roundtrip exercises
``parse_refusal``, and between the two every defaultable field is proven to
survive at a non-default value at least once. ``mode`` is the sole exception
and deliberately so: it is a single-value ``Literal`` with no non-default value
to carry, which is exactly the structural read-only marker it exists to be.

The legal guard is load-bearing here rather than incidental. Driving AEAT's
content control on an unread notification IS the comparecencia — it makes the
notification legally served, starts the appeal and payment periods, and requires
the taxpayer's own signature. So the refusal tests are not edge cases: they
assert that no layer added above the adapter can reach that control, and that a
refused row produces no bytes, no attachment and no record.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, override

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from ....adapters.outbound.aeat.sede import SedeNavigationError
from ....adapters.persistence.storage import AttachmentStore
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....core.directory_scan import scan_directory
from ....core.hashing import sha256_hex
from ....domain.attachments import AttachmentKind, load_attachment
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from ..errors import LiveApplicationInputError
from ..notification_documents import (
    NotificationDocumentNotFoundError,
    NotificationDocumentService,
    notification_document_object_key,
)
from ._notification_document_support import (
    BUCKET_ID as _BUCKET_ID,
)
from ._notification_document_support import (
    CERT_READ as _CERT_READ,
)
from ._notification_document_support import (
    CERT_UNREAD as _CERT_UNREAD,
)
from ._notification_document_support import (
    DETAIL_URL as _DETAIL_URL,
)
from ._notification_document_support import (
    DOCUMENT_NAMESPACE as _DOCUMENT_NAMESPACE,
)
from ._notification_document_support import (
    SANCION_TEXT_LINES,
    build_service,
)
from ._notification_document_support import (
    read_row as _read_row,
)
from ._notification_document_support import (
    sancion_pdf_bytes as _pdf_bytes,
)
from ._notification_document_support import (
    served_document as _document,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# ── Custody roundtrip ──────────────────────────────────────────────────────


def test_a_captured_document_survives_the_encrypted_roundtrip(tmp_path: Path) -> None:
    """Strict equality across the real encrypted store, field for field."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = build_service()
        document = _document()

        persisted = service.persist_document(bucket_id=_BUCKET_ID, row=_read_row(), document=document).record
        loaded = service.show(bucket_id=_BUCKET_ID, certificado_id=_CERT_READ)

        assert profile.paths.database_file.is_file()
        assert loaded == persisted

        # Witness every field a re-default would silently change.
        assert loaded.certificado_id == _CERT_READ
        assert loaded.bucket_id == _BUCKET_ID
        assert loaded.attachment_id == sha256_hex(document.pdf_bytes)
        assert loaded.document_sha256 == document.pdf_sha256
        assert loaded.byte_size == len(document.pdf_bytes)
        assert loaded.source_url == _DETAIL_URL
        assert loaded.parse_refusal is None
        assert loaded.mode == "read"

        # The reading is nested inside the record and must survive whole.
        assert loaded.sancion is not None
        assert loaded.sancion.base_sancion == Decimal("3687.12")
        assert loaded.sancion.importe_a_ingresar == Decimal("774.29")
        assert loaded.sancion.reduccion_conformidad == Decimal("553.07")
        assert loaded.sancion.reduccion_pronto_pago == Decimal("516.20")
        assert isinstance(loaded.sancion.importe_a_ingresar, Decimal)


def test_the_document_bytes_land_in_the_encrypted_attachment_store(tmp_path: Path) -> None:
    """The bytes are in encrypted custody, byte-identical, and classified honestly."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        service = build_service()
        document = _document()

        record = service.persist_document(bucket_id=_BUCKET_ID, row=_read_row(), document=document).record

        store = AttachmentStore()
        manifest = load_attachment(store, record.attachment_id)
        assert manifest.kind is AttachmentKind.AEAT_NOTIFICATION_PDF
        assert manifest.mime_type == "application/pdf"
        assert store.read_bytes(record.attachment_id) == document.pdf_bytes


def test_re_pulling_one_notification_stores_nothing_and_returns_what_is_held(tmp_path: Path) -> None:
    """A retried pull is a no-op against real custody, not a rewrite.

    Asserted here against the real encrypted adapters because that is where the
    claim has to hold: the operator of this CLI is an autonomous agent that
    retries, and the AEAT act behind one certificado was served once and cannot
    change. ``fetched_at`` is the field that betrays a rewrite — it is stamped
    from the clock on every genuine store, so an equal value across two calls
    is proof the second call never built a record at all.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        service = build_service()

        first = service.persist_document(bucket_id=_BUCKET_ID, row=_read_row(), document=_document())
        second = service.persist_document(bucket_id=_BUCKET_ID, row=_read_row(), document=_document())

        assert first.already_in_custody is False
        assert second.already_in_custody is True
        assert second.record == first.record
        assert second.record.fetched_at == first.record.fetched_at
        assert len(service.list_documents(bucket_id=_BUCKET_ID)) == 1


def test_an_unpulled_notification_is_a_miss_not_a_blank_record(tmp_path: Path) -> None:
    """A missing document refuses; it never resolves to an empty reading."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID),
        pytest.raises(NotificationDocumentNotFoundError),
    ):
        build_service().show(bucket_id=_BUCKET_ID, certificado_id=_CERT_READ)


# ── The legal guard ────────────────────────────────────────────────────────


def test_an_unread_notification_is_refused_before_any_byte_is_stored(tmp_path: Path) -> None:
    """The comparecencia guard bites through the custody layer, not only below it."""
    unread = _read_row(certificado_id=_CERT_UNREAD).model_copy(update={"leida": False})

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        service = build_service()

        with pytest.raises(SedeNavigationError, match=r"comparecencia|read"):
            service.persist_document(
                bucket_id=_BUCKET_ID,
                row=unread,
                document=_document(certificado_id=_CERT_UNREAD),
            )

        assert service.list_documents(bucket_id=_BUCKET_ID) == ()


def test_a_pending_notification_with_no_read_column_is_refused(tmp_path: Path) -> None:
    """``leida is None`` is fail-closed: unknown is not permission."""
    pending = _read_row(certificado_id=_CERT_UNREAD).model_copy(update={"leida": None, "tipo": "pendiente"})

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        service = build_service()

        with pytest.raises(SedeNavigationError):
            service.persist_document(
                bucket_id=_BUCKET_ID,
                row=pending,
                document=_document(certificado_id=_CERT_UNREAD),
            )

        assert service.list_documents(bucket_id=_BUCKET_ID) == ()


@pytest.mark.asyncio
async def test_a_refused_row_never_reaches_the_wire(tmp_path: Path) -> None:
    """A refused pull produces NO AEAT contact at all.

    The guard is checked before a session is touched, so the refusal cannot be
    a request that was issued and then discarded — issuing it against an unread
    notification would already have served it.

    ``session`` is deliberately an object that raises on ANY attribute access:
    it is not a stand-in for a session, it is a tripwire proving nothing on the
    fetch path is reached. A test double that answered politely here would
    prove the opposite of what this test is for.
    """

    class _Tripwire:
        @override
        def __getattribute__(self, name: str) -> object:
            raise AssertionError(f"the fetch path was entered on a refused row: touched {name!r}")

    unread = _read_row(certificado_id=_CERT_UNREAD).model_copy(update={"leida": False})

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        service = build_service()

        with pytest.raises(SedeNavigationError):
            await service.pull_document(
                bucket_id=_BUCKET_ID,
                session=_Tripwire(),  # type: ignore[arg-type]
                row=unread,
            )

        assert service.list_documents(bucket_id=_BUCKET_ID) == ()


def test_a_document_for_another_notification_is_refused(tmp_path: Path) -> None:
    """Custody must not file one taxpayer act under another notification's id."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        service = build_service()

        with pytest.raises(
            LiveApplicationInputError,
            match=r"application\.live\.notifications\.errors\.document_row_mismatch",
        ):
            service.persist_document(
                bucket_id=_BUCKET_ID,
                row=_read_row(),
                document=_document(certificado_id=_CERT_UNREAD),
            )

        assert service.list_documents(bucket_id=_BUCKET_ID) == ()


def test_the_service_exposes_no_verb_that_could_mutate_aeat_state(tmp_path: Path) -> None:
    """Structural check: no acknowledging, signing, filing or browser-opening verb.

    Worth asserting rather than reading off the current file. The control that
    serves this document is the same one that performs the comparecencia, so a
    verb named for opening or acknowledging one is the single most dangerous
    thing that could be added to this class.
    """
    forbidden = ("acknowledge", "acuse", "sign", "firmar", "submit", "file", "presentar", "open", "browse", "comparec")
    public = {name for name in dir(NotificationDocumentService) if not name.startswith("_")}
    assert not [name for name in public if any(verb in name.lower() for verb in forbidden)]


# ── Reading refusals are recorded, never zeroed ────────────────────────────


def test_an_unreadable_document_keeps_its_bytes_and_records_the_refusal(tmp_path: Path) -> None:
    """A document the reader will not vouch for yields no reading — never a zeroed one.

    The bytes are the authoritative artefact and stay in custody; the operator
    is told plainly that no figures were extracted. A partially-read record
    presenting as complete is the outcome this whole path is built to avoid.

    ``parse_refusal`` is the one field the sanción roundtrip above cannot
    exercise at a non-default value — it and ``sancion`` are mutually
    exclusive by construction — so the strict equality check here is what
    closes that gap across the two records.
    """
    truncated = _pdf_bytes(("Clave de liquidacion: A2860024500012345", "Referencia: 2024/0001234"))

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        service = build_service()

        record = service.persist_document(
            bucket_id=_BUCKET_ID,
            row=_read_row(),
            document=_document(data=truncated),
        ).record
        loaded = service.show(bucket_id=_BUCKET_ID, certificado_id=_CERT_READ)

        assert loaded == record
        assert record.sancion is None
        assert record.parse_refusal is not None
        assert "SancionParseError" in record.parse_refusal
        assert AttachmentStore().read_bytes(record.attachment_id) == truncated


# ── Anti-tautology proofs ──────────────────────────────────────────────────


def test_deleting_the_attachment_id_on_disk_makes_the_load_refuse(tmp_path: Path) -> None:
    """Anti-tautology proof: a dropped required field must surface at load.

    ``attachment_id`` is the field chosen because it is the ONLY link between
    the record and the bytes it claims custody of. Were it to silently
    re-default, the record would assert that a document is held while pointing
    at nothing — a custody claim with no custody.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = build_service()
        service.persist_document(bucket_id=_BUCKET_ID, row=_read_row(), document=_document())

        def _drop(decoded: dict[str, Any]) -> None:
            payload = decoded["payload"]
            assert "attachment_id" in payload, (  # type: ignore[operator]
                "fixture must serialise attachment_id for this proof to mean anything"
            )
            del payload["attachment_id"]  # type: ignore[index]

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=select(SecureObjectRow).where(
                SecureObjectRow.namespace == _DOCUMENT_NAMESPACE,
                SecureObjectRow.object_key == notification_document_object_key(_BUCKET_ID, _CERT_READ),
            ),
            mutate=_drop,
        )

        with pytest.raises(ValidationError, match="attachment_id"):
            service.show(bucket_id=_BUCKET_ID, certificado_id=_CERT_READ)


def test_dropping_a_figure_from_the_nested_reading_makes_the_load_refuse(tmp_path: Path) -> None:
    """The nested sanción is strict too, so a dropped figure cannot re-default to zero.

    Without this, the nested reading would be the one place in the record where
    a missing amount could come back as a plausible number.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = build_service()
        service.persist_document(bucket_id=_BUCKET_ID, row=_read_row(), document=_document())

        def _drop(decoded: dict[str, Any]) -> None:
            sancion = decoded["payload"]["sancion"]  # type: ignore[index]
            assert "importe_a_ingresar" in sancion, "fixture must serialise the payable for this proof to mean anything"
            del sancion["importe_a_ingresar"]

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=select(SecureObjectRow).where(
                SecureObjectRow.namespace == _DOCUMENT_NAMESPACE,
                SecureObjectRow.object_key == notification_document_object_key(_BUCKET_ID, _CERT_READ),
            ),
            mutate=_drop,
        )

        with pytest.raises(ValidationError, match="importe_a_ingresar"):
            service.show(bucket_id=_BUCKET_ID, certificado_id=_CERT_READ)


def test_deleting_the_parse_refusal_on_disk_silently_loses_it(tmp_path: Path) -> None:
    """Anti-tautology proof for the one field with a default to fall back to.

    Every other proof in this module deletes a REQUIRED field and shows the
    load refuses outright. ``parse_refusal`` is optional, so a dropped key
    does not raise at all — it silently re-defaults to ``None``. Strict
    equality against the originally persisted record is what surfaces that
    instead, which is exactly why the roundtrip above compares the whole
    record rather than checking individual fields.
    """
    truncated = _pdf_bytes(("Clave de liquidacion: A2860024500012345", "Referencia: 2024/0001234"))

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = build_service()
        persisted = service.persist_document(
            bucket_id=_BUCKET_ID,
            row=_read_row(),
            document=_document(data=truncated),
        ).record
        assert persisted.parse_refusal is not None

        def _drop(decoded: dict[str, Any]) -> None:
            payload = decoded["payload"]
            assert "parse_refusal" in payload, (  # type: ignore[operator]
                "fixture must serialise parse_refusal for this proof to mean anything"
            )
            del payload["parse_refusal"]  # type: ignore[index]

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=select(SecureObjectRow).where(
                SecureObjectRow.namespace == _DOCUMENT_NAMESPACE,
                SecureObjectRow.object_key == notification_document_object_key(_BUCKET_ID, _CERT_READ),
            ),
            mutate=_drop,
        )

        loaded = service.show(bucket_id=_BUCKET_ID, certificado_id=_CERT_READ)
        assert loaded != persisted
        assert loaded.parse_refusal is None


def test_a_zero_byte_size_on_disk_makes_the_load_refuse(tmp_path: Path) -> None:
    """A custody record claiming zero bytes is a contradiction, not a small document."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = build_service()
        service.persist_document(bucket_id=_BUCKET_ID, row=_read_row(), document=_document())

        def _zero(decoded: dict[str, Any]) -> None:
            decoded["payload"]["byte_size"] = 0  # type: ignore[index]

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=select(SecureObjectRow).where(
                SecureObjectRow.namespace == _DOCUMENT_NAMESPACE,
                SecureObjectRow.object_key == notification_document_object_key(_BUCKET_ID, _CERT_READ),
            ),
            mutate=_zero,
        )

        with pytest.raises(ValidationError, match="byte_size"):
            service.show(bucket_id=_BUCKET_ID, certificado_id=_CERT_READ)


def test_the_stored_record_is_not_readable_as_plaintext_on_disk(tmp_path: Path) -> None:
    """Sensitive figures must not be recoverable by reading the database file.

    The custody guarantee is the whole point of this path, so it is asserted
    against the real file rather than assumed from the namespace's declared
    sensitivity class. A single file is not the whole custody guarantee — see
    :func:`test_no_file_anywhere_under_the_profile_root_carries_the_plaintext_document`
    below for the full-tree sweep — but the database file is where every byte
    this service writes ultimately lands, so it stays pinned here too.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = build_service()
        record = service.persist_document(bucket_id=_BUCKET_ID, row=_read_row(), document=_document()).record

        raw = profile.paths.database_file.read_bytes()
        assert b"A2860024500012345" not in raw
        assert b"3.687,12" not in raw
        assert b"3687.12" not in raw
        assert record.document_sha256.encode("ascii") not in raw
        assert b"%PDF" not in raw


def test_no_file_anywhere_under_the_profile_root_carries_the_plaintext_document(tmp_path: Path) -> None:
    """The custody guarantee holds across the ENTIRE on-disk footprint, not one file.

    A single-file scan of the database misses a WAL or journal sidecar, the
    keystore's wrapped-DEK artefact, and the secret-store files this same
    fetch-and-store cycle writes — any one of which could carry a leak the
    database-file check alone would never see. This walks EVERY file under the
    temporary profile root and keys the assertion on the property that makes a
    file an encrypted store artefact rather than a plaintext one: it contains
    neither the PDF magic header nor any of the served document's own
    distinctive plaintext literals. No file count or filename is hardcoded —
    a store artefact this cycle has not been taught to write yet is covered
    the same way as one it already writes.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        service = build_service()
        document = _document()
        record = service.persist_document(bucket_id=_BUCKET_ID, row=_read_row(), document=document).record

        files = [path for path in scan_directory(tmp_path, recursive=True) if path.is_file()]
        # Anti-vacuity: the walk must find the real artefacts this cycle
        # writes (the database plus at least its keystore and secret-store
        # siblings), never an accidentally empty or single-file tree.
        assert profile.paths.database_file in files
        assert len(files) >= 3

        forbidden = (
            document.pdf_bytes,
            b"%PDF",
            record.document_sha256.encode("ascii"),
            *(line.encode("utf-8") for line in SANCION_TEXT_LINES),
        )
        for path in files:
            raw = path.read_bytes()
            for needle in forbidden:
                assert needle not in raw, f"{path.relative_to(tmp_path)} carries a plaintext leak: {needle!r}"
