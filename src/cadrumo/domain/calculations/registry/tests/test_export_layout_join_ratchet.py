"""The export-layout byte-coverage join is a ratchet that must shrink.

``validate_export_layout_record_coverage`` joins each official AEAT record-design
sheet to the authored export record meant to carry it, then asks whether that
record writes every required byte position. Where the join cannot be
established it falls back to asking whether ANY record of the layout writes the
coordinate.

That fallback is a deliberate, documented design -- it can only under-report,
never over-report, and a REFUSAL names the mode that produced it. The gap this
gate closes is the other half: a CLEAN verdict says nothing at all. Every record
in a fixed-width layout starts at byte offset 1, so "does any record write this
offset" is satisfied by an unrelated record occupying the same range, and a
sheet whose own record omits a position still passes. A pass produced by the
fallback is therefore indistinguishable from a pass produced by a real
per-record join, which is the silent under-declaration this project forbids.

So the fallback population is pinned here by name. A NEW unjoined sheet fails
this gate, and a sheet that becomes joinable must be DELETED from the inventory
rather than left standing -- a spare slot silently widens the guarantee back
out. The inventory is expected to shrink to empty as discriminating literal
constants are authored per sheet; it must never grow.

Every entry sits on a MULTI-record layout, which is what makes its fallback
verdict materially weaker. A single-record layout is excluded by construction:
with one record, "any record writes this byte" and "this record writes this
byte" are the same question, so the fallback loses no rigor there and does not
belong in a debt inventory.

This gate asserts a structural property of the join, not a tax figure. It makes
no claim that any casilla is mis-declared -- only that for these sheets the
registry cannot currently prove per-record byte coverage.

See Also:
    :class:`RegistrySnapshot`
        The compiled authority whose export layouts this gate reads.
"""

from __future__ import annotations

import pytest

from .....core import Modelo
from .. import _validate_export_layout_coverage as coverage
from ..authority import ValidatedRegistryAuthority, bundled_authority
from ..errors import RegistryError
from ..schema import RegistrySnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: ``(modelo, revision_id, design_sheet_name)`` for every design sheet whose
#: record join cannot currently be established, so its byte-coverage verdict
#: comes from the weaker any-record fallback. Shrink this; never grow it.
_UNJOINED_DESIGN_SHEETS: frozenset[tuple[str, str, str]] = frozenset(
    (
        ('151', '2015-2022', 'M15100'),  # 9-record layout
        ('151', '2025-y-siguientes', 'M15100'),  # 11-record layout
        ('184', '2023-2024', 'Tipo 2 - Registro De Rentas De La'),  # 3-record layout
        ('184', '2023-2024', 'Tipo 2 - Registro De Socio, Heredero,'),  # 3-record layout
        ('184', '2025-y-siguientes', 'Tipo 2 - Registro De Rentas De La'),  # 3-record layout
        ('184', '2025-y-siguientes', 'Tipo 2 - Registro De Socio, Heredero,'),  # 3-record layout
        ('193', '2024', 'Tipo 2 - Registro De Perceptor'),  # 3-record layout
        ('193', '2024', 'Tipo 2 - Registro De Perceptor  Relación De Gastos'),  # 3-record layout
        ('193', '2025-y-siguientes', 'Tipo 2 - Registro De Perceptor'),  # 3-record layout
        ('193', '2025-y-siguientes', 'Tipo 2 - Registro De Perceptor  Relación De Gastos'),  # 3-record layout
        ('296', '2024-y-siguientes', 'Tipo 2 - Registro De Perceptor'),  # 5-record layout
        ('303', '2022', 'DP30300'),  # 5-record layout
        ('303', '2023', 'DP30300'),  # 6-record layout
        ('303', '2024-hasta-08-y-2t', 'DP30300'),  # 6-record layout
        ('303', '2025', 'DP30300'),  # 6-record layout
        ('303', '2026-y-siguientes', 'DP30300'),  # 6-record layout
        ('322', '2008-2022', 'DR32200'),  # 4-record layout
        ('322', '2023', 'DR32200'),  # 4-record layout
        ('322', '2024-2025', 'DR32200'),  # 4-record layout
        ('349', '2020-y-siguientes', 'Tipo 2 - Registro De Operador Intracomunitario'),  # 3-record layout
        ('349', '2020-y-siguientes', 'Tipo 2 - Registro De Retificaciones'),  # 3-record layout
        ('720', '2013-y-siguientes', 'Tipo 1 - Registro De Declarante'),  # 2-record layout
        ('720', '2013-y-siguientes', 'Tipo 2 - Registro De Detalle'),  # 2-record layout
    )
)

