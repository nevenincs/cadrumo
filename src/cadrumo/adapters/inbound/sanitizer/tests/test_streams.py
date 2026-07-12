"""Unit tests for :mod:`cadrumo.adapters.inbound.sanitizer._streams`.

The tests synthesise PDFs in-process with content streams that pin each
text-show operator the sanitiser must rewrite (``Tj``, ``TJ``, ``'``,
``"``). For each operator the test asserts that the cleartext is gone
from the post-rewrite content stream, the synthetic value is present at
the same position, and one
:class:`cadrumo.adapters.inbound.sanitizer._records.Replacement` row landed
per cleartext occurrence carrying the SHA-256 of the cleartext (never
the cleartext itself).
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Callable

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


def _nif_mapping() -> TokenMap:
    return TokenMap(
        nif=(
            NifReplacement(
                real=SecretStr(_REAL_NIE_CANARY),
                synthetic=_SYNTHETIC_NIE,
                surface_label="taxpayer NIE",
            ),
        ),
    )


def _name_mapping() -> TokenMap:
    return TokenMap(
        name=(
            NameReplacement(
                real=SecretStr(_REAL_NAME_CANARY),
                synthetic=_SYNTHETIC_NAME,
                surface_label="taxpayer name",
            ),
        ),
    )


_RewriteCase = tuple[str, bytes, Callable[[], TokenMap], str, str]

_SINGLE_REWRITE_CASES: tuple[_RewriteCase, ...] = (
    ("literal-tj", b"BT /F1 12 Tf 100 700 Td (Y1234567X) Tj ET\n", _nif_mapping, _REAL_NIE_CANARY, _SYNTHETIC_NIE),
    (
        "ascii-hex-tj",
        b"BT /F1 12 Tf 100 700 Td <593132333435363758> Tj ET\n",
        _nif_mapping,
        _REAL_NIE_CANARY,
        _SYNTHETIC_NIE,
    ),
    (
        "tj-array",
        b"BT /F1 12 Tf 100 700 Td [(PERSONA PRUEBA UNO) -100 (filler)] TJ ET\n",
        _name_mapping,
        _REAL_NAME_CANARY,
        _SYNTHETIC_NAME,
    ),
    ("quote", b"BT /F1 12 Tf 100 700 Td (Y1234567X) ' ET\n", _nif_mapping, _REAL_NIE_CANARY, _SYNTHETIC_NIE),
    (
        "doublequote",
        b'BT /F1 12 Tf 100 700 Td 0 0 (Y1234567X) " ET\n',
        _nif_mapping,
        _REAL_NIE_CANARY,
        _SYNTHETIC_NIE,
    ),
)


def test_rewrites_single_text_show_operator_cases() -> None:
    for case_id, stream_bytes, mapping_factory, real, synthetic in _SINGLE_REWRITE_CASES:
        pdf = _pdf_with_content_stream(stream_bytes)
        edits = apply_token_map_to_pdf(pdf, mapping_factory())

        assert len(edits) == 1, case_id
        assert edits[0].surface == "content_stream", case_id
        assert edits[0].surface_index == (0, 3), case_id
        assert edits[0].synthetic == synthetic, case_id
        assert edits[0].encoding == "literal", case_id
        assert edits[0].real_sha256 == hashlib.sha256(real.encode("utf-8")).hexdigest(), case_id

        flattened = _flatten_content_streams(pdf)
        assert real.encode("utf-8") not in flattened, case_id
        assert synthetic.encode("utf-8") in flattened, case_id


def test_no_edits_when_no_cleartext_match_or_mapping_empty() -> None:
    cases = (
        ("cleartext-absent", b"BT /F1 12 Tf 100 700 Td (only a banner) Tj ET\n", _nif_mapping()),
        ("mapping-empty", b"BT /F1 12 Tf 100 700 Td (Y1234567X) Tj ET\n", TokenMap()),
    )
    for case_id, stream_bytes, mapping in cases:
        pdf = _pdf_with_content_stream(stream_bytes)
        assert apply_token_map_to_pdf(pdf, mapping) == (), case_id


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
