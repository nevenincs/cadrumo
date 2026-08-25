"""Modelo 390's pages write every position AEAT asks for, and leave blank only what it reserves.

Modelo 390 is the annual IVA summary -- the return every quarter's Modelo 303 reconciles
against -- so a position it silently fails to write is under-declaration at the most
filing-grade surface the registry has. Its records are also binding-derived: each
revision declares a few hundred bindings, and the committed layout for page 5 writes
forty positions where the shipped record writes 1216. Read on the committed tree, the
Régimen Simplificado surface appears almost entirely unwritten. Read on the snapshot it
is complete, and the only thing left blank is space AEAT reserves for itself.

WHAT AEAT RESERVES. The design marks trailing runs on every page ``RESERVADO PARA LA
A.E.A.T. (Dejar en blanco)`` -- literally "leave blank" -- along with a PAD reference
slot, an electronic-seal slot, and an EEDD client identifier. A record that leaves those
blank is obeying the design. A record that leaves anything ELSE blank is dropping a
declared value behind a full-length page.

THE ENVELOPE HEADER IS TREATED SEPARATELY AND DELIBERATELY. Its two unwritten fields,
``Versión del Programa`` and ``NIF Empresa Desarrollo``, are not marked reserved: they
identify the software house that produced the file. Whether AEAT requires them from a
self-filer is a question about its acceptance rules, not something the diseño states, so
this module does not assert they may be blank. It pins that they are the ONLY unwritten
fields in the envelope, which keeps the current state honest and fails the moment
anything else joins them, without claiming a permission that has not been grounded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.resources import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.record_design import extract_record_design
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Phrases AEAT uses in this design to mean "the filer writes nothing here". Matched on
#: the design's own text, so a page that stops reserving a run stops being excused.
_RESERVED_PHRASES = ("RESERVADO PARA LA A.E.A.T.", "DEJAR EN BLANCO", "BLANCOS", "RESERVADO PARA LAS EEDD")


def _revisions_with_records():
    modelo, catalogues = _committed_modelo("390")
    return modelo, catalogues, {rid: rev for rid, rev in modelo.revisions.items() if rev.export_layouts}


def _shipped(revision_id: str):
    authority = ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())
    snapshot = authority.snapshot("390", filing_year=int(revision_id), period="0A")
    assert snapshot.revision.id == revision_id, (
        f"390 filing year {revision_id} resolves to revision {snapshot.revision.id!r}; "
        "re-ground this module rather than pinning the stored id"
    )
    return snapshot.revision


def _design_pages(revision, catalogues) -> dict[str, object]:
    """``page number -> design sheet``, keyed on the trailing numeral for EQUALITY."""
    design_ref = next(
        ref
        for ref in revision.source_refs
        if (source := catalogues.sources.get(ref)) is not None and source.kind == "record_design"
    )
    source = catalogues.sources[design_ref]
    path = Path(source.corpus_path)
    if not path.exists():
        path = bundled_path() / source.corpus_path

    extraction = extract_record_design(path)
    assert not extraction.skipped, (
        "the design was not read whole, so an unwritten position cannot be told apart from an "
        f"unparsed one: {[(sheet.name, sheet.reason) for sheet in extraction.skipped]}"
    )

    pages: dict[str, object] = {}
    for sheet in extraction.sheets:
        number = sheet.name.split(".")[-1].strip()
        assert number not in pages, f"two design sheets claim page {number!r}"
        pages[number] = sheet
    return pages


def _page_key(record_id: str) -> str | None:
    tail = record_id.rsplit("-", 1)[-1]
    if tail.isdigit():
        return str(int(tail))
    return "0" if record_id.endswith("envelope-header") else None


def _written_positions(record) -> set[int]:
    written: set[int] = set()
    for field in record.fields:
        if field.offset is not None:
            written.update(range(field.offset, field.offset + (field.length or 1)))
    return written


def _reserved_positions(sheet) -> set[int]:
    reserved: set[int] = set()
    for field in sheet.fields:
        text = (field.description or field.content or "").upper()
        if field.offset is not None and any(phrase in text for phrase in _RESERVED_PHRASES):
            reserved.update(range(field.offset, field.offset + (field.length or 1)))
    return reserved


def _design_reach(sheet) -> int:
    return max(
        (field.offset + (field.length or 1) - 1 for field in sheet.fields if field.offset is not None),
        default=0,
    )


def _records(revision):
    return [record for layout in revision.export_layouts for record in layout.records]


def test_the_page_records_are_still_binding_derived() -> None:
    """The premise: page 5's Régimen Simplificado fields come from derivation, not the tree."""
    _modelo, _catalogues, revisions = _revisions_with_records()
    assert revisions, "no modelo 390 revision declares export records, so this module tests nothing"

    for revision_id, revision in revisions.items():
        committed = {record.id: _written_positions(record) for record in _records(revision)}
        grew = [
            record.id
            for record in _records(_shipped(revision_id))
            if len(_written_positions(record)) > len(committed.get(record.id, set()))
        ]
        assert grew, (
            f"no 390/{revision_id} record gains positions at snapshot build, so these records are "
            "no longer binding-derived and this module is reading the snapshot for nothing"
        )


