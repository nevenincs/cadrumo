"""Behaviour tests for the deterministic AEAT sanción document reader.

Every fixture here is a text layer in the shape AEAT prints — the label
vocabulary and the ``3.687,12euros`` rendering with no space before the unit
were observed on a live document. Nothing is mocked: the parser is a pure
function over text, so these exercise the real code path end to end.

The suite is deliberately weighted toward REFUSAL. A reader that returns a
complete record for a complete document is the easy half; the half that
matters is that an incomplete, ambiguous, mis-bound or reshaped document
produces an error rather than a confident wrong number.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....domain.notifications.sancion import SancionLiquidacion
from .._sancion import parse_sancion_document
from ..errors import SancionArithmeticError, SancionParseError

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_CERT = "2699101808461"
_SHA = "a" * 64

# The flat layout: every reducción subtracted from the sanción, the payable
# printed as ``Diferencia``.
FLAT_LAYOUT = """AGENCIA TRIBUTARIA
ACUERDO DE RESOLUCION DE PROCEDIMIENTO SANCIONADOR
Clave de liquidación: A2860024500012345
Referencia: 2024/0001234
N.I.F.: 12345678Z
Base sobre la que se liquida la sanción 3.687,12euros
Porcentaje mínimo de sanción 50,00%
Sanción resultante 1.843,56euros
Reducción del 30% 553,07euros
Reducción del 40% 516,20euros
Diferencia 774,29euros
"""

# The sequential layout: the same act, with each reducción applied to the
# running amount and the intermediate total also printed. The final payable is
# identical, which is the property the reconciliation relies on.
SEQUENTIAL_LAYOUT = """AGENCIA TRIBUTARIA
ACUERDO DE RESOLUCION DE PROCEDIMIENTO SANCIONADOR
Clave de liquidación: A2860024500012345
Referencia: 2024/0001234
N.I.F.: 12345678Z
Base sobre la que se liquida la sanción 3.687,12euros
Porcentaje mínimo de sanción 50,00%
Sanción resultante 1.843,56euros
Reducción del 30% 553,07euros
Diferencia 1.290,49euros
Reducción del 40% 516,20euros
Importe a ingresar 774,29euros
"""


def _parse(text: str) -> SancionLiquidacion:
    return parse_sancion_document(text, certificado_id=_CERT, document_sha256=_SHA)


def test_flat_layout_reads_every_printed_figure() -> None:
    """The flat layout yields every printed figure, unrounded and unre-derived."""
    record = _parse(FLAT_LAYOUT)

    assert record.clave_liquidacion == "A2860024500012345"
    assert record.referencia == "2024/0001234"
    assert record.nif == "12345678Z"
    assert record.objeto_tributario == "sancion"
    assert record.base_sancion == Decimal("3687.12")
    assert record.porcentaje_minimo == Decimal("50.00")
    assert record.sancion_resultante == Decimal("1843.56")
    assert record.reduccion_conformidad == Decimal("553.07")
    assert record.reduccion_pronto_pago == Decimal("516.20")
    assert record.importe_a_ingresar == Decimal("774.29")
    assert record.document_sha256 == _SHA
    assert record.certificado_id == _CERT


def test_sequential_layout_binds_the_final_payable_not_the_intermediate() -> None:
    """The sequential layout's payable is the final line, with the intermediate carried.

    This is the layout that would break a naive reader: ``Diferencia`` here is
    an INTERMEDIATE subtotal, and binding the payable to it would understate
    what is owed by the 40% reducción.
    """
    record = _parse(SEQUENTIAL_LAYOUT)

    assert record.importe_a_ingresar == Decimal("774.29")
    assert record.diferencia == Decimal("1290.49")


def test_both_layouts_agree_on_the_payable() -> None:
    """The two AEAT layouts of one act must produce the same payable amount."""
    assert _parse(FLAT_LAYOUT).importe_a_ingresar == _parse(SEQUENTIAL_LAYOUT).importe_a_ingresar


def test_an_act_with_no_reduccion_keeps_them_none_rather_than_zero() -> None:
    """An ungranted reducción is ``None``; a zero would assert AEAT granted one at zero."""
    text = """Clave de liquidación: A2860024500012345
