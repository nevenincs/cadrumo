"""A calculation summary is tagged, archival and self-describing, and says so honestly.

These are the machine-checkable halves of PDF/UA-1 and PDF/A-3 level ``a`` that
matter most to a reader using assistive technology and to an archive: every piece
of text is either in the logical structure or marked as decoration, the structure
tree and its parent tree agree, table headers carry a scope, the language and
title are declared, the embedded files are associated with their media type and
relationship, and every metadata property outside the predefined schemas is
declared. The independent validator is the development recipe; these checks run
in every lane.
"""

from __future__ import annotations

import io
from typing import Final

import pikepdf
import pytest
from defusedxml import ElementTree
from pikepdf import Name

from .....application.modelo.calculation_report_certification import CERTIFICATION_XMP_PROPERTIES
from .....application.modelo.calculation_summary_pdf_ports import (
    CALCULATION_SUMMARY_ATTACHMENTS,
    CALCULATION_SUMMARY_XMP_NAMESPACE,
)
from .....application.modelo.calculation_summary_presentation import (
    CalculationSummaryPresentation,
    build_calculation_summary_presentation,
)
from .....core.external_constants import OutputLanguage
from ..structure_tagging import SummaryTagPlanMismatchError, tag_summary_pages
from ..summary_layout import draw_summary_pages, lay_out_summary
from .summary_report_support import render_summary, synthetic_keypair, synthetic_report

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TEXT_SHOWING: Final[frozenset[str]] = frozenset({"Tj", "TJ", "'", '"'})
_PATH_CONSTRUCTION: Final[frozenset[str]] = frozenset({"m", "l", "c", "v", "y", "h", "re"})
_RDF = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
_PDFA_EXTENSION = "{http://www.aiim.org/pdfa/ns/extension/}"
_PDFA_SCHEMA = "{http://www.aiim.org/pdfa/ns/schema#}"
_PDFA_PROPERTY = "{http://www.aiim.org/pdfa/ns/property#}"
_PDFUA_NAMESPACE = "http://www.aiim.org/pdfua/ns/id/"


def untagged_content(pdf: pikepdf.Pdf) -> list[str]:
    """Return every text object or path drawn outside tagged or artifact content."""
    findings: list[str] = []
    for page_number, page in enumerate(pdf.pages, start=1):
        marks: list[str] = []
        in_text = False
        for instruction in pikepdf.parse_content_stream(page):
            operator = str(instruction.operator)
            if operator in {"BDC", "BMC"}:
                tag = str(instruction.operands[0])
                is_content_item = operator == "BDC" and "/MCID" in instruction.operands[1]
                marks.append("artifact" if tag == "/Artifact" else ("tagged" if is_content_item else "other"))
            elif operator == "EMC":
                marks.pop()
            elif operator == "BT":
                in_text = True
            elif operator == "ET":
                in_text = False
            elif operator in _TEXT_SHOWING and in_text and (not marks or marks[-1] == "other"):
                findings.append(f"page {page_number}: text outside marked content")
            elif operator in _PATH_CONSTRUCTION and (not marks or marks[-1] != "artifact"):
                findings.append(f"page {page_number}: path outside an artifact")
    return findings


def _content_items(page: pikepdf.Page) -> list[int]:
    return [
        int(instruction.operands[1].MCID)
        for instruction in pikepdf.parse_content_stream(page)
        if str(instruction.operator) == "BDC" and "/MCID" in instruction.operands[1]
    ]


def _element_kids(element: pikepdf.Object) -> list[pikepdf.Object]:
    kids = element.get("/K")
    if kids is None:
        return []
    return list(kids) if isinstance(kids, pikepdf.Array) else [kids]


def _structure_elements(root: pikepdf.Object) -> list[pikepdf.Object]:
    found: list[pikepdf.Object] = []
    pending = _element_kids(root)
    while pending:
        element = pending.pop()
        if isinstance(element, pikepdf.Dictionary) and element.get("/Type") == Name.StructElem:
            found.append(element)
            pending.extend(_element_kids(element))
    return found


@pytest.fixture(scope="module")
def summary() -> pikepdf.Pdf:
    return pikepdf.open(io.BytesIO(render_summary(synthetic_report(OutputLanguage.HU)).payload))


def test_every_text_object_is_tagged_or_an_artifact_and_every_path_is_decoration(summary: pikepdf.Pdf) -> None:
    assert untagged_content(summary) == []


def test_the_parent_tree_names_the_element_owning_every_content_item(summary: pikepdf.Pdf) -> None:
    """Each numbered content item resolves, through the parent tree, to an element that claims it."""
    parent_tree = summary.Root.StructTreeRoot.ParentTree.Nums
    owners_by_page = {int(parent_tree[index]): parent_tree[index + 1] for index in range(0, len(parent_tree), 2)}
    for page_index, page in enumerate(summary.pages):
        items = _content_items(page)
        assert items == list(range(len(items)))
        owners = owners_by_page[int(page.obj.StructParents)]
        assert len(owners) == len(items)
        for mcid in items:
            owner = owners[mcid]
            claimed = []
            for kid in _element_kids(owner):
                if isinstance(kid, int):
                    claimed.append((owner.Pg.objgen, kid))
                elif isinstance(kid, pikepdf.Dictionary) and kid.get("/Type") == Name.MCR:
                    claimed.append((kid.Pg.objgen, int(kid.MCID)))
            assert (summary.pages[page_index].obj.objgen, mcid) in claimed


