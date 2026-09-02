"""Focused unit tests for financial.detection.provider_for_extension.

`provider_for_extension` is the cheap-fallback provider selector
used by CLI command surfaces when content-aware detection
(`detect_provider`) returns None but the path's suffix is
unambiguous. Unlike `detect_provider`, this helper does NOT open
the file or sniff its bytes.

Currently exercised indirectly through CLI flows; a regression in
any branch (e.g., adding a ``.txt`` → OfxProvider entry, or
returning a non-None provider for ``.pdf``) would silently misroute
fallback dispatches without tripping the content-aware tests.

Tests pin each suffix → provider mapping plus the case-
insensitivity rule and the ``.pdf`` carve-out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._constants import CSV_EXTENSIONS, OFX_EXTENSIONS, PDF_EXTENSION, XLSX_EXTENSION
from ..csv import CsvProvider
from ..detection import provider_for_extension
from ..ofx import OfxProvider
from ..pdf_n26 import PdfN26Provider
from ..xlsx import XlsxProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_provider_for_extension_routes_csv_to_csv_provider() -> None:
    provider = provider_for_extension(Path("statement.csv"))

    assert isinstance(provider, CsvProvider)


def test_provider_for_extension_routes_txt_to_csv_provider() -> None:
    """``.txt`` is the CSV-with-different-extension alias supported by
    the dispatcher; some bank exports ship CSV content with a ``.txt``
    suffix."""
    provider = provider_for_extension(Path("statement.txt"))

    assert isinstance(provider, CsvProvider)


def test_provider_for_extension_routes_xlsx_to_xlsx_provider() -> None:
    provider = provider_for_extension(Path("statement.xlsx"))

    assert isinstance(provider, XlsxProvider)


def test_provider_for_extension_routes_ofx_to_ofx_provider() -> None:
    provider = provider_for_extension(Path("statement.ofx"))

    assert isinstance(provider, OfxProvider)


def test_provider_for_extension_routes_qfx_to_ofx_provider() -> None:
    """``.qfx`` is the Quicken-flavoured OFX variant; the dispatcher
    routes it through the same OFX provider."""
    provider = provider_for_extension(Path("statement.qfx"))

    assert isinstance(provider, OfxProvider)


def test_provider_for_extension_returns_none_for_pdf() -> None:
    """The dispatcher's documented carve-out: PDF requires content-
    aware detection because the bare ``.pdf`` suffix carries no
    statement-flavour information (N26 PDFs vs other-bank PDFs vs
    non-statement PDFs)."""
    assert provider_for_extension(Path("statement.pdf")) is None


def test_provider_for_extension_returns_none_for_unknown_extension() -> None:
    """An unrecognised extension falls through to the None case so
    the caller can fall back to content sniffing or fail loudly."""
    assert provider_for_extension(Path("statement.dat")) is None
    assert provider_for_extension(Path("statement.json")) is None


def test_provider_for_extension_handles_uppercase_suffix_case_insensitively() -> None:
    """``.suffix.lower()`` is applied before the dispatch, so uppercase
    or mixed-case extensions route to the same provider."""
    assert isinstance(provider_for_extension(Path("statement.CSV")), CsvProvider)
    assert isinstance(provider_for_extension(Path("statement.XLSX")), XlsxProvider)
    assert isinstance(provider_for_extension(Path("statement.OFX")), OfxProvider)


def test_provider_for_extension_returns_none_for_no_extension() -> None:
    """A path without a suffix has ``.suffix == ''``, which does not
    match any allow-listed entry."""
    assert provider_for_extension(Path("statement")) is None


# ---------------------------------------------------------------------------
# contract: assert detection routes through the shared _constants module
# ---------------------------------------------------------------------------


def test_csv_extensions_constant_drives_csv_provider_routing() -> None:
    """Every extension in CSV_EXTENSIONS routes to CsvProvider via the
    shared constant — if the constant and the dispatch branch diverge,
    at least one of these assertions will fail."""
    for ext in CSV_EXTENSIONS:
        provider = provider_for_extension(Path(f"statement{ext}"))
        assert isinstance(provider, CsvProvider), (
            f"Expected CsvProvider for extension {ext!r} from CSV_EXTENSIONS but got {type(provider).__name__}"
        )


def test_xlsx_extension_constant_drives_xlsx_provider_routing() -> None:
    """XLSX_EXTENSION constant is the single source used by provider_for_extension."""
    provider = provider_for_extension(Path(f"statement{XLSX_EXTENSION}"))
    assert isinstance(provider, XlsxProvider)


def test_pdf_extension_constant_returns_none_for_extension_routing() -> None:
    """PDF_EXTENSION via provider_for_extension returns None per the documented
    carve-out: PDF requires content-aware detection."""
    provider = provider_for_extension(Path(f"statement{PDF_EXTENSION}"))
    assert provider is None


def test_ofx_extensions_constant_drives_ofx_provider_routing() -> None:
    """Every extension in OFX_EXTENSIONS routes to OfxProvider via the
    shared constant — if the constant and the dispatch branch diverge,
    at least one of these assertions will fail."""
    for ext in OFX_EXTENSIONS:
        provider = provider_for_extension(Path(f"statement{ext}"))
        assert isinstance(provider, OfxProvider), (
            f"Expected OfxProvider for extension {ext!r} from OFX_EXTENSIONS but got {type(provider).__name__}"
        )


def test_csv_extensions_constant_matches_csv_provider_supported_extensions() -> None:
    """CsvProvider.supported_extensions must equal CSV_EXTENSIONS exactly.

    This is the structural invariant: both the detection router and the
    provider instance use the same constant so a future alias addition
    requires only one edit.
    """
    assert CsvProvider.supported_extensions == CSV_EXTENSIONS


def test_xlsx_extension_constant_matches_xlsx_provider_supported_extensions() -> None:
    """XlsxProvider.supported_extensions is built from XLSX_EXTENSION."""
    assert XLSX_EXTENSION in XlsxProvider.supported_extensions


def test_pdf_extension_constant_matches_pdf_provider_supported_extensions() -> None:
    """PdfN26Provider.supported_extensions is built from PDF_EXTENSION."""
    assert PDF_EXTENSION in PdfN26Provider.supported_extensions


def test_ofx_extensions_constant_matches_ofx_provider_supported_extensions() -> None:
    """OfxProvider.supported_extensions must equal OFX_EXTENSIONS exactly.

    This is the structural invariant: both the detection router and the
    provider instance use the same constant so a future alias addition
    requires only one edit.
    """
    assert OfxProvider.supported_extensions == OFX_EXTENSIONS