Referencia: 2024/0001234
N.I.F.: 12345678Z
Base sobre la que se liquida la sanción 1.000,00euros
Porcentaje mínimo de sanción 50,00%
Sanción resultante 500,00euros
Importe a ingresar 500,00euros
"""
    record = _parse(text)

    assert record.reduccion_conformidad is None
    assert record.reduccion_pronto_pago is None
    assert record.importe_a_ingresar == Decimal("500.00")


def test_a_reduccion_granted_at_zero_reads_as_zero_and_not_as_ungranted() -> None:
    """A printed ``0,00`` reducción is a granted zero, distinct from an absent line.

    The two are arithmetically indistinguishable — both subtract nothing — so
    nothing downstream of the arithmetic can tell them apart. Only the record
    can, and only if the reader keeps them apart: AEAT granting a reducción and
    quantifying it at zero is a different fact from AEAT granting none, and it
    is the fact an appeal turns on. Collapsing the granted zero to ``None``
    would erase a decision AEAT actually printed.
    """
    head = """Clave de liquidación: A2860024500012345
Referencia: 2024/0001234
N.I.F.: 12345678Z
Base sobre la que se liquida la sanción 1.000,00euros
Porcentaje mínimo de sanción 50,00%
Sanción resultante 500,00euros
"""
    granted_at_zero = _parse(f"{head}Reducción del 30% 0,00euros\nImporte a ingresar 500,00euros\n")
    ungranted = _parse(f"{head}Importe a ingresar 500,00euros\n")

    assert granted_at_zero.reduccion_conformidad == Decimal("0.00")
    assert ungranted.reduccion_conformidad is None
    # The distinction survives as a record-level difference, not merely as a
    # difference in spelling: a reader that returned None for the printed 0,00
    # would make these two readings compare equal.
    assert granted_at_zero.reduccion_conformidad != ungranted.reduccion_conformidad
    # ...while the arithmetic they drive is identical, which is exactly why the
    # payable cannot be used to recover the distinction.
    assert granted_at_zero.reducciones_total == ungranted.reducciones_total == Decimal("0.00")
    assert granted_at_zero.importe_a_ingresar == ungranted.importe_a_ingresar == Decimal("500.00")


def test_accent_free_and_loosely_spaced_rendering_reads_identically() -> None:
    """AEAT's accent-free, dot-leader template is the same document to this reader."""
    text = """Clave de liquidacion:   A2860024500012345
Referencia:  2024/0001234
N.I.F.:   12345678Z
Base sobre la que  se liquida la sancion .......... 3.687,12 euros
Porcentaje minimo de sancion .......... 50,00 %
Sancion resultante .......... 1.843,56 euros
Reduccion del 30% .......... 553,07 euros
Reduccion del 40% .......... 516,20 euros
Diferencia .......... 774,29 euros
"""
    record = _parse(text)

    assert record.base_sancion == Decimal("3687.12")
    assert record.porcentaje_minimo == Decimal("50.00")
    assert record.importe_a_ingresar == Decimal("774.29")


@pytest.mark.parametrize(
    ("separator", "name"),
    [
        (".", "full stop"),
        ("\u00a0", "non-breaking space"),
        ("\u202f", "narrow no-break space"),
    ],
)
def test_every_thousands_separator_aeat_actually_prints_is_read(separator: str, name: str) -> None:
    """AEAT groups thousands with a dot, an NBSP or a narrow NBSP, and all three read.

    Per UNE 82100 these are the three code points AEAT prints between thousand
    groups. The reader once accepted only the dot, so a genuine document
    rendered with either space form was refused outright — a safe direction,
    but a refusal on a real act the taxpayer has to answer.
    """
    text = f"""Clave de liquidación: A2860024500012345
Referencia: 2024/0001234
N.I.F.: 12345678Z
Base sobre la que se liquida la sanción 3{separator}687,12euros
Porcentaje mínimo de sanción 50,00%
Sanción resultante 1{separator}843,56euros
Importe a ingresar 1{separator}843,56euros
"""
    record = _parse(text)

    assert record.base_sancion == Decimal("3687.12"), name
    assert record.sancion_resultante == Decimal("1843.56"), name


@pytest.mark.parametrize(
    ("printed", "why"),
    [
        ("1 234,56", "an ASCII space is AEAT's COLUMN separator, never a thousands separator"),
        ("1\t234,56", "a tab is column whitespace for the same reason"),
        ("1.843", "a whole-euro rendering has no evidence for 1843 over 1.843"),
        ("1\u00a0843", "an NBSP-grouped whole euro is still a whole euro: the tail is what refuses"),
        ("3.687,1", "a one-digit tail is not AEAT's two-decimal convention"),
        ("3.687,123", "and neither is a three-digit one"),
    ],
)
def test_a_separator_or_tail_aeat_does_not_print_refuses(printed: str, why: str) -> None:
    """Widening the accepted separators must not widen anything else.

    The ASCII-space cases are the load-bearing half. AEAT separates COLUMNS
    with ordinary whitespace, so a grammar that accepted it could bridge the
    gap between a label and its value and read two adjacent printed numbers as
    one figure. The whole-euro cases pin the refusal the anchored shape exists
    for, in both the dot and the space rendering.
    """
    text = FLAT_LAYOUT.replace("Sanción resultante 1.843,56euros", f"Sanción resultante {printed}euros")

    with pytest.raises(SancionParseError) as excinfo:
        _parse(text)

    assert "sancion_resultante" in excinfo.value.malformed + excinfo.value.missing, why


