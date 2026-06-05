"""Unit tests for :mod:`aeat.adapters.inbound.sanitizer._dynamic` and ``_structtree``.

Each surface is exercised in isolation against a synthesised PDF
that pins the surface in question. The tests assert presence
before, absence after, and the correct counter recording on the
:class:`ScrubbedSurface` row returned.
"""

from __future__ import annotations

import io

import pikepdf
import pytest

from .._dynamic import (
    strip_acroform,
    strip_annotations,
    strip_attachments,
    strip_javascript,
    strip_optional_content_groups,
    strip_outlines,
    strip_page_labels,
    strip_thumbnails,
)
from .._structtree import drop_struct_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _new_one_page_pdf() -> pikepdf.Pdf:
    """Returns a freshly-allocated minimal one-page PDF."""
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(612, 792))
    return pdf


def _round_trip(pdf: pikepdf.Pdf) -> pikepdf.Pdf:
    """Save + re-open ``pdf`` so structural mutations settle."""
    buffer = io.BytesIO()
    pdf.save(buffer)
    buffer.seek(0)
    return pikepdf.Pdf.open(buffer)


class TestStripAttachments:
    """Embedded files are removed wholesale."""

    def test_removes_attached_file(self) -> None:
        pdf = _new_one_page_pdf()
        pdf.attachments["payload.txt"] = b"sensitive payload"
        result = strip_attachments(pdf)
        assert result.surface == "attachments"
        assert result.count == 1
        re_opened = _round_trip(pdf)
        assert len(list(re_opened.attachments)) == 0

    def test_no_op_when_table_empty(self) -> None:
        pdf = _new_one_page_pdf()
        result = strip_attachments(pdf)
        assert result.count == 0


class TestStripJavascript:
    """JavaScript surfaces in Names tree, OpenAction, AA are removed."""

    def test_removes_open_action(self) -> None:
        pdf = _new_one_page_pdf()
        pdf.Root["/OpenAction"] = pikepdf.Dictionary(
            S=pikepdf.Name.JavaScript,
            JS="alert('boo');",
        )
        _js, oa, _aa = strip_javascript(pdf)
        assert oa.count == 1
        assert "/OpenAction" not in pdf.Root

    def test_removes_root_aa(self) -> None:
        pdf = _new_one_page_pdf()
        pdf.Root["/AA"] = pikepdf.Dictionary()
        _, _, aa = strip_javascript(pdf)
        assert aa.count >= 1
        assert "/AA" not in pdf.Root

    def test_removes_per_page_aa(self) -> None:
        pdf = _new_one_page_pdf()
        page = pdf.pages[0]
        page.obj["/AA"] = pikepdf.Dictionary()
        _, _, aa = strip_javascript(pdf)
        assert aa.count >= 1
        assert "/AA" not in pdf.pages[0].obj

    def test_no_op_when_absent(self) -> None:
        pdf = _new_one_page_pdf()
        js, oa, aa = strip_javascript(pdf)
        assert js.count == 0
        assert oa.count == 0
        assert aa.count == 0


class TestStripAnnotations:
    """Annotations on every page are dropped."""

    def test_drops_annotation_array(self) -> None:
        pdf = _new_one_page_pdf()
        page = pdf.pages[0]
        annot = pikepdf.Dictionary(
            Type=pikepdf.Name.Annot,
            Subtype=pikepdf.Name.Text,
            Contents="real comment",
            Rect=[0, 0, 100, 100],
        )
        page.obj["/Annots"] = pikepdf.Array([annot])
        result = strip_annotations(pdf)
        assert result.count == 1
        re_opened = _round_trip(pdf)
        assert "/Annots" not in re_opened.pages[0].obj

    def test_no_op_when_absent(self) -> None:
        pdf = _new_one_page_pdf()
        result = strip_annotations(pdf)
        assert result.count == 0


class TestStripOptionalContentGroups:
    """OCG layers are removed."""

    def test_drops_ocproperties(self) -> None:
        pdf = _new_one_page_pdf()
        pdf.Root["/OCProperties"] = pikepdf.Dictionary(OCGs=pikepdf.Array(), D=pikepdf.Dictionary())
        result = strip_optional_content_groups(pdf)
        assert result.count == 1
        assert "/OCProperties" not in pdf.Root

    def test_no_op_when_absent(self) -> None:
        pdf = _new_one_page_pdf()
        result = strip_optional_content_groups(pdf)
        assert result.count == 0


