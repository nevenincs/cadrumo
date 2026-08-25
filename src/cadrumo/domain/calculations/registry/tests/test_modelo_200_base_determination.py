"""Modelo 200 base-determination chain (resultado contable -> base imponible).

Locks the durable fix for the silent zero-base under-declaration recorded in
the base-determination design note and grounded in the companion
reference artifact. The base imponible
``DP200014:00552`` was a free-standing manual entry: a positive resultado
contable with no entered base verified ``complete`` at zero tax. It is now
COMPUTED from the Liquidación I -> III chain:

* ``DP200014:00550`` (base imponible previa) = ``00501`` (resultado contable)
  ``+ DP200013:00417`` (total correcciones de aumento)
  ``- DP200013:00418`` (total correcciones de disminución).
* ``DP200014:00552`` (base imponible) = ``max(00550 - 01032 - 00547, 0)`` —
  base previa minus reserva de capitalización (LIS Art. 25) minus compensación
  de bases imponibles negativas aplicada (LIS Art. 26), non-negative-clamped
  («si el resultado es cero, consignar cero»).

The base previa is derived from the STORED Liquidación II column subtotals
``00417`` / ``00418``, not from the per-row correccion leaves, so the leaves
are never double-summed against their own totals.

Numeric oracle: the AEAT Manual práctico de Sociedades 2024 worked example
(Liquidación I -> III, manual page 401) carries a base imponible después de la
reserva de nivelación ``01330`` of 1.000.000 at a 25 % tipo de gravamen yielding
a cuota íntegra ``00562`` of 250.000. Feeding the resultado contable
``00501 = 1.000.000`` with zero correcciones, zero reserva and zero
compensación BIN must reproduce that published base and cuota — the test fails
if the chain diverges from the manual.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, RegistryAuthorityGrade, validated_casilla_id
from .._formula_runtime import calculate_registry_snapshot
from .._schema import InputKind
from ._registry_schema_support import _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DISPATCH_BINDING = "modelo-200-2024-profile-legal-entity-form"
_M200_RESULTADO_CONTABLE_CASILLA: CasillaId = validated_casilla_id("00501", surface="_M200_RESULTADO_CONTABLE_CASILLA")
_M200_CORRECCIONES_AUMENTO_CASILLA: CasillaId = validated_casilla_id(
    "DP200013:00417",
    surface="_M200_CORRECCIONES_AUMENTO_CASILLA",
)
_M200_CORRECCIONES_DISMINUCION_CASILLA: CasillaId = validated_casilla_id(
    "DP200013:00418",
    surface="_M200_CORRECCIONES_DISMINUCION_CASILLA",
)
_M200_BASE_PREVIA_CASILLA: CasillaId = validated_casilla_id("DP200014:00550", surface="_M200_BASE_PREVIA_CASILLA")
_M200_BASE_PREVIA_FORMULA = "modelo-200-base-imponible-previa"
_M200_BASE_PREVIA_DEFINITIONAL_REFS = {"ley-27-2014:art-10", "ley-27-2014:art-11"}
_M200_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:00552",
    surface="_M200_BASE_IMPONIBLE_CASILLA",
)
_M200_RESERVA_CAPITALIZACION_CASILLA: CasillaId = validated_casilla_id(
    "01032",
    surface="_M200_RESERVA_CAPITALIZACION_CASILLA",
)
_M200_BIN_APLICADA_CASILLA: CasillaId = validated_casilla_id("DP200014:00547", surface="_M200_BIN_APLICADA_CASILLA")
_M200_BASE_NIVELACION_CASILLA: CasillaId = validated_casilla_id(
    "DP200014:01330",
    surface="_M200_BASE_NIVELACION_CASILLA",
)
_M200_CUOTA_INTEGRA_CASILLA: CasillaId = validated_casilla_id("DP200014:00562", surface="_M200_CUOTA_INTEGRA_CASILLA")


def _snapshot_2024():
    return _committed_snapshot("200", 2025, "0A", grade=RegistryAuthorityGrade.CALCULATION)


def _calculate(inputs: dict[CasillaId, Decimal]):
    return calculate_registry_snapshot(
        _snapshot_2024(),
        inputs=inputs,
        enum_binding_values={_DISPATCH_BINDING: "sl"},
        binding_values={
            "modelo-200-2024-profile-new-entity-flag": Decimal("0"),
            "modelo-200-2024-profile-incn-prior-12-months": Decimal("10000000"),
            "modelo-200-2024-profile-tributacion-estado-porcentaje": Decimal("100"),
            "modelo-200-2024-bin-pendiente-ejercicios-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": Decimal("0"),
            "modelo-200-2024-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": Decimal("0"),
        },
        relation_values={
            "modelo-200-2024-rel-202-pagos-fraccionados": Decimal("0"),
            "modelo-200-2024-rel-202-pagos-fraccionados-40-2": Decimal("0"),
        },
        date_context={"filing_period": date(2024, 12, 31)},
    )


def test_base_chain_casillas_are_computed_not_manual() -> None:
    """00550 and 00552 are engine-owned; the subtotals/inputs stay manual.

    Anti-tautology guard: the resultado contable 00501 and the correcciones
    column subtotals 00417/00418 remain manual inputs, so the computed/manual
    classification machinery discriminates rather than blanket-flipping.
    """
    snapshot = _snapshot_2024()
    by_id = {c.id: c for c in snapshot.revision.casillas}
    assert by_id[_M200_BASE_PREVIA_CASILLA].input_kind == InputKind.COMPUTED
    assert by_id[_M200_BASE_IMPONIBLE_CASILLA].input_kind == InputKind.COMPUTED
    assert by_id[_M200_RESULTADO_CONTABLE_CASILLA].input_kind == InputKind.MANUAL
    assert by_id[_M200_CORRECCIONES_AUMENTO_CASILLA].input_kind == InputKind.MANUAL
    assert by_id[_M200_CORRECCIONES_DISMINUCION_CASILLA].input_kind == InputKind.MANUAL
    assert by_id[_M200_BIN_APLICADA_CASILLA].input_kind == InputKind.MANUAL


def test_base_previa_grounding_cites_lis_definition_and_accrual_rules() -> None:
    """The 00550 derivation must cite the current LIS base and accrual articles."""
    snapshot = _snapshot_2024()
    formula = next(formula for formula in snapshot.revision.formulas if formula.id == _M200_BASE_PREVIA_FORMULA)
    casilla = next(casilla for casilla in snapshot.revision.casillas if casilla.id == _M200_BASE_PREVIA_CASILLA)

    assert set(formula.legal_refs) >= _M200_BASE_PREVIA_DEFINITIONAL_REFS
    assert set(casilla.legal_refs) >= _M200_BASE_PREVIA_DEFINITIONAL_REFS
    assert set(snapshot.revision.legal_refs) >= _M200_BASE_PREVIA_DEFINITIONAL_REFS


def test_positive_resultado_zero_correcciones_yields_nonzero_base() -> None:
    """Silent-zero killer: positive resultado contable, zero correcciones.

    The original defect: 00501 = 140.000 with no entered base produced
    00552 = 0 and verified complete at zero tax. With the chain modelled,
    a positive resultado contable with zero correcciones, zero reserva and
    zero compensación BIN MUST compute base previa == resultado contable and
    base imponible == resultado contable — never a silent zero.
    """
    result = _calculate({_M200_RESULTADO_CONTABLE_CASILLA: Decimal("140000")})
    assert result.values[_M200_BASE_PREVIA_CASILLA] == Decimal("140000.00")
    assert result.values[_M200_BASE_IMPONIBLE_CASILLA] == Decimal("140000.00")
    assert result.values[_M200_BASE_IMPONIBLE_CASILLA] != Decimal("0")


def test_base_previa_is_complete_sum_of_resultado_and_correccion_subtotals() -> None:
    """Base previa = resultado contable + aumentos − disminuciones.

    Exercises the full Liquidación I -> previa structure with non-default
    values in each summand role: 140.000 resultado + 30.000 aumentos −
    10.000 disminuciones = 160.000. Asserts the structural sum identity
    (00550 == 00501 + 00417 − 00418), not a hand-computed engine output —
    the test fails if any summand is dropped or double-counted.
    """
    inputs = {
        _M200_RESULTADO_CONTABLE_CASILLA: Decimal("140000"),
        _M200_CORRECCIONES_AUMENTO_CASILLA: Decimal("30000"),
        _M200_CORRECCIONES_DISMINUCION_CASILLA: Decimal("10000"),
    }
    result = _calculate(inputs)
    expected_previa = (
        inputs[_M200_RESULTADO_CONTABLE_CASILLA]
        + inputs[_M200_CORRECCIONES_AUMENTO_CASILLA]
        - inputs[_M200_CORRECCIONES_DISMINUCION_CASILLA]
    )
    assert result.values[_M200_BASE_PREVIA_CASILLA] == Decimal("160000.00")
    assert result.values[_M200_BASE_PREVIA_CASILLA] == expected_previa


def test_reserva_and_bin_reduce_base_with_non_negative_clamp() -> None:
    """Reserva de capitalización and compensación BIN cannot drive base below zero.

    Base previa 50.000, reserva 20.000, compensación BIN 99.999 would arithmetic
    to a negative base; the «si el resultado es cero, consignar cero» clamp pins
    00552 to 0. A reserva/BIN within the base reduces it normally
    (50.000 − 20.000 − 10.000 = 20.000).
    """
    clamped = _calculate(
        {
            _M200_RESULTADO_CONTABLE_CASILLA: Decimal("50000"),
            _M200_RESERVA_CAPITALIZACION_CASILLA: Decimal("20000"),
            _M200_BIN_APLICADA_CASILLA: Decimal("99999"),
        },
    )
    assert clamped.values[_M200_BASE_PREVIA_CASILLA] == Decimal("50000.00")
    assert clamped.values[_M200_BASE_IMPONIBLE_CASILLA] == Decimal("0.00")

    within = _calculate(
        {
            _M200_RESULTADO_CONTABLE_CASILLA: Decimal("50000"),
            _M200_RESERVA_CAPITALIZACION_CASILLA: Decimal("20000"),
            _M200_BIN_APLICADA_CASILLA: Decimal("10000"),
        },
    )
    assert within.values[_M200_BASE_IMPONIBLE_CASILLA] == Decimal("20000.00")


def test_computed_base_reproduces_manual_cuota_oracle() -> None:
    """Computed base flows through the published cuota chain unchanged.

    AEAT Manual práctico de Sociedades 2024 (page 401): base 1.000.000 at the
    LIS Art. 29 general 25 % rate yields cuota íntegra 250.000. With the base
    now computed from resultado contable 1.000.000 (zero correcciones/reserva/
    BIN), the post-nivelación base 01330 and cuota 00562 must equal the manual
    oracle — confirming the manual->computed flip preserves the downstream
    chain. The expected figures are read from the manual table, not recomputed.
    """
    result = _calculate({_M200_RESULTADO_CONTABLE_CASILLA: Decimal("1000000")})
    assert result.values[_M200_BASE_IMPONIBLE_CASILLA] == Decimal("1000000.00")
    assert result.values[_M200_BASE_NIVELACION_CASILLA] == Decimal("1000000.00")
    assert result.values[_M200_CUOTA_INTEGRA_CASILLA] == Decimal("250000.00")
