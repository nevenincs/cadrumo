"""A página constant that is a composite, and the design that proves the split.

Most designs write the page directly: modelo 200's ``001``, modelo 763's ``02``.
Modelo 390's 2015 edition writes a five-digit composite -- ``01000`` through
``08000`` -- where the leading digits are the page and the trailing ``000`` is a
sub-counter.

THE SPLIT IS NOT ASSUMED, and this was refused once before it was read. The
design cross-checks itself: its second record is headed ``Pag. 1 DISENO DE
REGISTRO`` by AEAT's own running header, needing no help from the recovery at
all, and that SAME record declares ``Constante "01000"`` and closes
``</T39001000>``. Page 1 and token 01000 are one record stated two ways, which
fixes the reading. The other seven records run 02000 to 08000 and name pages 2
to 8, colliding with nothing.

An earlier tick recorded this as ungroundable, reasoning that decomposing
``01000`` to page 1 would collide with the header-derived ``Pag. 1`` and that
the collision showed the two schemes were different. The collision was real and
the inference backwards: they collide because they name the same record, which
is the corroboration rather than the objection.

A five-digit token that does NOT carry the sub-counter is left whole, because
nothing here says how to split it.
"""

from __future__ import annotations

import pytest

from .. import extract_record_design
from .. import RecordDesignField, RecordDesignSheet
from .._record_design import _page_label_from_token, _recovered_record_identity
from .test_every_bundled_design_is_read_or_reported import _bundled_designs

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(("token", "page"), [("01000", "1"), ("02000", "2"), ("08000", "8")])
def test_a_composite_token_yields_its_leading_page(token: str, page: str) -> None:
    assert _page_label_from_token(token) == page


@pytest.mark.parametrize(("token", "page"), [("001", "1"), ("014", "14"), ("02", "2")])
def test_a_plain_token_is_read_as_written(token: str, page: str) -> None:
    assert _page_label_from_token(token) == page


def test_a_five_digit_token_without_the_sub_counter_is_left_whole() -> None:
    """Nothing in the corpus says how to split this, so it is not split."""
    assert _page_label_from_token("01234") == "1234"


def test_the_bundled_modelo_390_design_names_its_eight_page_records() -> None:
    """The real corpus case: seven of these were anonymous before the split."""
    matches = [path for path in _bundled_designs() if path.name.startswith("08-390-ejercicio-2015")]
    assert matches, "the bundled modelo 390 2015 design is no longer in the corpus"

    extraction = extract_record_design(matches[0])
    named = {sheet.name for sheet in (*extraction.sheets, *extraction.skipped)}

    for page in range(1, 9):
        assert f"P\u00e1g. {page}" in named, sorted(named)


def _field(offset: int, length: int, description: str) -> RecordDesignField:
    return RecordDesignField(
        sheet="body", row=offset, offset=offset, length=length,
        type_code="An", description=description,
    )


def test_a_truncated_closing_identifier_defers_to_the_pagina_field() -> None:
    """Modelo 390's seventh record closes with a digit missing.

    ``</T3900700>`` carries seven digits where its siblings carry eight, so read
    on its own it names page 700. The Página field declares its component is
    five wide and reads ``07000``; that width contradiction is what exposes the
    loss, and only then is the identifier set aside.
    """
    sheet = RecordDesignSheet(
        name="<unidentified>",
        fields=(
            _field(3, 3, 'Modelo. Constante "390"'),
            _field(6, 5, 'Pagina. Constante "07000"'),
            _field(900, 9, 'Identificador de fin. Constante "</T3900700>"'),
        ),
    )

    assert _recovered_record_identity(sheet) == "Pág. 7"


def test_a_disagreement_without_a_width_contradiction_keeps_the_identifier() -> None:
    """Both are the same width, so nothing says which side is corrupt.

    Modelo 200's 2014 edition has one record whose constant reads ``060`` while
    its identifier reads ``200070``. Four of its five sibling records agree
    across both, so this is a single corruption -- but the design does not say
    on which side, and preferring the constant here would rename a record that
    has read the same way all along.
    """
    sheet = RecordDesignSheet(
        name="<unidentified>",
        fields=(
            _field(3, 3, 'Modelo. Constante "200"'),
            _field(6, 3, 'Pagina. Constante "060"'),
            _field(900, 9, 'Identificador de fin. Constante "</T200070>"'),
        ),
    )

    assert _recovered_record_identity(sheet) == "Pág. 70"


def test_an_alphabetic_page_token_is_the_label_itself() -> None:
    """Modelo 200 gives one record a page that is not a number.

    ``Constante "DID"``, closing ``</T200DID>``, and the design's own vector
    example lists it in the page sequence beside the numbered records
    (``...017018019019DIDFIN``). There is nothing to derive, so the token is the
    label.
    """
    assert _page_label_from_token("DID") == "DID"


def test_an_alphabetic_page_is_taken_only_from_the_pagina_field() -> None:
    """The closing identifier is matched anywhere in a field's text.

    ``</T200DID>`` appears in prose inside other records of the same design, and
    reading it there named a 1,618-field record after the token belonging to a
    45-field one. An alphabetic page is therefore accepted only where geometry
    anchors it -- the Página field at position 6, beside the modelo constant.
    """
    sheet = RecordDesignSheet(
        name="<unidentified>",
        fields=(
            _field(3, 3, 'Modelo. Constante "200"'),
            _field(6, 3, 'Pagina. Constante "520"'),
            _field(900, 10, 'Identificador de fin. Constante "</T200DID>"'),
        ),
    )

    assert _recovered_record_identity(sheet) == "Pág. 520"
