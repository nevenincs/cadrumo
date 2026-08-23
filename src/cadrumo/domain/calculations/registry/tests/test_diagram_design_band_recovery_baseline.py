"""What the geometry reader currently recovers from AEAT's pre-2003 form diagrams.

Two bundled designs are read only partly, and both are diagrams rather than row
tables: AEAT's older ordenes published the record as a PICTURE -- floating captions
above a byte ruler -- and the reader recovers fields by pairing each caption with the
ruler band beneath it. On modelo 180's 2000 orden design that pairing recovers
seventeen fields covering 205 of 260 positions and then stops, leaving 196-250
unread on both records.

WHY THIS MODULE EXISTS RATHER THAN A FIX. The pairing runs for every one of the 215
bundled designs, and its heuristics decide field OFFSETS. Retuning it to catch one
trailing band risks shifting offsets on designs that currently read correctly, which
is silent and filing-grade: a field read one byte over still parses, still validates,
and still writes the wrong bytes. Nothing currently records what the reader recovers
today, so such a change could not be reviewed -- the reviewer would have no baseline
to diff against. This module is that baseline.

WHAT THE NEXT CHANGE SHOULD LOOK LIKE. The two sheets fail differently, and the
difference is the lead. Modelo 180's Tipo 1 record DOES carry a caption for the
unread band -- ``SELLO ELECTRÓNICO`` / ``(RESERVADO)``, immediately above the
196-260 ruler -- so the caption exists and the pairing missed it. Its Tipo 2 record
ends with three consecutive rulers and no caption at all, so there is nothing to pair
and the band is undescribed by the document. A fix that closes the first without
inventing content for the second is the shape to aim for.

THIS PINS BEHAVIOUR, NOT CORRECTNESS. Every number here is what the reader does
today, including what it gets wrong. A change that IMPROVES coverage will fail this
module, and that failure is the signal to update it deliberately -- with the diff
showing exactly which bands moved. Read it as a tripwire, never as a specification.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import extract_record_design

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_180_DIAGRAM = ("modelo_180", "02-180-orden-de-20-de-noviembre-de-2000-12-kb-pdf.pdf")
_MODELO_349_DIAGRAM = ("modelo_349", "03-349-orden-hac-360-2002-28-kb-pdf.pdf")


def _extraction(folder: str, name: str):
    return extract_record_design(bundled_path("corpus", "aeat_official", "disenos_registro", folder, "files", name))


def _covered(reason: str) -> tuple[int, list[str]]:
    """``(declared total, the position runs the reader did not read)`` from a skip reason."""
    declared = int(reason.split("declares ", 1)[1].split(" total", 1)[0])
    runs = reason.split("positions but ", 1)[1].split(" were not read", 1)[0]
    return declared, [run.strip() for run in runs.split(",")]


def test_the_pre_2003_diagrams_are_still_the_only_partly_read_designs() -> None:
    """If a third design joins them, this baseline stops describing the population.

    Cheap to state and it prevents the quiet case: a parser change that fixes these
    two while breaking a third would leave every assertion below passing.
    """
    for folder, name in (_MODELO_180_DIAGRAM, _MODELO_349_DIAGRAM):
        extraction = _extraction(folder, name)
        assert extraction.skipped, f"{name} now reads whole; this baseline is stale and should be retired"


def test_modelo_180_recovers_both_records_up_to_the_trailing_reserved_band() -> None:
    """Seventeen fields per record, 205 of 260 positions, the same hole on both."""
    extraction = _extraction(*_MODELO_180_DIAGRAM)

    assert not extraction.sheets, "a sheet now reads cleanly; the recovery improved and this needs re-baselining"
    assert len(extraction.skipped) == 2, [sheet.name for sheet in extraction.skipped]

    for sheet in extraction.skipped:
        declared, runs = _covered(sheet.reason or "")
        assert declared == 260, f"{sheet.name}: record length moved to {declared}"
        assert runs == ["196-250"], f"{sheet.name}: the unread band moved to {runs}"


def test_modelo_349_leaves_a_leading_and_a_trailing_band_unread() -> None:
    """Four records, each missing its 18-57 opening band; two also miss 176-195.

    Recorded as the per-record shape rather than a total, because the two failure
    positions are different leads: a band missed at the START of a record is a
    different pairing problem from one missed at the end.
    """
    extraction = _extraction(*_MODELO_349_DIAGRAM)

    assert len(extraction.skipped) == 4, [sheet.name for sheet in extraction.skipped]

    shapes = sorted((_covered(sheet.reason or "")[1]) for sheet in extraction.skipped)
    assert all(runs[0] in {"18-57", "18-65"} for runs in shapes), (
        f"every modelo 349 record is expected to miss its opening band; got {shapes}"
    )
    assert any(len(runs) > 1 for runs in shapes), (
        f"at least one record is expected to miss a second band as well; got {shapes}"
    )


def test_the_unread_modelo_180_band_still_carries_its_caption_in_the_document() -> None:
    """The lead for the fix, asserted against the document rather than remembered.

    ``SELLO ELECTRÓNICO (RESERVADO)`` sits immediately above the 196-260 ruler on the
    Tipo 1 record. That is why this band is a pairing failure and not an undescribed
    one, and it is the fact a fix would act on -- so it is checked here, where it will
    fail if a re-bundled document ever drops it.
    """
    from .._record_design import _extract_pdf_text_lines

    folder, name = _MODELO_180_DIAGRAM
    path = bundled_path("corpus", "aeat_official", "disenos_registro", folder, "files", name)
    lines = [line.strip() for line in _extract_pdf_text_lines(path.read_bytes(), source_label=name)]

    assert any("SELLO ELECTR" in line for line in lines), (
        "the caption naming the unread 196-260 band is gone from the document, so the "
        "pairing lead recorded in this module no longer applies"
    )
    assert any(line.startswith("196 197 198") for line in lines), (
        "the 196-260 ruler is gone, so the band this baseline describes no longer exists"
    )
