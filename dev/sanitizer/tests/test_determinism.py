"""Determinism tests for :mod:`dev.sanitizer._determinism`.

The byte-stable save flag set is the load-bearing primitive for
fixture diff review: without it, two runs against the same source
produce different bytes and "the sanitised fixture matches the
sanitiser's output" stops being a checkable property. These tests
build a tiny PDF in-process with :mod:`pikepdf`, save it twice
through the deterministic helper, and assert byte equality.
"""

from __future__ import annotations

import io

import pikepdf
import pytest
from pikepdf import ObjectStreamMode

from .._determinism import deterministic_save_flags, save_with_deterministic_flags

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _new_one_page_pdf() -> pikepdf.Pdf:
    """Constructs a minimal one-page PDF in-memory.

    Returns:
        A fresh :class:`pikepdf.Pdf` with a single empty page.
    """
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    return pdf


class TestDeterministicSave:
    """The canonical flag set must produce byte-stable output."""

    def test_returns_canonical_flags(self) -> None:
        flags = deterministic_save_flags()
        assert flags.deterministic_id is True
        assert flags.static_id is False
        assert flags.object_stream_mode == "preserve"
        assert flags.linearize is False
        assert flags.recompress_flate is False
        assert flags.compress_streams is True

    def test_two_saves_produce_byte_equal_output(self) -> None:
        pdf_a = _new_one_page_pdf()
        bytes_a, flags_a = save_with_deterministic_flags(pdf_a)

        pdf_b = _new_one_page_pdf()
        bytes_b, flags_b = save_with_deterministic_flags(pdf_b)

        assert bytes_a == bytes_b
        assert flags_a == flags_b

    def test_default_save_is_non_deterministic_under_mutation(self) -> None:
        # Establishes the failure mode the deterministic flag set
        # defends against. Without ``deterministic_id=True`` the
        # ``/ID`` array gets re-stamped any time pikepdf re-emits
        # the trailer with mutated metadata. Two saves of the same
        # in-memory PDF after identical metadata mutations should
        # produce different bytes under default save (the timestamp
        # seeds the /ID array). The deterministic helper protects
        # the fixture-diff workflow against that drift.
        first = _new_one_page_pdf()
        with first.open_metadata() as metadata:
            metadata["dc:title"] = "drift"
        buffer_first = io.BytesIO()
        first.save(buffer_first)

        second = _new_one_page_pdf()
        with second.open_metadata() as metadata:
            metadata["dc:title"] = "drift"
        buffer_second = io.BytesIO()
        second.save(buffer_second)

        assert buffer_first.getvalue() != buffer_second.getvalue()

    def test_round_trip_through_save_is_parseable(self) -> None:
        pdf = _new_one_page_pdf()
        output, _ = save_with_deterministic_flags(pdf)
        re_opened = pikepdf.Pdf.open(io.BytesIO(output))
        assert len(re_opened.pages) == 1

    def test_the_reported_flags_are_the_flags_the_save_actually_applied(self) -> None:
        """The record shipped with the bytes must describe the save that made them.

        The flag set was declared twice — once as the audited
        :class:`DeterminismFlags` record, once as literal keywords on the
        ``Pdf.save`` call — and nothing compared the two. A save call edited
        away from the record kept returning the unchanged record, so every
        ``SanitizationResult`` would attest a flag set that never ran.

        Saving the same PDF a second time with the keywords read back off the
        REPORTED record reproduces the bytes only while the call still follows
        it; a divergence in ``deterministic_id``, ``static_id``,
        ``object_stream_mode``, ``linearize`` or ``compress_streams`` changes
        the output and reddens here.
        """
        reported_bytes, flags = save_with_deterministic_flags(_new_one_page_pdf())

        replayed = io.BytesIO()
        _new_one_page_pdf().save(
            replayed,
            deterministic_id=flags.deterministic_id,
            static_id=flags.static_id,
            object_stream_mode=ObjectStreamMode[flags.object_stream_mode],
            linearize=flags.linearize,
            recompress_flate=flags.recompress_flate,
            compress_streams=flags.compress_streams,
        )

        assert reported_bytes == replayed.getvalue(), "the save applied flags other than the ones it reported"
