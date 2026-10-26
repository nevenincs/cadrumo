"""Source-text extraction reports only the reader failures that belong to it.

An unreadable XLSX or PDF is relabelled as such, with the reader's own detail
carried into the message. The XLSX extraction limits keep their deliberate
``OSError`` message, and an unrelated failure inside either walk keeps its own
type and message.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..validate_evidence import _extract_pdf_text_impl, _extract_xlsx_text_impl

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _UnrelatedReaderError(RuntimeError):
    """Stands in for a defect deeper than the document reader's own refusals."""


def test_non_xlsx_payload_is_reported_as_an_unreadable_xlsx_source(tmp_path: Path) -> None:
    source = tmp_path / "record-design.xlsx"
    source.write_text("this is not a zip container", encoding="utf-8")

    with pytest.raises(OSError) as caught:
        _extract_xlsx_text_impl(str(source))

    assert f"could not extract text from XLSX source {source}" in str(caught.value)


def test_absent_xlsx_source_propagates_its_own_filesystem_error(tmp_path: Path) -> None:
    source = tmp_path / "absent.xlsx"

    with pytest.raises(FileNotFoundError) as caught:
        _extract_xlsx_text_impl(str(source))

    assert "could not extract text from XLSX source" not in str(caught.value)


def test_unrelated_xlsx_reader_failure_propagates_with_its_own_type_and_message(tmp_path: Path) -> None:
    source = tmp_path / "record-design.xlsx"
    source.write_text("unread", encoding="utf-8")

    def broken_open(path: str) -> object:
        del path
        raise _UnrelatedReaderError("openpyxl worksheet helper was removed")

    with pytest.raises(_UnrelatedReaderError) as caught:
        _extract_xlsx_text_impl(str(source), open_workbook=broken_open)  # ty: ignore[invalid-argument-type]

    assert str(caught.value) == "openpyxl worksheet helper was removed"
    assert "could not extract text from XLSX source" not in str(caught.value)


def test_non_pdf_payload_is_reported_as_an_unreadable_pdf_source(tmp_path: Path) -> None:
    source = tmp_path / "manual.pdf"
    source.write_text("this is not a PDF document", encoding="utf-8")

    with pytest.raises(OSError) as caught:
        _extract_pdf_text_impl(str(source))

    assert f"could not extract text from manual PDF {source}" in str(caught.value)
    assert str(caught.value) != f"could not extract text from manual PDF {source}"


def test_unrelated_pdf_reader_failure_propagates_with_its_own_type_and_message(tmp_path: Path) -> None:
    source = tmp_path / "manual.pdf"
    source.write_text("unread", encoding="utf-8")

    def broken_open(path: str) -> object:
        del path
        raise _UnrelatedReaderError("pdfium text-page helper was removed")

    with pytest.raises(_UnrelatedReaderError) as caught:
        _extract_pdf_text_impl(str(source), open_document=broken_open)  # ty: ignore[invalid-argument-type]

    assert str(caught.value) == "pdfium text-page helper was removed"
    assert "could not extract text from manual PDF" not in str(caught.value)
