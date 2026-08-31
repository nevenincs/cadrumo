"""Modelo 369's records tile their design sheets with nothing unwritten.

Modelo 369 files three separate schemes -- unión, exterior and importación --
each with its own revision, its own layout and its own subset of the shared
Diseño. Between them they declare sixteen fixed-width records spanning up to
5803 positions, and the whole set was raised as carrying gaps that fall over
design DATA positions.

They do not. Every record tiles its sheet completely: extent equal to the
sheet's declared positions, zero unwritten positions, and a field count equal
to the sheet's own. That last agreement is the one that matters most here,
because a record could cover every byte with one wide field and still have lost
the structure AEAT published.

WHY THE SHEET IS FOUND BY CODE. A record's ``record_type`` and its sheet name
share a leading identifier -- ``t36904-un`` and ``T36904 Un`` -- but nothing
else survives a mechanical transform: ``t3690-estruc-gral`` faces
``T3690 Estruc. gral``, with a period and a lowercase word. Matching on the code
prefix to a word boundary is the part that is actually reliable, and it is
asserted to resolve exactly one sheet so a loose prefix cannot quietly match two.

THE ENVELOPE IS THE ONE SHEET WITHOUT A DECLARED LENGTH. ``T3690 Estruc. gral``
is the AEAT transmission envelope, and the Diseño gives it no total. Its extent
is therefore unchecked -- but the exemption is not taken on faith: the module
asserts that this is the ONLY sheet in that position, so a second undeclared
total would fail rather than silently join it.
"""

from __future__ import annotations

import pytest

from .....core.resources.bundled_data import bundled_path
from ..export import derive_export_layouts_from_bindings
from ..record_design import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The transmission envelope, the one record whose sheet declares no length.
_ENVELOPE_CODE = "T3690"


def _sheet_code(record_type: str) -> str:
    """Return the design-sheet code a record type names, e.g. ``t36904-un`` -> ``T36904``."""
    return record_type.split("-", 1)[0].upper()


def _modelo_369_cases():
    modelos, catalogues = _committed_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "369")
    for revision_id, revision in modelo.revisions.items():
        design_ref = next(ref for ref in revision.source_refs if catalogues.sources[ref].kind == "record_design")
        design = extract_record_design(bundled_path() / catalogues.sources[design_ref].corpus_path)
        for layout in derive_export_layouts_from_bindings(revision):
            for record in layout.records:
                code = _sheet_code(record.record_type)
                matches = [sheet for sheet in design.sheets if sheet.name.upper().startswith(f"{code} ")]
                assert len(matches) == 1, (
                    f"369/{revision_id} record {record.id} names sheet code {code!r}, which "
                    f"resolves {len(matches)} sheets: {[sheet.name for sheet in matches]}"
                )
                yield revision_id, record, matches[0], code


def test_all_three_schemes_contribute_records() -> None:
    """Without this, a revision silently producing no layout would pass everything below."""
    revisions = {revision_id for revision_id, _record, _sheet, _code in _modelo_369_cases()}

    assert revisions == {"esquema-union", "esquema-exterior", "esquema-importacion"}, sorted(revisions)


def test_only_the_envelope_sheet_declares_no_length() -> None:
    """The exemption below is evidenced rather than assumed."""
    undeclared = {code for _revision_id, _record, sheet, code in _modelo_369_cases() if sheet.total_positions is None}

    assert undeclared == {_ENVELOPE_CODE}, (
        f"sheets without a declared length are {sorted(undeclared)}, so the envelope exemption "
        "no longer describes exactly one record"
    )


def test_each_record_spans_exactly_the_positions_its_sheet_declares() -> None:
    for revision_id, record, sheet, code in _modelo_369_cases():
        if code == _ENVELOPE_CODE:
            continue
        extent = max(field.offset + field.length - 1 for field in record.fields if field.offset)
        assert extent == sheet.total_positions, (
            f"369/{revision_id} record {record.id} spans {extent} positions but sheet "
            f"{sheet.name!r} declares {sheet.total_positions}"
        )


def test_no_record_leaves_a_position_unwritten() -> None:
    """An unclaimed position emits as a space, so a lost field is invisible in the line."""
    for revision_id, record, sheet, _code in _modelo_369_cases():
        occupied: set[int] = set()
        for field in record.fields:
            if field.offset and field.length:
                occupied |= set(range(field.offset, field.offset + field.length))
        span = sheet.total_positions or max(field.offset + field.length - 1 for field in record.fields if field.offset)
        unwritten = sorted(set(range(1, span + 1)) - occupied)
        assert not unwritten, (
            f"369/{revision_id} record {record.id} leaves {len(unwritten)} position(s) unwritten, "
            f"first at {unwritten[0]}"
        )


def test_each_record_reproduces_the_field_count_its_sheet_publishes() -> None:
    """Covering every byte is not the same as reproducing the published structure."""
    for revision_id, record, sheet, _code in _modelo_369_cases():
        positioned = [field for field in record.fields if field.offset and field.length]
        assert len(positioned) == len(sheet.fields), (
            f"369/{revision_id} record {record.id} resolved {len(positioned)} fields but sheet "
            f"{sheet.name!r} lists {len(sheet.fields)}"
        )
