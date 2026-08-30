"""Anti-tautology proofs for the M303 devengada chain.

Two properties are defended here, and they now live on two different paths
because the declaración extraction profile targets only what AEAT prints.

**The engine sums its primitive leaves** (calculate path). A round trip that
depends on the engine recomputing a total from per-rate cuota primitives MUST
carry a proof that the engine is actually summing them — not copying a printed
total, and not silently substituting a zero default. The probe mutates
``iva.repercutido.general`` by a known delta and asserts
``iva.cuota-devengada-total`` shifts by exactly that delta.

This proof used to source its primitive from a parsed corpus PDF. It no longer
can: the printed AEAT form does not carry per-rate cuota primitives, so the
profile stopped targeting them, and the printed totals cannot be substituted
because the engine refuses computed casillas as inputs. The primitive is
therefore supplied directly, which is how the calculate path supplies it in
production — from ledger aggregation rather than from a document. The property
being defended is unchanged; only the input path moved.

**The printed-arithmetic assertion can fail** (parse path). The parse path now
asserts a property of the document — box 46 == box 27 − box 45 — instead of
running the engine. An assertion that cannot fail is not a guard, so its
falsifiability is proven here by perturbing each printed amount in turn and
confirming refusal.

Grounded authority:
    Orden EHA/3786/2008 art. 1 (box 27 = total cuota devengada,
    box 45 = total a deducir, box 46 = box 27 - box 45).
    post-2022 Modelo 303 ``modelo-303-iva-cuota-devengada-total`` formula:
    add(iva.repercutido.general, iva.repercutido.reducido,
    iva.repercutido.super-reducido, iva.autorepercutido.intracomunitaria,
    iva.autoconsumo.promotor.cuota).
"""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._verification_chain_support import (
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
    _M303_STATE_ATTRIBUTION_RATIO_CASILLA,
    BindingId,
    CasillaId,
    Decimal,
    _assert_m303_printed_resultado_regimen_general_arithmetic,
    _calculate_m303_engine_values_from_inputs,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_IVA_REPERCUTIDO_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.repercutido.general")


def _run_engine(inputs: dict[CasillaId, Decimal], year: int, period: str) -> dict[CasillaId, Decimal]:
    """Calculate the registry snapshot with ``inputs`` and return engine values.

    ``_calculate_m303_engine_values_from_inputs`` is declared
    ``dict[CasillaId, object]`` (the shared support module serves modelos
    whose computed values are not always Decimal); every M303 engine casilla
    is a numeric amount, so this asserts each value is a real ``Decimal``
    rather than declaring a return type the callee cannot honestly promise.
    """
    binding_values: dict[BindingId, Decimal] = {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }
    raw_values = _calculate_m303_engine_values_from_inputs(
        inputs=inputs,
        year=year,
        period=period,
        binding_values=binding_values,
        label="M303 anti-tautology",
    )
    engine_values: dict[CasillaId, Decimal] = {}
    for casilla_id, value in raw_values.items():
        assert isinstance(value, Decimal), f"engine casilla {casilla_id!r} = {value!r} is not a Decimal"
        engine_values[casilla_id] = value
    return engine_values


def test_m303_engine_sums_supplied_primitives_not_a_printed_total() -> None:
    """Mutating ``iva.repercutido.general`` shifts ``iva.cuota-devengada-total`` by the same delta.

    Proves the engine sums the primitive leaves. The baseline primitive value is
    an INPUT, not an expected result, so no external oracle is required: the
    property under test is the delta identity, which holds for any input.

    Failure modes covered: the engine stops summing the primitive; the engine
    substitutes a zero default for a supplied primitive; a formula change drops
    the summand. (The former "extraction copies the printed total instead of the
    primitive" mode is no longer reachable — extraction does not supply
    primitives at all — so it is deliberately not claimed here.)
    """
    primitive = Decimal("21000.00")
    base_inputs: dict[CasillaId, Decimal] = {
        _IVA_REPERCUTIDO_GENERAL_CASILLA: primitive,
        _M303_STATE_ATTRIBUTION_RATIO_CASILLA: Decimal("100"),
    }

    base_values = _run_engine(base_inputs, 2023, "1T")
    base_devengada = base_values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]

    # A zero baseline would make the delta assertion pass even if the engine
    # ignored the primitive entirely and returned 0 both times.
    assert base_devengada == primitive, (
        "ANTI-TAUTOLOGY-PRECONDITION-FAIL: the engine did not carry the supplied "
        f"primitive into iva.cuota-devengada-total.\n  supplied = {primitive!r}\n"
        f"  devengada-total = {base_devengada!r}"
    )

    delta = Decimal("100.00")
    mutated_inputs = dict(base_inputs)
    mutated_inputs[_IVA_REPERCUTIDO_GENERAL_CASILLA] = primitive + delta
    mutated_values = _run_engine(mutated_inputs, 2023, "1T")
    mutated_devengada = mutated_values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]

    assert mutated_devengada - base_devengada == delta, (
        "ANTI-TAUTOLOGY-FAIL: mutating iva.repercutido.general by "
        f"{delta} should shift iva.cuota-devengada-total by exactly that amount.\n"
        f"  base iva.repercutido.general      = {primitive!r}\n"
        f"  base iva.cuota-devengada-total    = {base_devengada!r}\n"
        f"  mutated iva.repercutido.general   = {primitive + delta!r}\n"
        f"  mutated iva.cuota-devengada-total = {mutated_devengada!r}\n"
        f"  observed delta                    = {mutated_devengada - base_devengada!r}"
    )


