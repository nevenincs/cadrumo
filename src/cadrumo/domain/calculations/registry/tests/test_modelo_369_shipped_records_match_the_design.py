"""Modelo 369's three esquemas ship records that reproduce the design exactly.

Modelo 369 is the OSS/IOSS return, and like modelo 720 it authors almost none of its
export fields: each esquema declares a few hundred bindings, and the record's data
fields are DERIVED when the snapshot is built. Read on the committed tree its records
look gutted -- ``modelo-369-union-t36906`` carries seven fields covering thirty-five
positions against a design sheet of two hundred and three reaching 1687, and the union
esquema alone shows unwritten runs like ``(10, 1661)``. Read on the snapshot the same
record carries two hundred and three fields, reaches 1687, and leaves nothing unwritten.

THE PERIOD GRAMMAR IS PART OF READING IT. The three esquemas do not share one: the
unión esquema is quarterly (``1T``), importación is monthly (``01``), and exterior uses
its own ``EXT-1T`` family. A snapshot probed with the annual ``0A`` raises
``NoRevisionForPeriodError`` for all three, and falling back to the committed tree on
that error is what makes the gutted reading look authoritative. Each revision's period
is therefore taken from its own selector, never assumed.

RESOLVING A RECORD TO ITS DESIGN SHEET, AGAIN THE TRAP. The design names sheets
``T3690 Estruc. gral``, ``T36900 Info Adicional`` and ``T36901 Ext``; the first is a
string prefix of the other two. Any ``startswith`` resolution silently collapses the
envelope onto a detail sheet. Sheets are therefore keyed on their leading token
compared for EQUALITY, and the mapping is asserted to be a bijection before any
completeness verdict is drawn.

WHAT THIS PINS. That every shipped record spans exactly the extent its design sheet
declares, writes every position in it, and carries the same number of fields the design
defines -- and, separately and first, that the records are still binding-derived, so a
future change that starts authoring them is stated rather than absorbed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.resources import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.record_design import extract_record_design
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The earliest ejercicio the OSS/IOSS schemas govern; every esquema claims 2021 onward.
#: The snapshot is resolved from this year plus each revision's OWN period, so the
#: revision is law-determined and merely confirmed to be the one under test.
_FILING_YEAR = 2021


def _design_sheets_by_token() -> dict[str, object]:
    """``leading sheet token -> sheet``, keyed for EQUALITY rather than prefix."""
    _modelo, catalogues = _committed_modelo("369")
    source = catalogues.sources["aeat-dr-369-2021"]
    path = Path(source.corpus_path)
    if not path.exists():
        path = bundled_path() / source.corpus_path

    extraction = extract_record_design(path)
    assert not extraction.skipped, (
        "the design was not read whole, so an unwritten position cannot be told apart from an "
        f"unparsed one: {[(sheet.name, sheet.reason) for sheet in extraction.skipped]}"
    )

    by_token: dict[str, object] = {}
    for sheet in extraction.sheets:
        token = sheet.name.split()[0].upper()
        assert token not in by_token, f"two design sheets share the leading token {token!r}"
        by_token[token] = sheet
    return by_token


def _sheet_token(record_id: str) -> str:
    """The design sheet token a record id names, without any prefix matching."""
    tail = record_id.rsplit("-", 1)[-1]
    if tail == "envelope":
        return "T3690"
    if tail == "adicional":
        return "T36900"
    return tail.upper()


def _written_positions(record) -> set[int]:
    written: set[int] = set()
    for field in record.fields:
        if field.offset is not None:
            written.update(range(field.offset, field.offset + (field.length or 1)))
    return written


def _design_reach(sheet) -> int:
    return max(
        (field.offset + (field.length or 1) - 1 for field in sheet.fields if field.offset is not None),
        default=0,
    )


def _records(revision):
    return [record for layout in revision.export_layouts for record in layout.records]


def _shipped_revisions():
    """``revision id -> the snapshot revision that actually ships for it``."""
    modelo, _catalogues = _committed_modelo("369")
    authority = ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())

    shipped = {}
    for revision_id, revision in modelo.revisions.items():
        periods = revision.period_selector.periods
        assert periods, f"369/{revision_id} declares no period, so no snapshot can be resolved for it"

        snapshot = authority.snapshot("369", filing_year=_FILING_YEAR, period=periods[0])
        assert snapshot.revision.id == revision_id, (
            f"369 year {_FILING_YEAR} period {periods[0]!r} resolves to {snapshot.revision.id!r}, "
            f"not {revision_id!r}; re-ground this module rather than pinning the stored id"
        )
        shipped[revision_id] = snapshot.revision
    return modelo, shipped


def test_each_record_resolves_to_its_own_distinct_design_sheet() -> None:
    """The control that must hold before any completeness verdict is meaningful."""
    _modelo, shipped = _shipped_revisions()
    sheets = _design_sheets_by_token()

    for revision_id, revision in shipped.items():
        tokens = [_sheet_token(record.id) for record in _records(revision)]
        assert tokens, f"369/{revision_id} ships no records at all"

        unknown = sorted({token for token in tokens if token not in sheets})
        assert not unknown, f"369/{revision_id} names design sheets that do not exist: {unknown}; have {sorted(sheets)}"

        assert len(set(tokens)) == len(tokens), f"two 369/{revision_id} records resolve to one design sheet: {tokens}"


def test_the_records_are_still_binding_derived_rather_than_authored() -> None:
    """The premise the completeness check rests on, asserted as a difference.

    At least one record per esquema must write strictly more positions on the snapshot
    than in the committed tree. If none does, derivation has stopped supplying the data
    fields and reading the snapshot no longer buys anything.
    """
    modelo, shipped = _shipped_revisions()

    for revision_id, revision in shipped.items():
        committed = {record.id: _written_positions(record) for record in _records(modelo.revisions[revision_id])}
        grew = [
            record.id
            for record in _records(revision)
            if len(_written_positions(record)) > len(committed.get(record.id, set()))
        ]
        assert grew, (
            f"no 369/{revision_id} record gains positions at snapshot build, so its records are no "
            "longer binding-derived and this module is reading the snapshot for nothing"
        )


def test_every_shipped_record_reproduces_its_design_sheet() -> None:
    """Same extent, no holes, same field count -- all three read off the design.

    Field count is included deliberately. Extent and hole-freedom can both be satisfied
    by a record that fuses several declared fields into one wide span, which writes the
    right bytes while destroying the structure a reader needs to find a value in them.
    """
    _modelo, shipped = _shipped_revisions()
    sheets = _design_sheets_by_token()

    faults: list[str] = []
    for revision_id, revision in shipped.items():
        for record in _records(revision):
            sheet = sheets[_sheet_token(record.id)]
            declared = _design_reach(sheet)
            assert declared, f"the design sheet for {record.id} declares no extent at all"

            written = _written_positions(record)
            reach = max(written, default=0)
            if reach != declared:
                faults.append(f"369/{revision_id} {record.id}: reaches {reach}, design declares {declared}")
                continue

            unwritten = sorted(set(range(1, declared + 1)) - written)
            if unwritten:
                faults.append(
                    f"369/{revision_id} {record.id}: {len(unwritten)} unwritten position(s) of "
                    f"{declared}, starting at {unwritten[0]}"
                )
            if len(record.fields) != len(sheet.fields):
                faults.append(
                    f"369/{revision_id} {record.id}: ships {len(record.fields)} fields where the "
                    f"design defines {len(sheet.fields)}"
                )

    assert not faults, (
        "these shipped modelo 369 records do not reproduce their design sheet, so the export writes "
        "a structurally different record than AEAT published:\n  " + "\n  ".join(faults)
    )
