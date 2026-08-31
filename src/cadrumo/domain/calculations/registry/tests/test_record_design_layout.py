"""Tests for record-design workbook headers, layout markers, and completeness."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.directory_scan import DirectoryEntryKind, scan_directory
from .. import record_design_workbook_headers as record_design_headers_module
from ..errors import RegistryValidationError
from ..record_design import (
    extract_record_design,
    extract_record_design_pdf,
)
from ..record_design_schema import (
    RecordDesignRelativeSuffixMarker,
)
from ._record_design_support import (
    _RECORD_DESIGN_ROOT,
    _write_pdf_lines,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_header_matching_ignores_an_abbreviating_full_stop_on_either_side() -> None:
    """A header token means the same thing with or without AEAT's trailing stop.

    Pinned as a PROPERTY rather than as the accepted string set, because the set
    is what went wrong: ``posic.`` and ``oblig.`` were enrolled with their stop
    and ``lon`` without, so Modelo 115 -- which writes ``Lon`` on one sheet and
    ``Lon.`` on the next, inside ONE workbook -- matched the first and missed the
    second. A test naming the literal spellings would have been satisfied by the
    broken set. This one fails for any token whose two spellings disagree.
    """
    for token in ("lon", "posic", "tipo", "descripcion", "oblig", "validacion", "contenido"):
        with_stop = record_design_headers_module._optional_header_index((f"{token}.",), token)
        without_stop = record_design_headers_module._optional_header_index((token,), token)
        assert with_stop == without_stop == 0, token
        # And the expected side may carry the stop just as the cell may.
        assert record_design_headers_module._optional_header_index((token,), f"{token}.") == 0, token


def test_a_workbook_mixing_both_header_spellings_yields_every_sheet() -> None:
    """The real Modelo 115 binary: ``Lon`` on one sheet, ``Lon.`` on the other.

    The regression this locks is not a parse error -- it is a SILENT one. The
    body sheet was skipped for its header spelling, the remaining 13-field sheet
    was classified as an auxiliary envelope, and a healthy 1422-row design
    presented as carrying no record sheets at all.
    """
    design = scan_directory(
        _RECORD_DESIGN_ROOT / "modelo_115" / "files", pattern="*.xls", select=DirectoryEntryKind.FILES
    )[0]
    sheets = extract_record_design(design).accept_partial()

    assert len(sheets) == 2, [sheet.name for sheet in sheets]
    assert all(sheet.fields for sheet in sheets), {sheet.name: len(sheet.fields) for sheet in sheets}


def test_a_design_with_a_dropped_sheet_reports_the_read_as_partial() -> None:
    """A partial read must SAY it is partial -- the first half of the bite proof.

    Modelo 232 is the live case: its ``TABLAS`` tab is a legend -- two lookup
    tables of relationship-type and valuation-method codes (LIS art. 18.3/18.4)
    -- carrying no ``Posic.``/``Lon``/``Tipo``/``Contenido`` columns anywhere, so
    the header probe correctly finds nothing to parse there while the sheet's
    three genuine record pages (``DR23200``-``DR23202``) read cleanly. Modelo
    151's own nine header-shape-variant sheets were this test's specimen until
    the parser learned that second AEAT header shape (see
    ``test_a_second_recognised_header_shape_is_read_and_a_non_matching_sheet_still_skips``);
    now they parse, so this specimen moved to a sheet that is genuinely never
    going to become a record -- not a temporarily-unread one.

    Asserted on the PROPERTY -- some sheets read, some named as skipped, and the
    two disjoint -- rather than on the counts, which move whenever the header
    vocabulary widens or AEAT republishes.
    """
    design = (
        _RECORD_DESIGN_ROOT
        / "modelo_232"
        / "files"
        / "01-232-orden-hfp-816-2017-ejercicio-2016-y-siguientes-actualizado-15-01-2020-145-kb-xlsx.xlsx"
    )
    assert design.is_file(), f"corpus anchor moved: {design}"

    extraction = extract_record_design(design)

    assert extraction.skipped, "Modelo 232 drops its TABLAS tab; a read that reports none is not seeing it"
    assert extraction.sheets, "some sheets do parse, so this must be a PARTIAL read rather than a refusal"
    # A DECLARED non-record tab is named in ``skipped`` but does not make the
    # read incomplete: the reviewer already adjudicated that it carries no
    # record, so counting it as unread would report a defect that does not
    # exist. ``is_complete`` therefore keys on ``unread_record_sheets``, and the
    # genuinely-partial property is proved on its own specimen below.
    assert all(skipped.declared_non_record for skipped in extraction.skipped)
    assert not extraction.unread_record_sheets
    assert extraction.is_complete is True


def test_a_design_with_an_undeclared_hole_reports_the_read_as_partial(tmp_path: Path) -> None:
    """A genuinely partial read must SAY it is partial -- the other half of the proof.

    Built SYNTHETICALLY rather than pinned to whichever bundled design happens
    to be partial today. Pinning it would encode a live defect as this test's
    contract: the specimen goes green the moment someone legitimately fixes that
    design, and the property this test exists for would stop being checked
    without anyone noticing. Modelo 840 was exactly that -- partial when this
    was written and complete an hour later.

    TWO records, deliberately: the first reads cleanly and the second declares
    positions 1-12 while printing no row for 6-10. A holed record is moved
    WHOLLY to ``skipped`` rather than kept as a half-read sheet, so a
    single-record specimen would leave ``sheets`` empty and prove a refusal
    instead of the partial read this asserts.
    """
    pdf_path = tmp_path / "holed-record-design.pdf"
    _write_pdf_lines(
        pdf_path,
        (
            "Pág 1 DISEÑO DE REGISTRO 01/12/2003",
            "Nº Posic. Lon Tipo Descripción Validación Contenido",
            "1 1 3 An Inicio del identificador de modelo.",
            "2 4 2 Num Ejercicio.",
            "3 6 5 An Nombre.",
            "4 11 2 An Salto de línea. Constante CRLF.",
            "Pág 2 DISEÑO DE REGISTRO 01/12/2003",
            "Nº Posic. Lon Tipo Descripción Validación Contenido",
            "1 1 3 An Inicio del identificador de modelo.",
            "2 4 2 Num Ejercicio.",
            "3 11 2 An Salto de línea. Constante CRLF.",
        ),
    )

    extraction = extract_record_design_pdf(pdf_path)

    assert extraction.sheets, "some rows do parse, so this is a PARTIAL read rather than a refusal"
    assert extraction.unread_record_sheets, "the holed record must be named, not silently dropped"
    assert extraction.is_complete is False
    reason = extraction.skipped[0].reason
    assert "6-10" in reason, reason
    assert not extraction.skipped[0].declared_non_record


def test_a_second_recognised_header_shape_is_read_and_a_non_matching_sheet_still_skips() -> None:
    """AEAT's real second header shape is read; a sheet matching neither shape still refuses.

    Modelo 151's nine annex sheets (``M15100000``, ``M15102000``-``M15109000``)
    title their description column with the sheet's own topical caption instead
    of the literal ``Descripción``, and carry no ``Validación`` column at all --
    a real published AEAT shape, not a parser defect. Resilience to it is
    permitted precisely because it is matched as specifically as the ordinary
    shape (``Com.`` present by its own recognised alias AND the very next
    column non-blank), never by relaxing the ordinary shape's own token match.

    Both directions are asserted: the nine sheets read with correct geometry
    (spot-checked against the raw workbook, not just "it parsed"), AND a sheet
    matching NEITHER shape -- no ``Descripción``, no ``Com.`` -- still skips.
    """
    design = _RECORD_DESIGN_ROOT / "modelo_151" / "files" / "01-151-ejercicio-2023-y-siguientes.xls"
    assert design.is_file(), f"corpus anchor moved: {design}"
    extraction = extract_record_design(design)

    annex_sheet_names = {f"M1510{n}000" for n in range(2, 10)} | {"M15100000"}
    read_names = {sheet.name for sheet in extraction.sheets}
    assert annex_sheet_names <= read_names, f"still skipped: {annex_sheet_names - read_names}"

    # Spot-check exact geometry against the raw workbook (row 6, sheet M15102000):
    # ``38.0, 480.0, 1.0, 'Num', 'Datos Adicionales...Situación [13]'`` verified directly.
    m15102000 = next(sheet for sheet in extraction.sheets if sheet.name == "M15102000")
    first = m15102000.fields[0]
    assert (first.ordinal, first.offset, first.length, first.type_code) == ("1", 1, 2, "An")
    assert "Inicio del identificador de modelo y p" in (first.description or "")
    last = m15102000.fields[-1]
    assert (last.offset, last.length, last.type_code) == (1089, 12, "An")
    assert last.description == "Indicador de fin de registro"

    # Negative case: a header row with NEITHER "Descripcion" NOR "Com." must still refuse,
    # proving Shape B did not widen the match rather than add a second one.
    no_shape_match = record_design_headers_module._probe_header_row(
        ("Nº", "Posic.", "Lon", "Tipo", "Contenido"),
        1,
        label="test",
        sheet_name="test",
        header_corrections={},
    )
    assert no_shape_match is None, "a header with no description column and no 'Com.' column must not match"

    # Negative case: "Com." present but the following column is blank -- no caption to
    # treat as the description -- must also still refuse.
    blank_caption = record_design_headers_module._probe_header_row(
        ("Nº", "Posic.", "Lon", "Tipo", "Com.", None, "Contenido"),
        1,
        label="test",
        sheet_name="test",
        header_corrections={},
    )
    assert blank_caption is None, "a 'Com.' column followed by a blank cell must not match Shape B"


def test_a_declared_header_cell_correction_is_read_and_an_undeclared_blank_column_still_refuses() -> None:
    """A declared header correction recovers a design; an undeclared one still skips.

    Modelo 100's ``100-03`` sheet (2015 and 2016 editions, both containers) is
    the live case: AEAT's own length-column header cell is a whitespace-only
    string, not the literal word ``Long.``/``Lon`` -- confirmed by cross-year
    comparison against the 2017 edition's identical cell. The correction fires
    ONLY because a sidecar declares it for this exact sheet, row and column;
    without one, the same blank cell must still refuse (proven with a
    synthetic row carrying no declared correction).
    """
    design = _RECORD_DESIGN_ROOT / "modelo_100" / "files" / "20-100-ejercicio-2015-1-75-mb-xls.xls"
    assert design.is_file(), f"corpus anchor moved: {design}"
    extraction = extract_record_design(design)

    assert not extraction.skipped, f"still skipped: {[item.name for item in extraction.skipped]}"
    header_corrections = [c for c in extraction.corrections if c.kind == "header_cell"]
    assert len(header_corrections) == 1
    correction = header_corrections[0]
    assert (correction.sheet, correction.header_row, correction.column_index, correction.column_role) == (
        "100-03",
        5,
        2,
        "length",
    )

    # Spot-check exact geometry against the raw workbook, sheet 100-03:
    sheet = next(item for item in extraction.sheets if item.name == "100-03")
    assert len(sheet.fields) == 54
    first = sheet.fields[0]
    assert (first.ordinal, first.offset, first.length, first.type_code) == ("1", 1, 2, "An")
    assert first.description == "Inicio del identificador de modelo y página."
    last = sheet.fields[-1]
    assert (last.ordinal, last.offset, last.length, last.type_code) == ("54", 630, 2, "An")

    # Negative case: the identical blank-length-column shape with NO declared correction
    # must still refuse -- proving the sidecar is load-bearing, not a fallback default.
    undeclared = record_design_headers_module._probe_header_row(
        ("Nº", "Posic.", "", "Tipo", "Descripción", "Validación", "Contenido"),
        5,
        label="test",
        sheet_name="100-03",
        header_corrections={},
    )
    assert undeclared is None, "a blank length-column cell with no declared correction must not match"


def test_a_design_read_in_full_reports_complete_and_hands_over_its_sheets() -> None:
    """The other half, and the one that matters more.

    2,458 of the corpus's 2,803 workbook sheets read cleanly today. If completeness
    reporting were wrong in the permissive direction it would be caught by the test
    above; wrong in the strict direction it would make every complete design refuse,
    which is the more expensive failure and the easier one to ship unnoticed.
    """
    design = scan_directory(
        _RECORD_DESIGN_ROOT / "modelo_115" / "files", pattern="*.xls", select=DirectoryEntryKind.FILES
    )[0]
    extraction = extract_record_design(design)

    assert extraction.skipped == ()
    assert extraction.is_complete is True
    assert extraction.require_complete() == extraction.sheets
    assert extraction.require_complete() == extraction.accept_partial()


def test_every_sheet_of_a_source_is_either_read_or_named_as_skipped() -> None:
    """Nothing may fall between the two lists -- the anti-vacuity guard.

    A completeness notion that under-counts the container is worse than none: it
    reports ``is_complete`` on a design whose sheets it never enumerated. This
    reads the container's OWN sheet listing, independently of the extractor, and
    requires every sheet to appear on exactly one side of the result.
    """
    from openpyxl import load_workbook

    design = scan_directory(
        _RECORD_DESIGN_ROOT / "modelo_232" / "files", pattern="*.xlsx", select=DirectoryEntryKind.FILES
    )[0]
    workbook = load_workbook(design, read_only=True, data_only=True)
    try:
        present = {worksheet.title.strip() for worksheet in workbook.worksheets}
    finally:
        workbook.close()

    extraction = extract_record_design(design)
    accounted = {sheet.name for sheet in extraction.sheets} | {item.name for item in extraction.skipped}

    assert accounted == present, (
        "every sheet the container holds must be either read or named as skipped; "
        f"unaccounted: {sorted(present - accounted)}, invented: {sorted(accounted - present)}"
    )


def test_a_truncated_header_spelling_names_the_same_column() -> None:
    """``Lon``, ``Lon.``, ``Long.`` and ``Longitud`` are one column, not four.

    The unit half of the truncation rule. Pinned on the RELATION rather than on a
    list of accepted spellings: a test naming the spellings would be satisfied by
    an enrolled set, which is the design this replaced and which went silent again
    the moment AEAT wrote a spelling nobody had enrolled.
    """
    for spelling in ("lon", "lon.", "long", "long.", "longitud"):
        assert record_design_headers_module._optional_header_index((spelling,), "lon") == 0, spelling

    # The floor: a token under three characters may not prefix-match a column.
    assert record_design_headers_module._optional_header_index(("n",), "no") is None
    assert record_design_headers_module._optional_header_index(("lo",), "lon") is None
    # And an unrelated column is still not matched, however long it is.
    assert record_design_headers_module._optional_header_index(("contenido",), "lon") is None
    assert record_design_headers_module._optional_header_index(("descripcion",), "tipo") is None


def test_the_truncation_rule_recovers_a_sheet_that_was_silently_dropped() -> None:
    """Modelo 714 spells its length column two ways and lost a sheet to it.

    The corpus half. Eleven body sheets head the column ``Lon`` and the twelfth
    heads it ``Long.``, so that sheet failed header detection and was dropped --
    silently, because eleven others survived. This asserts the design now reads
    COMPLETE, which is the property; the sheet count is checked as "more than the
    survivors" rather than pinned, so a republished design cannot make it vacuous.
    """
    design = _RECORD_DESIGN_ROOT / "modelo_714" / "files" / "DR714_2025.xls"
    assert design.is_file(), f"corpus anchor moved: {design}"

    extraction = extract_record_design(design)

    assert extraction.is_complete, (
        f"Modelo 714 still drops {[item.name for item in extraction.skipped]}; the length column "
        "on its header sheet is spelled 'Long.' where its body sheets spell it 'Lon'"
    )
    assert len(extraction.sheets) > 11


def test_a_declared_end_of_record_terminator_is_separated_and_kept() -> None:
    """The closing identifies the record; the CRLF row ends the line.

    Thirty bundled designs across eight modelos declare both as adjacent
    relative-offset rows, and the closing recogniser -- which accepted one suffix of
    length 18 or exactly six -- refused every one. They were not exotic: each is the
    ordinary 18-byte identifier followed by a row AEAT labels ``Fin de Registro.
    Constante CRLF``.

    The assertion that matters is the second one. Separating the terminator makes
    them parse; KEEPING it is what stops that being a clean-looking wrong answer,
    because those two bytes are part of the record and a parse that drops them
    understates every record built from it.
    """
    design = _RECORD_DESIGN_ROOT / "modelo_100" / "files" / "20-100-ejercicio-2015-1-75-mb-xls.xls"
    assert design.is_file(), f"corpus anchor moved: {design}"

    envelopes = [sheet.variable_envelope for sheet in extract_record_design(design).accept_partial()]
    envelope = next(item for item in envelopes if item is not None)

    assert isinstance(envelope.closing, RecordDesignRelativeSuffixMarker)
    assert envelope.closing.length == 18, "the closing identifier must remain the closing identifier"
    assert envelope.terminator is not None, (
        "the end-of-record row was consumed instead of kept; its two bytes are part of the record"
    )
    assert envelope.terminator.length == 2
    assert "fin de registro" in envelope.terminator.description.casefold()


def test_a_two_byte_closing_part_that_is_not_a_terminator_is_not_peeled() -> None:
    """The split matches the declared MEANING, never the length alone.

    A two-byte relative suffix is not automatically a line terminator -- the Modelo
    220 composite closing carries a two-byte ``0A`` part that is genuinely part of
    the record identifier. Peeling on width would silently truncate that closing and
    reclassify a real identifier component as physical padding.
    """
    from ..record_design_layout_markers import _split_record_terminator
    from ..record_design_schema import RecordDesignRelativeSuffixMarker

    def suffix(length: int, description: str, ordinal: int) -> RecordDesignRelativeSuffixMarker:
        return RecordDesignRelativeSuffixMarker(
            sheet="S",
            row=ordinal,
            ordinal=ordinal,
            offset="***",
            length=length,
            type_code="An",
            description=description,
        )

    identifier_part = suffix(2, "Periodo. Constante 0A", 2)
    kept, terminator = _split_record_terminator([suffix(18, "Constante. </T...>", 1), identifier_part])
    assert terminator is None, "a two-byte identifier component was mistaken for a line terminator"
    assert len(kept) == 2

    real = suffix(2, "Fin de Registro. Constante CRLF (Hexadecimal 0D0A)", 2)
    kept, terminator = _split_record_terminator([suffix(18, "Constante. </T...>", 1), real])
    assert terminator is real
    assert len(kept) == 1


def test_a_terminator_that_does_not_come_last_is_refused() -> None:
    """A terminator that is not last is not a terminator.

    Without this the split would accept a line-terminator row appearing anywhere in
    the closing and quietly reorder the record's tail. Refusing is right: a design
    declaring it early is either malformed or has been misread, and rearranging it
    would hide both.
    """
    from ..record_design_schema import RecordDesignRelativeSuffixMarker
    from ..record_design_workbook import _require_terminator_closes_the_record

    def suffix(ordinal: int, length: int, description: str) -> RecordDesignRelativeSuffixMarker:
        return RecordDesignRelativeSuffixMarker(
            sheet="S",
            row=ordinal,
            ordinal=ordinal,
            offset="***",
            length=length,
            type_code="An",
            description=description,
        )

    closing = (suffix(9, 18, "Constante. </T...>"),)
    _require_terminator_closes_the_record("S", closing, suffix(10, 2, "Fin de Registro. CRLF"))
    with pytest.raises(RegistryValidationError, match="not last is not a terminator"):
        _require_terminator_closes_the_record("S", closing, suffix(8, 2, "Fin de Registro. CRLF"))


def test_a_design_declaring_no_terminator_does_not_acquire_one() -> None:
    """THE INVERSE FALSE GREEN: peeling is conditional on the row being declared.

    A design closing with a bare 18-byte identifier and no CRLF row must parse with
    no terminator and an unchanged record tail. If the split ever fired on the
    closing merely LOOKING like it wants a terminator, every such design would
    silently gain two bytes it does not have -- the same defect as dropping two
    bytes, with the sign reversed, and equally invisible.

    Modelo 303's current design is the anchor: it declares the same DP30300
    variable envelope as the older editions that DO carry a terminator, so the two
    differ in exactly the thing under test.
    """
    design = (
        _RECORD_DESIGN_ROOT
        / "modelo_303"
        / "files"
        / "01-303-ejercicio-2026-y-siguientes-actualizado-28-01-26-378-kb-xlsx.xlsx"
    )
    assert design.is_file(), f"corpus anchor moved: {design}"

    extraction = extract_record_design(design)
    assert extraction.is_complete
    envelope = next(sheet.variable_envelope for sheet in extraction.sheets if sheet.variable_envelope is not None)

    assert envelope.terminator is None, (
        "a design that declares no end-of-record row acquired one; peeling must be conditional "
        "on the row being present, never inferred from the closing's shape"
    )
    assert isinstance(envelope.closing, RecordDesignRelativeSuffixMarker)
    assert envelope.closing.length == 18


def test_the_workbook_and_pdf_parsers_share_one_notion_of_a_crlf_row() -> None:
    """One concept, one home -- the two parsers may not drift on the same fact.

    They already had. The PDF compact-row recogniser has known the end-of-record row
    since it was written; the workbook closing recogniser refused thirty designs
    across eight modelos for declaring one. Two private spellings of a single domain
    fact is what let that divergence stand, so the PDF pattern now composes the
    shared phrase rather than restating it.

    Asserted by composition, not by equality of behaviour: this fails if either side
    grows its own copy.
    """
    from ..record_design_layout_markers import _RECORD_TERMINATOR, _RECORD_TERMINATOR_PHRASE
    from ..record_design_pdf_rows import _COMPACT_PDF_CRLF_ROW_RE

    assert _RECORD_TERMINATOR_PHRASE in _COMPACT_PDF_CRLF_ROW_RE.pattern
    assert _RECORD_TERMINATOR.pattern == _RECORD_TERMINATOR_PHRASE

    # Every wording the shared phrase claims to cover must actually match, so a
    # dead alternative cannot hide behind a live one. The bare-CRLF spelling was
    # dead for exactly this reason before this test existed.
    for wording in ("Fin de Registro. Constante CRLF", "Salto de linea. CRLF", "Salto de línea. CRLF"):
        assert _RECORD_TERMINATOR.search(wording), wording
    assert not _RECORD_TERMINATOR.search("Periodo. Constante 0A")


def test_envelope_composition_order_is_checked_by_source_position_not_by_ordinal() -> None:
    """Removing the ordinal comparison must not remove the coverage it appeared to give.

    The envelope-order check asserted composition order twice, on source row and on
    ordinal, and the ordinal half asserted nothing the row half did not. Deleting a
    redundant assertion is only safe if the survivor still bites, so every
    misordering the pair used to catch is exercised here against the row check
    alone.

    Why the ordinal half had to go rather than be made string-safe: AEAT's ordinal
    is a PRINTED LABEL, not an arithmetic value -- it publishes ``14bis`` to insert
    a field between 14 and 15 without renumbering. Ordering by it assumes a density
    the authority never promised, and a string ordering would place ``2`` after
    ``10`` by construction.
    """
    from ..record_design_schema import (
        RecordDesignField,
        RecordDesignRelativeSuffixMarker,
        RecordDesignVariableBodyMarker,
        RecordDesignVariableTotalMarker,
    )
    from ..record_design_workbook import _require_ordered_variable_envelope

    def field(row: int) -> RecordDesignField:
        return RecordDesignField(sheet="S", row=row, ordinal="1", offset=1, length=1, type_code="An", description="d")

    def body(row: int) -> RecordDesignVariableBodyMarker:
        return RecordDesignVariableBodyMarker(
            sheet="S", row=row, ordinal=2, offset=2, length="Variable", type_code="An", description="d"
        )

    def closing(row: int) -> RecordDesignRelativeSuffixMarker:
        return RecordDesignRelativeSuffixMarker(
            sheet="S", row=row, ordinal=3, offset="***", length=18, type_code="An", description="d"
        )

    def total(row: int) -> RecordDesignVariableTotalMarker:
        return RecordDesignVariableTotalMarker(sheet="S", row=row, label="total", length="Variable")

    _require_ordered_variable_envelope("S", [field(10)], body(11), (closing(12),), total(13))

    for label, args in (
        ("body before the fixed prefix", ([field(11)], body(10), (closing(12),), total(13))),
        ("closing before the body", ([field(10)], body(12), (closing(11),), total(13))),
        ("total before the closing", ([field(10)], body(11), (closing(12),), total(11))),
    ):
        with pytest.raises(RegistryValidationError, match="misordered variable-envelope"):
            _require_ordered_variable_envelope("S", *args)
            pytest.fail(f"{label} was accepted; the row check does not cover it")
