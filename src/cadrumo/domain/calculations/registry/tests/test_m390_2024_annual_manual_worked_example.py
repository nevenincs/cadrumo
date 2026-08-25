"""Oracle test for M390 2024 annual resumen casillas grounded against the
AEAT Manual practico IVA 2024's own worked example (Cap. 9, "La declaracion-
resumen anual. Modelo 390"), summed across all four trimestres.

Ground truth (bundled AEAT Manual practico IVA 2024):

    raw_evidence_locator: corpus/manuals/iva/2024/source.pdf#Pag.293-302

The manual's "Supuesto practico" (pag. 292-302) follows "el senor 'X'"
(fabricacion de aparatos electrodomesticos, epigrafe IAE 345.1) through a full
calendar year of Modelo 303 quarterly liquidaciones feeding the annual Modelo
390 resumen. Chapter 9 never prints a single casilla-keyed M390 annual table
(the M390 casillas this revision computes are internal reconciliation
aggregates, not literal AEAT DR-390 box numbers - see
``iva.anual.cuota-devengada-total`` in ``casillas/civa.anual.repercutido.general__civa.anual.resultado-regimen-general.toml``), so
this test grounds the annual totals as the SUM of the manual's own four
printed quarterly "Liquidacion" solucion lines - itself simple arithmetic
over AEAT's own stated subtotals, never a hand-run of the registry formula
under test:

    1T (pag. 293): "TOTAL CUOTA DEVENGADA: 23.088 euros",
                    "TOTAL A DEDUCIR: 16.800 euros"
    2T (pag. 297): "TOTAL CUOTA DEVENGADA: 21.624 euros",
                    "TOTAL A DEDUCIR: 23.730 euros"
    3T (pag. 300): "TOTAL CUOTA DEVENGADA: 22.290 euros",
                    "TOTAL A DEDUCIR: 4.032 euros"
    4T (pag. 302): "TOTAL CUOTA DEVENGADA: 21.414 euros",
                    "TOTAL A DEDUCIR: 23.640 euros"

    Devengada anual = 23.088+21.624+22.290+21.414 = 88.416
    Deducible anual = 16.800+23.730+4.032+23.640  = 68.202
    Resultado anual  = 88.416-68.202               = 20.214

Each quarter's own printed "TOTAL CUOTA DEVENGADA" itself sums that quarter's
own printed "Recargo de equivalencia" line (1T 1.248, 2T 624, 3T 1.248,
4T 624 = 3.744 anual, LIVA art. 161) - the same cross-quarter fact the M303
casilla-27 grounding used (see
test_m303_2024_regimen_general_manual_worked_example.py).

Per-quarter category breakdown fed to the registry as :class:`IvaLedgerObservation`
rows (each row's base/iva/recargo is the manual's own printed per-quarter
category subtotal, net of that same quarter's own printed rectificacion
lines when the manual states one - never a hand-derived absolute figure).
Aggregation ``sum`` is associative, so one row carrying a pre-summed
base/iva/recargo resolves identically to N rows summing to the same totals:

    1T (pag. 292-293):
      domestic_general REPERCUTIDO: "Ventas interiores ... + Servicios
        prestados ... Total IVA devengado en Ventas interiores y servicios
        prestados (83.000 x 21%): 17.430 euros" -> base=83.000, iva=17.430;
        recargo "(24.000(9) x 5,2%): 1.248 euros" -> recargo=1.248.
      AIC (autorepercutido intracomunitaria): "Adquisiciones intracomunitarias:
        [(18.000(2) + 3.000(4))] x 21%: 4.410 euros" -> base=21.000, iva=4.410.
      domestic_general SOPORTADO: "Total cuotas soportadas en operaciones
        interiores: 9.870 euros" -> base=47.000 (36.000+6.000+5.000),
        iva=9.870.
      import_third_country SOPORTADO: "Por cuotas satisfechas en
        importaciones: (12.000(6) x 21%): 2.520 euros" -> base=12.000,
        iva=2.520.

    2T (pag. 296-297): the manual's own devengado total nets a
      "Rectificacion IVA devengado [(-6.000(27) - 6.000(25)) x 21%]:
      -2.520 euros" line, where op(27) is a plain domestic sale return and
      op(25) is an AIC correction ("Devuelve a Holanda productos
      defectuosos de los comprados en el punto (19) ... IVA devengado y
      soportado: (-6.000 x 21%): -1.260 euros"), and the deducible total
      separately nets "Rectificacion de deducciones: (-6.000(25) x 21%):
      -1.260 euros" (the same AIC correction's deducible leg):
      domestic_general REPERCUTIDO: "Total IVA Devengado en Ventas
        interiores y servicios prestados (91.000 x 21%): 19.110 euros" net
        of op(27)'s -1.260/-6.000 domestic correction -> base=85.000
        (91.000-6.000), iva=17.850 (19.110-1.260); recargo "(12.000(14) x
        5,2%): 624 euros" -> recargo=624.
      AIC: "Adquisiciones intracomunitarias: [(3.000(16) + 18.000(19))
        x 21%]: 4.410 euros" net of op(25)'s -1.260/-6.000 AIC correction
        (shared identically by the devengado and deducible legs, since
        both read the SAME iva.anual.autorepercutido.intracomunitaria
        casilla) -> base=15.000 (21.000-6.000), iva=3.150 (4.410-1.260).
      domestic_general SOPORTADO: "Total cuotas soportadas en
        operaciones interiores: 13.020 euros" (corrientes 11.970 +
        bienes de inversion 1.050) -> base=62.000 (57.000+5.000),
        iva=13.020.
      import_third_country SOPORTADO: "(36.000(11) x 21%): 7.560 euros"
        -> base=36.000, iva=7.560.

    3T (pag. 299-300): devengado nets "Devolucion de ventas: (-6.000(38)
      x 21%): -1.260 euros" (a plain domestic return, no AIC leg this
      quarter):
      domestic_general REPERCUTIDO: "Ventas interiores: [...] : 19.782
        euros" net of the -1.260/-6.000 devolucion -> base=88.200
        (94.200-6.000), iva=18.522 (19.782-1.260); recargo "(24.000(32) x
        5,2%): 1.248 euros" -> recargo=1.248.
      AIC: "Adquisiciones intracomunitarias: (12.000(36) x 21%): 2.520
        euros" (no correction this quarter) -> base=12.000, iva=2.520.
      domestic_general SOPORTADO: "Servicios recibidos: (1.200(39) x
        21%): 252 euros" -> base=1.200, iva=252.
      import_third_country SOPORTADO: "(6.000(31) x 21%): 1.260 euros"
        -> base=6.000, iva=1.260.

    4T (pag. 301-302): devengado nets "Devolucion de mercancias: -3.000(46)
      x 21%: -630 euros" (no AIC this quarter - op(47)'s AIC anticipo
      explicitly "no devengan el IVA"):
      domestic_general REPERCUTIDO: "Ventas interiores:[(12.000(45) +
        90.000(49))x 21%]: 21.420 euros" net of the -630/-3.000 devolucion
        -> base=99.000 (102.000-3.000), iva=20.790 (21.420-630); recargo
        "(12.000(45) x 5,2%): 624 euros" -> recargo=624.
      domestic_general SOPORTADO: "[(12.000(42) + 72.000(53)) x 21%]:
        17.640 euros" plus "Facturas pendientes de recibir: (18.000(44) x
        21%): 3.780 euros" plus "Rectificacion deduccion (-18.000(43) x
        21%): -3.780 euros" (the pending-invoice and its rectification
        net to zero) -> base=84.000 (12.000+72.000+18.000-18.000),
        iva=17.640 (17.640+3.780-3.780).
      domestic_reduced SOPORTADO: "Compras realizadas: (60.000(41) x
        10%): 6.000 euros" (op(41), "Le repercuten el 10% en lugar del
        21%. No puede deducirse mas de lo que le han repercutido") ->
        base=60.000, iva=6.000.
      (no import_third_country this quarter.)

Cross-check: summing each quarter's fed observations reproduces that
quarter's own manual-printed TOTAL CUOTA DEVENGADA / TOTAL A DEDUCIR exactly
(1T 23.088/16.800, 2T 21.624/23.730, 3T 22.290/4.032, 4T 21.414/23.640,
matching the module docstring above), which is itself the anti-tautology
proof that the per-quarter observation set is faithful to the manual before
ever reaching the annual M390 formula under test.

Registry mapping (the M390 revision law-selected for ejercicio 2024):

    iva.anual.cuota-devengada-total = repercutido.general (iva sum across all
      four quarters = 17.430+17.850+18.522+20.790 = 74.592) +
      repercutido.reducido (0, no reduced-rate sales) +
      repercutido.super-reducido (0) +
      autorepercutido.intracomunitaria (iva sum = 4.410+3.150+2.520+0 =
      10.080) + repercutido.recargo.general (recargo sum =
      1.248+624+1.248+624 = 3.744) + repercutido.recargo.reducido (0) =
      74.592+10.080+3.744 = 88.416 -> matches the sum of the manual's own
      four quarterly "TOTAL CUOTA DEVENGADA" lines exactly.
    iva.anual.cuota-deducible-total = soportado.interiores (general iva sum
      9.870+13.020+252+17.640=40.782, plus reduced 6.000 = 46.782) +
      soportado.importaciones (2.520+7.560+1.260+0=11.340) +
      autorepercutido.intracomunitaria (same shared casilla, 10.080) =
      46.782+11.340+10.080 = 68.202 -> matches the sum of the manual's own
      four quarterly "TOTAL A DEDUCIR" lines exactly.
    iva.anual.resultado-regimen-general = 88.416-68.202 = 20.214 -> matches
      the manual's own annual devengada-minus-deducible arithmetic exactly.

Anti-tautology: this test does not hand-compute 88.416, 68.202, or 20.214
from the registry's own annual-aggregation formulas under test. Every raw
per-quarter base/iva/recargo figure quoted above is the manual's own printed
subtotal (net of the manual's own printed rectificacion lines where stated),
fed to the registry as :class:`IvaLedgerObservation` rows, and the three
target casillas are graded against the manual's own four-quarter arithmetic.
A companion test cross-validates the recargo contribution to the annual
devengada total by dropping every quarter's recargo_amount and asserting the
delta equals the dropped total exactly (never a hand-computed absolute
figure) - the same fix this revision needed once already had (recall
casilla 27 on the applicable Modelo 303 epoch, which the M303 grounding pass
found silently excluded the recargo de equivalencia cuota tiers). Before
this fix, ``iva.anual.cuota-devengada-total`` resolved to 84.672
(88.416 - 3.744, the annual recargo total) - a modelling gap symmetrical to
the pre-fix M303 casilla 27 defect - which would also have failed the
``modelo-390-cuota-devengada-total-equals-reconciliacion-303`` BLOCKING_RULE
for any recargo-de-equivalencia filer (that predicate reconciles against the
sum of the four FILED Modelo 303 quarters' casilla 27, which DOES include
recargo).
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

from .....core import CasillaId, IvaDeductionFactKind, validated_casilla_id
from .....core.resources import resources
from ....iva import (
    IvaCategory,
    IvaFlowDirection,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ._ledger_iva_aggregation_support import _deduction_provenance

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_CASILLA_DEVENGADA: CasillaId = validated_casilla_id(
    "iva.anual.cuota-devengada-total",
    surface="_CASILLA_DEVENGADA",
)
_CASILLA_DEDUCIBLE: CasillaId = validated_casilla_id(
    "iva.anual.cuota-deducible-total",
    surface="_CASILLA_DEDUCIBLE",
)
_CASILLA_PRORRATA_REGULARIZACION: CasillaId = validated_casilla_id(
    "iva.anual.regularizacion-prorrata-definitiva",
    surface="_CASILLA_PRORRATA_REGULARIZACION",
)
_CASILLA_RESULTADO: CasillaId = validated_casilla_id(
    "iva.anual.resultado-regimen-general",
    surface="_CASILLA_RESULTADO",
)
_CASILLA_TOTAL_BASES_CUOTAS_IVA: CasillaId = validated_casilla_id(
    "iva.anual.total-bases-cuotas-iva",
    surface="_CASILLA_TOTAL_BASES_CUOTAS_IVA",
)
_M390_BIENES_INVERSION_REGULARIZACION_BINDING = "modelo-390-bienes-inversion-regularizacion-casilla-63"

_FILING_YEAR = 2024
_PERIOD = "0A"


def _dg_repercutido(ledger_id: str, *, day_month: tuple[int, int], base: Decimal, iva: Decimal, recargo: Decimal):
    month, day = day_month
    return {
        "ledger_id": ledger_id,
        "transaction_date": date(2024, month, day),
        "category": IvaCategory.DOMESTIC_GENERAL,
        "rate_kind": IvaRateKind.GENERAL,
        "flow_direction": IvaFlowDirection.REPERCUTIDO,
        "base_amount": base,
        "iva_amount": iva,
        "recargo_amount": recargo,
    }


def _aic(ledger_id: str, *, day_month: tuple[int, int], base: Decimal, iva: Decimal):
    month, day = day_month
    return {
        "ledger_id": ledger_id,
        "transaction_date": date(2024, month, day),
        "category": IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        "rate_kind": IvaRateKind.GENERAL,
        "flow_direction": IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        "base_amount": base,
        "iva_amount": iva,
        "deduction_fact_kind": IvaDeductionFactKind.INTRA_EU_CURRENT,
        "deduction_provenance": _deduction_provenance(
            IvaDeductionFactKind.INTRA_EU_CURRENT,
            source_locator=f"manual-iva-2024:{ledger_id}",
        ),
    }


def _dg_soportado(ledger_id: str, *, day_month: tuple[int, int], base: Decimal, iva: Decimal):
    month, day = day_month
    return {
        "ledger_id": ledger_id,
        "transaction_date": date(2024, month, day),
        "category": IvaCategory.DOMESTIC_GENERAL,
        "rate_kind": IvaRateKind.GENERAL,
        "flow_direction": IvaFlowDirection.SOPORTADO,
        "base_amount": base,
        "iva_amount": iva,
        "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_CURRENT,
        "deduction_provenance": _deduction_provenance(
            IvaDeductionFactKind.DOMESTIC_CURRENT,
            source_locator=f"manual-iva-2024:{ledger_id}",
        ),
    }


def _dr_soportado(ledger_id: str, *, day_month: tuple[int, int], base: Decimal, iva: Decimal):
    month, day = day_month
    return {
        "ledger_id": ledger_id,
        "transaction_date": date(2024, month, day),
        "category": IvaCategory.DOMESTIC_REDUCED,
        "rate_kind": IvaRateKind.REDUCED,
        "flow_direction": IvaFlowDirection.SOPORTADO,
        "base_amount": base,
        "iva_amount": iva,
        "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_CURRENT,
        "deduction_provenance": _deduction_provenance(
            IvaDeductionFactKind.DOMESTIC_CURRENT,
            source_locator=f"manual-iva-2024:{ledger_id}",
        ),
    }


def _import_soportado(ledger_id: str, *, day_month: tuple[int, int], base: Decimal, iva: Decimal):
    month, day = day_month
    return {
        "ledger_id": ledger_id,
        "transaction_date": date(2024, month, day),
        "category": IvaCategory.IMPORT_THIRD_COUNTRY,
        "rate_kind": IvaRateKind.GENERAL,
        "flow_direction": IvaFlowDirection.SOPORTADO,
        "base_amount": base,
        "iva_amount": iva,
        "deduction_fact_kind": IvaDeductionFactKind.IMPORT_CURRENT,
        "deduction_provenance": _deduction_provenance(
            IvaDeductionFactKind.IMPORT_CURRENT,
            source_locator=f"manual-iva-2024:{ledger_id}",
        ),
    }


def _annual_observations(*, include_recargo: bool) -> tuple[IvaLedgerObservation, ...]:
    """The manual's four trimestres, as net per-quarter category aggregate rows.

    ``include_recargo`` toggles ONLY the recargo_amount on the four
    domestic-general-repercutido rows - the anti-tautology companion test
    uses this to isolate the recargo contribution to the annual devengada
    total without hand-computing an absolute figure.
    """

    def _recargo(value: Decimal) -> Decimal:
        return value if include_recargo else Decimal("0")

    rows = (
        # 1T (pag. 292-293).
        _dg_repercutido(
            "1t-devengado-general",
            day_month=(1, 31),
            base=Decimal("83000.00"),
            iva=Decimal("17430.00"),
            recargo=_recargo(Decimal("1248.00")),
        ),
        _aic("1t-aic", day_month=(1, 15), base=Decimal("21000.00"), iva=Decimal("4410.00")),
        _dg_soportado("1t-soportado-general", day_month=(1, 10), base=Decimal("47000.00"), iva=Decimal("9870.00")),
        _import_soportado("1t-importacion", day_month=(1, 20), base=Decimal("12000.00"), iva=Decimal("2520.00")),
        # 2T (pag. 296-297).
        _dg_repercutido(
            "2t-devengado-general",
            day_month=(5, 31),
            base=Decimal("85000.00"),
            iva=Decimal("17850.00"),
            recargo=_recargo(Decimal("624.00")),
        ),
        _aic("2t-aic", day_month=(5, 15), base=Decimal("15000.00"), iva=Decimal("3150.00")),
        _dg_soportado("2t-soportado-general", day_month=(5, 10), base=Decimal("62000.00"), iva=Decimal("13020.00")),
        _import_soportado("2t-importacion", day_month=(4, 5), base=Decimal("36000.00"), iva=Decimal("7560.00")),
        # 3T (pag. 299-300).
        _dg_repercutido(
            "3t-devengado-general",
            day_month=(8, 31),
            base=Decimal("88200.00"),
            iva=Decimal("18522.00"),
            recargo=_recargo(Decimal("1248.00")),
        ),
        _aic("3t-aic", day_month=(8, 20), base=Decimal("12000.00"), iva=Decimal("2520.00")),
        _dg_soportado("3t-soportado-general", day_month=(9, 5), base=Decimal("1200.00"), iva=Decimal("252.00")),
        _import_soportado("3t-importacion", day_month=(8, 10), base=Decimal("6000.00"), iva=Decimal("1260.00")),
        # 4T (pag. 301-302). No AIC and no import_third_country this quarter.
        _dg_repercutido(
            "4t-devengado-general",
            day_month=(11, 30),
            base=Decimal("99000.00"),
            iva=Decimal("20790.00"),
            recargo=_recargo(Decimal("624.00")),
        ),
        _dg_soportado("4t-soportado-general", day_month=(10, 15), base=Decimal("84000.00"), iva=Decimal("17640.00")),
        _dr_soportado("4t-soportado-reducido", day_month=(10, 1), base=Decimal("60000.00"), iva=Decimal("6000.00")),
    )
    return tuple(
        IvaLedgerObservation(
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
            **row,
        )
        for row in rows
    )


def _calculate(
    *,
    include_recargo: bool,
    regularizacion_prorrata: Decimal | None = None,
) -> RegistryCalculationResult:
    snapshot = resources().modelos.authority.snapshot("390", filing_year=_FILING_YEAR, period=_PERIOD)
    binding_values: dict[str, Decimal] = {
        # This scenario grounds only the ledger-derived annual totals against
        # the manual's own four-quarter arithmetic; it does not exercise the
        # cross-modelo Modelo 303 reconciliation (relation_prefill /
        # iva_compensation_annual_partition) bindings, which read prior filed
        # 303 quarters this test never files. Every bound casilla still needs
        # a resolved fact, so these are pinned to zero.
        _M390_BIENES_INVERSION_REGULARIZACION_BINDING: Decimal("0"),
        "modelo-390-prev-303-cuota-devengada-total": Decimal("0"),
        "modelo-390-prev-303-cuota-deducible-total": Decimal("0"),
        "modelo-390-prev-303-resultado-regimen-general": Decimal("0"),
        "modelo-390-prev-303-compensacion-ultimo-periodo": Decimal("0"),
        "modelo-390-prev-303-compensacion-generada-ejercicio-no-97": Decimal("0"),
        **resolve_ledger_iva_aggregation_binding_values(
            snapshot.revision,
            _annual_observations(include_recargo=include_recargo),
        ),
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    if regularizacion_prorrata is not None:
        inputs = {**inputs, _CASILLA_PRORRATA_REGULARIZACION: regularizacion_prorrata}
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2025, 1, 30)},
    )


def test_m390_2024_annual_manual_worked_example_devengada_deducible_resultado() -> None:
    """Annual devengada/deducible/resultado = 88.416 / 68.202 / 20.214.

    Oracle: AEAT Manual practico IVA 2024, Cap. 9, pag. 293-302, the sum of
    the manual's own four printed quarterly "TOTAL CUOTA DEVENGADA" /
    "TOTAL A DEDUCIR" solucion lines. Every raw base/iva/recargo figure
    feeding the scenario is quoted verbatim (or netted per the manual's own
    printed rectificacion lines) from the manual's per-quarter breakdown;
    see the module docstring for the full per-casilla trace.
    """
    result = _calculate(include_recargo=True)

    assert result.values[_CASILLA_DEVENGADA] == Decimal("88416.00")
    assert result.values[_CASILLA_DEDUCIBLE] == Decimal("68202.00")
    assert result.values[_CASILLA_RESULTADO] == Decimal("20214.00")


def test_m390_box_34_excludes_recargo_while_box_47_includes_it() -> None:
    """Box [34] "Total bases y cuotas IVA - Cuota" (page 02) must equal the
    IVA-only total, excluding recargo de equivalencia; box [47] "Total cuotas
    IVA y recargo equivalencia" (page 02 bis) is the recargo-INCLUSIVE total.

    Oracle: the same AEAT Manual practico IVA 2024 four-quarter arithmetic
    the sibling test above grounds ``iva.anual.cuota-devengada-total`` (box
    [47]) against -- 88.416,00 EUR, of which 3.744,00 EUR is the manual's own
    four printed "Recargo de equivalencia" lines (1T 1.248, 2T 624, 3T 1.248,
    4T 624). The expected box [34] figure, 84.672,00 EUR, is simple
    arithmetic over those two bundled AEAT figures (88.416 - 3.744), never a
    hand-run of the registry's ``iva.anual.total-bases-cuotas-iva`` formula
    under test.

    Anti-tautology companion: dropping every quarter's recargo must leave box
    [34] UNCHANGED (it never depended on the recargo terms) while box [47]
    drops by exactly the dropped amount -- proving the two totals draw from
    disjoint formula membership, not merely different labels on one shared
    value.
    """
    with_recargo = _calculate(include_recargo=True)
    without_recargo = _calculate(include_recargo=False)

    assert with_recargo.values[_CASILLA_TOTAL_BASES_CUOTAS_IVA] == Decimal("84672.00")
    assert with_recargo.values[_CASILLA_DEVENGADA] == Decimal("88416.00")
    assert with_recargo.values[_CASILLA_DEVENGADA] - with_recargo.values[_CASILLA_TOTAL_BASES_CUOTAS_IVA] == Decimal(
        "3744.00"
    )

    assert (
        without_recargo.values[_CASILLA_TOTAL_BASES_CUOTAS_IVA] == with_recargo.values[_CASILLA_TOTAL_BASES_CUOTAS_IVA]
    )
    assert with_recargo.values[_CASILLA_DEVENGADA] - without_recargo.values[_CASILLA_DEVENGADA] == Decimal("3744.00")


def test_m390_annual_devengada_anti_tautology_recargo_changes_total() -> None:
    """Dropping every quarter's recargo must lower the annual devengada total
    by exactly the dropped amount.

    Anti-tautology: the annual devengada formula is a sum over six
    components, two of which (``iva.anual.repercutido.recargo.general`` /
    ``.reducido``) are the recargo-de-equivalencia cuota tiers this test
    isolates. It does not hand-compute the with-recargo absolute figure
    (that is graded against the manual's own four-quarter sum above); it
    only asserts the delta between the with-recargo and without-recargo
    scenarios equals the dropped recargo_amount total (1.248+624+1.248+624=
    3.744), mirroring the M303 casilla-27 anti-tautology pattern. A formula
    that ignored the recargo terms, or always returned a constant, would
    fail this check - it is exactly the defect this grounding pass fixed.
    """
    with_recargo = _calculate(include_recargo=True)
    without_recargo = _calculate(include_recargo=False)

    assert with_recargo.values[_CASILLA_DEVENGADA] - without_recargo.values[_CASILLA_DEVENGADA] == Decimal("3744.00")
    # Recargo is devengado-only (no matching deducible leg), so the deducible
    # total and, therefore, the resultado must shift by exactly the same
    # 3.744,00 EUR.
    assert with_recargo.values[_CASILLA_DEDUCIBLE] == without_recargo.values[_CASILLA_DEDUCIBLE]
    assert with_recargo.values[_CASILLA_RESULTADO] - without_recargo.values[_CASILLA_RESULTADO] == Decimal("3744.00")


def test_m390_prorrata_regularizacion_flows_to_deducciones_and_resultado() -> None:
    """A nonzero box 522 raises annual deductions and lowers the net result.

    The check is delta-based: it runs the existing registry calculation twice
    with identical AEAT-manual observation inputs and changes only the
    operator-supplied box 522 value. It therefore proves formula membership
    without reimplementing the annual deductible-total formula in the test.
    """
    regularizacion = Decimal("1234.56")
    without_regularizacion = _calculate(include_recargo=True)
    with_regularizacion = _calculate(include_recargo=True, regularizacion_prorrata=regularizacion)

    assert with_regularizacion.values[_CASILLA_DEVENGADA] == without_regularizacion.values[_CASILLA_DEVENGADA]
    assert (
        with_regularizacion.values[_CASILLA_DEDUCIBLE] - without_regularizacion.values[_CASILLA_DEDUCIBLE]
        == regularizacion
    )
    assert (
        without_regularizacion.values[_CASILLA_RESULTADO] - with_regularizacion.values[_CASILLA_RESULTADO]
        == regularizacion
    )


def _dr_super_reducido_repercutido(
    ledger_id: str,
    *,
    day_month: tuple[int, int],
    base: Decimal,
    iva: Decimal,
    recargo: Decimal,
):
    month, day = day_month
    return {
        "ledger_id": ledger_id,
        "transaction_date": date(2024, month, day),
        "category": IvaCategory.DOMESTIC_SUPER_REDUCED,
        "rate_kind": IvaRateKind.SUPER_REDUCED,
        "flow_direction": IvaFlowDirection.REPERCUTIDO,
        "base_amount": base,
        "iva_amount": iva,
        "recargo_amount": recargo,
    }


def _calculate_with_super_reducido_recargo(*, include_super_reducido_recargo: bool) -> RegistryCalculationResult:
    """The manual's 1T scenario plus one synthetic super-reducido (4pct) sale.

    The AEAT manual worked example this module grounds against charges no
    super-reducido recargo (the manual's own ``el senor 'X'`` scenario has no
    4pct-rate operations), so the 0.5pct tier cannot be graded against a
    bundled oracle figure; this scenario is therefore synthetic and
    structural, proving the mechanism the same delta-based way the
    general/reducido tiers are proven above rather than asserting an absolute
    figure the manual never states.
    """
    snapshot = resources().modelos.authority.snapshot("390", filing_year=_FILING_YEAR, period=_PERIOD)
    observations = (
        *_annual_observations(include_recargo=True),
        IvaLedgerObservation(
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
            **_dr_super_reducido_repercutido(
                "synthetic-super-reducido-recargo-equivalencia",
                day_month=(6, 30),
                base=Decimal("10000.00"),
                iva=Decimal("400.00"),
                recargo=Decimal("50.00") if include_super_reducido_recargo else Decimal("0"),
            ),
        ),
    )
    binding_values: dict[str, Decimal] = {
        _M390_BIENES_INVERSION_REGULARIZACION_BINDING: Decimal("0"),
        "modelo-390-prev-303-cuota-devengada-total": Decimal("0"),
        "modelo-390-prev-303-cuota-deducible-total": Decimal("0"),
        "modelo-390-prev-303-resultado-regimen-general": Decimal("0"),
        "modelo-390-prev-303-compensacion-ultimo-periodo": Decimal("0"),
        "modelo-390-prev-303-compensacion-generada-ejercicio-no-97": Decimal("0"),
        **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations),
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2025, 1, 30)},
    )


def test_m390_super_reducido_recargo_delta() -> None:
    """Adding a super-reducido (0.5pct) recargo line raises the annual devengada total.

    Closes the residual gap the general/reducido tiers left: before this fix,
    ``iva.anual.cuota-devengada-total`` had no ``iva.anual.repercutido.recargo.
    super-reducido`` casilla, binding, or formula term at all — a
    recargo-de-equivalencia filer whose supplier charged the 4pct
    super-reducido rate (and therefore the 0.5pct recargo, LIVA art. 161) had
    that tier's annual cuota silently excluded, symmetrically breaking
    ``modelo-390-cuota-devengada-total-equals-reconciliacion-303`` for that
    filer the same way the pre-fix general/reducido omission did.

    Anti-tautology: this does not hand-compute the with-recargo absolute
    figure from the registry's own formula under test. It runs the full
    calculation engine twice — once with a super-reducido recargo ledger
    observation, once with the identical scenario but that recargo zeroed —
    and asserts the delta equals exactly the dropped recargo_amount. A
    formula that ignored the super-reducido recargo term, or always returned
    a constant, would fail this check.
    """
    with_recargo = _calculate_with_super_reducido_recargo(include_super_reducido_recargo=True)
    without_recargo = _calculate_with_super_reducido_recargo(include_super_reducido_recargo=False)

    assert with_recargo.values[_CASILLA_DEVENGADA] - without_recargo.values[_CASILLA_DEVENGADA] == Decimal("50.00")
    # Recargo is devengado-only (no matching deducible leg), so the deducible
    # total is unchanged and the resultado shifts by exactly the same amount.
    assert with_recargo.values[_CASILLA_DEDUCIBLE] == without_recargo.values[_CASILLA_DEDUCIBLE]
    assert with_recargo.values[_CASILLA_RESULTADO] - without_recargo.values[_CASILLA_RESULTADO] == Decimal("50.00")


def test_m390_2024_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The manual-oracle grounding of the three annual totals is enrolled, not
    just computed.

    Mirrors ``test_m303_2024_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction``
    (see ``test_external_oracle_grounding_enrolled.py`` for the shared
    registry-honesty gate this proves reaches the live, VALIDATED
    :class:`RegistryVerificationPolicy` fold for M390 as well as M303). Not
    tautological: the grounded set and the fraction are read from the
    registry's own declared+validated data, never hand-computed or asserted
    from a synthetic fixture.
    """
    authority = registry_authority
    snapshot = authority.snapshot("390", filing_year=_FILING_YEAR, period=_PERIOD)
    policy = snapshot.verification_policy()

    for casilla_id in (_CASILLA_DEVENGADA, _CASILLA_DEDUCIBLE, _CASILLA_RESULTADO):
        assert casilla_id in policy.externally_grounded_casilla_ids

    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids
    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )

    assert _CASILLA_RESULTADO in externally_grounded
    assert independently_grounded_fraction > 0.0
