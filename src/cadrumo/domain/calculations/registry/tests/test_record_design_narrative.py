"""Tests for narrative record-design extraction and declared single-position corrections."""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from ..record_design import (
    extract_record_design,
)
from ..record_design_pdf_rows import unnamed_position_candidate
from ..record_design_schema import (
    RecordDesignSinglePositionCorrection,
)
from ._record_design_support import (
    _RECORD_DESIGN_ROOT,
    _write_pdf_lines,
    bundled_path,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_an_unnumbered_row_is_admitted_and_a_printed_label_is_admitted_verbatim() -> None:
    """The ordinal CELL decides, not the parse result -- both directions.

    AEAT leaves the ordinal blank for rows it declines to number: Modelo 036 writes
    one `Fecha de constitución` as three unnumbered rows for día, mes and año,
    sharing casilla ``[C71]``. Dropping them put their eight bytes into a downstream
    geometry gap whose message blamed the design.

    THE OTHER DIRECTION IS THE POINT THIS TEST NOW COVERS. ``ordinal`` is
    ``str | None`` precisely because AEAT's ordinal is a PRINTED LABEL, not an
    arithmetic value: Modelo 303 prints ``14bis`` beside its ``14`` to insert a
    field without renumbering. A ``14bis`` row is now admitted VERBATIM as its
    own peer field -- not absorbed into anything, not discarding the label -- and
    representable exactly as AEAT printed it, closing the gap the earlier,
    ``int``-typed ordinal could not represent.
    """
    root = _RECORD_DESIGN_ROOT
    unnumbered = (
        root / "modelo_036" / "files" / "04-036-ejercicio-2021-y-siguientes-actualizado-11-04-2023-106-kb-xlsx.xlsx"
    )
    printed_label = (
        root / "modelo_303" / "files" / "12-303-orden-hap-2373-2014-de-9-de-diciembre-ejercicio-2018-292-kb-xlsx.xlsx"
    )
    for path in (unnumbered, printed_label):
        assert path.is_file(), f"corpus anchor moved: {path}"

    extraction = extract_record_design(unnumbered)
    sheet = next(item for item in extraction.sheets if item.name == "Pag. 2C")
    unnumbered_fields = [item for item in sheet.fields if item.ordinal is None]
    assert unnumbered_fields, "the unnumbered rows are still being dropped"
    assert all("[C71]" in item.description for item in unnumbered_fields), (
        "the admitted unnumbered fields are not the shared-casilla group this covers"
    )
    # Their bytes are now part of the record rather than a phantom gap.
    assert {item.offset for item in unnumbered_fields} == {1294, 1296, 1298}

    # The other half: a row whose ordinal cell is NON-EMPTY is admitted verbatim as
    # its own peer field, `14bis` included -- no longer refused, and not absorbed
    # into `14` or `15` either (it is contiguous with, never nested inside, either).
    printed_extraction = extract_record_design(printed_label)
    printed_sheets = printed_extraction.require_complete()
    dp30303 = next(item for item in printed_sheets if item.name == "DP30303")
    fourteen = next(item for item in dp30303.fields if item.ordinal == "14")
    fourteen_bis = next(item for item in dp30303.fields if item.ordinal == "14bis")
    fifteen = next(item for item in dp30303.fields if item.ordinal == "15")
    assert fourteen_bis.components == ()
    assert "Reservado" in fourteen_bis.description
    # Contiguous with its neighbours, a genuine peer rather than a nested detail.
    assert fourteen.offset + fourteen.length == fourteen_bis.offset
    assert fourteen_bis.offset + fourteen_bis.length == fifteen.offset


def test_a_dotted_ordinal_is_absorbed_as_a_component_not_a_peer() -> None:
    """Modelo 576's ``19.1``..``19.8`` desglosa (break out) their parent's own span.

    THE DISCRIMINATOR IS CONJUNCTIVE, both conditions required together: a
    dotted ordinal's integer prefix must match the IMMEDIATELY PRECEDING field's
    own ordinal, AND its byte span must fall entirely inside that field's own
    already-declared offset/length. Neither condition alone is enough -- a
    coincidental prefix match elsewhere in the sheet must not absorb an
    unrelated field, and an in-span row with a non-matching prefix must not be
    silently swallowed either.

    ADDITIVE, NOT REPLACING: the parent's own ``offset``/``length`` continue to
    span the whole 40-byte group exactly as before components existed, so a
    consumer reading only ``offset``/``length`` -- the contiguity check, the IR
    projection -- sees exactly what it saw when these rows were still invisible.
    """
    root = _RECORD_DESIGN_ROOT
    path = root / "modelo_576" / "files" / "01-576-diseno-de-registro-vigente.xlsx"
    assert path.is_file(), f"corpus anchor moved: {path}"

    extraction = extract_record_design(path)
    sheets = extraction.require_complete()
    parent = next(item for sheet in sheets for item in sheet.fields if item.ordinal == "19")

    assert parent.offset == 514
    assert parent.length == 40
    assert [component.ordinal for component in parent.components] == [f"19.{n}" for n in range(1, 9)]
    # Zero remainder: the eight components exactly tile the parent's own span.
    assert parent.components[0].offset == parent.offset
    assert parent.components[-1].offset + parent.components[-1].length == parent.offset + parent.length
    for left, right in itertools.pairwise(parent.components):
        assert left.offset + left.length == right.offset, "components must themselves be contiguous"

    # A component is never counted as a top-level peer -- the outer sheet sees
    # only the parent at this position, exactly as before components existed.
    all_ordinals = [item.ordinal for sheet in sheets for item in sheet.fields]
    assert "19.1" not in all_ordinals


def _narrative_pdf(path: Path, rows: tuple[str, ...]) -> None:
    """Write a narrative-style AEAT record design with ``rows`` as its body."""
    _write_pdf_lines(
        path,
        (
            "Tipo de registro 1: Registro de Declarante",
            "POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS",
            *rows,
        ),
    )


def test_a_row_whose_naturaleza_aeat_omitted_fills_the_gap_it_leaves(tmp_path: Path) -> None:
    """A range-carrying row with no naturaleza is read when nothing else claims its span.

    AEAT prints the naturaleza between the range and the description on every
    ordinary row, and omits it occasionally. Refusing those outright left a hole,
    and a record read with a hole understates every coverage figure taken from it.
    """
    pdf_path = tmp_path / "gap.pdf"
    _narrative_pdf(
        pdf_path,
        (
            "1-4 Numérico EJERCICIO.",
            "5-8 CÓDIGO LEI DEL DECLARANTE",
            "9-12 Alfanumérico NIF.",
        ),
    )

    sheet = extract_record_design(pdf_path).sheets[0]
    admitted = [field for field in sheet.fields if field.offset == 5]

    assert [field.offset for field in sheet.fields] == [1, 5, 9]
    assert len(admitted) == 1
    assert admitted[0].length == 4
    assert admitted[0].type_code == "No consta"
    assert "CÓDIGO LEI" in admitted[0].description


def test_prose_restating_a_claimed_range_is_never_admitted_as_a_row(tmp_path: Path) -> None:
    """Mutation proof for the containment guard, the thing that makes the fill safe.

    AEAT routinely opens a field's DESCRIPTION with that field's own range, and 41
    bundled designs do it. Such a line is shaped exactly like the admitted row
    above; the ONLY thing separating them is that a prose line's range is already
    claimed by the field it describes. Remove the disjointness test in
    ``fill_unread_gaps`` and this record grows a duplicate field at position 5.
    """
    pdf_path = tmp_path / "prose.pdf"
    _narrative_pdf(
        pdf_path,
        (
            "1-4 Numérico EJERCICIO.",
            "5-8 Alfanumérico APELLIDOS Y NOMBRE.",
            "5-8 APELLIDOS Y NOMBRE: Se consignará el primer apellido.",
        ),
    )

    sheet = extract_record_design(pdf_path).sheets[0]

    assert [field.offset for field in sheet.fields] == [1, 5]
    assert not [field for field in sheet.fields if field.type_code == "No consta"]


def test_a_single_position_without_a_naturaleza_is_not_evidence_of_extent(tmp_path: Path) -> None:
    """Only an explicit range is admitted; a lone number is an ordinary sentence.

    ``5 Se consignará ...`` is indistinguishable from numbered prose, so admitting
    it would invent a one-byte field wherever a design happens to number a
    paragraph.
    """
    pdf_path = tmp_path / "single.pdf"
    _narrative_pdf(
        pdf_path,
        (
            "1-4 Numérico EJERCICIO.",
            "5 Se consignará lo indicado en el apartado anterior.",
            "6-9 Alfanumérico NIF.",
        ),
    )

    extraction = extract_record_design(pdf_path)

    # The hole at position 5 SURVIVES, and the record is refused for it. That is
    # the assertion: had the lone number been admitted the hole would have closed
    # and this design would read clean on an invented one-byte field.
    assert not extraction.sheets
    assert [skipped.name for skipped in extraction.skipped] == ["Tipo 1 - Registro De Declarante"]
    assert "5 were not read at all" in (extraction.skipped[0].reason or "")


def test_modelo_296_perceptor_record_reads_whole_after_the_gap_fill() -> None:
    """The bundled design this fill exists for now reads without a hole.

    Modelo 296 declares 500 positions on its perceptor record and read none of
    413-432, because AEAT printed ``413-432 CÓDIGO LEI DEL PERCEPTOR`` with no
    naturaleza while its neighbour ``433-452 Alfanumérico NIF EN EL PAÍS DE
    RESIDENCIA FISCAL`` carries one. The record was reported skipped entirely.
    """
    design = (
        bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_296", "files") / "01-296-ejercicio-2024.pdf"
    )

    sheets = {sheet.name: sheet for sheet in extract_record_design(design).sheets}
    perceptor = sheets["Tipo 2 - Registro De Perceptor"]
    lei = [field for field in perceptor.fields if field.offset == 413]

    assert len(lei) == 1
    assert lei[0].length == 20
    assert lei[0].type_code == "No consta"
    assert "LEI" in lei[0].description


def test_a_page_heading_abbreviated_with_a_period_is_recognised(tmp_path: Path) -> None:
    """``Pág. 2 DISEÑO DE REGISTRO`` heads a record exactly as ``Pág 2`` does.

    AEAT abbreviates the word both ways. Requiring whitespace straight after the
    stem matched only the period-less form, so a period-form heading was read as
    ordinary prose and the body under it became an unidentified record -- present
    in the file, absent from the read, and reported skipped.
    """
    pdf_path = tmp_path / "period.pdf"
    _write_pdf_lines(
        pdf_path,
        (
            "Pág. 1 DISEÑO DE REGISTRO 25/03/2021",
            "Nº Posic. Lon Tipo Descripción Validación Contenido",
            "1 1 3 An Inicio del identificador.",
            "2 4 2 Num Ejercicio.",
        ),
    )

    extraction = extract_record_design(pdf_path)

    assert [sheet.name for sheet in extraction.sheets] == ["Pág. 1"]
    assert not extraction.skipped


def test_modelo_360_reads_both_pages_after_the_period_form_heading(tmp_path: Path) -> None:
    """The bundled design this fix exists for now reads whole.

    Modelo 360 heads its second page ``Pág. 2 DISEÑO DE REGISTRO 25/03/2021``.
    Before the period form was recognised the design returned one unnamed sheet
    and reported the second body skipped; both pages are now named and read.
    """
    design = (
        bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_360", "files")
        / "01-360-orden-eha-789-2010.pdf"
    )

    extraction = extract_record_design(design)

    assert [sheet.name for sheet in extraction.sheets] == ["Pág. 1", "Pág. 2"]
    assert extraction.is_complete
    assert not extraction.skipped


def test_a_quoted_anexo_title_names_the_record_body_under_it(tmp_path: Path) -> None:
    """``ANEXO «TITLE»`` heads an annex record, which is a real AEAT shape.

    Modelo 296 heads the two anexos following its perceptor record this way. Read
    as prose, both bodies arrived unidentified and the design never read whole.
    """
    pdf_path = tmp_path / "anexo.pdf"
    _write_pdf_lines(
        pdf_path,
        (
            "Tipo de registro 1: Registro de Declarante",
            "POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS",
            "1-4 Numérico EJERCICIO.",
            "ANEXO «VALORES NEGOCIABLES. RELACIÓN DE PAGO»",
            "(Tipo de Hoja «A»)",
            "POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS",
            "1-4 Numérico EJERCICIO.",
        ),
    )

    extraction = extract_record_design(pdf_path)

    assert [sheet.name for sheet in extraction.sheets] == [
        "Tipo 1 - Registro De Declarante",
        "Anexo - Valores Negociables  Relación De Pago",
    ]
    assert not extraction.skipped


def test_a_prose_reference_to_a_numbered_anexo_names_no_record(tmp_path: Path) -> None:
    """Mutation proof: the opening quotation mark is what separates title from prose.

    AEAT refers to numbered annexes constantly ("... que figuran en el anexo II de
    la Orden EHA/3496/2011"). Drop the required quote from the pattern and such a
    line stages a record name, which geometry then attaches to the next body --
    renaming a record after an unrelated citation.
    """
    pdf_path = tmp_path / "prose_anexo.pdf"
    _write_pdf_lines(
        pdf_path,
        (
            "Tipo de registro 1: Registro de Declarante",
            "POSICIONES NATURALEZA DESCRIPCIÓN DE LOS CAMPOS",
            "1-4 Numérico EJERCICIO.",
            "ANEXO II DE LA ORDEN EHA/3496/2011, de 15 de diciembre.",
            "5-8 Alfanumérico NIF.",
        ),
    )

    extraction = extract_record_design(pdf_path)

    assert [sheet.name for sheet in extraction.sheets] == ["Tipo 1 - Registro De Declarante"]


def test_modelo_296_reads_all_five_record_bodies() -> None:
    """The bundled design reads whole: declarante, two perceptor records, two anexos.

    Before, it returned two sheets and reported three skips -- the perceptor
    record dropped for an unread span, and both anexos unidentified.
    """
    design = (
        bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_296", "files") / "01-296-ejercicio-2024.pdf"
    )

    extraction = extract_record_design(design)
    anexos = [sheet for sheet in extraction.sheets if sheet.name.startswith("Anexo - ")]

    assert extraction.is_complete
    assert not extraction.skipped
    assert len(extraction.sheets) == 5
    assert len(anexos) == 2


class TestSinglePositionCorrection:
    """A naturaleza-less single-position row is admitted only when declared.

    Modelo 280's declarante record is the live case: AEAT printed
    ``58 TIPO DE SOPORTE`` with no naturaleza and no range, at a page break,
    leaving position 58 the only byte of its declared 500 that no row covered.
    """

    @staticmethod
    def _declaration() -> RecordDesignSinglePositionCorrection:
        return RecordDesignSinglePositionCorrection(
            sheet="Tipo 1 - Registro De Declarante",
            position=58,
            corrected_type="Alfabético",
            description="TIPO DE SOPORTE",
            reason="AEAT omitted the naturaleza column at a page break; the continuation declares the single value 'T'.",
            editions_read=("DR_280_2022.pdf pages 4-5",),
        )

    def test_a_declared_single_position_row_is_admitted(self) -> None:
        index = {("Tipo 1 - Registro De Declarante", 58): self._declaration()}

        candidate = unnamed_position_candidate(
            "58 TIPO DE SOPORTE",
            1,
            sheet="Tipo 1 - Registro De Declarante",
            single_position_corrections=index,
        )

        assert candidate is not None
        assert (candidate.offset, candidate.length) == (58, 1)
        assert candidate.type_code == "Alfabético"
        assert candidate.description == "TIPO DE SOPORTE"

    def test_an_undeclared_single_position_row_is_still_refused(self) -> None:
        """The control: without this the declaration would be buying nothing."""
        assert (
            unnamed_position_candidate(
                "58 TIPO DE SOPORTE",
                1,
                sheet="Tipo 1 - Registro De Declarante",
                single_position_corrections={},
            )
            is None
        )

    def test_a_declaration_does_not_travel_to_another_sheet_or_position(self) -> None:
        """The key is ``(sheet, position)``; neither half may be assumed."""
        index = {("Tipo 1 - Registro De Declarante", 58): self._declaration()}

        assert (
            unnamed_position_candidate(
                "58 TIPO DE SOPORTE", 1, sheet="Tipo 2 - Registro De Declarado", single_position_corrections=index
            )
            is None
        )
        assert (
            unnamed_position_candidate(
                "59 TIPO DE SOPORTE", 1, sheet="Tipo 1 - Registro De Declarante", single_position_corrections=index
            )
            is None
        )

    def test_the_bundled_modelo_280_design_reads_complete_and_says_it_was_corrected(self) -> None:
        """Real binary, real sidecar: complete, and never passing as pristine."""
        extraction = extract_record_design(
            bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_280", "files", "DR_280_2022.pdf"),
        )

        assert extraction.is_complete
        assert not extraction.skipped
        declarante = next(sheet for sheet in extraction.sheets if sheet.name.startswith("Tipo 1"))
        corrected = next(field for field in declarante.fields if field.offset == 58)
        assert (corrected.length, corrected.type_code) == (1, "Alfabético")
        positions = []
        for correction in declarante.corrections:
            assert isinstance(correction, RecordDesignSinglePositionCorrection)
            positions.append(correction.position)
        assert positions == [58]