def test_every_page_spans_its_design_and_leaves_blank_only_reserved_space() -> None:
    """The filing-grade assertion, over every revision that ships records."""
    _modelo, catalogues, revisions = _revisions_with_records()

    checked = 0
    faults: list[str] = []
    for revision_id in revisions:
        shipped = _shipped(revision_id)
        pages = _design_pages(shipped, catalogues)

        keys = [key for record in _records(shipped) if (key := _page_key(record.id)) is not None]
        assert len(set(keys)) == len(keys), f"two 390/{revision_id} records resolve to one design page: {keys}"

        for record in _records(shipped):
            key = _page_key(record.id)
            if key is None or key == "0":
                continue
            sheet = pages.get(key)
            assert sheet is not None, f"390/{revision_id} {record.id} names page {key!r}, which the design lacks"

            checked += 1
            declared = _design_reach(sheet)
            written = _written_positions(record)
            reach = max(written, default=0)
            if reach != declared:
                faults.append(f"390/{revision_id} {record.id}: reaches {reach}, design declares {declared}")
                continue

            stranded = sorted(set(range(1, declared + 1)) - written - _reserved_positions(sheet))
            if stranded:
                sample = [
                    (field.offset, (field.description or field.content or "").strip()[:48])
                    for field in sheet.fields
                    if field.offset is not None and field.offset in set(stranded)
                ][:3]
                faults.append(
                    f"390/{revision_id} {record.id}: {len(stranded)} position(s) unwritten that AEAT "
                    f"does not reserve, starting at {stranded[0]} -- {sample}"
                )

    assert checked, "no page record was compared at all, so this assertion is vacuous"
    assert not faults, (
        "modelo 390 is the annual IVA summary every Modelo 303 reconciles against, and these pages "
        "leave declared positions unwritten behind a full-length record:\n  " + "\n  ".join(faults)
    )


def test_the_envelope_header_leaves_only_the_developer_identification_fields_blank() -> None:
    """Pinned as the current state, without claiming AEAT permits it.

    These two fields identify the producing software house rather than the taxpayer, and
    the diseño does not mark them reserved. Asserting they MAY be blank would be asserting
    an acceptance rule this module cannot read. Asserting they are the ONLY blanks costs
    nothing and catches any real omission that joins them.
    """
    _modelo, catalogues, revisions = _revisions_with_records()

    for revision_id in revisions:
        shipped = _shipped(revision_id)
        pages = _design_pages(shipped, catalogues)
        header = next(record for record in _records(shipped) if record.id.endswith("envelope-header"))
        sheet = pages["0"]

        unwritten = set(range(1, _design_reach(sheet) + 1)) - _written_positions(header)
        blank_fields = sorted(
            (field.offset, " ".join((field.description or field.content or "").split()))
            for field in sheet.fields
            if field.offset is not None and set(range(field.offset, field.offset + (field.length or 1))) & unwritten
        )
        described = [text for _offset, text in blank_fields]

        assert len(described) == 2, f"390/{revision_id} envelope leaves {len(described)} fields blank: {described}"
        assert any("Programa" in text for text in described), described
        assert any("Desarrollo" in text for text in described), described
