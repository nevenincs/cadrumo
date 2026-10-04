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

from functools import cache

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import AmbiguousRevisionSelectionError
from cadrumo.domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from dev.registry.compiler.authority import compiled_bundled_authority
from dev.registry.maintenance_support import (
    coverage_assessment_floor,
    coverage_assessment_horizon,
    declared_revision_selection_date,
    revision_selection_coordinates,
)

from ..compiler import export_layout_record_join as coverage_records

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: ``(modelo, revision_id, design_sheet_name)`` for every design sheet whose
#: record join cannot currently be established, so its byte-coverage verdict
#: comes from the weaker any-record fallback. Shrink this; never grow it.
_UNJOINED_DESIGN_SHEETS: frozenset[tuple[str, str, str]] = frozenset[tuple[str, str, str]]()

#: A scan resolving almost nothing would satisfy the equality assertion
#: perfectly. This floor sits far below the real figure so ordinary authoring
#: churn never moves it.
_MINIMUM_REVISIONS_SCANNED = 40


def _resolve_declared(
    authority: ValidatedRegistryAuthority,
    modelo_id: str,
    revision: ModeloRevision,
    filing_year: int,
    period: str,
) -> RegistrySnapshot:
    """Select the declared coordinate at its honest grade, or fail the scan."""
    try:
        snapshot = authority.snapshot(
            modelo_id, filing_year=filing_year, period=period, grade=revision.effective_authority_grade
        )
    except AmbiguousRevisionSelectionError:
        on = declared_revision_selection_date(revision, filing_year)
        if on is None:
            raise
        snapshot = authority.snapshot(
            modelo_id, filing_year=filing_year, period=period, on=on, grade=revision.effective_authority_grade
        )
    assert snapshot.revision.id == revision.id, (
        f"declared coordinate {modelo_id}/{revision.id} {filing_year}/{period} selected {snapshot.revision.id}"
    )
    return snapshot


@cache
def _scan() -> tuple[
    frozenset[tuple[str, str, str]],
    int,
    dict[tuple[str, str, str], int],
    frozenset[tuple[str, str, int, str]],
    tuple[str, ...],
]:
    """Return unjoined sheets, exact selected frames, and auxiliary misfilings."""
    authority = compiled_bundled_authority()
    horizon = coverage_assessment_horizon(authority.catalogues)
    floor = coverage_assessment_floor(authority.catalogues)
    source_refs = authority.catalogues.sources
    source_refs = getattr(source_refs, "entries", None) or source_refs
    if not hasattr(source_refs, "get"):
        source_refs = {entry.id: entry for entry in source_refs}

    seen: set[tuple[str, str]] = set()
    frames: set[tuple[str, str, int, str]] = set()
    unjoined: set[tuple[str, str, str]] = set()
    record_counts: dict[tuple[str, str, str], int] = {}
    misfiled: list[str] = []
    for definition in authority.modelos:
        modelo_id = definition.id
        for declared in definition.revisions.values():
            for filing_year, period in revision_selection_coordinates(
                declared, assessment_horizon=horizon, assessment_floor=floor
            ):
                snapshot = _resolve_declared(authority, modelo_id, declared, filing_year, str(period))
                revision = snapshot.revision
                revision_id = revision.id
                frames.add((str(modelo_id), str(revision_id), filing_year, str(period)))
                if (modelo_id, revision_id) in seen:
                    continue
                seen.add((modelo_id, revision_id))
                # Read the SAME constant channels the coverage checker reads. A
                # ratchet seeing fewer would pin sheets the checker joins fine
                # and report debt that does not exist.
                constants = coverage_records._design_constant_values(revision)
                for layout in getattr(revision, "export_layouts", ()) or ():
                    for source in coverage_records._design_sources(layout, source_refs):
                        sheets = coverage_records._read_design_sheets(source)
                        if isinstance(sheets, str):
                            raise AssertionError(
                                f"cannot assess official design sheets for modelo {modelo_id} revision {revision_id} "
                                f"layout {layout.id} source {source.id}: {sheets}"
                            )
                        for sheet in sheets:
                            if not coverage_records._belongs_to_layout(sheet, layout.records, constants, source=source):
                                continue
                            key = (modelo_id, str(revision_id), sheet.name)
                            if key in _UNJOINED_DESIGN_SHEETS and sheet.auxiliary_envelope_header is not None:
                                misfiled.append(f"{key[0]} {key[1]} {key[2]!r}")
                            if (
                                coverage_records._join_record(sheet, layout.records, constants, source=source)
                                is not None
                            ):
                                continue
                            if (
                                layout.filing_envelope is not None
                                and sheet.name == layout.filing_envelope.record_identity
                            ):
                                # The layout's declared filing ENVELOPE never
                                # reaches the fallback either: the coverage
                                # check decides it BEFORE the join and answers
                                # from the envelope contract. The join is
                                # skipped there deliberately -- an envelope
                                # opens with the same `<T` and modelo bytes its
                                # page records do, so it agrees with every one
                                # of them and would "join" a page whose fields
                                # sit at unrelated offsets.
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
                            if (
                                layout.auxiliary_envelope_header is not None
                                and sheet.name == layout.auxiliary_envelope_header.record_identity
                            ):
                                # The source's variable envelope header is
                                # proved against this exact authored auxiliary
                                # prefix, including roles and source pin, by
                                # the coverage validator before fallback.
                                continue
                            unjoined.add(key)
                            record_counts[key] = len(layout.records)
    return frozenset(unjoined), len(seen), record_counts, frozenset(frames), tuple(sorted(misfiled))


def test_the_scan_reaches_the_real_registry() -> None:
    """Anti-vacuity: a scan resolving nothing satisfies the equality assertion."""
    _, scanned, _, frames, _ = _scan()

    assert scanned >= _MINIMUM_REVISIONS_SCANNED, (
        f"only {scanned} revisions scanned; the snapshot walk collapsed and every assertion in this module is vacuous"
    )
    assert {
        ("131", "2026", 2026, "1T"),
        ("131", "2026", 2026, "2T"),
        ("131", "2026-late", 2026, "3T"),
        ("131", "2026-late", 2026, "4T"),
    } <= frames


def test_the_unjoined_design_sheet_inventory_is_exact() -> None:
    """The fallback population must equal the declared inventory, in both directions."""
    measured, _, _, _, _ = _scan()

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
    measured, _, record_counts, _, _ = _scan()

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
    ALSO true of a separately declared AUX header. The historical inventory
    carried two Modelo 232 entries before its official variable envelope was
    enrolled. The sibling multi-record assertion catches one flavour of
    overstatement; this catches the other.
    """
    _, _, _, _, misfiled = _scan()

    assert not misfiled, (
        "inventory entr(ies) are auxiliary envelope headers, which the coverage check handles on "
        "their own branch rather than through the weak fallback, so they are not debt: " + ", ".join(sorted(misfiled))
    )
