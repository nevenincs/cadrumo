"""An unheaded PDF record body is named from the identity it declares about itself.

Some AEAT designs head no record with a title. Modelo 200's 2010 orden edition
publishes eleven page records separated only by a running page header, so the
heading recogniser saw nothing and every body arrived anonymous: the whole
design read as ZERO sheets and forty-four skips.

The identity was in the document the entire time. AEAT fixes each page record's
Página constant at positions 6-8, immediately after the modelo constant at 3-5,
and requires the record's last field to carry a ``</T200006>`` closing
identifier. Both are declared REQUIRED CONTENT, not prose, which is what makes
reading them recovery rather than guesswork.

Two properties keep that from becoming invention, and both are pinned below: a
body that declares NEITHER identity stays anonymous, and two bodies resolving to
one name both stay anonymous rather than one silently absorbing the other.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.record_design import RecordDesignField, RecordDesignSheet, extract_record_design
from ..record_design import (
    _PdfParseState,
    _PdfSheetResult,
    _recovered_record_identity,
)
from .test_every_bundled_design_is_read_or_reported import _bundled_designs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _field(offset: int, length: int, description: str, *, content: str | None = None) -> RecordDesignField:
    return RecordDesignField(
        sheet="body",
        row=offset,
        offset=offset,
        length=length,
        type_code="An",
        description=description,
        content=content,
    )


def _sheet(*fields: RecordDesignField) -> RecordDesignSheet:
    return RecordDesignSheet(name="<unidentified>", fields=fields)


def test_the_closing_identifier_names_the_page() -> None:
    sheet = _sheet(
        _field(1, 2, 'Inicio del identificador. Constante "<T"'),
        _field(742, 10, 'Identificador de fin de registro OBLIGATORIO Constante "</T200006>"'),
    )

    assert _recovered_record_identity(sheet) == "Pág. 6"


def test_the_page_constant_is_read_from_geometry_not_from_the_spanish_label() -> None:
    """The label arrives as ``P?gina`` when the PDF text layer does not decode.

    This is the case that decides the whole strategy: a reader keyed on the word
    would work on the editions that decode cleanly and fail on the ones that do
    not. AEAT fixes the positions, so the positions are what this reads.
    """
    sheet = _sheet(
        _field(1, 2, 'Inicio del identificador de modelo y p\ufffdgina. Constante "<T"'),
        _field(3, 3, 'Modelo. OBLIGATORIO Constante "200"'),
        _field(6, 3, 'P\ufffdgina. OBLIGATORIO Constante "008"'),
    )

    assert _recovered_record_identity(sheet) == "Pág. 8"


def test_a_page_constant_without_the_modelo_constant_beside_it_is_not_enough() -> None:
    """One three-digit constant is not an identity claim; the pair is."""
    sheet = _sheet(
        _field(6, 3, 'Algo. Constante "008"'),
        _field(20, 5, "Importe"),
    )

    assert _recovered_record_identity(sheet) is None


def test_a_body_declaring_no_identity_stays_anonymous() -> None:
    sheet = _sheet(
        _field(1, 10, "Apellidos y nombre"),
        _field(11, 17, "Importe \u00edntegro"),
    )

    assert _recovered_record_identity(sheet) is None


def test_two_bodies_claiming_one_page_both_stay_anonymous() -> None:
    """A collision must not let one record silently absorb the other's identity.

    Naming both ``Pág. 3`` would merge two distinct records under one name, which
    is the exact failure the unidentified-body report exists to surface. Leaving
    both anonymous keeps them on the worklist where a reader can adjudicate.
    """
    state = _PdfParseState(source_label="collision.pdf")
    for index in (1, 2):
        body = RecordDesignSheet(
            name=f"<unidentified body {index}>",
            fields=(
                _field(3, 3, 'Modelo. Constante "200"'),
                _field(6, 3, 'Pagina. Constante "003"'),
            ),
        )
        state.results.append(_PdfSheetResult(sheet=body, identified=False, opened_at_row=index * 100))

    state._recover_unidentified_bodies()

    assert [result.identified for result in state.results] == [False, False]
    assert all(result.sheet.name.startswith("<unidentified") for result in state.results)


def test_the_bundled_modelo_200_orden_design_now_reads_named_page_records() -> None:
    """The real corpus case this recovery was built for, read end to end.

    Before the recovery this design produced ZERO sheets: every one of its page
    records was anonymous, so the whole document was reported unread.
    """
    matches = [path for path in _bundled_designs() if path.name.startswith("17-200-orden-eha-1338-2010")]
    assert matches, "the bundled modelo 200 2010 orden design is no longer in the corpus"

    extraction = extract_record_design(matches[0])
    names = [sheet.name for sheet in extraction.sheets]

    assert names, "no record body was read from a design whose pages all declare their identity"
    assert any(name.startswith("Pág. ") for name in names), (
        f"no page record was recovered by its declared identity; read {names}"
    )


def test_a_two_digit_page_constant_is_read_the_same_as_a_three_digit_one() -> None:
    """The page constant's WIDTH is not part of the evidence; its position is.

    Modelo 763, 202 and 210 write ``Constante "02"`` where modelo 200 writes
    ``Constante "001"``. Pinning three digits recognised the wide form only, and
    five designs kept a record nobody could name for want of a leading zero.
    """
    sheet = _sheet(
        _field(1, 2, 'Inicio del identificador de modelo y pagina. Constante "<T"'),
        _field(3, 3, 'Modelo Obligatorio Constante "763"'),
        _field(6, 2, 'P�gina Obligatorio Constante "02"'),
    )

    assert _recovered_record_identity(sheet) == "Pág. 2"


def test_a_page_constant_of_another_width_is_not_read_as_a_page() -> None:
    """Two or three digits is the observed range; a four-digit constant is something else."""
    sheet = _sheet(
        _field(3, 3, 'Modelo. Constante "200"'),
        _field(6, 4, 'Ejercicio. Constante "2011"'),
    )

    assert _recovered_record_identity(sheet) is None
