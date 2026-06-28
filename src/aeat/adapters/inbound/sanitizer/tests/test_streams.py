"""Unit tests for :mod:`aeat.adapters.inbound.sanitizer._streams`.

The tests synthesise PDFs in-process with content streams that pin each
text-show operator the sanitiser must rewrite (``Tj``, ``TJ``, ``'``,
``"``). For each operator the test asserts that the cleartext is gone
from the post-rewrite content stream, the synthetic value is present at
the same position, and one
:class:`aeat.adapters.inbound.sanitizer._records.Replacement` row landed
per cleartext occurrence carrying the SHA-256 of the cleartext (never
the cleartext itself).
"""

from __future__ import annotations

import hashlib
import io

import pikepdf
import pytest
from pydantic import SecretStr

from .._records import ArbitraryReplacement, NameReplacement, NifReplacement, TokenMap
from .._streams import apply_token_map_to_pdf

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_REAL_NIE_CANARY = "Y1234567X"
_REAL_NIE_CANARY_PREFIX = "Y1234567"
_REAL_NAME_CANARY = "PERSONA PRUEBA UNO"
_SYNTHETIC_NIE = "Y0000001S"
_SYNTHETIC_NAME = "APELLIDO APELLIDO NOMBRE"


def _pdf_with_content_stream(stream_bytes: bytes) -> pikepdf.Pdf:
    """Construct a one-page PDF carrying ``stream_bytes`` as its content.

    Args:
        stream_bytes: Raw PDF content stream operators to embed.

    Returns:
        A reopened :class:`pikepdf.Pdf` round-tripped through ``save``
        so the content stream lands in its on-disk form before the
        rewriter runs.
    """
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    pdf.pages[0].contents_add(stream_bytes)
    # Round-trip through save+reopen so the content stream lands
    # in its on-disk form before the test exercises the rewriter.
    buffer = io.BytesIO()
    pdf.save(buffer)
    buffer.seek(0)
    return pikepdf.Pdf.open(buffer)


def _flatten_content_streams(pdf: pikepdf.Pdf) -> bytes:
    """Return the concatenated raw bytes of every page's content stream."""
    chunks: list[bytes] = []
    for page in pdf.pages:
        contents = page.obj.get("/Contents")
        if contents is None:
            continue
        if isinstance(contents, pikepdf.Array):
            for index in range(len(contents)):
                chunks.append(bytes(contents[index].read_bytes()))
        else:
            chunks.append(bytes(contents.read_bytes()))
    return b"\n".join(chunks)


class TestRewriteSingleTj:
    """Replaces a cleartext value carried by a literal-encoded Tj operand."""

    def test_replaces_literal_string(self) -> None:
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td (Y1234567X) Tj ET\n",
        )
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr(_REAL_NIE_CANARY),
                    synthetic=_SYNTHETIC_NIE,
                    surface_label="taxpayer NIE",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert len(edits) == 1
        assert edits[0].surface == "content_stream"
        assert edits[0].surface_index == (0, 3)  # BT, Tf, Td, Tj
        assert edits[0].synthetic == _SYNTHETIC_NIE
        assert edits[0].encoding == "literal"
        # Hash matches the cleartext.
        expected_sha = hashlib.sha256(_REAL_NIE_CANARY.encode("utf-8")).hexdigest()
        assert edits[0].real_sha256 == expected_sha
        # Cleartext gone, synthetic present.
        flattened = _flatten_content_streams(pdf)
        assert _REAL_NIE_CANARY.encode("utf-8") not in flattened
        assert _SYNTHETIC_NIE.encode("utf-8") in flattened

    def test_replaces_when_decoded_from_hex(self) -> None:
        # Use the canonical ASCII hex of the synthetic NIE canary.
        # `Y1234567X` -> 59 31 32 33 34 35 36 37 58
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td <593132333435363758> Tj ET\n",
        )
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr(_REAL_NIE_CANARY),
                    synthetic=_SYNTHETIC_NIE,
                    surface_label="taxpayer NIE",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert len(edits) == 1
        assert edits[0].synthetic == _SYNTHETIC_NIE
        flattened = _flatten_content_streams(pdf)
        assert _REAL_NIE_CANARY.encode("utf-8") not in flattened
        assert _SYNTHETIC_NIE.encode("utf-8") in flattened


