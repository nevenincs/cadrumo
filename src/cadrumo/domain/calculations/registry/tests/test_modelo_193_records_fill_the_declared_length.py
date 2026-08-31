"""Modelo 193's records reach the declared length, and every gap in them is declared blank.

A fixed-width record is wrong in two different ways, and only one of them is visible
without the design. It can STOP SHORT -- the last field ends before the record's
declared length, so every reader that trusts the length reads past the data. Or it can
be FULL OF HOLES -- it reaches the end, but positions inside it are never written. The
second is the dangerous one: the file is the right size, the digest is valid, and the
missing values are simply absent.

WHAT THE DESIGN LETS US SEPARATE. AEAT's diseño declares BLANCOS runs -- stretches the
record is required to leave blank. A hole over a BLANCOS run is the record being
correct. A hole over a declared data field is a value the export silently never writes,
which is under-declaration with a valid digest in front of it.

Modelo 193's three records are measured on both counts here. All three reach 500 in
both revisions, and their interior holes -- one in the declarante, two in the perceptor,
one long run in the gastos record -- each fall wholly inside a BLANCOS field. That is
the finding: nothing is missing, and now something says so.

THE OTHER TRAP IS THE ARTEFACT. Export layouts may be REPLACED at snapshot build by
fields derived from the revision's bindings, so the committed TOML and the record that
actually ships are not always the same document. Modelo 720 is the worked example: its
committed layout declares two filler tails and nothing else, and only on the snapshot do
its fourteen and thirty-one binding-derived fields exist. Measured on the committed tree
it looks catastrophically empty; measured on the snapshot it is complete. Modelo 193
authors its fields explicitly and the two agree exactly, which is asserted below rather
than assumed -- if 193 ever gains a binding, this module must stop reading the tree.

RESOLVING A RECORD TO ITS DESIGN SHEET IS THE OTHER TRAP, NOT THE MEASUREMENT. Modelo 193's
design names two sheets ``Tipo 2 - Registro De Perceptor`` and ``Tipo 2 - Registro De
Perceptor  Relación De Gastos``. They agree for their first twenty-eight characters, so
any prefix or "startswith" resolution silently reads the perceptor sheet for the gastos
record -- and the perceptor sheet packs real data across positions 76-194 where the
gastos sheet declares one BLANCOS run. Resolved that way the gastos record appears to
drop nineteen filing-grade fields, including BASE RETENCIONES E INGRESOS A CUENTA and
RETENCIONES E INGRESOS A CUENTA. The mapping below is therefore exact, and asserted to
be a bijection onto distinct sheets before any gap is judged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.resources._boundary import bundled_path
from ..authority import ValidatedRegistryAuthority
from ..record_design import extract_record_design
from ..record_design_schema import RecordDesignSheet
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: ``export record id -> the design sheet that defines it``, by EXACT name. Exact
#: because the two Tipo 2 names share a long prefix; see the module docstring. If the
#: extractor ever renames a sheet this fails loudly, which is the correct outcome --
#: a silently re-resolved record is what this module exists to prevent.
_RECORD_TO_DESIGN_SHEET = {
    "modelo-193-declarante": "Tipo 1 - Registro De Declarante",
    "modelo-193-perceptor": "Tipo 2 - Registro De Perceptor",
    "modelo-193-gastos": "Tipo 2 - Registro De Perceptor  Relaci\xf3n De Gastos",
}

#: AEAT's own word for a run the record must leave blank. Matched on the normalised
#: description so a trailing period does not change the verdict.
_BLANK_MARKER = "BLANCOS"


def _design_sheets(revision, catalogues):
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
    return design_ref, {sheet.name: sheet for sheet in extraction.sheets}


def _written_positions(record) -> set[int]:
    written: set[int] = set()
    for field in record.fields:
        if field.offset is not None:
            written.update(range(field.offset, field.offset + (field.length or 1)))
    return written


def _blank_positions(sheet) -> set[int]:
    blank: set[int] = set()
    for field in sheet.fields:
        text = (field.description or field.content or "").strip().rstrip(".").upper()
        if field.offset is not None and text == _BLANK_MARKER:
            blank.update(range(field.offset, field.offset + (field.length or 1)))
    return blank


def _design_reach(sheet: RecordDesignSheet) -> int:
    return max(
        (field.offset + (field.length or 1) - 1 for field in sheet.fields if field.offset is not None),
        default=0,
    )


def _records(revision):
    return [record for layout in revision.export_layouts for record in layout.records]


def test_each_record_resolves_to_its_own_distinct_design_sheet() -> None:
    """The control that has to pass before any gap verdict means anything.

    Run first and separately: if two records resolve to one sheet, every gap
    conclusion below is drawn against the wrong document, and the failure is far
    easier to read here than as a bogus list of missing fields.
    """
    modelo, catalogues = _committed_modelo("193")

    for revision_id, revision in modelo.revisions.items():
        _ref, sheets = _design_sheets(revision, catalogues)
        record_ids = {record.id for record in _records(revision)}
        assert record_ids == set(_RECORD_TO_DESIGN_SHEET), (
            f"193/{revision_id} declares records {sorted(record_ids)}, which is not the set this "
            f"module maps: {sorted(_RECORD_TO_DESIGN_SHEET)}"
        )

        missing = sorted(name for name in _RECORD_TO_DESIGN_SHEET.values() if name not in sheets)
        assert not missing, f"193/{revision_id}'s design has no sheet named {missing}; available: {sorted(sheets)}"

        resolved = [_RECORD_TO_DESIGN_SHEET[record_id] for record_id in sorted(record_ids)]
        assert len(set(resolved)) == len(resolved), (
            f"two 193/{revision_id} records resolve to the same design sheet: {resolved}"
        )


def test_every_record_reaches_the_length_its_design_declares() -> None:
    """Stopping short leaves every reader that trusts the declared length reading past the data."""
    modelo, catalogues = _committed_modelo("193")

    short: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        _ref, sheets = _design_sheets(revision, catalogues)
        for record in _records(revision):
            sheet = sheets[_RECORD_TO_DESIGN_SHEET[record.id]]
            declared = _design_reach(sheet)
            assert declared, f"the design sheet for {record.id} declares no extent at all"

            written = _written_positions(record)
            reach = max(written, default=0)
            if reach != declared:
                short.append(f"193/{revision_id} {record.id}: reaches {reach}, design declares {declared}")

    assert not short, "these records do not span the length their own design declares:\n  " + "\n  ".join(short)


def test_every_unwritten_position_is_one_the_design_declares_blank() -> None:
    """A hole is only correct where AEAT asked for a hole.

    Judged position by position rather than run by run, so a gap that merely OVERLAPS a
    BLANCOS field -- spilling a few bytes into the data on either side -- is reported
    instead of being credited to the blank run it touches.
    """
    modelo, catalogues = _committed_modelo("193")

    unwritten_total = 0
    over_data: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        _ref, sheets = _design_sheets(revision, catalogues)
        for record in _records(revision):
            sheet = sheets[_RECORD_TO_DESIGN_SHEET[record.id]]
            written = _written_positions(record)
            declared = _design_reach(sheet)

            unwritten = set(range(1, declared + 1)) - written
            unwritten_total += len(unwritten)
            stranded = sorted(unwritten - _blank_positions(sheet))
            if stranded:
                over_data.append(
                    f"193/{revision_id} {record.id}: {len(stranded)} position(s) the design does not "
                    f"declare blank, starting at {stranded[0]}"
                )

    assert unwritten_total, (
        "no modelo 193 record has any unwritten position, so this assertion passed without "
        "examining a single gap -- re-ground it before trusting it"
    )
    assert not over_data, (
        "these records leave positions unwritten that the design declares as data, so the export "
        "omits a value while still producing a full-length record:\n  " + "\n  ".join(over_data)
    )


def test_the_committed_layout_is_the_one_that_ships() -> None:
    """Modelo 193's records must survive snapshot build unchanged.

    Every assertion above reads the committed tree. That is only legitimate while
    binding derivation leaves these records alone -- and derivation REPLACES a layout
    rather than extending it, so the day 193 gains a binding, the tree and the shipped
    record diverge silently and this module keeps grading a document nobody exports.

    Asserted on the covered POSITIONS rather than on field identity: derivation is
    free to describe the same bytes differently, and what this module reasons about is
    which positions get written.
    """
    authority = ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())
    modelo, _catalogues = _committed_modelo("193")

    diverged: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        claimed = revision.period_selector.year_from
        assert claimed, f"193/{revision_id} claims no filing year, so no snapshot can be resolved for it"

        snapshot = authority.snapshot("193", filing_year=claimed, period="0A")
        assert snapshot.revision.id == revision_id, (
            f"filing year {claimed} resolves to revision {snapshot.revision.id!r}, not {revision_id!r}; "
            "re-ground this module before trusting the comparison"
        )

        shipped = {record.id: _written_positions(record) for record in _records(snapshot.revision)}
        for record in _records(revision):
            if shipped.get(record.id) != _written_positions(record):
                diverged.append(f"193/{revision_id} {record.id}")

    assert not diverged, (
        "these records are written differently on the snapshot than in the committed tree, so the "
        f"assertions in this module grade a document that is not exported: {diverged}"
    )
