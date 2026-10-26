"""The unpinned G313 parser refuses loudly and instructively, never silently."""

from __future__ import annotations

import pytest

from .....domain.censo.certificado import CertificadoCensalParseError
from ..parser import parse_certificado_censal_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_non_pdf_bytes_refuse_as_unrecognised_document() -> None:
    with pytest.raises(CertificadoCensalParseError) as excinfo:
        parse_certificado_censal_bytes(b"not a certificate")
    assert excinfo.value.translated_message == "errors.censo.certificado_not_a_pdf"


def test_pdf_bytes_refuse_while_extraction_is_unpinned() -> None:
    """A real-looking PDF still refuses: no layout is pinned, so nothing extracts.

    This is the honesty contract of the structure-only parser — the day a
    specimen pins the extraction, THIS test is the one that must change,
    loudly, instead of a silent behavioural drift.
    """
    with pytest.raises(CertificadoCensalParseError) as excinfo:
        parse_certificado_censal_bytes(b"%PDF-1.7 minimal")
    assert excinfo.value.translated_message == "errors.censo.certificado_extraction_unpinned"
