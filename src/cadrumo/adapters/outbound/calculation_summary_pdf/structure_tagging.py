"""Tag a drawn calculation summary for accessibility and archival conformance.

The page writer does not tag. This pass does, over the drawn file: every text
object is wrapped in marked content -- either a structure element's numbered
content item or an ``Artifact`` -- every path is wrapped as an ``Artifact``, and
the structure tree, its parent tree and the document-level flags a tagged PDF
needs are written. The result is what PDF/UA-1 and PDF/A-3 level ``a`` require of
logical structure: standard roles in reading order, table headers with a scope,
decoration kept out of the tree, and the document language declared.

The pass pairs the page content's text objects with the tag plan the layout
recorded, one to one and in order. A page on which they do not pair is refused
rather than tagged approximately, because a mispaired tag reads a figure under
the wrong heading to anyone using assistive technology.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Final

import pikepdf
from pikepdf import Array, Dictionary, Name, Operator, String

from ....core.errors.hierarchy import CadrumoError

type StructNode = tuple[str, str, tuple[tuple[str, str], ...]]
"""One structure element: its standard role, a key unique in the document, its attributes."""
type StructPath = tuple[StructNode, ...]
"""The chain of structure elements from ``Document`` down to one piece of text."""

_TEXT_SHOWING: Final[frozenset[str]] = frozenset({"Tj", "TJ", "'", '"'})
_PATH_CONSTRUCTION: Final[frozenset[str]] = frozenset({"m", "l", "c", "v", "y", "h", "re"})
_PATH_PAINTING: Final[frozenset[str]] = frozenset({"S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n"})


class SummaryTagPlanMismatchError(CadrumoError):
    """A page's text objects and its tag plan do not pair one to one.

    Means the page writer drew text the layout did not plan, or planned text it
    did not draw -- a change in the writer's output shape. Refused, because a
    summary tagged by guesswork is not accessible, only labelled as such.
    """


@dataclass(slots=True)
class _Node:
    role: str
    attributes: tuple[tuple[str, str], ...]
    parent: str | None
    kids: list[tuple[str, int, int] | str] = field(default_factory=list)
    first_page: int | None = None


type _Instruction = pikepdf.ContentStreamInstruction | pikepdf.ContentStreamInlineImage


def _instruction(operands: list[pikepdf.Object], operator: str) -> pikepdf.ContentStreamInstruction:
    return pikepdf.ContentStreamInstruction(operands, Operator(operator))


def _plan_mismatch(page_index: int, detail: str) -> SummaryTagPlanMismatchError:
    return SummaryTagPlanMismatchError(
        translated_message="adapters.outbound.calculation_summary_pdf.errors.tag_plan_mismatch",
        context={"page": page_index + 1, "detail": detail},
    )


class _StructureBuilder:
    """Accumulate structure nodes and marked-content ids while pages are rewritten."""

    def __init__(self) -> None:
        self.nodes: dict[str, _Node] = {}
        self.roots: list[str] = []

    def leaf_for(self, path: StructPath) -> str:
        parent: str | None = None
        for role, key, attributes in path:
            if key not in self.nodes:
                self.nodes[key] = _Node(role=role, attributes=attributes, parent=parent)
                if parent is None:
                    self.roots.append(key)
                else:
                    self.nodes[parent].kids.append(key)
            parent = key
        if parent is None:
            raise ValueError("a structure path names at least one element")
        return parent

    def add_content(self, leaf: str, *, page_index: int, mcid: int) -> None:
        node = self.nodes[leaf]
        node.kids.append(("mcid", page_index, mcid))
        if node.first_page is None:
            node.first_page = page_index


def _rewrite_page(
    pdf: pikepdf.Pdf,
    page: pikepdf.Page,
    plan: Sequence[StructPath | None],
    *,
    page_index: int,
    builder: _StructureBuilder,
) -> list[str]:
    """Wrap one page's content in marked content; return the leaf owning each MCID."""
    instructions = list(pikepdf.parse_content_stream(page))
    rewritten: list[_Instruction] = []
    owners: list[str] = []
    remaining = iter(plan)
    index = 0
    while index < len(instructions):
        operator = str(instructions[index].operator)
        if operator == "BT":
            end = index
            while str(instructions[end].operator) != "ET":
                end += 1
            block = instructions[index : end + 1]
            _append_summary_text_block(block, remaining, rewritten, owners, page_index=page_index, builder=builder)
            index = end + 1
            continue
        if operator in _PATH_CONSTRUCTION:
            end = index
            while str(instructions[end].operator) not in _PATH_PAINTING:
                end += 1
            rewritten.append(_instruction([Name.Artifact], "BMC"))
            rewritten.extend(instructions[index : end + 1])
            rewritten.append(_instruction([], "EMC"))
            index = end + 1
            continue
        rewritten.append(instructions[index])
        index += 1
    leftover = sum(1 for _ in remaining)
    if leftover:
        raise _plan_mismatch(page_index, f"{leftover} planned entries without a text object")
    page.obj.Contents = pdf.make_stream(pikepdf.unparse_content_stream(rewritten))
    page.obj.StructParents = page_index
    return owners