_PRINTED_27 = Decimal("21000.00")
_PRINTED_45 = Decimal("4200.00")
_PRINTED_46 = _PRINTED_27 - _PRINTED_45


def _printed_m303_totals() -> dict[CasillaId, Decimal]:
    return {
        _M303_CUOTA_DEVENGADA_TOTAL_CASILLA: _PRINTED_27,
        _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: _PRINTED_45,
        _M303_RESULTADO_REGIMEN_GENERAL_CASILLA: _PRINTED_46,
    }


def test_m303_printed_arithmetic_assertion_holds_on_a_consistent_document() -> None:
    """The control: a self-consistent printed triple is accepted."""
    _assert_m303_printed_resultado_regimen_general_arithmetic(
        pdf_stem="synthetic-consistent",
        extracted=_printed_m303_totals(),
    )


@pytest.mark.parametrize(
    "perturbed_casilla,label",
    [
        (_M303_CUOTA_DEVENGADA_TOTAL_CASILLA, "box 27"),
        (_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA, "box 45"),
        (_M303_RESULTADO_REGIMEN_GENERAL_CASILLA, "box 46"),
    ],
)
def test_m303_printed_arithmetic_assertion_is_falsifiable(
    perturbed_casilla: CasillaId,
    label: str,
) -> None:
    """Perturbing any one of the three printed amounts must be refused.

    This is the proof that the parse-path assertion is a guard rather than a
    decoration. It replaces an engine comparison whose second half was
    tautological — it compared the engine's resultado against the engine's own
    ``box 27 - box 45``, which is the registry formula for resultado, so it held
    by construction and would have passed even at zero.
    """
    perturbed = _printed_m303_totals()
    perturbed[perturbed_casilla] += Decimal("0.01")

    with pytest.raises(AssertionError, match="DOCUMENT-INCONSISTENT"):
        _assert_m303_printed_resultado_regimen_general_arithmetic(
            pdf_stem=f"synthetic-perturbed-{label.replace(' ', '-')}",
            extracted=perturbed,
        )


def test_m303_printed_arithmetic_assertion_refuses_a_missing_box() -> None:
    """A printed amount absent from the parse is refused, not silently skipped."""
    incomplete = _printed_m303_totals()
    del incomplete[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]

    with pytest.raises(AssertionError, match="PARSER-GAP"):
        _assert_m303_printed_resultado_regimen_general_arithmetic(
            pdf_stem="synthetic-missing-box-45",
            extracted=incomplete,
        )
