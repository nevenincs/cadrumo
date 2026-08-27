"""Modelo 390 writes the complementaria indicator on exactly the pages AEAT asks for.

Position 12 of every Modelo 390 page record is the "Indicador de página
complementaria", and AEAT does NOT give it the same instruction on every page.
Its Diseño says, verbatim:

* ``En Blanco`` on páginas 1, 2, 2 bis, 3, 4, 6 and 8; and
* ``Blanco (No complementaria) o "C" (Complementaria)`` on páginas 5 and 7.

So one byte at a fixed position is a declared blank on seven pages and a real
operator-supplied value on two. The registry follows that split: pages 5 and 7
cover position 12 with a binding field, every other page with a filler.

WHY THIS NEEDS A GATE. The two shapes are indistinguishable in a rendered line
-- a filler and an unset binding both emit a space -- so writing the indicator
on the wrong pages produces a file that looks correct and silently drops the
operator's declaration that a page is complementaria. It is also the exact
inversion that gets reported: pages 5 and 7 look like the ones MISSING a field,
because they are the two that differ from the other seven.

THE AUTHORITY IS THE DESIGN'S OWN WORDS. Which pages carry a value is read from
the Diseño's ``content`` text at position 12, never from a list kept here, so
a revision where AEAT moves the indicator re-targets this gate instead of
breaking it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

import pytest

from .....core.resources import bundled_path
from ..export import derive_export_layouts_from_bindings
from ..record_design import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The position AEAT gives the indicator on every page record.
_INDICATOR_OFFSET = 12

#: AEAT's way of saying "this position carries nothing".
_DECLARED_BLANK = re.compile(r"^\s*en\s+blanco\s*\.?\s*$", re.IGNORECASE)

#: Field kinds that put an operator- or registry-supplied value on the wire.
_DATA_BEARING = {"binding", "casilla", "draft", "literal", "producer", "projection", "computed"}

_PAGE_RECORD = re.compile(r"^modelo-390-page-(?P<page>\d+)(?P<bis>b?)$")


def _sheet_for(record_id: str, sheets: Mapping[str, object]):
    match = _PAGE_RECORD.match(record_id)
    if match is None:
        return None
    page = match.group("page").lstrip("0") or "0"
    suffix = f"{page} bis" if match.group("bis") else page
    for name, sheet in sheets.items():
        if name.endswith(f" {suffix}"):
            return sheet
    return None


def _cases():
    modelos, catalogues = _committed_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "390")
    for revision_id, revision in sorted(modelo.revisions.items()):
        design_ref = next(ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design")
        design = extract_record_design(bundled_path() / catalogues.sources[design_ref].corpus_path)
        sheets = {sheet.name: sheet for sheet in design.sheets}
        for layout in derive_export_layouts_from_bindings(revision):
            for record in layout.records:
                sheet = _sheet_for(record.id, sheets)
                if sheet is None:
                    continue
                design_field = next(
                    (field for field in sheet.fields if field.offset == _INDICATOR_OFFSET and field.length == 1),
                    None,
                )
                if design_field is None:
                    continue
                covering = [
                    field
                    for field in record.fields
                    if field.offset and field.length and field.offset <= _INDICATOR_OFFSET < field.offset + field.length
                ]
                yield revision_id, record, sheet, design_field, covering


def test_the_design_gives_two_different_instructions_at_this_position() -> None:
    """The whole point of the gate: the instruction is not uniform across pages.

    If AEAT ever made it uniform, the checks below would still pass but would no
    longer be testing anything interesting, and this states that plainly.
    """
    instructions = {
        (revision_id, sheet.name): (design_field.content or "").strip()
        for revision_id, _record, sheet, design_field, _covering in _cases()
    }
    assert instructions, "no modelo 390 page records were resolved to a design sheet"

    per_revision: dict[str, set[bool]] = {}
    for (revision_id, _name), content in instructions.items():
        per_revision.setdefault(revision_id, set()).add(bool(_DECLARED_BLANK.match(content)))

    for revision_id, variants in per_revision.items():
        assert variants == {True, False}, (
            f"390/{revision_id} gives the same instruction at position {_INDICATOR_OFFSET} on every "
            "page, so the value/blank split this gate exists for is gone"
        )


def test_a_page_the_design_gives_a_value_writes_a_data_bearing_field() -> None:
    """Pages 5 and 7 today -- read from the design, not listed here."""
    checked = 0
    for revision_id, record, sheet, design_field, covering in _cases():
        if _DECLARED_BLANK.match((design_field.content or "").strip()):
            continue
        assert covering, (
            f"390/{revision_id} record {record.id} leaves position {_INDICATOR_OFFSET} unwritten, but "
            f"sheet {sheet.name!r} declares {design_field.content!r} there"
        )
        kinds = {str(getattr(field, "kind", "")) for field in covering}
        assert kinds & _DATA_BEARING, (
            f"390/{revision_id} record {record.id} covers position {_INDICATOR_OFFSET} with {sorted(kinds)}, "
            f"but sheet {sheet.name!r} declares {design_field.content!r} -- the operator's "
            "complementaria declaration would be dropped silently"
        )
        checked += 1
    assert checked, "no page declared a value at the indicator position, so this asserts nothing"


def test_a_page_the_design_declares_blank_writes_no_value_there() -> None:
    """The converse. Writing a value where AEAT declares blank corrupts the record just as well."""
    checked = 0
    for revision_id, record, sheet, design_field, covering in _cases():
        if not _DECLARED_BLANK.match((design_field.content or "").strip()):
            continue
        kinds = {str(getattr(field, "kind", "")) for field in covering}
        assert not (kinds & _DATA_BEARING), (
            f"390/{revision_id} record {record.id} writes {sorted(kinds)} at position "
            f"{_INDICATOR_OFFSET}, but sheet {sheet.name!r} declares {design_field.content!r}"
        )
        checked += 1
    assert checked, "no page declared a blank at the indicator position, so this asserts nothing"


def test_every_supported_revision_is_covered() -> None:
    """A revision dropping out of the layout walk would silently shrink this gate."""
    revisions = {revision_id for revision_id, *_rest in _cases()}

    assert {"2022", "2023", "2024", "2025"} <= revisions, sorted(revisions)