class TestRewriteTJArray:
    """Replaces cleartext inside a TJ array of strings + kerning numbers."""

    def test_replaces_one_string_in_array(self) -> None:
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td [(PERSONA PRUEBA UNO) -100 (filler)] TJ ET\n",
        )
        mapping = TokenMap(
            name=(
                NameReplacement(
                    real=SecretStr(_REAL_NAME_CANARY),
                    synthetic=_SYNTHETIC_NAME,
                    surface_label="taxpayer name",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert len(edits) == 1
        assert edits[0].synthetic == _SYNTHETIC_NAME
        flattened = _flatten_content_streams(pdf)
        assert _REAL_NAME_CANARY.encode("utf-8") not in flattened
        assert _SYNTHETIC_NAME.encode("utf-8") in flattened


class TestRewriteApostropheOperator:
    """The ' operator (move + show) is rewritten."""

    def test_replaces_quote_operand(self) -> None:
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td (Y1234567X) ' ET\n",
        )
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr(_REAL_NIE_CANARY),
                    synthetic=_SYNTHETIC_NIE,
                    surface_label="taxpayer NIE",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert len(edits) == 1
        flattened = _flatten_content_streams(pdf)
        assert _REAL_NIE_CANARY.encode("utf-8") not in flattened


class TestRewriteDoubleQuoteOperator:
    """The " operator (set spacing + show) is rewritten."""

    def test_replaces_doublequote_operand(self) -> None:
        pdf = _pdf_with_content_stream(
            b'BT /F1 12 Tf 100 700 Td 0 0 (Y1234567X) " ET\n',
        )
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr(_REAL_NIE_CANARY),
                    synthetic=_SYNTHETIC_NIE,
                    surface_label="taxpayer NIE",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert len(edits) == 1
        flattened = _flatten_content_streams(pdf)
        assert _REAL_NIE_CANARY.encode("utf-8") not in flattened


class TestNoMatch:
    """Nothing is mutated when no real value occurs."""

    def test_no_edits_when_cleartext_absent(self) -> None:
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td (only a banner) Tj ET\n",
        )
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr(_REAL_NIE_CANARY),
                    synthetic=_SYNTHETIC_NIE,
                    surface_label="taxpayer NIE",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert edits == ()

    def test_no_edits_when_mapping_empty(self) -> None:
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td (Y1234567X) Tj ET\n",
        )
        edits = apply_token_map_to_pdf(pdf, TokenMap())
        assert edits == ()


class TestMultipleOccurrences:
    """One :class:`Replacement` row per occurrence of the same cleartext."""

    def test_two_hits_in_one_operand(self) -> None:
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td (Y1234567X and again Y1234567X) Tj ET\n",
        )
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr(_REAL_NIE_CANARY),
                    synthetic=_SYNTHETIC_NIE,
                    surface_label="taxpayer NIE",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert len(edits) == 2
        flattened = _flatten_content_streams(pdf)
        assert flattened.count(_REAL_NIE_CANARY.encode("utf-8")) == 0
        assert flattened.count(_SYNTHETIC_NIE.encode("utf-8")) == 2


class TestLongestMatchPriority:
    """Longer cleartext values match first, before any shorter prefix."""

    def test_longer_real_matches_before_shorter(self) -> None:
        # If the full NIE is replaced first with "X", a later prefix rule
        # could leave the synthetic "X" still in the output. Sort by descending
        # real-length to defend against this.
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td (Y1234567X) Tj ET\n",
        )
        mapping = TokenMap(
            arbitrary=(
                ArbitraryReplacement(
                    real=SecretStr(_REAL_NIE_CANARY_PREFIX),
                    synthetic="SHORTER",
                    surface_label="prefix-only",
                ),
                ArbitraryReplacement(
                    real=SecretStr(_REAL_NIE_CANARY),
                    synthetic="LONGER",
                    surface_label="full-id",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        flattened = _flatten_content_streams(pdf)
        # Longer match should have applied first, leaving no NIE-prefix
        # for the shorter rule to find.
        assert _REAL_NIE_CANARY_PREFIX.encode("utf-8") not in flattened
        assert b"LONGER" in flattened
        assert b"SHORTER" not in flattened
        assert len(edits) == 1
