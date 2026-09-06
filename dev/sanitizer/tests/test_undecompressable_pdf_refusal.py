"""A PDF-shaped artefact that will not decompress must refuse, not read clean.

:func:`dev.sanitizer.residual_identity.scan_for_residual_identities` reads two
surfaces: the raw bytes, and the decompressed content streams. Identities that
sit inside a Flate stream are invisible on the raw surface, so a decompression
failure on a PDF-shaped artefact leaves the scan unable to see the surface the
answer depends on. Returning an empty tuple there would hand the caller a value
indistinguishable from a clean specimen, which is the one verdict this gate
family exists to make impossible; the scanner therefore re-raises.

An artefact carrying no PDF header is the opposite case -- the real-provenance
corpus also holds images, which have no stream surface at all -- so that failure
is absorbed deliberately.

Both halves of that asymmetry are asserted below, because only the pair pins it:
the refusal alone would still hold if every failure raised, and the absorption
alone would still hold if every failure were swallowed.
"""

from __future__ import annotations

import zlib

import pikepdf
import pytest

from ..residual_identity import scan_for_residual_identities

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: A checksum-valid NIF. The value is the all-zero specimen the sibling planted
#: identity proofs use, so a reader meets one vocabulary rather than two.
_PLANTED_NIF = "00000000T"

_EMPTY_SIDECAR: dict[str, list[object]] = {"replacements_applied": []}

_PDF_MARKER = b"%PDF-1.7\n"


def _flate_hidden_identity() -> bytes:
    """Bytes carrying a checksum-valid NIF only inside a Flate stream.

    The identity is compressed, so it is legible on the decompressed surface and
    absent from the raw one. That is precisely the artefact whose verdict cannot
    be reached without decompression.
    """
    body = zlib.compress(f"BT (NIF: {_PLANTED_NIF}) Tj ET".encode("ascii"))
    header = b"1 0 obj<</Length %d/Filter/FlateDecode>>stream\n" % len(body)
    return header + body + b"\nendstream endobj\n"


def test_the_planted_identity_is_invisible_on_the_raw_surface() -> None:
    """Anti-vacuity: the specimen must really hide its identity under compression."""
    payload = _flate_hidden_identity()

    assert _PLANTED_NIF.encode("ascii") not in payload, (
        "the specimen carries the NIF in cleartext, so the raw surface alone would find it "
        "and the decompression surface this module is about would not be load-bearing"
    )


def test_a_pdf_shaped_artefact_that_will_not_decompress_is_refused() -> None:
    """The blocking half: a PDF header plus an unreadable body must raise."""
    artefact = _PDF_MARKER + _flate_hidden_identity()

    with pytest.raises(pikepdf.PdfError):
        scan_for_residual_identities(artefact, _EMPTY_SIDECAR)


def test_an_artefact_without_a_pdf_header_absorbs_the_failure() -> None:
    """The permitted half: an artefact with no stream surface scans to empty."""
    findings = scan_for_residual_identities(_flate_hidden_identity(), _EMPTY_SIDECAR)

    assert findings == (), "a headerless artefact has no stream surface, so it must scan clean rather than raise"


def test_the_header_is_the_only_difference_between_refusal_and_a_clean_verdict() -> None:
    """The two halves meet on one payload, which is what makes the refusal matter.

    The same bytes scan clean without the marker and refuse with it. Absorbing
    the PDF-shaped failure would therefore return ``()`` for a document that does
    carry a checksum-valid identity -- a clean verdict on a surface never read.
    """
    payload = _flate_hidden_identity()

    assert scan_for_residual_identities(payload, _EMPTY_SIDECAR) == ()

    with pytest.raises(pikepdf.PdfError):
        scan_for_residual_identities(_PDF_MARKER + payload, _EMPTY_SIDECAR)
