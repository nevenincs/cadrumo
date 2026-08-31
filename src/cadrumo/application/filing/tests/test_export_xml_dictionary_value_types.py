"""Rendered XML-dictionary values satisfy the type AEAT's XSD declares for them.

The dictionary row's declared type, not the Python type of the value, decides how
a value is rendered. Deciding from the value alone cannot tell two rows apart that
carry the same Python type but are declared differently: a boolean row is
``tipo_logico`` (``([0-1]){1}``) in most of the tree but ``tipo_SINO_Exclusivo``
(``SI``/``NO``) in a handful of places, and a numeric row is an ``xs:integer`` for
some type codes and an ``xs:decimal`` carrying ``fractionDigits="2"`` for others.

Expected tokens are never written by hand here. Each assertion reads the facets the
bundled official AEAT XSD declares for that element or attribute and checks the
rendered value against them, so the oracle is AEAT's schema rather than a
restatement of the code under test.

Checking one field at a time is the stronger instrument here, not a weaker stand-in
for validating a whole exported document. A schema validator stops a sequence at its
first error, and an exported declaration currently fails on a mandatory element the
dictionary cannot supply, so validating the document as a whole never reaches a
single rendered value. Per-field checking is also independent of how much of a draft
happens to be populated, which document validation is not.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....core.resources.bundled_data import bundled_path
from ....domain.filing.errors import FilingExportValidationError
from .._export_xml_dictionary import _format_xml_dictionary_value

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_XSD_NS = "{http://www.w3.org/2001/XMLSchema}"
_MODELO_100_2024_XSD = "29-100-esquema-xsd-ejercicio-2024-actualizado-19-01-2026-747-kb-ejecutable.xsd"


def _xsd_root() -> Element[str]:
    xsd = bundled_path(
        "corpus",
        "aeat_official",
        "disenos_registro",
        "modelo_100",
        "files",
        _MODELO_100_2024_XSD,
    )
    root = DefusedElementTree.parse(Path(xsd)).getroot()
    assert root is not None
    return root


def _simple_type(type_name: str) -> Element[str]:
    for simple_type in _xsd_root().iter(f"{_XSD_NS}simpleType"):
        if simple_type.attrib.get("name") == type_name:
            return simple_type
    pytest.fail(f"bundled Modelo 100 XSD declares no simpleType named {type_name!r}")


def _accepts(type_name: str, value: str) -> bool:
    """Whether AEAT's XSD type ``type_name`` accepts the rendered ``value``.

    Reads the enumeration, pattern, and base facets the schema declares. The
    numeric bases are checked for representability rather than range, which is
    what the rendering decision turns on.
    """
    simple_type = _simple_type(type_name)
    enumerations = {
        node.attrib["value"] for node in simple_type.iter(f"{_XSD_NS}enumeration") if "value" in node.attrib
    }
    if enumerations:
        return value in enumerations
    patterns = [node.attrib["value"] for node in simple_type.iter(f"{_XSD_NS}pattern") if "value" in node.attrib]
    if patterns:
        return any(re.fullmatch(pattern, value) is not None for pattern in patterns)
    bases = {node.attrib.get("base") for node in simple_type.iter(f"{_XSD_NS}restriction")}
    if "xs:integer" in bases:
        return re.fullmatch(r"-?\d+", value) is not None
    if "xs:decimal" in bases:
        return re.fullmatch(r"-?\d+(\.\d+)?", value) is not None
    pytest.fail(f"bundled XSD type {type_name!r} declares no facet this oracle understands")
    return False


def test_the_xsd_oracle_rejects_what_it_should_accept_nothing_of() -> None:
    """The oracle discriminates, so a passing assertion below means something.

    Without this, an oracle that accepted everything would make every other test
    in this module vacuous.
    """
    assert _accepts("tipo_logico", "1")
    assert not _accepts("tipo_logico", "S")
    assert _accepts("tipo_SINO_Exclusivo", "SI")
    assert not _accepts("tipo_SINO_Exclusivo", "S")
    assert _accepts("tipo_Integer1a366", "365")
    assert not _accepts("tipo_Integer1a366", "365.00")
    assert _accepts("tipo_ImpPositivo", "12000.25")


@pytest.mark.parametrize(
    ("dictionary_type", "xsd_type"),
    [
        ("LGC", "tipo_logico"),
        ("S_N", "tipo_SINO_Exclusivo"),
    ],
)
def test_boolean_rows_render_the_token_their_declared_type_accepts(
    dictionary_type: str,
    xsd_type: str,
) -> None:
    for value in (True, False):
        rendered = _format_xml_dictionary_value(dictionary_type, value)
        assert _accepts(xsd_type, rendered), (
            f"{dictionary_type} row rendered {rendered!r} for {value!r}, which {xsd_type} rejects"
        )
    assert _format_xml_dictionary_value("LGC", True) != _format_xml_dictionary_value("LGC", False)
    assert _format_xml_dictionary_value("S_N", True) != _format_xml_dictionary_value("S_N", False)


@pytest.mark.parametrize(
    ("dictionary_type", "xsd_type"),
    [
        ("P010", "tipo_Integer1a9"),
        ("P020", "tipo_Integer020"),
        ("P030", "tipo_Integer1a366"),
        ("P040", "tipo_Integer1a9999"),
    ],
)
def test_integer_rows_render_without_fractional_digits(dictionary_type: str, xsd_type: str) -> None:
    rendered = _format_xml_dictionary_value(dictionary_type, Decimal("3"))

    assert _accepts(xsd_type, rendered), f"{dictionary_type} rendered {rendered!r}, which {xsd_type} rejects"
    assert "." not in rendered


@pytest.mark.parametrize(
    ("dictionary_type", "xsd_type"),
    [
        ("P012", "tipo_Decimal012"),
        ("P032", "tipo_Porcentaje"),
        ("P072", "tipo_Decimal072"),
        ("P102", "tipo_ImpPositivo"),
        ("N102", "tipo_ImpNegativo"),
    ],
)
def test_two_decimal_rows_keep_their_two_decimals(dictionary_type: str, xsd_type: str) -> None:
    rendered = _format_xml_dictionary_value(dictionary_type, Decimal("1.5"))

    assert rendered == "1.50"
    assert _accepts(xsd_type, rendered)


def test_the_scale_is_read_off_the_type_code_rather_than_enumerated() -> None:
    """A type code this module never names still renders at its declared scale.

    The dictionary's numeric codes carry their own fractional-digit count in the
    trailing digit, so a code AEAT adds later is rendered correctly without the
    renderer being edited. Asserting that here keeps the property from being
    quietly replaced by a lookup table over today's codes.
    """
    assert _format_xml_dictionary_value("P083", Decimal("1.2394")) == "1.239"
    assert _format_xml_dictionary_value("P060", Decimal("1.6")) == "2"


def test_a_non_numeric_row_is_left_alone() -> None:
    assert _format_xml_dictionary_value("X", "12345678Z") == "12345678Z"
    assert _format_xml_dictionary_value("TIT", Decimal("2")) == "2"


def test_a_numeric_row_refuses_an_amount_it_cannot_read() -> None:
    """An unreadable amount refuses rather than rendering as zero.

    The renderer previously coerced with ``default=Decimal("0")``, so a value it
    could not read became ``0.00`` on the filed artefact. ``0.00`` satisfies the
    XSD for a ``P102`` row, so neither the schema nor any downstream check could
    have caught it: a taxpayer's figure would have been declared to AEAT as
    nothing, silently.

    The Spanish shape is the case that matters. ``1.234,56`` cannot be told from a
    three-decimal figure by any parser, which is why the operator-facing amount
    grammar already refuses it rather than guessing -- this aligns the write side
    with the decision the read side and the CLI option grammar both enforce.
    """
    for unreadable in ("1.234,56", "-1.234,56", "abc", ""):
        with pytest.raises(FilingExportValidationError, match="could not be read"):
            _format_xml_dictionary_value("P102", unreadable)


def test_the_refusal_does_not_reach_a_value_the_row_can_read() -> None:
    """Positive control: the refusal is not simply rejecting everything.

    Without this, a renderer that raised on every numeric row would satisfy the
    refusal test above while breaking every export.
    """
    assert _format_xml_dictionary_value("P102", Decimal("1234.56")) == "1234.56"
    assert _format_xml_dictionary_value("P102", "1234.56") == "1234.56"
    assert _format_xml_dictionary_value("P102", 0) == "0.00"
    assert _format_xml_dictionary_value("X", "1.234,56") == "1.234,56"


def test_a_text_amount_that_could_be_a_thousands_group_is_refused() -> None:
    """``1.000`` on a euro-cent row is ambiguous, so it refuses.

    That text is either one euro or one thousand, and no parser in the tree can
    tell -- ``coerce_decimal`` and ``parse_spanish_decimal`` both read it as one
    euro. Silently resolving it either way under-declares by a factor of 1000 or
    over-declares by the same, on a filed artefact. The canonical grammar's
    fractional-digit cap is a decision about an undecidable input, and this is
    the renderer applying it.
    """
    with pytest.raises(FilingExportValidationError, match="could not be read"):
        _format_xml_dictionary_value("P102", "1.000")


def test_the_cap_is_a_precision_rule_and_ambiguity_is_refused_separately() -> None:
    """Two independent refusals, and the row's scale relaxes only one of them.

    The CAP is precision and never falls below two: capping an integer row at
    its declared scale of zero would refuse ``1.6``, unambiguous input this
    renderer has always rounded.

    The AMBIGUITY guard is separate, and a row's declared scale does NOT relax
    it. This test previously asserted that ``1.000`` parses on a three-decimal
    row because such a row "reads it unambiguously". That premise is false: the
    scale disambiguates the FIELD, never the STRING. An operator writing one
    thousand types the same eight characters whatever the row declares, so the
    token stays two-way readable and refuses on ``P083`` exactly as on the
    euro-cent ``P102``. Resolving it either way would misstate a filed amount by
    a factor of one thousand.
    """
    assert _format_xml_dictionary_value("P060", "1.6") == "2"
    for data_type in ("P060", "P083", "P102"):
        with pytest.raises(FilingExportValidationError, match="could not be read"):
            _format_xml_dictionary_value(data_type, "1.000")


def test_the_ambiguity_guard_keys_on_shape_not_on_fraction_count() -> None:
    """The actual contract, which nothing previously stated.

    A token is refused when it could open a Spanish thousands run: a lead of one
    to three digits with no leading zero, then exactly three more. Tokens that
    carry their own evidence parse at the same scale -- a leading zero was never
    grouped, and a four-digit lead would itself have been grouped.

    Pinned because a pure fraction-digit cap would pass every assertion in the
    test above while silently refusing ``0.239`` and admitting nothing extra: it
    is the accepting half that distinguishes an ambiguity rule from a precision
    rule, and only these cases exercise it.
    """
    assert _format_xml_dictionary_value("P083", "0.239") == "0.239"
    assert _format_xml_dictionary_value("P083", "1234.239") == "1234.239"
    assert _format_xml_dictionary_value("P083", "1000.000") == "1000.000"
    for ambiguous in ("1.239", "123.000", "1.000"):
        with pytest.raises(FilingExportValidationError, match="could not be read"):
            _format_xml_dictionary_value("P083", ambiguous)


def test_an_already_typed_amount_skips_the_text_grammar() -> None:
    """A value that arrives typed carries no ambiguity to resolve.

    The grammar exists to read *text*. A ``Decimal`` or ``int`` already says
    what it is, so routing it through a text parser could only lose information.
    """
    assert _format_xml_dictionary_value("P102", Decimal("1.000")) == "1.00"
    assert _format_xml_dictionary_value("P102", 0) == "0.00"


def test_a_row_aeat_does_not_declare_boolean_refuses_a_boolean() -> None:
    """A boolean renders on the two boolean row types and nowhere else.

    The boolean branch is evaluated before every other, so it used to claim any
    row a boolean arrived on: ``True`` on a ``P102`` euro-cent row rendered ``1``,
    a plausible one-euro amount the XSD accepts, and on an ``X`` or ``FEC`` row it
    rendered ``1`` where AEAT expects text or a date. Both launder an upstream type
    error, and the amount case is the one that hides: nothing on the export path
    validates against the schema, and ``1`` would satisfy it anyway, so a taxpayer
    files a figure they never stated.

    The row types are enumerated here rather than derived, because deriving them
    from the same set the renderer consults would make this test agree with the
    code by construction. ``MOD`` and ``AAA`` are the codes the Modelo 100
    dictionary carries beyond the four asserted above.

    This is a guard rather than a live fix. No route measured today delivers a
    boolean here: the casilla input door refuses one for every declared family, and
    no Modelo 100 revision declares a boolean casilla on a non-boolean row. The
    guard exists so that a route added later fails loudly instead of filing a value.
    """
    for dictionary_type in ("P102", "N102", "P010", "P012", "X", "FEC", "TIT", "MOD", "AAA"):
        for value in (True, False):
            with pytest.raises(FilingExportValidationError, match="cannot carry the boolean"):
                _format_xml_dictionary_value(dictionary_type, value)


def test_the_boolean_refusal_spares_the_rows_declared_boolean() -> None:
    """Positive control: the two rows AEAT declares boolean still render.

    A guard that refused every boolean would satisfy the refusal test above while
    emptying the identity block of every declaration, and a guard that refused
    every value would satisfy it while breaking the whole export -- so both the
    boolean rows and a representative non-boolean value are asserted here. The
    rendered tokens are checked against the XSD facets rather than restated, so
    this stays an oracle test rather than a copy of the code.
    """
    for dictionary_type, xsd_type in (("LGC", "tipo_logico"), ("S_N", "tipo_SINO_Exclusivo")):
        for value in (True, False):
            rendered = _format_xml_dictionary_value(dictionary_type, value)
            assert _accepts(xsd_type, rendered), (
                f"{dictionary_type} row rendered {rendered!r} for {value!r}, which {xsd_type} rejects"
            )
    assert _format_xml_dictionary_value("P102", Decimal("1")) == "1.00"
    assert _format_xml_dictionary_value("X", "12345678Z") == "12345678Z"


def test_a_row_type_aeat_adds_later_refuses_a_boolean_by_default() -> None:
    """The claim list is positive, so an unlisted row type is refused, not rendered.

    This is the property that makes the guard survive AEAT extending its type
    table. A negative carve-out -- "numeric rows refuse" -- would leave a new code
    inheriting whatever the last branch did, which is how the defect existed in the
    first place. ``ZZZ`` stands for that future code and is deliberately not a type
    the dictionary declares today.
    """
    with pytest.raises(FilingExportValidationError, match="cannot carry the boolean"):
        _format_xml_dictionary_value("ZZZ", True)


def test_a_date_row_refuses_text_that_is_not_in_aeats_form() -> None:
    """An ISO date on a date row refuses rather than rendering verbatim.

    Reachable, unlike the boolean guard above, and measured end to end: all 42
    casillas addressing a ``FEC`` row in the 2024 revision declare the registry's
    GENERIC ``text`` family, whose validator is an identity -- it accepts
    ``1980-01-02``, ``not a date`` and ``''`` alike -- so an ISO date passes the
    input door untouched and lands here as a string.

    The renderer refuses instead of parsing. Reading ``03/04/2024`` would mean
    choosing between day-month and month-day with no basis for the choice, which
    is the same undecidable-input situation the amount grammar already refuses.

    This is a backstop, not the fix. The root cause is that those casillas
    declare ``text`` while the registry has a ``date`` family that no casilla in
    the tree uses; declaring it would route them through the typed channel and
    make this check unreachable again.
    """
    for unusable in ("1980-01-02", "02-01-1980", "1980/01/02", "2/1/80", "notadate", ""):
        with pytest.raises(FilingExportValidationError, match="not in the form AEAT accepts"):
            _format_xml_dictionary_value("FEC", unusable)


def test_a_date_row_accepts_the_form_aeat_declares() -> None:
    """Positive control: AEAT's own pattern decides what passes.

    A guard that refused every string would satisfy the refusal test above while
    breaking every correctly-supplied date, so the accepted forms are checked
    against the ``tipo_Fecha`` facet rather than against a restatement of the
    regex in the renderer. One- and two-digit day and month both pass because the
    facet allows both.
    """
    for usable in ("2/1/1980", "02/01/1980", "31/12/2024"):
        rendered = _format_xml_dictionary_value("FEC", usable)
        assert _accepts("tipo_Fecha", rendered), f"tipo_Fecha rejects {rendered!r}"
    assert _format_xml_dictionary_value("FEC", date(1980, 1, 2)) == "2/1/1980"
    assert _accepts("tipo_Fecha", _format_xml_dictionary_value("FEC", date(1980, 1, 2)))
