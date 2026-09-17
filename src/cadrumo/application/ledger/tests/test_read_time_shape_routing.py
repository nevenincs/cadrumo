"""Read-time routing asks the bytes, not the label the producer attached.

``MediaKind`` is derived from the STORED MIME TYPE. A label cannot see inside a
document, so a ZUGFeRD invoice -- a PDF carrying a complete machine-readable
EN16931 record -- answered ``PDF`` and was routed to prose extraction exactly
like a photograph of a receipt. The most exactly readable document in the corpus
took the least exact path, decided by a label.

``DocumentShape`` is probed from the bytes themselves. These assertions pin the
division: every READ-time decision consults the shape, and no read path
branches on the two-member media kind.

Structural rather than behavioural, because a caller that re-derives the routing
from ``media_kind`` still produces correct output for the two easy cases and
silently mis-routes the structured ones -- the failure this replaced.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ....core.document_shape import PDF_CONTAINER_SHAPES, DocumentShape

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LEDGER = Path("src/cadrumo/application/ledger")


def _media_kind_comparisons(tree: ast.AST) -> list[int]:
    """Return the lines comparing an attribute against a ``MediaKind`` member."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        # Both spellings count: an attribute read (`evidence.media_kind`) and a
        # bare binding (`media_kind`, the parameter form). Matching only the
        # attribute left the parameter form invisible, which is how the storage
        # module's own comparison escaped the first version of this walk -- and
        # a read path could have taken the same shape.
        touches_media_kind = any(
            (isinstance(operand, ast.Attribute) and operand.attr == "media_kind")
            or (isinstance(operand, ast.Name) and operand.id == "media_kind")
            for operand in operands
        )
        names_the_enum = any(
            isinstance(operand, ast.Attribute)
            and isinstance(operand.value, ast.Name)
            and operand.value.id == "MediaKind"
            for operand in operands
        )
        if touches_media_kind and names_the_enum:
            lines.append(node.lineno)
    return lines


def test_no_read_path_branches_on_the_two_member_media_kind() -> None:
    """The step's own red condition, as an executable assertion.

    A read path that asks ``media_kind is MediaKind.PDF`` is asking the MIME
    label whether the bytes are a PDF. That question is answerable from the
    bytes, and answering it from the label is what routed a structured invoice
    into prose extraction.

    Mutation that must trip this: restore any of the four
    ``media_kind is MediaKind.PDF`` branches this step replaced.
    """
    offences: list[str] = []
    scanned = 0
    for path in scan_directory(_LEDGER, pattern="*.py", recursive=True):
        if path.name.startswith("test_"):
            continue
        scanned += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offences.extend(f"{path.as_posix()}:{line}" for line in _media_kind_comparisons(tree))

    assert scanned > 0, "the walk reached no ledger modules; this assertion would be vacuous"
    assert offences == [], (
        "read-time routing must consult DocumentShape, which is probed from the document's own "
        f"bytes, rather than the MIME-derived media kind. Offending comparisons: {offences}"
    )


def test_every_pdf_carrying_shape_is_in_the_container_set() -> None:
    """A PDF shape the routing cannot recognise falls to the vision path silently.

    The set is hand-listed on purpose, which means a new PDF-carrying member can
    be added to the enum and forgotten here. The consequence is not a crash: the
    document simply stops being offered its text layer and gets rasterised, which
    reads as a slightly worse extraction rather than as a bug.

    Keyed on the enum's own naming so the check cannot drift from the taxonomy.
    """
    pdf_named = {shape for shape in DocumentShape if shape.name.startswith("PDF_")}

    assert pdf_named == PDF_CONTAINER_SHAPES, (
        "every PDF-carrying shape must be routable as a PDF container.\n"
        f"  named PDF_ but not in the set: {sorted(s.name for s in pdf_named - PDF_CONTAINER_SHAPES)}\n"
        f"  in the set but not named PDF_: {sorted(s.name for s in PDF_CONTAINER_SHAPES - pdf_named)}"
    )
