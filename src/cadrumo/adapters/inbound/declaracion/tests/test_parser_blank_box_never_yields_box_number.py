"""A blank money box must extract as ABSENT, never as its own box number.

``named_label`` extraction captures the last whitespace-delimited token on the
matched line. On a real AEAT-rendered declaration a BLANK money box leaves its
own printed box number as that final token, and
:func:`~adapters.inbound.pdf.parse_spanish_decimal` is deliberately permissive
enough to read a bare integer, so the box number was being returned as the
declared amount.

The line shapes below are quoted verbatim from the AEAT Manual practico IVA
2024 Cap. 9 ANEXO (the four filled Modelo 303 declarations of ejercicio 2024),
which is an AEAT-rendered form rather than a generated fixture.

Recorded pre-fix behaviour, which these tests exist to keep from returning:

* ``"Cuotas a compensar de periodos anteriores aplicadas en este periodo
  ......... 78"`` (box 78 blank, in 2T, 3T and 4T) extracted as
  ``Decimal("78")`` - a compensation of 78,00 EUR applied against the quarter
  that the filing never declared, in the direction of under-paying.
* ``"En adquisiciones intracomunitarias de bienes y servicios corrientes
  .... 36 37"`` (boxes 36 and 37 both blank, in 4T) extracted casilla ``37`` as
  ``Decimal("37")``.

Both now classify as *missing* rather than *malformed*: a blank box is a box the
filing legitimately left empty, not a corrupt one, so the profile's coverage
threshold decides whether its absence is tolerable.

The generated corpus cannot exercise any of this - ``_generate.py`` prints an
explicit ``0,00`` into every box and prints no box numbers at all, so no
synthetic fixture can produce the blank-box input that breaks the parser.

See Also:
    :func:`~adapters.inbound.declaracion._parser._is_own_box_number_of_blank_box`
        The box-number guard these tests pin.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core import validated_casilla_id
from .....core.resources import resources
from cadrumo.domain.calculations.registry.schema import ExtractionTargetDefinition
from .._parser import _classify_target, _printed_box_numbers, _TargetClassification

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


# Verbatim from the ANEXO's "Pagina 3" Resultado block. In 1T the box carries a
# value; in 2T/3T/4T it is blank and the line ends on the box number itself.
_COMPENSACION_APLICADA_LABEL = r"Cuotas\s+a\s+compensar\s+de\s+periodos\s+anteriores\s+aplicadas\s+en\s+este\s+periodo"
_COMPENSACION_POPULATED_LINE = (
    "Cuotas a compensar de periodos anteriores aplicadas en este periodo ................. 78 3.000,00"
)
_COMPENSACION_BLANK_LINE = "Cuotas a compensar de periodos anteriores aplicadas en este periodo ................. 78"

# Verbatim from the ANEXO's form page 1 "IVA deducible" block: in 4T both the
# base box (36) and the cuota box (37) are blank.
_ADQUISICIONES_LABEL = r"En\s+adquisiciones\s+intracomunitarias\s+de\s+bienes\s+y\s+servicios\s+corrientes"
_ADQUISICIONES_POPULATED_LINE = (
    "En adquisiciones intracomunitarias de bienes y servicios corrientes ..... 36 21.000,00 37 4.410,00"
)
_ADQUISICIONES_BLANK_LINE = "En adquisiciones intracomunitarias de bienes y servicios corrientes ..... 36 37"

# The one money value AEAT prints without a decimal tail, from the same block.
_PENDIENTE_POSTERIORES_LABEL = (
    r"Cuotas\s+a\s+compensar\s+de\s+periodos\s+previos\s+pendientes\s+para\s+periodos\s+posteriores\s+\(110\s*-\s*78\)"
)
_PENDIENTE_POSTERIORES_ZERO_LINE = (
    "Cuotas a compensar de periodos previos pendientes para periodos posteriores (110 - 78) ..... 87 0"
)

# The informativas (M180, M193) declare a perceptor COUNT with value_kind="amount";
# AEAT prints it as a bare integer, so the guard must not mistake it for a label.
_PERCEPTORES_LABEL = r"Numero\s+total\s+de\s+perceptores"
_PERCEPTORES_LINE = "Numero total de perceptores 3"

# Verbatim from the Modelo 390 annual-summary render, deducible block. This box
# was unguarded until its casilla gained a form_number: the guard read `number`,
# which on this semantically-named casilla is its own id string and can never
# equal a captured token, so a blank box 64 returned 64,00 EUR of deductions.
_M390_DEDUCCIONES_LABEL = r"(?:Suma\s+de\s+deducciones|Total\s+deductions)"
_M390_DEDUCCIONES_POPULATED_LINE = (
    "Suma de deducciones (49 + 513 + 51 + 521 + 53 + 55 + 57 + 59 + 598 + 61 + 661 + 62 + 652 + 63 + 522) "
    "....................... 64 68.202,00"
)
_M390_DEDUCCIONES_BLANK_LINE = (
    "Suma de deducciones (49 + 513 + 51 + 521 + 53 + 55 + 57 + 59 + 598 + 61 + 661 + 62 + 652 + 63 + 522) "
    "....................... 64"
)

# Verbatim from the Modelo 190 resumen page. Same defect, sharper consequence:
# this profile floors at 1.0, so a fabricated 2,00 EUR would have SATISFIED the
# coverage floor rather than tripping it. Its `number` is the fichero-BOE
# positional range "145-160", which is correct for what that field means.
_M190_PERCEPCIONES_LABEL = r"Importe\s+total\s+de\s+las\s+percepciones"
_M190_PERCEPCIONES_POPULATED_LINE = (
    "Importe total de las percepciones relacionadas "
    "................................................................................."
    "................................................................ 02 1.000,00"
)
_M190_PERCEPCIONES_BLANK_LINE = (
    "Importe total de las percepciones relacionadas "
    "................................................................................."
    "................................................................ 02"
)


def _target(casilla_id: str, label_pattern: str) -> ExtractionTargetDefinition:
    return ExtractionTargetDefinition(
        casilla_id=validated_casilla_id(casilla_id, surface="blank-box regression target"),
        match_strategy="named_label",
        value_kind="amount",
        label_pattern=label_pattern,
    )


def _classify(
    casilla_id: str,
    label_pattern: str,
    line: str,
    printed_box_number: str,
) -> _TargetClassification:
    target = _target(casilla_id, label_pattern)
    return _classify_target(
        target,
        pages=(line,),
        pages_words=None,
        numeric_anchors={},
        printed_box_numbers={target.casilla_id: printed_box_number},
    )


@pytest.mark.parametrize(
    "casilla_id,label_pattern,line,printed_box_number",
    [
        ("iva.compensacion-aplicada-periodo", _COMPENSACION_APLICADA_LABEL, _COMPENSACION_BLANK_LINE, "78"),
        ("37", _ADQUISICIONES_LABEL, _ADQUISICIONES_BLANK_LINE, "37"),
        (
            "iva.anual.cuota-deducible-total",
            _M390_DEDUCCIONES_LABEL,
            _M390_DEDUCCIONES_BLANK_LINE,
            "64",
        ),
        (
            "decl.percepciones-total",
            _M190_PERCEPCIONES_LABEL,
            _M190_PERCEPCIONES_BLANK_LINE,
            "02",
        ),
    ],
    ids=[
        "compensacion-aplicada-box-78-blank",
        "adquisiciones-cuota-box-37-blank",
        "m390-deducciones-box-64-blank",
        "m190-percepciones-box-02-blank",
    ],
)
def test_blank_box_is_absent_not_its_own_box_number(
    casilla_id: str,
    label_pattern: str,
    line: str,
    printed_box_number: str,
) -> None:
    """A blank box yields ``missing`` and never a Decimal.

    Fails on the pre-fix parser, which returned ``Decimal("78")`` and
    ``Decimal("37")`` respectively - the box numbers printed on those lines.
    """
    outcome = _classify(casilla_id, label_pattern, line, printed_box_number)

    assert outcome.value is None, (
        f"blank box for casilla {casilla_id!r} extracted a value "
        f"{outcome.value.printed_value if outcome.value else None!r}; a box the filing left empty "
        "must never yield an amount"
    )
    assert outcome.missing is not None, (
        f"blank box for casilla {casilla_id!r} must classify as missing (absent), not "
        f"malformed={outcome.malformed!r} / ambiguous={outcome.ambiguous!r}"
    )


@pytest.mark.parametrize(
    "casilla_id,label_pattern,line,printed_box_number,expected",
    [
        (
            "iva.compensacion-aplicada-periodo",
            _COMPENSACION_APLICADA_LABEL,
            _COMPENSACION_POPULATED_LINE,
            "78",
            Decimal("3000.00"),
        ),
        ("37", _ADQUISICIONES_LABEL, _ADQUISICIONES_POPULATED_LINE, "37", Decimal("4410.00")),
        (
            "iva.compensacion-pendiente-periodos-posteriores",
            _PENDIENTE_POSTERIORES_LABEL,
            _PENDIENTE_POSTERIORES_ZERO_LINE,
            "87",
            Decimal("0"),
        ),
        # A count-valued target: the informativas declare total-perceptores as an
        # "amount" and AEAT prints it as a bare integer. It must survive the guard.
        ("decl.total-perceptores", _PERCEPTORES_LABEL, _PERCEPTORES_LINE, "01", Decimal("3")),
        (
            "iva.anual.cuota-deducible-total",
            _M390_DEDUCCIONES_LABEL,
            _M390_DEDUCCIONES_POPULATED_LINE,
            "64",
            Decimal("68202.00"),
        ),
        (
            "decl.percepciones-total",
            _M190_PERCEPCIONES_LABEL,
            _M190_PERCEPCIONES_POPULATED_LINE,
            "02",
            Decimal("1000.00"),
        ),
    ],
    ids=[
        "compensacion-aplicada-3000",
        "adquisiciones-cuota-4410",
        "pendiente-posteriores-printed-bare-zero",
        "total-perceptores-printed-bare-count",
        "m390-deducciones-68202",
        "m190-percepciones-1000",
    ],
)
def test_populated_box_still_extracts_its_printed_amount(
    casilla_id: str,
    label_pattern: str,
    line: str,
    printed_box_number: str,
    expected: Decimal,
) -> None:
    """The guard must not cost a single populated box, nor any legitimate bare integer.

    The last two cases are the ones a "must contain a decimal comma" rule would
    break, and both were found by running the guard against the real corpus: AEAT
    prints an explicit bare ``0`` in a genuinely-zero box, and the informativas
    print ``total-perceptores`` as a bare count. Keying the refusal on the
    target's own box number keeps both while still refusing a blank box's label.
    """
    outcome = _classify(casilla_id, label_pattern, line, printed_box_number)

    assert outcome.value is not None, (
        f"populated box for casilla {casilla_id!r} failed to extract (missing={outcome.missing!r}, "
        f"malformed={outcome.malformed!r}, ambiguous={outcome.ambiguous!r})"
    )
    assert outcome.value.printed_value == expected


@pytest.mark.parametrize(
    "modelo,filing_year,period,expected_printed",
    [
        (
            "390",
            2021,
            "0A",
            {
                "iva.anual.cuota-devengada-total": "47",
                "iva.anual.cuota-deducible-total": "64",
                "iva.anual.resultado-regimen-general": "65",
            },
        ),
        (
            "190",
            2024,
            "0A",
            {
                "decl.total-percepciones": "01",
                "decl.percepciones-total": "02",
                "decl.retenciones-total": "03",
            },
        ),
    ],
    ids=["modelo-390-totals", "modelo-190-resumen"],
)
def test_the_guard_is_actually_armed_for_semantically_named_casillas(
    modelo: str,
    filing_year: int,
    period: str,
    expected_printed: dict[str, str],
) -> None:
    """The guard resolves a real printed box number for these targets.

    The cases above prove the guard refuses a blank box when it is told the box
    number. This proves it is told: the whole defect was that it was not.

    ``_printed_box_numbers`` read ``number``, which is reviewed AEAT
    record-design metadata. On a numerically-named casilla that happens to equal
    the printed number, so the guard worked by accident; on a semantically-named
    one it is the casilla id or a fichero-BOE positional range, which no captured
    token can equal, so these six targets were silently unguarded. The printed
    numbers below are read off the bundled AEAT renders, not from the casilla
    records under test.

    Asserting the resolved value rather than mere presence is what makes this
    bite: reverting to ``number`` still returns an entry for every target, and
    only the value shows it is the wrong one.
    """
    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)
    revision = snapshot.revision
    profile = next(
        p
        for p in revision.extraction_profiles
        if p.surface == "declaracion_pdf" and "declaration_pdf" in p.accepted_artefact_kinds
    )

    printed = {str(k): v for k, v in _printed_box_numbers(profile, revision).items()}

    for casilla_id, expected in expected_printed.items():
        assert printed.get(casilla_id) == expected, (
            f"M{modelo} {casilla_id!r}: blank-box guard resolves printed box number "
            f"{printed.get(casilla_id)!r}, but the AEAT render prints {expected!r}; a blank "
            f"box would be read as {expected} euros"
        )


@pytest.mark.parametrize("ambiguous", ["1.234", "45.678", "100.000"])
def test_ambiguous_thousands_amount_is_malformed_not_a_thousandfold_misread(ambiguous: str) -> None:
    """A dot-only printed amount is refused rather than read a thousandfold small.

    Only the ``casilla`` strategy's regex embeds ``SPANISH_AMOUNT_GROUP`` and so
    guarantees the ``,NN`` tail. ``named_label`` takes the line's last word
    unvalidated, so a bare ``1.234`` reaches the permissive parser, where it
    decodes as one point two three four. On a filed declaración that is a box
    read a thousandfold small, behind an otherwise successful extraction.
    """
    outcome = _classify("0150", r"Rendimiento", f"Rendimiento neto ......... {ambiguous}", "0150")
    assert outcome.malformed == validated_casilla_id("0150", surface="ambiguity regression")
    assert outcome.value is None


def test_the_ambiguity_guard_does_not_swallow_a_well_formed_amount() -> None:
    """The guard must reject only the two-way token, or it would eat real boxes.

    A comma settles the reading, so the canonical Spanish form still extracts.
    Without this the previous test would pass against a parser that had simply
    stopped reading amounts at all.
    """
    outcome = _classify("0150", r"Rendimiento", "Rendimiento neto ......... 1.234,56", "0150")
    assert outcome.malformed is None
    assert outcome.value is not None
    assert outcome.value.printed_value == Decimal("1234.56")