class TestStripAcroform:
    """AcroForm field values are cleared; whole form drops on demand."""

    def test_clears_field_values_in_place(self) -> None:
        pdf = _new_one_page_pdf()
        field = pikepdf.Dictionary(T="taxpayer_nif", V="Y1234567X", DV="Y1234567X")
        pdf.Root["/AcroForm"] = pikepdf.Dictionary(Fields=pikepdf.Array([field]))
        result, warnings = strip_acroform(pdf)
        assert result.surface == "acroform_field_value"
        assert result.count == 1
        assert warnings == ()
        re_opened = _round_trip(pdf)
        re_field = re_opened.Root["/AcroForm"]["/Fields"][0]
        assert "/V" not in re_field
        assert "/DV" not in re_field

    def test_drops_form_entirely(self) -> None:
        pdf = _new_one_page_pdf()
        pdf.Root["/AcroForm"] = pikepdf.Dictionary(Fields=pikepdf.Array())
        result, warnings = strip_acroform(pdf, drop_entirely=True)
        assert result.surface == "acroform_dropped"
        assert result.count == 1
        assert warnings == ()
        assert "/AcroForm" not in pdf.Root

    def test_no_op_when_absent(self) -> None:
        pdf = _new_one_page_pdf()
        result, warnings = strip_acroform(pdf)
        assert result.count == 0
        assert warnings == ()

    def test_emits_warning_when_kids_present(self) -> None:
        pdf = _new_one_page_pdf()
        child = pikepdf.Dictionary(T="child", V="real_value")
        parent = pikepdf.Dictionary(T="parent", Kids=pikepdf.Array([child]))
        pdf.Root["/AcroForm"] = pikepdf.Dictionary(Fields=pikepdf.Array([parent]))
        result, warnings = strip_acroform(pdf)
        assert result.surface == "acroform_field_value"
        assert {w.code for w in warnings} == {"unknown_surface_present"}


class TestStripThumbnails:
    """Per-page thumbnails are dropped."""

    def test_drops_thumb(self) -> None:
        pdf = _new_one_page_pdf()
        page = pdf.pages[0]
        page.obj["/Thumb"] = pikepdf.Stream(pdf, b"raster bytes here")
        result = strip_thumbnails(pdf)
        assert result.count == 1
        re_opened = _round_trip(pdf)
        assert "/Thumb" not in re_opened.pages[0].obj

    def test_no_op_when_absent(self) -> None:
        pdf = _new_one_page_pdf()
        result = strip_thumbnails(pdf)
        assert result.count == 0


class TestStripOutlines:
    """Bookmarks are dropped."""

    def test_drops_outlines(self) -> None:
        pdf = _new_one_page_pdf()
        pdf.Root["/Outlines"] = pikepdf.Dictionary(Type=pikepdf.Name.Outlines, Count=0)
        result = strip_outlines(pdf)
        assert result.count == 1
        assert "/Outlines" not in pdf.Root

    def test_no_op_when_absent(self) -> None:
        pdf = _new_one_page_pdf()
        result = strip_outlines(pdf)
        assert result.count == 0


class TestStripPageLabels:
    """PageLabels are dropped."""

    def test_drops_page_labels(self) -> None:
        pdf = _new_one_page_pdf()
        pdf.Root["/PageLabels"] = pikepdf.Dictionary(Nums=pikepdf.Array())
        result = strip_page_labels(pdf)
        assert result.count == 1
        assert "/PageLabels" not in pdf.Root

    def test_no_op_when_absent(self) -> None:
        pdf = _new_one_page_pdf()
        result = strip_page_labels(pdf)
        assert result.count == 0


class TestDropStructTree:
    """StructTree drop emits the lossy warning when present."""

    def test_drops_struct_tree(self) -> None:
        pdf = _new_one_page_pdf()
        pdf.Root["/StructTreeRoot"] = pikepdf.Dictionary(
            Type=pikepdf.Name.StructTreeRoot,
            K=pikepdf.Array(),
        )
        pdf.Root["/MarkInfo"] = pikepdf.Dictionary(Marked=True)
        scrubbed, warnings = drop_struct_tree(pdf)
        assert scrubbed.count == 1
        codes = {w.code for w in warnings}
        assert "structtree_dropped_lossy" in codes
        assert "/StructTreeRoot" not in pdf.Root
        assert "/MarkInfo" not in pdf.Root

    def test_no_op_when_absent(self) -> None:
        pdf = _new_one_page_pdf()
        scrubbed, warnings = drop_struct_tree(pdf)
        assert scrubbed.count == 0
        assert warnings == ()