def test_a_label_reprinted_with_the_same_value_is_a_repeat_not_an_ambiguity() -> None:
    """AEAT reprints labels in headers and summary blocks; identical values collapse."""
    record = _parse(FLAT_LAYOUT + "\nSanción resultante 1.843,56euros\nN.I.F.: 12345678Z\n")

    assert record.sancion_resultante == Decimal("1843.56")


# ── Refusals ───────────────────────────────────────────────────────────────


def test_a_missing_required_label_refuses_and_names_the_field() -> None:
    """A document with no ``Sanción resultante`` line is not a readable document."""
    text = FLAT_LAYOUT.replace("Sanción resultante 1.843,56euros\n", "")

    with pytest.raises(SancionParseError) as excinfo:
        _parse(text)

    assert "sancion_resultante" in excinfo.value.missing


def test_a_document_with_no_payable_line_refuses_rather_than_reading_zero() -> None:
    """No payable line means the document was not read — never a zero payable.

    This is the exact failure this parser exists to prevent: a reader that
    answers ``0,00`` here reads, at every layer above it, as "nothing owed".
    """
    text = FLAT_LAYOUT.replace("Diferencia 774,29euros\n", "")

    with pytest.raises(SancionParseError) as excinfo:
        _parse(text)

    assert "importe_a_ingresar" in excinfo.value.missing


_FULLY_REDUCED_HEAD = """Clave de liquidación: A2860024500012345
Referencia: 2024/0001234
N.I.F.: 12345678Z
Base sobre la que se liquida la sanción 1.000,00euros
Porcentaje mínimo de sanción 50,00%
Sanción resultante 500,00euros
Reducción del 30% 150,00euros
"""
"""An act whose reducciones absorb the sanción entirely, leaving nothing payable.

500,00 less 150,00 and 350,00 is exactly zero, so AEAT prints a payable of
``0,00``. The figure is real, reconciles, and is the one a reader must not
confuse with an absent line.
"""


def test_a_printed_zero_payable_is_read_in_the_flat_layout() -> None:
    """``Importe a ingresar 0,00`` alone is a payable AEAT stated, not a missing line.

    The flat layout prints one payable line. A reader selecting between the two
    payable labels by TRUTHINESS discards a zero Decimal and then reports the
    field missing — refusing a document it had in fact read correctly, and
    telling the operator the reading failed when the act simply has nothing
    left to pay after its reducciones.
    """
    record = _parse(f"{_FULLY_REDUCED_HEAD}Reducción del 40% 350,00euros\nImporte a ingresar 0,00euros\n")

    assert record.importe_a_ingresar == Decimal("0.00")
    assert record.diferencia is None
    assert record.reducciones_total == Decimal("500.00")


def test_a_printed_zero_payable_binds_to_importe_a_ingresar_in_the_sequential_layout() -> None:
    """With both labels printed, the zero ``Importe a ingresar`` still takes precedence.

    ``Diferencia`` in this layout is the INTERMEDIATE subtotal after the first
    reducción. Falling through to it because the final payable is zero binds the
    record to 350,00 — an act reported as owing money it does not owe — and the
    reconciliation then fails, so the truthiness selection turned a correct
    reading into an arithmetic refusal naming the wrong field.
    """
    record = _parse(
        f"{_FULLY_REDUCED_HEAD}Diferencia 350,00euros\nReducción del 40% 350,00euros\nImporte a ingresar 0,00euros\n",
    )

    assert record.importe_a_ingresar == Decimal("0.00")
    # The intermediate is still carried, so the precedence is a choice between
    # two values that both resolved -- not an artefact of one being unread.
    assert record.diferencia == Decimal("350.00")


def test_a_printed_zero_diferencia_is_read_when_it_is_the_only_payable_line() -> None:
    """The flat layout names its payable ``Diferencia``; a printed zero there reads too."""
    record = _parse(f"{_FULLY_REDUCED_HEAD}Reducción del 40% 350,00euros\nDiferencia 0,00euros\n")

    assert record.importe_a_ingresar == Decimal("0.00")
    assert record.diferencia == Decimal("0.00")


def test_a_document_with_neither_payable_label_still_refuses_after_the_zero_fix() -> None:
    """Reading a printed zero must not soften the refusal for a genuinely absent payable.

    The two are opposite facts — AEAT stated nothing is owed, versus AEAT stated
    nothing at all — and only the first may produce a record.
    """
    with pytest.raises(SancionParseError) as excinfo:
        _parse(f"{_FULLY_REDUCED_HEAD}Reducción del 40% 350,00euros\n")

    assert "importe_a_ingresar" in excinfo.value.missing


