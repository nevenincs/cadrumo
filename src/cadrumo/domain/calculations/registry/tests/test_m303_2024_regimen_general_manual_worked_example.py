"""Oracle test for M303 2024 casillas 09/11/27/29/33/37/45/46/69/71 grounded
against the AEAT Manual practico IVA 2024's own worked example (Cap. 9, "La
declaracion-resumen anual. Modelo 390", primer trimestre solucion).

The two aggregate totals (27, 45) and the resultado chain (69, 71) are graded
alongside the six per-casilla leaves the same solucion states verbatim (09, 11,
29, 33, 37 and "Diferencia" = iva.resultado-regimen-general, form_number 46).
Grading the leaves as well as the totals is what closes the compensating-error
gap: two offsetting mistakes inside the devengado or deducible sum leave both
printed totals correct, so a totals-only oracle stays green while the individual
boxes the operator actually files are wrong.

Ground truth (bundled AEAT Manual practico IVA 2024):

    raw_evidence_locator: corpus/manuals/iva/2024/source.pdf#Pag.293-294

The manual's "Supuesto practico" (pag. 291-294) follows "el senor 'X'"
(fabricacion de aparatos electrodomesticos, epigrafe IAE 345.1) through a full
calendar year of Modelo 303 quarterly liquidaciones, feeding the annual Modelo
390. This test grounds ONLY the primer-trimestre ("Liquidacion primer
trimestre", pag. 293-294) solucion, which the manual states verbatim:

    IVA DEVENGADO (pag. 293):
      "Ventas interiores: [(55.000(7) + 24.000(9))] x 21%: 16.590 euros"
      "Servicios prestados: (4.000(8) x 21%): 840 euros"
      "Total IVA devengado en Ventas interiores y servicios prestados
       (83.000 x 21%): 17.430 euros"
      "Recargo de equivalencia: (24.000(9) x 5,2%): 1.248 euros"
      "Adquisiciones intracomunitarias: [(18.000(2) + 3.000(4))] x 21%:
       4.410 euros"
      "TOTAL CUOTA DEVENGADA: 23.088 euros"
    IVA DEDUCIBLE (pag. 293-294):
      "Compra interiores: (36.000(1) x 21%): 7.560 euros"
      "Servicios recibidos: [(6.000(3) + 5.000(5)) x 21%]: 2.310 euros"
      "Total cuotas soportadas en operaciones interiores: 9.870 euros"
      "Por cuotas satisfechas en importaciones: (12.000(6) x 21%): 2.520 euros"
      "En adquisiciones intracomunitarias: [18.000(2) + 3.000(4)) x 21%]:
       4.410 euros"
      "TOTAL A DEDUCIR: 16.800 euros"
    RESULTADO (pag. 294):
      "Diferencia: 6.288 euros"
      "Cuota a compensar de periodos anteriores: 3.000 euros, de las que
       aplicamos a este trimestre 3.000 euros"
      "Diferencia a ingresar: 3.288 euros"

The underlying operations (pag. 292-293), each quoted verbatim, are the raw
inputs this scenario feeds the registry's ledger-IVA-aggregation resolver as
:class:`IvaLedgerObservation` rows:

    (1) "Compra motores a un empresario espanol por 36.000 euros ...
        IVA soportado: (36.000 x 21%): 7.560 euros" -> domestic general 21%,
        SOPORTADO, base=36.000, iva=7.560.
    (2) "Compra chapa a un fabricante aleman por 18.000 euros ... HI:
        adquisicion intracomunitaria de bienes ... IVA devengado y soportado:
        (18.000 x 21%): 3.780 euros" -> intra-community acquisition reverse
        charge, base=18.000, iva=3.780 (self-assessed both sides).
    (3) "Recibe servicios de un abogado por 6.000 euros ... IVA soportado:
        (6.000 x 21%): 1.260 euros" -> domestic general 21%, SOPORTADO,
        base=6.000, iva=1.260.
    (4) "Recibe la factura del transporte realizado por un transportista
        aleman ... 3.000 euros ... Se produce la inversion del sujeto pasivo
        ... IVA devengado y soportado: (3.000 x 21%): 630 euros" -> intra-
        community acquisition reverse charge (the manual's own "Adquisiciones
        intracomunitarias" bucket groups this services line with op (2)),
        base=3.000, iva=630.
    (5) "Paga por alquiler del local ... 5.000 euros ... IVA soportado:
        (5.000 x 21%): 1.050 euros" -> domestic general 21%, SOPORTADO,
        base=5.000, iva=1.050.
    (6) "Compra tornillos en Marruecos por importe de 12.000 euros ... HI:
        importacion ... IVA soportado: (12.000 x 21%): 2.520 euros" -> third-
        country import, SOPORTADO, base=12.000, iva=2.520.
    (7) "Vende electrodomesticos a un mayorista por importe de 55.000 euros
        ... IVA devengado: (55.000 x 21%): 11.550 euros" -> domestic general
        21%, REPERCUTIDO, base=55.000, iva=11.550.
    (8) "Factura por montajes y arreglos ... 4.000 euros ... IVA devengado:
        (4.000 x 21%): 840 euros" -> domestic general 21%, REPERCUTIDO,
        base=4.000, iva=840.
    (9) "Vende electrodomesticos a comerciantes en el regimen especial del
        recargo de equivalencia por 24.000 euros ... tiene que repercutir el
        IVA y el recargo sobre la misma base ... IVA devengado: (24.000 x
        21%): 5.040 euros / Recargo de equivalencia: (24.000 x 5,2%): 1.248
        euros" -> domestic general 21%, REPERCUTIDO, base=24.000, iva=5.040,
        recargo=1.248.

Registry mapping (M303 early-2024 revision):

    casilla 27 "Total cuota devengada" = projection of
      `iva.cuota-devengada-total` = iva.repercutido.general (17.430, ops
      7+8+9) + iva.repercutido.reducido (0) + iva.repercutido.super-reducido
      (0) + iva.autorepercutido.intracomunitaria (4.410, ops 2+4) +
      iva.autorepercutido.interior.devengado (0) +
      iva.autoconsumo.promotor.cuota (0) + casilla 18 (0) + casilla 21 (0) +
      casilla 24 recargo general (1.248, op 9) = 23.088 -> matches the
      manual's own "TOTAL CUOTA DEVENGADA: 23.088 euros" exactly.
    casilla 45 "Total a deducir" = projection of `iva.cuota-deducible-total`
      = iva.soportado.interiores (9.870, ops 1+3+5) +
      iva.soportado.importaciones (2.520, op 6) +
      iva.autorepercutido.intracomunitaria (4.410, ops 2+4, same casilla the
      devengado total also folds in - the self-assessed AIC cuota nets to
      zero across the two totals) + iva.autorepercutido.interior.deducible
      (0) = 16.800 -> matches the manual's own "TOTAL A DEDUCIR: 16.800
      euros" exactly.
    iva.resultado-regimen-general (form_number 46, [27]-[45]) = 23.088 -
      16.800 = 6.288 -> matches the manual's own "Diferencia: 6.288 euros".
    64 ([46]+[58]+[76]) = 6.288 (no regimen simplificado, no art-80.5
      regularizacion in this scenario).
    66 ([64]x[65]/100, [65]=100 territorio comun) = 6.288.
    iva.compensacion-aplicada-periodo (casilla 78,
      min([110], max(0, [46]))) = min(3.000, 6.288) = 3.000 -> matches the
      manual's own "Cuota a compensar de periodos anteriores: 3.000 euros, de
      las que aplicamos a este trimestre 3.000 euros" (casilla 110 fed via
      the `modelo-303-compensacion-pendiente-anteriores` previous_filing
      binding).
    casilla 69 "iva.resultado" ([66]+[77]+[68]-[78]) = 6.288+0+0-3.000 =
      3.288 -> the manual's own resultado ("Diferencia a ingresar: 3.288
      euros" is precisely this figure before the [69]-[70]+[109] rectificativa
      terms, which are all zero here - no rectificativa in this scenario).
    casilla 71 "Resultado final" ([69]-[70]+[109]) = 3.288-0+0 = 3.288 ->
      matches the manual's own "Diferencia a ingresar: 3.288 euros" exactly.
      THIS is the primary oracle target alongside 27 and 45.

Anti-tautology: this test does not hand-compute 23.088, 16.800, or 3.288 from
the registry's own ledger-aggregation-then-resultado-chain formulas under
test. Every raw base/iva/recargo line item quoted above is fed to the
registry as an :class:`IvaLedgerObservation`, and the four target casillas
(27, 45, `iva.resultado`, 71) are graded against the manual's own printed
"TOTAL CUOTA DEVENGADA", "TOTAL A DEDUCIR", and "Diferencia a ingresar"
figures. A companion test cross-validates the recargo-de-equivalencia
contribution to casilla 27 by dropping the recargo line and asserting the
figure changes by exactly the dropped amount (never a hand-computed absolute
figure) - a formula that silently excluded casilla 24 (recargo general
cuota), or that always returned a constant, would fail that check. The same
recargo-in-27 inclusion is independently cross-validated (in prose, not by
this test) across all four quarters of the SAME AEAT worked example (Cap. 9,
pag. 293-302): 1T 17.430+1.248+4.410=23.088; 2T
19.110+4.410+624-2.520=21.624; 3T 19.782-1.260+1.248+2.520=22.290; 4T
21.420-630+624=21.414 - every quarter's own printed "TOTAL CUOTA DEVENGADA"
sums its own "Recargo de equivalencia" line, confirming casilla 27 = suma de
[03]+[06]+[09]+[11]+[13]+[15]+[18]+[21]+[24]+[26] per the official Orden
EHA/3786/2008 casilla-27 instructions (the registry formula
`modelo-303-iva-cuota-devengada-total` was missing the [18]/[21]/[24] recargo
terms prior to this grounding; see the comment on that formula in
revision.toml).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from cadrumo.domain.calculations.registry.ledger_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
)

from .....core import (
    CasillaId,
    IvaDeductionFactKind,
    validated_casilla_id,
)
from .....core.resources import resources
from ....iva import (
    IvaCategory,
    IvaFlowDirection,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ._ledger_iva_aggregation_support import _deduction_provenance

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_CASILLA_27: CasillaId = validated_casilla_id("27", surface="_CASILLA_27")
_CASILLA_45: CasillaId = validated_casilla_id("45", surface="_CASILLA_45")
_CASILLA_RESULTADO_69: CasillaId = validated_casilla_id("iva.resultado", surface="_CASILLA_RESULTADO_69")
_CASILLA_71: CasillaId = validated_casilla_id("71", surface="_CASILLA_71")

# Per-casilla leaves the same 1T solucion states verbatim (pag. 293-294); see
# the module docstring for each quoted line.
_CASILLA_09: CasillaId = validated_casilla_id("09", surface="_CASILLA_09")
_CASILLA_11: CasillaId = validated_casilla_id("11", surface="_CASILLA_11")
_CASILLA_29: CasillaId = validated_casilla_id("29", surface="_CASILLA_29")
_CASILLA_33: CasillaId = validated_casilla_id("33", surface="_CASILLA_33")
_CASILLA_37: CasillaId = validated_casilla_id("37", surface="_CASILLA_37")
_CASILLA_RESULTADO_REGIMEN_GENERAL_46: CasillaId = validated_casilla_id(
    "iva.resultado-regimen-general",
    surface="_CASILLA_RESULTADO_REGIMEN_GENERAL_46",
)

_MANUAL_1T_LEAF_FIGURES: dict[CasillaId, Decimal] = {
    # "Total IVA devengado en Ventas interiores y servicios prestados
    # (83.000 x 21%): 17.430 euros" (pag. 293).
    _CASILLA_09: Decimal("17430.00"),
    # "Adquisiciones intracomunitarias: [(18.000(2) + 3.000(4))] x 21%:
    # 4.410 euros" (pag. 293) - the devengado leg of the self-assessed AIC.
    _CASILLA_11: Decimal("4410.00"),
    # "Total cuotas soportadas en operaciones interiores: 9.870 euros" (pag. 294).
    _CASILLA_29: Decimal("9870.00"),
    # "Por cuotas satisfechas en importaciones: (12.000(6) x 21%): 2.520
    # euros" (pag. 294).
    _CASILLA_33: Decimal("2520.00"),
    # "En adquisiciones intracomunitarias: [18.000(2) + 3.000(4)) x 21%]:
    # 4.410 euros" (pag. 294) - the deducible leg of the same AIC.
    _CASILLA_37: Decimal("4410.00"),
    # "Diferencia: 6.288 euros" (pag. 294) - form_number 46, [27]-[45].
    _CASILLA_RESULTADO_REGIMEN_GENERAL_46: Decimal("6288.00"),
}

_FILING_YEAR = 2024
_PERIOD = "1T"


def _op(
    ledger_id: str,
    *,
    day: int,
    category: IvaCategory,
    flow: IvaFlowDirection,
    base: Decimal,
    iva: Decimal,
    recargo: Decimal = Decimal("0"),
    rate_kind: IvaRateKind = IvaRateKind.GENERAL,
    deduction_fact_kind: IvaDeductionFactKind | None = None,
) -> IvaLedgerObservation:
    deduction_provenance = (
        _deduction_provenance(
            deduction_fact_kind,
            source_locator=f"test-ledger:{ledger_id}",
        )
        if deduction_fact_kind is not None
        else None
    )
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=date(2024, 1, day if day <= 28 else 28),
        category=category,
        rate_kind=rate_kind,
        flow_direction=flow,
        base_amount=base,
        iva_amount=iva,
        recargo_amount=recargo,
        deduction_fact_kind=deduction_fact_kind,
        deduction_provenance=deduction_provenance,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _quarter_observations(*, include_recargo: bool) -> tuple[IvaLedgerObservation, ...]:
    """The manual's ten primer-trimestre operations, as raw IvaLedgerObservation rows.

    ``include_recargo`` toggles ONLY the recargo_amount on operation (9) - the
    anti-tautology companion test uses this to isolate the recargo
    contribution to casilla 27 without hand-computing an absolute figure.
    """
    return (
        _op(
            "op1-compra-motores",
            day=5,
            category=IvaCategory.DOMESTIC_GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            base=Decimal("36000.00"),
            iva=Decimal("7560.00"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        ),
        _op(
            "op2-compra-chapa-intracomunitaria",
            day=7,
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            base=Decimal("18000.00"),
            iva=Decimal("3780.00"),
            deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
        ),
        _op(
            "op3-servicios-abogado",
            day=8,
            category=IvaCategory.DOMESTIC_GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            base=Decimal("6000.00"),
            iva=Decimal("1260.00"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        ),
        _op(
            "op4-transporte-intracomunitario",
            day=9,
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            base=Decimal("3000.00"),
            iva=Decimal("630.00"),
            deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
        ),
        _op(
            "op5-alquiler-local",
            day=1,
            category=IvaCategory.DOMESTIC_GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            base=Decimal("5000.00"),
            iva=Decimal("1050.00"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
        ),
        _op(
            "op6-importacion-marruecos",
            day=20,
            category=IvaCategory.IMPORT_THIRD_COUNTRY,
            flow=IvaFlowDirection.SOPORTADO,
            base=Decimal("12000.00"),
            iva=Decimal("2520.00"),
            deduction_fact_kind=IvaDeductionFactKind.IMPORT_CURRENT,
        ),
        _op(
            "op7-ventas-mayorista",
            day=10,
            category=IvaCategory.DOMESTIC_GENERAL,
            flow=IvaFlowDirection.REPERCUTIDO,
            base=Decimal("55000.00"),
            iva=Decimal("11550.00"),
        ),
        _op(
            "op8-montajes-arreglos",
            day=15,
            category=IvaCategory.DOMESTIC_GENERAL,
            flow=IvaFlowDirection.REPERCUTIDO,
            base=Decimal("4000.00"),
            iva=Decimal("840.00"),
        ),
        _op(
            "op9-ventas-recargo-equivalencia",
            day=18,
            category=IvaCategory.DOMESTIC_GENERAL,
            flow=IvaFlowDirection.REPERCUTIDO,
            base=Decimal("24000.00"),
            iva=Decimal("5040.00"),
            recargo=Decimal("1248.00") if include_recargo else Decimal("0"),
        ),
    )


def _calculate(*, include_recargo: bool) -> RegistryCalculationResult:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=_FILING_YEAR, period=_PERIOD)
    binding_values = {
        # "Cuota a compensar de periodos anteriores: 3.000 euros" (pag. 294).
        "modelo-303-compensacion-pendiente-anteriores": Decimal("3000.00"),
        "modelo-303-autoconsumo-promotor-base": Decimal("0"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        **resolve_ledger_iva_aggregation_binding_values(
            snapshot.revision,
            _quarter_observations(include_recargo=include_recargo),
        ),
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2024, 3, 31)},
    )


def test_m303_2024_1t_manual_worked_example_devengada_deducible_resultado() -> None:
    """27/45/69/71 = 23.088 / 16.800 / 3.288 / 3.288 for the manual's 1T solucion.

    Oracle: AEAT Manual practico IVA 2024, Cap. 9, pag. 293-294, "Liquidacion
    primer trimestre" - "TOTAL CUOTA DEVENGADA: 23.088 euros", "TOTAL A
    DEDUCIR: 16.800 euros", "Diferencia a ingresar: 3.288 euros". Every raw
    base/iva/recargo figure feeding the scenario is quoted verbatim from the
    manual's per-operation breakdown; see the module docstring for the full
    per-casilla trace.
    """
    result = _calculate(include_recargo=True)

    assert result.values[_CASILLA_27] == Decimal("23088.00")
    assert result.values[_CASILLA_45] == Decimal("16800.00")
    assert result.values[_CASILLA_RESULTADO_69] == Decimal("3288.00")
    assert result.values[_CASILLA_71] == Decimal("3288.00")


def test_m303_2024_1t_manual_worked_example_per_casilla_leaves() -> None:
    """Each leaf the manual states verbatim is reproduced in its own casilla.

    Oracle: the same "Liquidacion primer trimestre" solucion (pag. 293-294)
    prints six per-casilla figures alongside the two totals - 17.430 (09),
    4.410 (11), 9.870 (29), 2.520 (33), 4.410 (37) and "Diferencia: 6.288"
    (iva.resultado-regimen-general, form_number 46). Grading the leaves and not
    only ``27``/``45`` closes the compensating-error gap: two offsetting
    mistakes inside the devengado or deducible sum leave both totals correct,
    so a leaf-blind gate stays green while the individual boxes an operator
    files are wrong. Each expected figure is the manual's own printed euro
    amount, never a hand-run of the registry formula under test.
    """
    result = _calculate(include_recargo=True)

    for casilla_id, expected in _MANUAL_1T_LEAF_FIGURES.items():
        assert result.values[casilla_id] == expected, (
            f"casilla {casilla_id!r}: manual states {expected}, engine computed {result.values[casilla_id]}"
        )


def test_casilla_27_anti_tautology_recargo_changes_total_cuota_devengada() -> None:
    """Dropping op (9)'s recargo must lower casilla 27 by exactly the dropped amount.

    Anti-tautology: casilla 27's own formula is a sum over nine devengado
    components, three of which (casillas 18/21/24) are the recargo-de-
    equivalencia cuota tiers - the terms this test isolates. It does not
    hand-compute the with-recargo absolute figure (that is graded against the
    manual's own printed 23.088 in the primary test above); it only asserts
    the delta between the with-recargo and without-recargo scenarios equals
    the dropped recargo_amount, mirroring the ``!=``-only anti-tautology
    pattern used elsewhere in this test suite. A formula that ignored the
    recargo terms, or always returned a constant, would fail this check.
    """
    with_recargo = _calculate(include_recargo=True)
    without_recargo = _calculate(include_recargo=False)

    assert with_recargo.values[_CASILLA_27] - without_recargo.values[_CASILLA_27] == Decimal("1248.00")
    # The recargo cuota is devengado-only (no matching deducible leg), so it
    # is not netted anywhere else in the resultado chain: the resultado-side
    # casillas must shift by exactly the same 1.248,00 EUR.
    assert with_recargo.values[_CASILLA_71] - without_recargo.values[_CASILLA_71] == Decimal("1248.00")


def test_m303_2024_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The manual-oracle grounding of 27/45/69/71 is enrolled, not just computed.

    A companion registry-honesty gate
    (``test_external_oracle_grounding_enrolled.py``, generalised beyond M100
    in this same change) already proves the ``externally_grounded_casilla_ids``
    declaration on the ``modelo-303-iva-chain-verification`` verification
    expectation is backed by the bundled
    ``corpus/manual_oracles/modelo-303-2024-regimen-general-recargo-intracomunitaria-importacion.json``
    evidence. This test proves the OTHER end of the wire: that the
    declaration actually reaches the live, VALIDATED
    :class:`RegistryVerificationPolicy` fold, so 27/45/69/71 raise
    ``independently_grounded_fraction`` above zero for M303 rather than
    sitting inert in TOML. Not tautological: the grounded set and the
    fraction are read from the registry's own declared+validated data, never
    hand-computed or asserted from a synthetic fixture.
    """
    authority = registry_authority
    snapshot = authority.snapshot("303", filing_year=_FILING_YEAR, period=_PERIOD)
    policy = snapshot.verification_policy()

    grounded_here = (
        _CASILLA_27,
        _CASILLA_45,
        _CASILLA_RESULTADO_69,
        _CASILLA_71,
        *_MANUAL_1T_LEAF_FIGURES,
    )
    for casilla_id in grounded_here:
        assert casilla_id in policy.externally_grounded_casilla_ids

    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids
    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )

    assert _CASILLA_71 in externally_grounded
    assert independently_grounded_fraction > 0.0
