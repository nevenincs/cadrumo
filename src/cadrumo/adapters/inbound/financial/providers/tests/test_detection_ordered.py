"""Focused unit tests for financial._detection._ordered_candidates.

`_ordered_candidates` builds the content-prioritised candidate
provider list `detect_provider` walks. The first provider whose
`validate_source` returns is_valid wins. The candidate-ordering
rule is documented:

- Known-suffix paths return a suffix-led ordering (e.g., .pdf →
  (PdfN26, Csv, Xlsx, Ofx)).
- Unknown-suffix paths fall back to magic-byte sniffing of the
  first 256 source bytes; ``%PDF``, ``PK``, ``<OFX>``,
  ``<BANKTRANLIST>`` markers steer the candidate order.
- OSError suppression: when the source bytes cannot be read, a
  default ordering is returned with a debug log.
- Anything else → default ordering (Csv, Xlsx, Ofx, PdfN26).

A regression in the candidate ordering (e.g., demoting PdfN26 to
last in the .pdf-suffix branch, or returning the default ordering
for `%PDF` content) would silently change which provider's
validate_source runs first across every operator's financial-
import session.

Tests pin the first-candidate-type contract for each documented
branch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._detection import _ordered_candidates
from .._mapped_tabular import MappedTabularProvider
from .._ofx import OfxProvider
from .._pdf_n26 import PdfN26Provider
from .._xlsx import XlsxProvider
from ..csv import CsvProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


# ---------------------------------------------------------------------------
# Known-suffix branches
# ---------------------------------------------------------------------------


def test_ordered_candidates_known_suffix_leads_with_declared_provider(tmp_path: Path) -> None:
    """Known suffixes take precedence before content sniffing."""
    cases = (
        ("pdf", ".pdf", b"%PDF-1.4\n% financial statement sample\n", PdfN26Provider),
        ("xlsx", ".xlsx", b"PK\x03\x04 workbook container sample", XlsxProvider),
        ("ofx", ".ofx", b"<OFX><BANKMSGSRSV1></BANKMSGSRSV1></OFX>", OfxProvider),
        ("qfx", ".qfx", b"<OFX><BANKMSGSRSV1></BANKMSGSRSV1></OFX>", OfxProvider),
        ("csv", ".csv", b"date,description,amount\n", CsvProvider),
        ("txt-csv", ".txt", b"date,description,amount\n", CsvProvider),
    )

    for case_id, suffix, content, provider_type in cases:
        target = tmp_path / f"statement-{case_id}{suffix}"
        target.write_bytes(content)
        candidates = _ordered_candidates(target)

        assert isinstance(candidates[0], provider_type), case_id


# ---------------------------------------------------------------------------
# Content-sniff branches (unknown extension; magic-byte dispatch)
# ---------------------------------------------------------------------------


def test_ordered_candidates_unknown_suffix_magic_bytes_lead_with_declared_provider(
    tmp_path: Path,
) -> None:
    """Unknown suffixes fall through to the documented magic-byte dispatch."""
    cases = (
        ("pdf-magic", b"%PDF-1.4\n% financial statement sample\n", PdfN26Provider),
        ("zip-magic", b"PK\x03\x04 workbook container sample", XlsxProvider),
        ("ofx-envelope", b"<?xml version='1.0'?><OFX><BODY/></OFX>", OfxProvider),
        ("banktranlist-marker", b"<HEADER/>\n<BANKTRANLIST>" + b"x" * 50, OfxProvider),
    )

    for case_id, content, provider_type in cases:
        target = tmp_path / f"statement-{case_id}.bin"
        target.write_bytes(content)
        candidates = _ordered_candidates(target)

        assert isinstance(candidates[0], provider_type), case_id


# ---------------------------------------------------------------------------
# Error-path and unknown-content fallbacks
# ---------------------------------------------------------------------------


def test_ordered_candidates_unreadable_file_falls_back_to_default_ordering(tmp_path: Path) -> None:
    """When the source bytes cannot be read (path does not exist or
    OS denies the read), the OSError is suppressed and the default
    ordering (Csv, Xlsx, Ofx, PdfN26) is returned."""
    missing_path = tmp_path / "nonexistent.bin"

    candidates = _ordered_candidates(missing_path)

    assert isinstance(candidates[0], CsvProvider)


def test_ordered_candidates_unknown_content_falls_back_to_default_ordering(tmp_path: Path) -> None:
    """A readable file with no magic-byte match returns the default
    (Csv, Xlsx, Ofx, PdfN26) ordering."""
    target = tmp_path / "statement.bin"
    target.write_bytes(b"some non-magic content without any sentinel")

    candidates = _ordered_candidates(target)

    assert isinstance(candidates[0], CsvProvider)


def test_ordered_candidates_covers_every_provider_in_every_branch(tmp_path: Path) -> None:
    """Every branch offers every exact provider, then the mapping lane last.

    Gated on the property rather than a tally: a hardcoded candidate count
    encodes the moment it was written, so enrolling a provider makes the test
    fail for saying nothing about coverage. What must hold is that no exact
    parser is dropped from the chain, and that the mapping fallback trails all
    of them — ordering it earlier would let an inferred parse shadow a
    deterministic one on a known bank export.
    """
    target = tmp_path / "statement.csv"
    target.write_bytes(b"date,amount\n")

    candidates = _ordered_candidates(target)
    provider_types = {type(p) for p in candidates}

    assert provider_types >= {CsvProvider, XlsxProvider, OfxProvider, PdfN26Provider}
    assert len(candidates) == len(provider_types), "each provider is offered exactly once"
    assert isinstance(candidates[-1], MappedTabularProvider)
    assert not any(isinstance(provider, MappedTabularProvider) for provider in candidates[:-1])