def _materialise(
    pdf: pikepdf.Pdf,
    builder: _StructureBuilder,
    owners_by_page: list[list[str]],
) -> None:
    """Write the structure tree, its parent tree and the tagged-document flags."""
    struct_root = pdf.make_indirect(Dictionary(Type=Name.StructTreeRoot))
    elements: dict[str, pikepdf.Object] = {}

    def build(key: str, parent: pikepdf.Object) -> pikepdf.Object:
        node = builder.nodes[key]
        element = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=Name("/" + node.role), P=parent))
        if node.attributes:
            attributes = Dictionary(O=Name.Table)
            for name, value in node.attributes:
                attributes[Name("/" + name)] = Name("/" + value)
            element.A = attributes
        if node.first_page is not None:
            element.Pg = pdf.pages[node.first_page].obj
        elements[key] = element
        kids = Array()
        for kid in node.kids:
            if isinstance(kid, str):
                kids.append(build(kid, element))
                continue
            _marker, page_index, mcid = kid
            if page_index == node.first_page:
                kids.append(mcid)
            else:
                kids.append(Dictionary(Type=Name.MCR, Pg=pdf.pages[page_index].obj, MCID=mcid))
        element.K = kids
        return element

    if len(builder.roots) != 1:
        raise ValueError(f"a summary has exactly one Document element, found {len(builder.roots)}")
    struct_root.K = build(builder.roots[0], struct_root)
    numbers = Array()
    for page_index, owners in enumerate(owners_by_page):
        numbers.append(page_index)
        numbers.append(pdf.make_indirect(Array([elements[owner] for owner in owners])))
    struct_root.ParentTree = pdf.make_indirect(Dictionary(Nums=numbers))
    struct_root.ParentTreeNextKey = len(owners_by_page)
    pdf.Root.StructTreeRoot = struct_root
    pdf.Root.MarkInfo = Dictionary(Marked=True)
    pdf.Root.ViewerPreferences = Dictionary(DisplayDocTitle=True)


def tag_summary_pages(
    pdf: pikepdf.Pdf,
    plans: Sequence[Sequence[StructPath | None]],
    *,
    language: str,
) -> None:
    """Tag every page of ``pdf`` from its plan and declare the document language.

    Raises:
        SummaryTagPlanMismatchError: A page's text objects and plan entries do
            not pair one to one, or the plan count differs from the page count.
    """
    if len(plans) != len(pdf.pages):
        raise _plan_mismatch(0, f"{len(plans)} page plans for {len(pdf.pages)} pages")
    builder = _StructureBuilder()
    owners_by_page = [
        _rewrite_page(pdf, page, plan, page_index=page_index, builder=builder)
        for page_index, (page, plan) in enumerate(zip(pdf.pages, plans, strict=True))
    ]
    _materialise(pdf, builder, owners_by_page)
    pdf.Root.Lang = String(language)


__all__ = ["StructNode", "StructPath", "SummaryTagPlanMismatchError", "tag_summary_pages"]


def _append_summary_text_block(
    block: Sequence[_Instruction],
    remaining: Iterator[StructPath | None],
    rewritten: list[_Instruction],
    owners: list[str],
    *,
    page_index: int,
    builder: _StructureBuilder,
) -> None:
    """Pair one text object with its planned tag or preserve its undecorated content."""
    if any(str(item.operator) in _TEXT_SHOWING for item in block):
        try:
            tag = next(remaining)
        except StopIteration:
            raise _plan_mismatch(page_index, "more text objects than planned entries") from None
        if tag is None:
            rewritten.append(_instruction([Name.Artifact, Dictionary(Type=Name.Pagination)], "BDC"))
        else:
            leaf = builder.leaf_for(tag)
            mcid = len(owners)
            rewritten.append(_instruction([Name("/" + builder.nodes[leaf].role), Dictionary(MCID=mcid)], "BDC"))
            builder.add_content(leaf, page_index=page_index, mcid=mcid)
            owners.append(leaf)
        rewritten.extend(block)
        rewritten.append(_instruction([], "EMC"))
    else:
        rewritten.extend(block)
