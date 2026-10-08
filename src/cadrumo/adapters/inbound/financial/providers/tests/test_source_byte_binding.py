"""The size guard runs before detection reads, and rows come from the hashed bytes.

A provider hashes the guarded source bytes for provenance. Each test here
hands a provider one byte payload through its guarded read while the file on
disk holds something else, so a parser that reopened the path would read the
disk content, fail, or stamp a digest of bytes it never parsed.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import override

import pytest

from ......core.hashing import sha256_hex
from ......tests.inventory import FIXTURES_DIR
from ......tests.xls_fixtures import xls_workbook_bytes
from ..base import _MAX_SOURCE_BYTES, FinancialProvider, InvalidFinancialSourceError
from ..detection import detect_provider
from ..ofx import OfxProvider
from ..pdf_n26 import PdfN26Provider
from ..xls import XlsProvider
from ..xlsx import XlsxProvider
from .test_xls import _xlsx_cell_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_FIXTURES = FIXTURES_DIR / "financial"


class _OfxFromBytes(OfxProvider):
    def __init__(self, payload: bytes) -> None:
        super().__init__()
        self.payload = payload

    @override
    def _read_source_bytes(self, path: Path) -> bytes:
        return self.payload


class _PdfFromBytes(PdfN26Provider):
    def __init__(self, payload: bytes) -> None:
        super().__init__()
        self.payload = payload

    @override
    def _read_source_bytes(self, path: Path) -> bytes:
        return self.payload


class _XlsxFromBytes(XlsxProvider):
    def __init__(self, payload: bytes) -> None:
        super().__init__()
        self.payload = payload

    @override
    def _read_source_bytes(self, path: Path) -> bytes:
        return self.payload


class _XlsFromBytes(XlsProvider):
    def __init__(self, payload: bytes) -> None:
        super().__init__()
        self.payload = payload

    @override
    def _read_source_bytes(self, path: Path) -> bytes:
        return self.payload


def test_detection_refuses_an_oversized_source_before_any_provider_probe(tmp_path: Path) -> None:
    """An over-ceiling source is refused as too large instead of probed as unrecognised."""
    oversized = tmp_path / "statement.bin"
    with oversized.open("wb") as handle:
        handle.truncate(_MAX_SOURCE_BYTES + 1)

    with pytest.raises(InvalidFinancialSourceError) as refusal:
        detect_provider(oversized)

    assert refusal.value.translated_message == "errors.financial.source_file_too_large"


def test_detection_of_an_admissible_source_still_probes_providers(tmp_path: Path) -> None:
    """Below the ceiling, an unrecognised source is a probe miss, not a refusal."""
    unknown = tmp_path / "statement.bin"
    unknown.write_bytes(b"\x00\x01 not a statement")

    assert detect_provider(unknown) is None


def _ofx() -> tuple[FinancialProvider, bytes]:
    payload = (_FIXTURES / "synthetic-transactions.ofx").read_bytes()
    return _OfxFromBytes(payload), payload


def _pdf() -> tuple[FinancialProvider, bytes]:
    payload = (_FIXTURES / "n26" / "n26-savings-2025-01.pdf").read_bytes()
    return _PdfFromBytes(payload), payload


def _xlsx() -> tuple[FinancialProvider, bytes]:
    payload = (_FIXTURES / "synthetic-transactions.xlsx").read_bytes()
    return _XlsxFromBytes(payload), payload


def _xls() -> tuple[FinancialProvider, bytes]:
    payload = xls_workbook_bytes(_xlsx_cell_values(_FIXTURES / "synthetic-transactions.xlsx"))
    return _XlsFromBytes(payload), payload


@pytest.mark.parametrize(
    ("build", "suffix"),
    [
        pytest.param(_ofx, ".ofx", id="ofx"),
        pytest.param(_pdf, ".pdf", id="pdf-n26"),
        pytest.param(_xlsx, ".xlsx", id="xlsx"),
        pytest.param(_xls, ".xls", id="xls"),
    ],
)
def test_provider_parses_the_bytes_it_hashes(
    tmp_path: Path,
    build: Callable[[], tuple[FinancialProvider, bytes]],
    suffix: str,
) -> None:
    """Validation and ingest parse the guarded bytes, and provenance names their digest."""
    on_disk = tmp_path / f"statement{suffix}"
    on_disk.write_bytes(b"different content on disk")
    provider, payload = build()

    assert provider.validate_source(on_disk).is_valid
    rows = tuple(provider.ingest(on_disk))

    assert rows
    assert {row.raw.provenance.source_sha256 for row in rows} == {sha256_hex(payload)}
