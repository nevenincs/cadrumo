"""Focused unit tests for financial._detection.provider_for_extension.

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

from ._csv import CsvProvider
from ._detection import provider_for_extension
from ._ofx import OfxProvider
from ._xlsx import XlsxProvider

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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
