"""No export record may reach past the extent its own AEAT design declares.

A fixed-width export record is a byte window. The design that record encodes declares
how many positions the window has -- its "TOTAL n POSICIONES" row -- and a layout whose
fields reach past that number writes declared values outside the record AEAT will read.

THE HARM IS PROVED, NOT HYPOTHETICAL. Measured on Modelo 390 during the design-relayout
campaign: an ``export_draft`` call succeeded and wrote the total cuota at byte 1628,
against a record its own design declares ending at 1526. The export did not fail. It
produced a byte-valid, length-valid, digest-valid file with a load-bearing figure
outside the record, and nothing in the pipeline objected.

WHY THIS CHECK IS POSSIBLE WHEN THE OBVIOUS ONE IS NOT. The natural check -- compare
every layout field against its published box -- needs a casilla-to-official-box mapping.
Measured on Modelo 200, pairing its 6,537 layout fields to its design's 6,808 slots by
box number matches only 36.7% unambiguously: 42.3% of casilla ids match SEVERAL slots
because AEAT repeats a box across regimen segments and prorrata rows, and 18.9% are
literal or draft envelope fields the design never numbers at all. There may be no such
mapping to find, because the layouts were never derived from a design in the first
place.

This check needs NO mapping. A record's implied extent is the largest ``offset + length``
its own fields declare, and the design's declared total is a single number per sheet.
Comparing a maximum against a maximum pairs nothing. That is exactly how the Modelo 390
mis-write was found -- by internal inconsistency rather than by identifying which box
the stray value belonged to.

WHAT THIS DOES NOT CHECK, so its silence is not over-read. It does not verify that any
field sits at its correct offset; a layout entirely shifted within its record passes
here. It does not detect a record that stops SHORT of its declared total, which is
legitimate when trailing positions are reserved. And it is bounded by the coarsest
comparison available: a record is only flagged when it exceeds the LARGEST total any
sheet of its design declares, so a record overflowing a smaller sheet while fitting a
larger one is not caught. Each of those needs the record-to-sheet pairing this module
deliberately avoids depending on.

UNREADABLE IS UNMEASURED, NEVER PASSING. A design whose POSICIONES totals cannot be
extracted is reported, not skipped. Six revisions are in that state today, including
Modelo 200 -- the modelo most closely inspected during this work is the one this
check cannot speak about. A parser that cannot read a total returns the same answer as a
layout that fits, and that equivalence is what every instrument corrected here
had in common.

No count is hardcoded. The number of revisions, records and design totals all move as
the corpus grows, and gating on any of them would encode today and detect nothing
tomorrow.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .....tests.registry_tree import bundled_registry_tree
from ..authority import ValidatedRegistryAuthority
from ..record_design import extract_record_design
from ..schema import ModeloRevision
from .._schema_exports import ExportRecordDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _authority() -> ValidatedRegistryAuthority:
    return ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())


def _record_design_sources() -> dict[str, Path]:
    """``source id -> bundled design path`` for every declared record-design source.

    Resolved through the registry's own source catalogue rather than by globbing the
    corpus, so a revision is measured against the design IT declares rather than
    whichever file sorts newest. Selecting by filename was the first draft's defect: it
    compared Modelo 303's revisions against a design neither of them encodes and
    produced a 194-byte overshoot that was an artefact of the comparison.
    """

    _modelos, catalogues = bundled_registry_tree()
    corpus_root = Path(bundled_path())
    resolved: dict[str, Path] = {}
    for source_id, source in catalogues.sources.items():
        if getattr(source, "kind", None) != "record_design":
            continue
        corpus_path = getattr(source, "corpus_path", None)
        if not corpus_path:
            continue
        resolved[str(source_id)] = corpus_root / corpus_path
    return resolved


def _implied_extent(record: ExportRecordDefinition) -> int | None:
    """The last byte position ``record`` declares a field at, or ``None`` if it declares none."""
    extents = [
        field.offset + field.length - 1
        for field in record.fields
        if field.offset is not None and field.length is not None
    ]
    return max(extents) if extents else None


def _declared_totals(design: Path) -> tuple[int, ...]:
    """Every readable ``TOTAL n POSICIONES`` figure the design declares, per sheet."""
    try:
        sheets = extract_record_design(design).accept_partial()
    except Exception:  # an unparseable design is reported as unmeasured, never raised
        return ()
    return tuple(sheet.total_positions for sheet in sheets if isinstance(sheet.total_positions, int))


def _exporting_revisions() -> list[tuple[str, str, ModeloRevision]]:
    return [
        (modelo.id, revision_id, revision)
        for modelo in _authority().modelos
        for revision_id, revision in modelo.revisions.items()
        if revision.export_layouts
    ]


def test_no_export_record_reaches_past_its_design_declared_extent() -> None:
    """Every record must fit inside the largest window its own design declares.

    Compares a maximum against a maximum, so it pairs no field to any slot. A record
    flagged here declares a field beyond the last position AEAT's design admits for any
    sheet of that record's design, which means an export writes a declared value outside
    the record a reader will parse.
    """
    designs = _record_design_sources()
    overshoots: list[str] = []
    compared = 0
    for modelo_id, revision_id, revision in _exporting_revisions():
        for layout in revision.export_layouts:
            totals: list[int] = []
            for source_id in layout.source_refs:
                design = designs.get(str(source_id))
                if design is not None and design.is_file():
                    totals.extend(_declared_totals(design))
            if not totals:
                continue
            widest = max(totals)
            for record in layout.records:
                extent = _implied_extent(record)
                if extent is None:
                    continue
                compared += 1
                if extent > widest:
                    overshoots.append(
                        f"modelo {modelo_id} revision {revision_id!r} record {record.id!r} declares a "
                        f"field ending at byte {extent}, past the widest extent its design declares "
                        f"({widest})"
                    )
    assert compared, (
        "no export record was compared against a design total at all, so this assertion would be "
        "vacuous -- either the source catalogue no longer resolves record-design entries or no "
        "design publishes a readable POSICIONES figure"
    )
    assert not overshoots, (
        "these export records reach past the extent their own AEAT design declares, so an export "
        "writes declared values outside the record a reader parses -- the shape proved on Modelo 390, "
        "where a total cuota was written at byte 1628 against a record ending at 1526:\n  "
        + "\n  ".join(sorted(overshoots))
    )


def test_a_revision_whose_design_publishes_no_readable_total_is_reported_as_unmeasured() -> None:
    """An unreadable design total is UNMEASURED, never a pass.

    A parser that cannot extract a POSICIONES figure returns the same answer as a layout
    that fits, and that equivalence is what every instrument corrected here had
    in common. This names the revisions the extent check cannot speak about, so its
    silence about them is not read as their being correct.

    It asserts the inventory is REPORTED rather than empty, deliberately: the unmeasured
    set is expected to be non-empty today, and requiring it to be empty would fail on a
    corpus property this module cannot fix. What must never happen is the set being
    invisible.
    """
    designs = _record_design_sources()
    unmeasured: list[str] = []
    measured: list[str] = []
    for modelo_id, revision_id, revision in _exporting_revisions():
        for layout in revision.export_layouts:
            declared = [str(source_id) for source_id in layout.source_refs if str(source_id) in designs]
            totals: list[int] = []
            for source_id in declared:
                design = designs[source_id]
                if design.is_file():
                    totals.extend(_declared_totals(design))
            target = f"modelo {modelo_id} revision {revision_id!r} layout {layout.id!r}"
            if totals:
                measured.append(target)
            elif not declared:
                unmeasured.append(f"{target}: declares no record-design source this catalogue resolves")
            else:
                unmeasured.append(f"{target}: its design(s) {declared} publish no readable POSICIONES")

    assert measured, (
        "no exporting layout resolved a design with a readable total, so the extent check above is "
        "measuring nothing and its silence means nothing"
    )
    # Printed rather than asserted-empty: the unmeasured set is a corpus property this
    # module reports, not a defect it can close. Failing on it would make the honest
    # negative unshippable and invite an allowlist.
    if unmeasured:
        print(f"\nUNMEASURED by the export-extent check ({len(unmeasured)}):")
        for entry in sorted(unmeasured):
            print(f"  {entry}")
