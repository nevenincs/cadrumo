"""Unit tests for :mod:`aeat.sanitizer._streams`.

The tests synthesise PDFs in-process with content streams that
pin each text-show operator the sanitiser must rewrite (Tj, TJ,
', "). For each, the test asserts:

* The cleartext is gone from the post-rewrite content stream.
* The synthetic value is present at the same position.
* One :class:`Replacement` row landed per cleartext occurrence,
  carrying the SHA-256 of the cleartext (never the cleartext).
"""

from __future__ import annotations

import hashlib
import io

import pikepdf
import pytest
from pydantic import SecretStr

from ._records import ArbitraryReplacement, NameReplacement, NifReplacement, TokenMap
from ._streams import apply_token_map_to_pdf

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


def _pdf_with_content_stream(stream_bytes: bytes) -> pikepdf.Pdf:
    """Constructs a one-page PDF carrying ``stream_bytes`` as its content."""
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
    """Returns the concatenated raw bytes of every page's content stream."""
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
            b"BT /F1 12 Tf 100 700 Td (Y4113523X) Tj ET\n",
        )
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr("Y4113523X"),
                    synthetic="Y0000001S",
                    surface_label="taxpayer NIE",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert len(edits) == 1
        assert edits[0].surface == "content_stream"
        assert edits[0].surface_index == (0, 3)  # BT, Tf, Td, Tj
        assert edits[0].synthetic == "Y0000001S"
        assert edits[0].encoding == "literal"
        # Hash matches the cleartext.
        expected_sha = hashlib.sha256(b"Y4113523X").hexdigest()
        assert edits[0].real_sha256 == expected_sha
        # Cleartext gone, synthetic present.
        flattened = _flatten_content_streams(pdf)
        assert b"Y4113523X" not in flattened
        assert b"Y0000001S" in flattened

    def test_replaces_when_decoded_from_hex(self) -> None:
        # `<5934313133353233583E>` would actually be `Y4113523X>` —
        # use the canonical hex of `Y4113523X` (10 ASCII chars).
        # `Y4113523X` → 59 34 31 31 33 35 32 33 58
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td <593431313335323358> Tj ET\n",
        )
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr("Y4113523X"),
                    synthetic="Y0000001S",
                    surface_label="taxpayer NIE",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert len(edits) == 1
        assert edits[0].synthetic == "Y0000001S"
        flattened = _flatten_content_streams(pdf)
        assert b"Y4113523X" not in flattened
        assert b"Y0000001S" in flattened


class TestRewriteTJArray:
    """Replaces cleartext inside a TJ array of strings + kerning numbers."""

    def test_replaces_one_string_in_array(self) -> None:
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td [(WOOTSCH GERGELY DOMOKOS) -100 (filler)] TJ ET\n",
        )
        mapping = TokenMap(
            name=(
                NameReplacement(
                    real=SecretStr("WOOTSCH GERGELY DOMOKOS"),
                    synthetic="APELLIDO APELLIDO NOMBRE",
                    surface_label="taxpayer name",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert len(edits) == 1
        assert edits[0].synthetic == "APELLIDO APELLIDO NOMBRE"
        flattened = _flatten_content_streams(pdf)
        assert b"WOOTSCH GERGELY DOMOKOS" not in flattened
        assert b"APELLIDO APELLIDO NOMBRE" in flattened


class TestRewriteApostropheOperator:
    """The ' operator (move + show) is rewritten."""

    def test_replaces_quote_operand(self) -> None:
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td (Y4113523X) ' ET\n",
        )
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr("Y4113523X"),
                    synthetic="Y0000001S",
                    surface_label="taxpayer NIE",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert len(edits) == 1
        flattened = _flatten_content_streams(pdf)
        assert b"Y4113523X" not in flattened


class TestRewriteDoubleQuoteOperator:
    """The " operator (set spacing + show) is rewritten."""

    def test_replaces_doublequote_operand(self) -> None:
        pdf = _pdf_with_content_stream(
            b'BT /F1 12 Tf 100 700 Td 0 0 (Y4113523X) " ET\n',
        )
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr("Y4113523X"),
                    synthetic="Y0000001S",
                    surface_label="taxpayer NIE",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert len(edits) == 1
        flattened = _flatten_content_streams(pdf)
        assert b"Y4113523X" not in flattened


class TestNoMatch:
    """Nothing is mutated when no real value occurs."""

    def test_no_edits_when_cleartext_absent(self) -> None:
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td (only a banner) Tj ET\n",
        )
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr("Y4113523X"),
                    synthetic="Y0000001S",
                    surface_label="taxpayer NIE",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert edits == ()

    def test_no_edits_when_mapping_empty(self) -> None:
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td (Y4113523X) Tj ET\n",
        )
        edits = apply_token_map_to_pdf(pdf, TokenMap())
        assert edits == ()


class TestMultipleOccurrences:
    """One :class:`Replacement` row per occurrence of the same cleartext."""

    def test_two_hits_in_one_operand(self) -> None:
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td (Y4113523X and again Y4113523X) Tj ET\n",
        )
        mapping = TokenMap(
            nif=(
                NifReplacement(
                    real=SecretStr("Y4113523X"),
                    synthetic="Y0000001S",
                    surface_label="taxpayer NIE",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        assert len(edits) == 2
        flattened = _flatten_content_streams(pdf)
        assert flattened.count(b"Y4113523X") == 0
        assert flattened.count(b"Y0000001S") == 2


class TestLongestMatchPriority:
    """Longer cleartext values match first, so a shorter prefix doesn't shadow."""

    def test_longer_real_matches_before_shorter(self) -> None:
        # If "Y4113523X" replaced first with "X", a later "Y4113523" → "Y" rule
        # could leave the synthetic "X" still in the output. Sort by descending
        # real-length to defend against this.
        pdf = _pdf_with_content_stream(
            b"BT /F1 12 Tf 100 700 Td (Y4113523X) Tj ET\n",
        )
        mapping = TokenMap(
            arbitrary=(
                ArbitraryReplacement(
                    real=SecretStr("Y4113523"),
                    synthetic="SHORTER",
                    surface_label="prefix-only",
                ),
                ArbitraryReplacement(
                    real=SecretStr("Y4113523X"),
                    synthetic="LONGER",
                    surface_label="full-id",
                ),
            ),
        )
        edits = apply_token_map_to_pdf(pdf, mapping)
        flattened = _flatten_content_streams(pdf)
        # Longer match should have applied first, leaving no Y4113523-prefix
        # for the shorter rule to find.
        assert b"Y4113523" not in flattened
        assert b"LONGER" in flattened
        assert b"SHORTER" not in flattened
        assert len(edits) == 1
