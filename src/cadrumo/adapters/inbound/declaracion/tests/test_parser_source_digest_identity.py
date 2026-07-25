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

import pytest

from .....core.hashing import sha256_hex
from .. import parse_declaracion_bytes
from ._parser_boundary_support import FIXTURES_DIR

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