def test_a_whole_euro_rendering_refuses_instead_of_being_reinterpreted() -> None:
    """A template that drops the decimals is a shape change, not a thousands-grouped integer.

    ``1.843 euros`` read permissively becomes ``1843`` — or, worse, ``1.843``.
    The anchored shape refuses it so the template change surfaces as itself.
    """
    text = FLAT_LAYOUT.replace("Sanción resultante 1.843,56euros", "Sanción resultante 1.843 euros")

    with pytest.raises(SancionParseError) as excinfo:
        _parse(text)

    assert "sancion_resultante" in excinfo.value.malformed + excinfo.value.missing


def test_a_label_reprinted_with_a_conflicting_value_refuses_rather_than_picking_one() -> None:
    """Two different printed values under one label admit no defensible reading."""
    text = FLAT_LAYOUT + "Sanción resultante 9.999,99euros\n"

    with pytest.raises(SancionParseError) as excinfo:
        _parse(text)

    assert "sancion_resultante" in excinfo.value.ambiguous


def test_a_base_bound_to_the_wrong_number_refuses_on_reconciliation() -> None:
    """``base x porcentaje`` must reproduce the printed sanción, or a label is mis-bound."""
    text = FLAT_LAYOUT.replace(
        "Base sobre la que se liquida la sanción 3.687,12euros",
        "Base sobre la que se liquida la sanción 9.000,00euros",
    )

    with pytest.raises(SancionArithmeticError) as excinfo:
        _parse(text)

    assert excinfo.value.context is not None
    assert excinfo.value.context["check"] == "base_times_porcentaje"


def test_a_payable_that_does_not_follow_from_the_reducciones_refuses() -> None:
    """The payable must equal the sanción less the printed reducciones, to the cent."""
    text = FLAT_LAYOUT.replace("Diferencia 774,29euros", "Diferencia 74,29euros")

    with pytest.raises(SancionArithmeticError) as excinfo:
        _parse(text)

    assert excinfo.value.context is not None
    assert excinfo.value.context["check"] == "sancion_less_reducciones"


def test_reconciliation_tolerates_one_cent_of_aeat_rounding_and_no_more() -> None:
    """One cent is AEAT's own half-up rounding; two cents is a mis-binding.

    The tolerance is the whole risk surface of the reconciliation guard: too
    wide and it starts absorbing the mis-bindings it exists to catch.
    """
    base = "Base sobre la que se liquida la sanción 1.000,05euros"
    head = f"""Clave de liquidación: A2860024500012345
Referencia: 2024/0001234
N.I.F.: 12345678Z
{base}
Porcentaje mínimo de sanción 50,00%
"""
    # 1.000,05 x 50% = 500,025 -> AEAT prints 500,03; a one-cent-off 500,02 is
    # still accepted, while two cents off is not.
    for printed in ("500,03", "500,02"):
        record = parse_sancion_document(
            f"{head}Sanción resultante {printed}euros\nImporte a ingresar {printed}euros\n",
            certificado_id=_CERT,
            document_sha256=_SHA,
        )
        assert record.sancion_resultante == Decimal(printed.replace(",", "."))

    with pytest.raises(SancionArithmeticError):
        parse_sancion_document(
            f"{head}Sanción resultante 500,01euros\nImporte a ingresar 500,01euros\n",
            certificado_id=_CERT,
            document_sha256=_SHA,
        )


def test_a_malformed_identifier_refuses_rather_than_carrying_prose() -> None:
    """A ``Clave de liquidación`` that is not an identifier is not a clave."""
    text = FLAT_LAYOUT.replace("Clave de liquidación: A2860024500012345", "Clave de liquidación: (pendiente)")

    with pytest.raises(SancionParseError) as excinfo:
        _parse(text)

    assert "clave_liquidacion" in excinfo.value.missing + excinfo.value.malformed


def test_an_empty_document_refuses_with_every_required_field_named() -> None:
    """An empty text layer names the whole required set rather than failing on the first."""
    with pytest.raises(SancionParseError) as excinfo:
        _parse("")

    assert {"clave_liquidacion", "nif", "base_sancion", "sancion_resultante"} <= set(excinfo.value.missing)


def test_the_record_is_frozen_so_a_read_figure_cannot_be_edited_downstream() -> None:
    """A reading is evidence; a consumer must not be able to adjust it in place."""
    record = _parse(FLAT_LAYOUT)

    with pytest.raises(ValueError, match="frozen"):
        record.importe_a_ingresar = Decimal("0.00")  # type: ignore[misc]
