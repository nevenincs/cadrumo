"""A page-record design is read by whichever extractor reads it more completely.

A design that names its records by page is read through pdfplumber, because the
plain text extractor does not recover those headings. That switch used to be
unconditional, and for one design it cost more than it bought.

WHAT IT COST, on Modelo 390's 2015 edition. Under pdfplumber its ``Pág. 7`` came
back with the row at ``@132`` missing entirely AND the surviving tail mis-paired
onto ``@115``, so that position carried casilla ``[654]`` -- which belongs to
``@132`` -- while its own ``[523]`` was left stranded as a bare fragment. The
plain extraction reads the same design whole, nine records, with every casilla
tag in that run landing where its sibling editions put it -- ``[523]``
included, since the stranded-tag fold reattaches it.

WHY THE MIS-PAIRING MATTERS MORE THAN THE HOLE. The reversed-column repair's
docstring states that a wrong pairing "cannot pass quietly: it would place a
field at a position some other row already covers". Here it did pass quietly:
the mis-paired tail tiled ``@115+17`` exactly, so nothing overlapped and nothing
was missing at that position. Only the orphaned head left a hole for the
contiguity check to catch, and that hole is at a DIFFERENT position than the
error. A pairing that tiles is invisible to that check, which is why this module
pins the descriptions rather than only the record count.

THE GROUND TRUTH IS THE CORPUS, NOT THIS FILE. The expected descriptions are
computed from the sibling editions that read cleanly, so the assertion is
"the 2015 PDF agrees with the editions around it" rather than "the 2015 PDF
matches a string someone typed here".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from cadrumo.domain.calculations.registry.record_design import extract_record_design
from ..record_design import (
    _EMPTY_CORRECTIONS,
    _better_page_record_lines,
    _collapse_stuttered_row_prefix,
    _extract_pdf_text_lines,
    _extract_pdfplumber_text_lines,
    _join_wrapped_row_descriptions,
    _uses_page_record_layout,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A bracketed casilla number as AEAT prints it in a design's description.
_TAG = re.compile(r"\[(\d+)\]")

_MODELO_390 = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_390", "files")
_REPAIRED_DESIGN = "08-390-ejercicio-2015-103-kb-pdf.pdf"
_CONTESTED_SHEET = "Pág. 7"
#: The section-11 run. Under pdfplumber ``@132`` was lost entirely and its
#: casilla tag surfaced on ``@115`` instead, so the whole run is checked rather
#: than the two positions that happened to show the damage.
_CONTESTED_OFFSETS = (115, 132, 149, 166, 183)

#: A page-record design whose pdfplumber read is already whole. It must keep
#: using that reader, or the change would be a blanket preference for the plain
#: extractor rather than a measured choice.
_CLEAN_PAGE_RECORD_DESIGN = bundled_path(
    "corpus",
    "aeat_official",
    "disenos_registro",
    "modelo_840",
    "files",
    "01-840-orden-hac-2572-2003-99-kb-pdf.pdf",
)


def _read_or_abstain(design: Path):
    """Return the design's extraction, or ``None`` where it cannot be read.

    A sibling this parser cannot read simply does not vote on the consensus.
    Abstaining is right here and would be wrong in the assertions below, which
    is why it is confined to the sibling walk.
    """
    try:
        return extract_record_design(design)
    except Exception:  # an unreadable sibling abstains rather than failing the vote
        return None


def _sibling_descriptions() -> dict[int, str]:
    """Return ``offset -> description`` agreed by every cleanly-read sibling edition."""
    agreed: dict[int, set[str]] = {offset: set() for offset in _CONTESTED_OFFSETS}
    editions = 0
    for design in sorted(_MODELO_390.iterdir()):
        if design.name == _REPAIRED_DESIGN or design.suffix.lower() not in {".pdf", ".xls", ".xlsx"}:
            continue
        extraction = _read_or_abstain(design)
        if extraction is None:
            continue
        sheet = next((s for s in extraction.sheets if s.name == _CONTESTED_SHEET), None)
        if sheet is None:
            continue
        by_offset = {field.offset: (field.description or "") for field in sheet.fields}
        if not all(offset in by_offset for offset in _CONTESTED_OFFSETS):
            continue
        editions += 1
        for offset in _CONTESTED_OFFSETS:
            agreed[offset].add(by_offset[offset])

    assert editions >= 3, f"only {editions} sibling editions voted; the consensus would be thin"
    consensus: dict[int, str] = {}
    for offset, seen in agreed.items():
        assert len(seen) == 1, f"the siblings disagree at @{offset}: {sorted(seen)}"
        consensus[offset] = next(iter(seen))
    return consensus


def test_the_repaired_design_reads_every_record() -> None:
    extraction = extract_record_design(_MODELO_390 / _REPAIRED_DESIGN)

    assert not extraction.skipped, [(s.name, s.reason) for s in extraction.skipped]
    assert extraction.is_complete


def test_no_position_carries_another_position_s_casilla_tag() -> None:
    """The defect this pins: a tag that tiled onto the wrong bytes.

    Asserted as a SUBSET of the sibling consensus at the same offset, which
    fails on a foreign tag and tolerates a missing one. That asymmetry is
    deliberate: a lost tag understates coverage and is visible as such, while a
    tag on the wrong bytes reads as a real declaration about a position AEAT
    never made it about. The companion below stops the tolerance from hollowing
    the check out.
    """
    consensus = _sibling_descriptions()
    extraction = extract_record_design(_MODELO_390 / _REPAIRED_DESIGN)
    sheet = next(s for s in extraction.sheets if s.name == _CONTESTED_SHEET)
    by_offset = {field.offset: (field.description or "") for field in sheet.fields}

    for offset, expected in consensus.items():
        assert offset in by_offset, f"@{offset} is not read at all"
        read_tags = set(_TAG.findall(by_offset[offset]))
        expected_tags = set(_TAG.findall(expected))
        foreign = read_tags - expected_tags
        assert not foreign, (
            f"@{offset} declares casilla {sorted(foreign)}, which the sibling editions put elsewhere; "
            f"they declare {sorted(expected_tags)} here"
        )


def test_every_contested_position_carries_its_own_tag() -> None:
    """The subset check above must not pass by the design losing every tag.

    All five positions carry theirs, ``@115`` included. It did not when this
    module was written: its ``[523]`` was emitted as a bare bracket on its own
    line that no repair reattached, which is a smaller and separate gap from
    the mis-attribution this module exists for -- and a real one, since a
    position with no tag contributes no casilla number to coverage. The fold
    that closed it is pinned in its own module; asserted here as equality
    because this run is where the loss was found.
    """
    consensus = _sibling_descriptions()
    extraction = extract_record_design(_MODELO_390 / _REPAIRED_DESIGN)
    sheet = next(s for s in extraction.sheets if s.name == _CONTESTED_SHEET)
    by_offset = {field.offset: (field.description or "") for field in sheet.fields}

    for offset, expected in consensus.items():
        expected_tags = set(_TAG.findall(expected))
        if not expected_tags:
            continue
        assert set(_TAG.findall(by_offset.get(offset, ""))) == expected_tags, (
            f"@{offset} does not carry the casilla the sibling editions put there: expected {sorted(expected_tags)}"
        )


def test_a_page_record_design_that_reads_whole_keeps_its_own_extractor() -> None:
    """The choice is measured per design, not a preference for one reader.

    Without this, replacing an unconditional switch with a different
    unconditional switch would pass every assertion above.
    """
    raw = Path(_CLEAN_PAGE_RECORD_DESIGN).read_bytes()
    label = _CLEAN_PAGE_RECORD_DESIGN.name
    base_lines = _extract_pdf_text_lines(raw, source_label=label)
    assert _uses_page_record_layout(base_lines), "this design must use the page-record layout to be a witness"

    plain = _collapse_stuttered_row_prefix(_join_wrapped_row_descriptions(base_lines))
    page = _collapse_stuttered_row_prefix(
        _join_wrapped_row_descriptions(_extract_pdfplumber_text_lines(raw, source_label=label)),
    )
    assert plain != page, "the two extractions are identical here, so the choice is untested"

    chosen = _better_page_record_lines(page, plain, source_label=label, corrections=_EMPTY_CORRECTIONS)

    assert chosen is page