#: A scan resolving almost nothing would satisfy the equality assertion
#: perfectly. This floor sits far below the real figure so ordinary authoring
#: churn never moves it.
_MINIMUM_REVISIONS_SCANNED = 40


def _resolve(
    authority: ValidatedRegistryAuthority, modelo: Modelo, filing_year: int, period: str
) -> RegistrySnapshot | None:
    """Return the snapshot for this coordinate, or ``None`` when law defines none.

    A ``(modelo, year, period)`` triple that no published revision covers is not
    an error here -- it is simply a coordinate outside the scan. Narrowed to
    :exc:`RegistryError` rather than a blanket catch so a genuine loader or
    schema fault still propagates and reds the gate instead of silently
    shrinking the scanned population.
    """
    try:
        return authority.snapshot(modelo.value, filing_year=filing_year, period=period)
    except RegistryError:
        return None


def _scan() -> tuple[frozenset[tuple[str, str, str]], int, dict[tuple[str, str, str], int]]:
    """Return the unjoined sheets, revisions scanned, and each entry's record count."""
    authority = bundled_authority()
    source_refs = authority.catalogues.sources
    source_refs = getattr(source_refs, "entries", None) or source_refs
    if not hasattr(source_refs, "get"):
        source_refs = {entry.id: entry for entry in source_refs}

    seen: set[tuple[str, str]] = set()
    unjoined: set[tuple[str, str, str]] = set()
    record_counts: dict[tuple[str, str, str], int] = {}
    # Every filing year is walked, not just the first that resolves: a modelo's
    # revisions are keyed by year span, so stopping at the first hit would scan
    # one revision per modelo and silently shrink the population this gate pins.
    for modelo in Modelo:
        for filing_year in range(2008, 2028):
            for period in ("0A", "1T", "01"):
                resolution = _resolve(authority, modelo, filing_year, period)
                if resolution is None:
                    continue
                snapshot = resolution
                revision = snapshot.revision
                revision_id = revision.id
                if (modelo.value, revision_id) in seen:
                    break
                seen.add((modelo.value, revision_id))
                for layout in getattr(revision, "export_layouts", ()) or ():
                    for source in coverage._design_sources(layout, source_refs):
                        sheets = coverage._read_design_sheets(source)
                        if isinstance(sheets, str):
                            continue
                        for sheet in sheets:
                            if not coverage._belongs_to_layout(sheet, layout.records):
                                continue
                            if coverage._join_record(sheet, layout.records) is not None:
                                continue
                            if sheet.auxiliary_envelope_header is not None:
                                # An auxiliary envelope header never reaches the
                                # weak fallback: the coverage check branches on
                                # it BEFORE the fallback and attributes its
                                # prefix extent to the header itself. Counting
                                # one here would overstate the debt with a sheet
                                # that gives up no rigor at all -- and the
                                # coverage module records that the generic
                                # fallback is "actively wrong" for these,
                                # because neighbouring records' fields sit at
                                # the same low offsets.
                                continue
                            key = (modelo.value, str(revision_id), sheet.name)
                            unjoined.add(key)
                            record_counts[key] = len(layout.records)
                break
    return frozenset(unjoined), len(seen), record_counts


def test_the_scan_reaches_the_real_registry() -> None:
    """Anti-vacuity: a scan resolving nothing satisfies the equality assertion."""
    _, scanned, _ = _scan()

    assert scanned >= _MINIMUM_REVISIONS_SCANNED, (
        f"only {scanned} revisions scanned; the snapshot walk collapsed and every "
        "assertion in this module is vacuous"
    )


