"""A modelo 151 casilla that cites a design must sit on a record that design carries.

Modelo 151 addresses its design slots by RECORD PAGE -- ``M15107000`` -- because
that is the unit AEAT's Diseño de Registros defines a box on. The printed form's
page numbering (``151-07``) is a different naming of a related thing, and the two
are easy to confuse: they refer to the same page of the same modelo, and only one
of them appears anywhere in the design.

SIX CASILLAS ONCE CARRIED THE FORM SLUG. The anexo transmisión IIC boxes
(``01``-``05`` and ``53``) cited ``aeat-dr-151-2023`` and were declared under
``151-07``, while their own file header stated the convention they broke --
"``segmento`` is the record page on which the box is defined" -- and named
``M15107000`` as their source page. The design carries those exact six numbers on
``M15107000`` and carries no ``151-07`` record at all, so the boxes were real and
correctly numbered and only their record slug was wrong. Nothing refused: the
coverage report is advisory, so the six simply scored as uncovered, which reads
identically to work not yet authored.

WHAT IS PINNED. Not the six ids and not a coverage tally -- the property that a
design-citing casilla names a record its cited design defines. A slug that names
the printed form instead, or a page that moved between editions, fails it; a
correctly addressed box satisfies it whatever its number.

Scoped to modelo 151, where the correspondence is grounded against both bundled
editions. Whether every other modelo's segmentos satisfy the same property is not
measured here and should not be inferred from this module passing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.resources import bundled_path
from ..record_design import extract_record_design
from ..record_design_coverage import build_diseno_coverage_report
from ..schema import ModeloRevision, RegistryCatalogues
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _design_path(revision: ModeloRevision, catalogues: RegistryCatalogues) -> Path:
    design_refs = [
        ref
        for ref in revision.source_refs
        if (source := catalogues.sources.get(ref)) is not None and source.kind == "record_design"
    ]
    assert design_refs, f"151/{revision.id} cites no record design to measure against"

    source = catalogues.sources[design_refs[0]]
    path = Path(source.corpus_path)
    if not path.exists():
        path = bundled_path() / source.corpus_path
    return path


def _design_record_names(revision: ModeloRevision, catalogues: RegistryCatalogues) -> set[str]:
    """Every record the cited design DEFINES, read from its sheets.

    Deliberately not read from the coverage report's casilla set. That set holds
    only boxes the design prints a bracketed number for, and modelo 151 has records
    -- ``M151DID00``, and ``M15101000`` in the 2015 edition -- that are read whole
    and carry no tagged box at all. Deriving record existence from tagged boxes
    reports those records as undefined, which is a statement about the numbering,
    not about the document.
    """
    extraction = extract_record_design(_design_path(revision, catalogues))
    assert not extraction.skipped, (
        "the design was not read whole, so an absent record cannot be distinguished from an "
        f"unparsed one: {[(sheet.name, sheet.reason) for sheet in extraction.skipped]}"
    )
    return {sheet.name for sheet in extraction.sheets}


def _design_box_sets(revision, catalogues) -> dict[str, set[str]]:
    """``record page -> the box numbers the cited design prints on it``."""
    report = build_diseno_coverage_report(_design_path(revision, catalogues), "151", revision, multi_segment=True)
    records: dict[str, set[str]] = {}
    for entry in report.diseno_casillas:
        segmento = getattr(entry, "segmento", None)
        if segmento:
            records.setdefault(str(segmento), set()).add(str(entry.number))
    return records


def _design_backed(revision, catalogues):
    return [
        casilla
        for casilla in revision.casillas
        if getattr(casilla, "segmento", None)
        and any(
            str(ref) in catalogues.sources and catalogues.sources[str(ref)].kind == "record_design"
            for ref in (getattr(casilla, "source_refs", ()) or ())
        )
    ]


def test_every_declared_segmento_is_a_record_the_cited_design_defines() -> None:
    """The property the form-page slug broke, stated over both revisions.

    A segmento naming no record in the design is unfalsifiable by the coverage
    report -- every casilla under it scores uncovered forever, indistinguishable
    from a page nobody has authored yet.
    """
    modelo, catalogues = _committed_modelo("151")

    stray: dict[str, list[str]] = {}
    for revision_id, revision in modelo.revisions.items():
        records = _design_record_names(revision, catalogues)
        assert records, f"151/{revision_id}'s design defined no records, so this proves nothing"

        declared = {str(c.segmento) for c in _design_backed(revision, catalogues)}
        assert declared, f"151/{revision_id} declares no design-backed casillas, so this proves nothing"

        unknown = sorted(declared - records)
        if unknown:
            stray[revision_id] = unknown

    assert not stray, (
        "these modelo 151 casillas cite a record design but sit on a segmento that design does not "
        f"define, so nothing can ever confirm or refute their placement: {stray}"
    )


def test_the_anexo_transmision_iic_boxes_sit_on_the_record_that_carries_their_numbers() -> None:
    """The concrete case, pinned by its box numbers rather than by its slug.

    Box numbers repeat across modelo 151's record pages, so a box set that merely FITS
    inside a page identifies nothing. The anexo transmisión IIC page is picked out by
    carrying these six boxes and no others, which is true of exactly one record in the
    2023 design and agrees with the naming in the casillas' own file header. Asserting
    the numbers rather than the segmento string means a future edition that renamed the
    page still passes if it kept the boxes together, and fails if it scattered them.
    """
    modelo, catalogues = _committed_modelo("151")
    revision = modelo.revisions["2025-y-siguientes"]

    declared = {str(c.number) for c in revision.casillas if str(getattr(c, "section", "")).count("transmision_iic")}
    assert declared, "the anexo transmisión IIC casillas are gone; re-ground this module before deleting it"

    records = _design_box_sets(revision, catalogues)
    carrying = sorted(page for page, numbers in records.items() if declared == numbers)

    # Containment does NOT identify the record: modelo 151 restarts box numbering on
    # each page, so M15108000's forty-one boxes include 01-05 and 53 as well. What
    # picks one record is the box set matching EXACTLY -- the anexo transmisión IIC
    # page carries these six and nothing else.
    assert len(carrying) == 1, (
        f"the anexo transmisión IIC box set {sorted(declared)} must be exactly one design record's "
        f"box set, or its placement is not determined by the design: {carrying}"
    )

    placed = {str(c.segmento) for c in revision.casillas if str(getattr(c, "section", "")).count("transmision_iic")}
    assert placed == {carrying[0]}, (
        f"the boxes are declared on {sorted(placed)} but the design carries them together on {carrying[0]!r}"
    )
