"""Source-PDF digest identity for the declaracion parser byte entry point.

:func:`parse_declaracion_bytes` stamps every parsed observation with a
``source_pdf_sha256`` provenance digest and derives the redacted
``source_pdf_path`` reference from it. That digest is a stable content address:
if it ever changes, previously stamped observations stop resolving to their
source artefact.

These tests pin the digest against an oracle OUTSIDE the canonical helper the
parser calls. The expected values come from the published NIST SHA-256 vector
and from the standard library's own :mod:`hashlib`, never from
``core.hashing``, so they fail if the parser's digest mechanics ever drift away
from plain SHA-256 rather than merely agreeing with themselves.
"""

from __future__ import annotations

import hashlib
import os
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.hashing import sha256_hex
from ..parser import parse_declaracion, parse_declaracion_bytes
from ._parser_boundary_support import FIXTURES_DIR, _modelo_snapshot, _write_declaration_pdf

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

#: Published NIST SHA-256 vector for the ASCII bytes ``abc``.
_NIST_ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_canonical_helper_matches_the_published_nist_vector() -> None:
    """``sha256_hex`` reproduces the published NIST SHA-256 vector for ``abc``."""
    assert sha256_hex(b"abc") == _NIST_ABC_SHA256


def test_canonical_helper_agrees_with_the_standard_library_on_pdf_bytes() -> None:
    """``sha256_hex`` agrees with :mod:`hashlib` on real, multi-kilobyte PDF bytes.

    The NIST vector pins a three-byte input; a real justificante exercises the
    same equivalence over a payload large enough to cross any internal buffering.
    """
    pdf_bytes = (FIXTURES_DIR / "justificantes" / "130" / "2022-2T.pdf").read_bytes()

    assert pdf_bytes, "corpus fixture must be non-empty for the digest comparison to mean anything"
    assert sha256_hex(pdf_bytes) == hashlib.sha256(pdf_bytes).hexdigest()


def test_parsed_observation_stamps_the_standard_library_digest_of_its_source_bytes() -> None:
    """The parsed observation's ``source_pdf_sha256`` equals :mod:`hashlib`'s digest.

    Drives the real production path end to end, so a change to the parser's
    digest mechanics surfaces as a provenance mismatch rather than passing
    silently.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "130" / "2022-2T.pdf"
    pdf_bytes = pdf_path.read_bytes()

    filing = parse_declaracion_bytes(
        pdf_bytes,
        modelo_override="130",
        año_override=2022,
        period_override="2T",
    )

    assert filing.source_pdf_sha256 == hashlib.sha256(pdf_bytes).hexdigest()


def test_path_parser_reloads_equal_metadata_replacement_and_stamps_its_digest(tmp_path: Path) -> None:
    """A same-size, same-mtime replacement cannot inherit cached text or provenance.

    Modelo 123 is used (rather than the default modelo 130) because its
    ``numeric_casilla`` targets match on printed label text alone; modelo 130's
    ``bbox_anchored`` targets additionally require the box number to sit in a
    specific x-coordinate band that the generic ``_write_declaration_pdf``
    layout never populates, so no amount of ``values`` could clear its
    coverage floor. The values themselves are incidental to this test, which
    exercises cache/digest identity, not extraction fidelity.
    """
    snapshot = _modelo_snapshot("123", filing_year=2024, period="1T")
    profile = snapshot.extraction_profiles["modelo-123-declaracion-pdf"]
    values = {
        target.casilla_id: Decimal(index).quantize(Decimal("0.01"))
        for index, target in enumerate(profile.target_casillas, start=1)
    }

    first_pdf = tmp_path / "first.pdf"
    second_pdf = tmp_path / "second.pdf"
    target_pdf = tmp_path / "declaracion.pdf"
    _write_declaration_pdf(first_pdf, modelo="123", ejercicio="2024", period="1T", values=values, tax_id="00000000T")
    _write_declaration_pdf(second_pdf, modelo="123", ejercicio="2024", period="1T", values=values, tax_id="00000001R")

    first_bytes = first_pdf.read_bytes()
    second_bytes = second_pdf.read_bytes()
    equal_size = max(len(first_bytes), len(second_bytes))
    first_bytes = first_bytes.ljust(equal_size, b" ")
    second_bytes = second_bytes.ljust(equal_size, b" ")
    assert len(first_bytes) == len(second_bytes)
    assert hashlib.sha256(first_bytes).digest() != hashlib.sha256(second_bytes).digest()

    fixed_ns = 1_700_000_000_000_000_000
    target_pdf.write_bytes(first_bytes)
    os.utime(target_pdf, ns=(fixed_ns, fixed_ns))
    first = parse_declaracion(
        target_pdf,
        modelo_override="123",
        año_override=2024,
        period_override="1T",
    )
    original_stat = target_pdf.stat()

    target_pdf.write_bytes(second_bytes)
    os.utime(target_pdf, ns=(fixed_ns, fixed_ns))
    replacement_stat = target_pdf.stat()
    replacement = parse_declaracion(
        target_pdf,
        modelo_override="123",
        año_override=2024,
        period_override="1T",
    )

    assert replacement_stat.st_size == original_stat.st_size
    assert replacement_stat.st_mtime_ns == original_stat.st_mtime_ns
    assert first.tax_id == "00000000T"
    assert replacement.tax_id == "00000001R"
    assert replacement.source_pdf_sha256 == hashlib.sha256(second_bytes).hexdigest()