def test_the_unjoined_design_sheet_inventory_is_exact() -> None:
    """The fallback population must equal the declared inventory, in both directions."""
    measured, _, _ = _scan()

    grown = sorted(measured - _UNJOINED_DESIGN_SHEETS)
    fixed = sorted(_UNJOINED_DESIGN_SHEETS - measured)

    assert not grown, (
        "new design sheet(s) fell back to the weaker any-record byte check, so their export "
        "coverage is no longer per-record and nothing else says so:\n  "
        + "\n  ".join(f"{modelo} {revision} {sheet!r}" for modelo, revision, sheet in grown)
        + "\nAuthor a discriminating literal constant so the sheet joins its record, or add the "
        "entry here with the reason it cannot join."
    )
    assert not fixed, (
        "inventory entr(ies) no longer describe an unjoined sheet -- the join was fixed and the "
        "entry must be deleted, because a spare slot silently widens the guarantee back out:\n  "
        + "\n  ".join(f"{modelo} {revision} {sheet!r}" for modelo, revision, sheet in fixed)
    )


def test_every_inventory_entry_sits_on_a_multi_record_layout() -> None:
    """A single-record layout loses no rigor to the fallback and is not debt.

    Without this, the inventory would accept a benign single-record entry and
    quietly overstate how much coverage the project has actually given up.
    """
    measured, _, record_counts = _scan()

    benign = sorted(key for key in measured if record_counts.get(key, 0) < 2)

    assert not benign, (
        "inventory entr(ies) sit on a single-record layout, where the fallback asks the same "
        "question as a real join and so gives up nothing:\n  "
        + "\n  ".join(f"{modelo} {revision} {sheet!r}" for modelo, revision, sheet in benign)
        + "\nRemove them; this inventory is for real rigor loss only."
    )


def test_no_inventory_entry_is_an_auxiliary_envelope_header() -> None:
    """An AUX header is not fallback debt, and pinning one would overstate it.

    The coverage check branches on ``auxiliary_envelope_header`` BEFORE the
    generic fallback and attributes the header's declared prefix extent to the
    header itself, so such a sheet never takes the weaker any-record question.
    The module goes further and records that the fallback is "actively wrong"
    there, because neighbouring records' fields sit at the same low offsets --
    Modelo 232 was seen blaming ``dr23201`` fields for writing into
    ``DR23200``'s administracion bytes.

    This inventory was built from ``_join_record(...) is None`` alone, which is
    ALSO true of every AUX header, so it carried two Modelo 232 entries that
    gave up no rigor whatsoever. The sibling multi-record assertion catches one
    flavour of overstatement; this catches the other.
    """
    authority = bundled_authority()
    source_refs = authority.catalogues.sources
    source_refs = getattr(source_refs, "entries", None) or source_refs
    if not hasattr(source_refs, "get"):
        source_refs = {entry.id: entry for entry in source_refs}

    misfiled: list[str] = []
    seen: set[tuple[str, str]] = set()
    for modelo in Modelo:
        for filing_year in range(2008, 2028):
            for period in ("0A", "1T", "01"):
                snapshot = _resolve(authority, modelo, filing_year, period)
                if snapshot is None:
                    continue
                revision = snapshot.revision
                revision_id = str(revision.id)
                if (modelo.value, revision_id) in seen:
                    break
                seen.add((modelo.value, revision_id))
                for layout in getattr(revision, "export_layouts", ()) or ():
                    for source in coverage._design_sources(layout, source_refs):
                        sheets = coverage._read_design_sheets(source)
                        if isinstance(sheets, str):
                            continue
                        for sheet in sheets:
                            key = (modelo.value, revision_id, sheet.name)
                            if key in _UNJOINED_DESIGN_SHEETS and sheet.auxiliary_envelope_header is not None:
                                misfiled.append(f"{key[0]} {key[1]} {key[2]!r}")
                break

    assert not misfiled, (
        "inventory entr(ies) are auxiliary envelope headers, which the coverage check handles on "
        "their own branch rather than through the weak fallback, so they are not debt: "
        + ", ".join(sorted(misfiled))
    )