def test_structure_uses_standard_roles_and_every_table_header_has_a_scope(summary: pikepdf.Pdf) -> None:
    elements = _structure_elements(summary.Root.StructTreeRoot)
    roles = {str(element.S) for element in elements}

    assert roles <= {"/Document", "/H1", "/H2", "/P", "/Div", "/Table", "/TR", "/TH", "/TD"}
    assert {"/Document", "/H1", "/H2", "/Table", "/TR", "/TH", "/TD"} <= roles
    headers = [element for element in elements if element.S == Name.TH]
    assert headers
    assert all(str(header.A.Scope) in {"/Row", "/Column"} for header in headers)


def test_the_document_declares_language_title_display_and_marking(summary: pikepdf.Pdf) -> None:
    assert str(summary.Root.Lang) == OutputLanguage.HU.value
    assert bool(summary.Root.ViewerPreferences.DisplayDocTitle) is True
    assert bool(summary.Root.MarkInfo.Marked) is True
    assert "/Info" not in summary.trailer
    assert str(summary.Root.OutputIntents[0].S) == "/GTS_PDFA1"


def test_every_embedded_file_is_associated_with_its_media_type_and_relationship(summary: pikepdf.Pdf) -> None:
    associated = {str(spec.UF): spec for spec in summary.Root.AF}

    assert set(associated) == {attachment.name for attachment in CALCULATION_SUMMARY_ATTACHMENTS}
    for attachment in CALCULATION_SUMMARY_ATTACHMENTS:
        spec = associated[attachment.name]
        assert str(spec.AFRelationship) == f"/{attachment.relationship}"
        assert str(spec.EF.F.Subtype) == "/" + attachment.mime_type


def test_every_product_metadata_property_is_declared_in_the_extension_schema(summary: pikepdf.Pdf) -> None:
    """Archival conformance admits a property outside the predefined schemas only when declared."""
    packet = ElementTree.fromstring(summary.Root.Metadata.read_bytes())
    declared: dict[str, set[str]] = {}
    for schema in packet.iter(f"{_RDF}li"):
        namespace = schema.find(f"{_PDFA_SCHEMA}namespaceURI")
        if namespace is not None:
            declared[namespace.text or ""] = {name.text or "" for name in schema.iter(f"{_PDFA_PROPERTY}name")}
    used = {
        element.tag.split("}", 1)[1]
        for element in packet.iter()
        if element.tag.startswith("{" + CALCULATION_SUMMARY_XMP_NAMESPACE + "}")
    }

    assert used, "the summary's metadata carries no product property at all"
    assert used <= declared[CALCULATION_SUMMARY_XMP_NAMESPACE]
    assert declared[CALCULATION_SUMMARY_XMP_NAMESPACE] == {name for name, _ in CERTIFICATION_XMP_PROPERTIES}
    assert declared[_PDFUA_NAMESPACE] == {"part"}
    assert any(True for _ in packet.iter(f"{_PDFA_EXTENSION}schemas"))


def test_a_plan_longer_than_the_drawn_text_is_refused() -> None:
    """Detector teeth: a planned entry with no text object behind it stops tagging."""
    drawn = draw_summary_pages(lay_out_summary(_presentation()), language="es")
    plans = [list(plan) for plan in drawn.plans]
    plans[0].append(None)

    with pikepdf.open(io.BytesIO(drawn.payload)) as pdf, pytest.raises(SummaryTagPlanMismatchError):
        tag_summary_pages(pdf, plans, language="es")


def test_drawn_text_the_plan_does_not_cover_is_refused() -> None:
    """Detector teeth: a text object with no planned entry stops tagging."""
    drawn = draw_summary_pages(lay_out_summary(_presentation()), language="es")
    plans = [list(plan) for plan in drawn.plans]
    plans[-1].pop()

    with pikepdf.open(io.BytesIO(drawn.payload)) as pdf, pytest.raises(SummaryTagPlanMismatchError):
        tag_summary_pages(pdf, plans, language="es")


def test_an_untagged_heading_is_found_by_the_structure_check(summary: pikepdf.Pdf) -> None:
    """Detector teeth: stripping one heading's marked content is what the check reports."""
    with pikepdf.open(io.BytesIO(render_summary(synthetic_report(OutputLanguage.ES)).payload)) as pdf:
        page = pdf.pages[0]
        instructions = list(pikepdf.parse_content_stream(page))
        opening = next(
            index
            for index, instruction in enumerate(instructions)
            if str(instruction.operator) == "BDC" and instruction.operands[0] == Name.H1
        )
        closing = next(
            index for index in range(opening, len(instructions)) if str(instructions[index].operator) == "EMC"
        )
        del instructions[closing]
        del instructions[opening]
        page.obj.Contents = pdf.make_stream(pikepdf.unparse_content_stream(instructions))

        assert untagged_content(pdf) == ["page 1: text outside marked content"]
    assert untagged_content(summary) == []


def _presentation() -> CalculationSummaryPresentation:
    return build_calculation_summary_presentation(
        synthetic_report(OutputLanguage.ES),
        csv_sha256="0" * 64,
        signing_key_fingerprint=synthetic_keypair().public_key_hex,
        brand="CADRUMO",
    )
