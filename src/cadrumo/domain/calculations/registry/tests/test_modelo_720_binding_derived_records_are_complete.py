"""Modelo 720's records are complete -- but only the snapshot can say so.

Modelo 720 does not author its export fields. Its committed layout declares exactly
two things, a reserved filler tail on each record, and every data field is DERIVED
from the revision's bindings when the snapshot is built. Derivation REPLACES the
layout rather than extending it, so the committed TOML and the record that actually
ships are two different documents.

THAT IS WHY THE COMMITTED TREE READS AS A CATASTROPHE. Measured there, the type_1
record holds one field covering positions 181-500 and the type_2 record one covering
481-500 -- so the first 180 and 480 positions carry nothing at all, against a design
declaring 500. Every value modelo 720 exists to declare appears to be missing. On the
snapshot the same two records carry fourteen and thirty-one fields, reach 500, and
leave no position unwritten -- matching the design's own fourteen and thirty-one
sheets field for field.

Nothing was fixed to get from one reading to the other. The first reading measured a
document that is never exported.

WHAT THIS PINS. That the shipped records stay complete, and -- separately and first --
that they are still binding-derived, so the day someone authors fields into the
committed layout, or derivation stops running for this modelo, the difference is
stated rather than absorbed. The second assertion is what keeps the first honest: a
completeness check that silently began reading the committed tree would report modelo
720 as broken, and a reader who had forgotten why would go looking for the wrong bug.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.resources._boundary import bundled_path
from ..authority import ValidatedRegistryAuthority
from ..record_design import extract_record_design
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION_ID = "2013-y-siguientes"

#: Ejercicio 2012 is the earliest modelo 720 governs (Orden HAP/72/2013's disposición
#: final única), and its filing campaign opens in 2013. The snapshot is resolved from
#: this year rather than from a stored revision id, so the revision is law-determined
#: and merely CONFIRMED to be the one under test.
_FILING_YEAR = 2013

_RECORD_TO_DESIGN_SHEET = {
    "modelo-720-type-1": "Tipo 1 - Registro De Declarante",
    "modelo-720-type-2": "Tipo 2 - Registro De Detalle",
}


def _snapshot_revision():
    authority = ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())
    snapshot = authority.snapshot("720", filing_year=_FILING_YEAR, period="0A")
    assert snapshot.revision.id == _REVISION_ID, (
        f"filing year {_FILING_YEAR} resolves to revision {snapshot.revision.id!r}, not {_REVISION_ID!r}; "
        "re-ground this module rather than pinning the stored id"
    )
    return snapshot.revision


def _records(revision):
    return [record for layout in revision.export_layouts for record in layout.records]


def _written_positions(record) -> set[int]:
    written: set[int] = set()
    for field in record.fields:
        if field.offset is not None:
            written.update(range(field.offset, field.offset + (field.length or 1)))
    return written


def _design_sheets():
    _modelo, catalogues = _committed_modelo("720")
    source = catalogues.sources["aeat-dr-720"]
    path = Path(source.corpus_path)
    if not path.exists():
        path = bundled_path() / source.corpus_path

    extraction = extract_record_design(path)
    assert not extraction.skipped, (
        "the design was not read whole, so an unwritten position cannot be told apart from an "
        f"unparsed one: {[(sheet.name, sheet.reason) for sheet in extraction.skipped]}"
    )
    return {sheet.name: sheet for sheet in extraction.sheets}


def test_the_records_are_still_binding_derived_rather_than_authored() -> None:
    """The premise the completeness check depends on, asserted before it.

    Stated as the DIFFERENCE between the two documents, not as a field count: the
    committed layout must carry strictly fewer written positions than the shipped one.
    If they ever coincide, modelo 720 has started authoring its fields and the reason
    this module reads the snapshot has gone away.
    """
    committed, _catalogues = _committed_modelo("720")
    committed_revision = committed.revisions[_REVISION_ID]
    shipped = {record.id: _written_positions(record) for record in _records(_snapshot_revision())}

    authored_only: list[str] = []
    for record in _records(committed_revision):
        committed_positions = _written_positions(record)
        shipped_positions = shipped.get(record.id)
        assert shipped_positions is not None, f"{record.id} is not present on the snapshot at all"
        if not committed_positions < shipped_positions:
            authored_only.append(
                f"{record.id}: committed writes {len(committed_positions)} positions, "
                f"snapshot writes {len(shipped_positions)}"
            )

    assert not authored_only, (
        "modelo 720's committed layout no longer carries strictly less than its shipped one, so "
        "binding derivation is not adding the data fields this module assumes it adds:\n  " + "\n  ".join(authored_only)
    )


def test_every_shipped_record_writes_every_position_its_design_declares() -> None:
    """No hole anywhere. Modelo 720's design declares no BLANCOS run to excuse one."""
    revision = _snapshot_revision()
    sheets = _design_sheets()

    record_ids = {record.id for record in _records(revision)}
    assert record_ids == set(_RECORD_TO_DESIGN_SHEET), (
        f"720 ships records {sorted(record_ids)}, which is not the set this module maps: "
        f"{sorted(_RECORD_TO_DESIGN_SHEET)}"
    )
    resolved = [_RECORD_TO_DESIGN_SHEET[record_id] for record_id in sorted(record_ids)]
    assert len(set(resolved)) == len(resolved), f"two 720 records resolve to one design sheet: {resolved}"

    faults: list[str] = []
    for record in _records(revision):
        sheet = sheets[_RECORD_TO_DESIGN_SHEET[record.id]]
        declared = max(
            (field.offset + (field.length or 1) - 1 for field in sheet.fields if field.offset is not None),
            default=0,
        )
        assert declared, f"the design sheet for {record.id} declares no extent at all"

        unwritten = sorted(set(range(1, declared + 1)) - _written_positions(record))
        if unwritten:
            faults.append(
                f"720 {record.id}: {len(unwritten)} unwritten position(s) of {declared}, starting at {unwritten[0]}"
            )

    assert not faults, (
        "these shipped modelo 720 records leave positions unwritten, so the export omits declared "
        "values behind a full-length record:\n  " + "\n  ".join(faults)
    )
