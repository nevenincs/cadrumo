"""Behaviour tests for the shared PDF source-provenance helpers."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pytest

from .....domain.justificante.errors import PdfModeloImportError
from ..source_provenance import sha256_file, source_pdf_reference_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_SENSITIVE_BASENAME = "12345678Z-renta-borrador-source.pdf"


class TestSha256File:
    """The shared hashing helper preserves digest behavior and redacts read failures."""

    def test_hashes_file_bytes(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / "sample.pdf"
        payload = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
        pdf_path.write_bytes(payload)

        assert sha256_file(pdf_path) == hashlib.sha256(payload).hexdigest()

    def test_missing_file_error_uses_redacted_source_label(
        self,
        caplog: pytest.LogCaptureFixture,
        tmp_path: Path,
    ) -> None:
        missing_pdf = tmp_path / _SENSITIVE_BASENAME

        caplog.set_level(logging.DEBUG, logger=sha256_file.__module__)
        with pytest.raises(PdfModeloImportError) as exc_info:
            sha256_file(missing_pdf)

        message = str(exc_info.value)
        assert _SENSITIVE_BASENAME not in message
        assert str(missing_pdf) not in message
        assert message == "PDF file could not be hashed: <input-pdf>"
        assert exc_info.value.context == {"path": "<input-pdf>"}
        assert exc_info.value.translated_message == "adapters.inbound.pdf.errors.hash_failed"
        assert exc_info.value.__cause__ is None

        log_text = "\n".join(record.getMessage() for record in caplog.records)
        assert _SENSITIVE_BASENAME not in log_text
        assert str(missing_pdf) not in log_text
        assert "source=<input-pdf>" in log_text
        assert "failure=FileNotFoundError" in log_text


class TestSourcePdfReferencePath:
    """Persisted PDF provenance uses digest references, not local paths."""

    def test_reference_path_is_digest_derived(self) -> None:
        digest = "a" * 64

        reference = source_pdf_reference_path(digest)

        assert reference == Path(".secure-source") / f"{digest}.pdf"
        assert _SENSITIVE_BASENAME not in str(reference)
