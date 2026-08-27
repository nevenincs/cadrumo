"""The ledger-income chain driven by an AEAT worked example of exempt services.

The sibling oracle modules build their own invoice and ground its figures on
published RATES: the base is chosen by the test, the retención is the RIRPF art.
95 rate read from the registry parameter catalogue, and the grounding is that
two unrelated routes to the same withheld figure meet. That is real, and it is
the strongest grounding available for a withheld invoice, because no bundled
AEAT source publishes a worked retención on actividad-económica income.

This module grounds the other half differently, and more strongly: the SCENARIO
itself is AEAT's. Every income figure below is quoted from a caso práctico the
bundled Manual práctico de Renta 2024 prints, and the totals the chain must
reach are the manual's own printed subtotals rather than any rate applied by
this test.

The example (Parte 1, Capítulo 7, "Caso práctico (determinación del rendimiento
neto derivado de actividad profesional en estimación directa, modalidad
simplificada)", extracted markdown L19807-L19965)::

    Honorarios por prestación de servicios      124.000   (L19824)
    Conferencias y publicaciones                 10.800   (L19825)
    Autoconsumo                                     600   (nota 1, L19916)
    Variación de existencias                      3.000   (nota 3, L19920)
    --------------------------------------------------
    Total ingresos (valores fiscales)           138.400   (L19883)
    Total gastos   (valores fiscales)            78.300   (L19909)
    Rendimiento neto                             58.100   (L19912-19914)

**Why this is the exempt-services case.** The manual says so on its own account.
Nota (7), L19946-19947: "Se deduce como gasto el IVA soportado por tratarse de
una actividad exenta de este impuesto que no da derecho a deducir las cuotas
soportadas." The IVA soportado is a deductible gasto precisely BECAUSE the
activity is exempt — that is AEAT stating the exemption, not this test inferring
it from the profession. The manual attributes the exemption to the activity as a
whole and gives no per-income-line IVA split, so both printed ingresos lines are
modelled under the one exempt category the manual states; no per-line legal claim
is invented here.

**What this module covers that nothing else did.** Casilla 0171 ("Ingresos de
explotación") is ``input_kind = "bound"``, resolved by the
``ledger_renta_income_aggregation`` binding. The existing 0226 oracle supplies
0171 as a hand-typed casilla input, so it grounds the FORMULA chain above the
binding while stepping over the binding itself: the aggregation that turns
invoices into observations, and the resolver that folds observations into the
bound casilla, are both bypassed. Here the same published example is driven
through those two links for real, and the manual's own printed 138.400 and
58.100 are what the chain has to land on.

**Fixture provenance.** The rows below carry the operations the example
DESCRIBES — two income lines, their amounts, the exempt treatment it states —
and never its RESULT. Nothing in the fixture is derived from 138.400 or from
58.100; those are what the registry computes from the described facts and what
the assertions check. A fixture constructed backwards from a total would agree
with the engine whatever the engine did, which is the failure this shape exists
to rule out rather than reproduce.

**The under-declaration direction, honestly scoped.** Dropping the base from an
income row sends it to the cash fallback. On THIS example the euro figure does
not move, because an exempt invoice with no withholding is banked at exactly its
base — so the harm here is not a shortfall but a silent loss of grounding, and
the screen firing is the whole safeguard. The case where the euros actually move
is the withheld one, and it is pinned by the sibling exempt module against the
statutory rate. Saying which of the two this example can and cannot demonstrate
is the point: an assertion that claimed a shortfall here would be claiming a
number the scenario does not produce.

That boundary was measured rather than assumed. Rebinding the resolver so it
folds the banked cash instead of the declared base reddens nothing here, and
reddens the sibling module — so this example is genuinely blind to the
cash-versus-base substitution, and stating that is what keeps the module from
reading as broader coverage than it has.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.aggregation import aggregate_renta_m100_income_ledger
from .....core import CasillaId, Period, validated_casilla_id
from .....core.aggregation import LedgerIncomeGrounding
from .....core.resources import bundled_path
from ....iva import InvoiceKind, IvaCategory, category_cuota_is_zero_by_law
from ....transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from ..ledger_bindings import (
    resolve_ledger_renta_income_aggregation_binding_values,
    ungrounded_ledger_renta_income_observations,
)
from ..schema import ModeloRevision
from ..schema_input_kind import InputKind
from ..snapshot import build_snapshot
from ._registry_schema_support import _committed_modelo
from ._scenarios import (
    RegistryCalculationScenario,
    RegistryScenarioExpectedOutput,
    RegistryScenarioRunReport,
    assert_registry_scenario_matches,
    run_registry_calculation_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FILING_YEAR = 2024
_PERIOD = Period.from_year_and_code(_FILING_YEAR, "0A")
_BUCKET = "26535a03-c534-45c1-88cd-f248184acf4f"  # was 'bucket-aeat-exempt-worked-example'

# Every figure below is printed by the manual; see the module docstring for the
# per-line anchors. Nothing here is computed by this module.
_HONORARIOS = Decimal("124000.00")
_CONFERENCIAS = Decimal("10800.00")
_AUTOCONSUMO = Decimal("600.00")
_VARIACION_EXISTENCIAS = Decimal("3000.00")
_TOTAL_INGRESOS = Decimal("138400.00")
_TOTAL_GASTOS = Decimal("78300.00")
_RENDIMIENTO_NETO = Decimal("58100.00")

_INGRESOS_BINDING = "renta-2024-ledger-income-0171"

_CASILLA_INGRESOS_EXPLOTACION: CasillaId = validated_casilla_id("0171", surface="_CASILLA_INGRESOS_EXPLOTACION")
_CASILLA_TOTAL_INGRESOS: CasillaId = validated_casilla_id("0180", surface="_CASILLA_TOTAL_INGRESOS")
_CASILLA_TOTAL_GASTOS: CasillaId = validated_casilla_id("0218", surface="_CASILLA_TOTAL_GASTOS")
_CASILLA_RENDIMIENTO_NETO_REDUCIDO: CasillaId = validated_casilla_id(
    "0226",
    surface="_CASILLA_RENDIMIENTO_NETO_REDUCIDO",
)

# The 0226 formula's own declared provenance, as the scenario comparison reads
# it off the calculation entry.
_LEGAL_REFS = ("ley-35-2006:art-28", "ley-35-2006:art-30", "ley-35-2006:art-32")
_SOURCE_REFS = ("lirpf-cuota-chain-authority",)

# The gasto side of the same caso práctico, quoted per box from the manual's
# "valores fiscales" column. These are inputs to the registry chain exactly as
# the manual states them; the chain's own 0218 total is asserted against the
# manual's printed "Total gastos" below, so a mis-allocation between boxes
# cannot pass silently.
_GASTO_INPUTS: dict[CasillaId, Decimal] = {
    validated_casilla_id("0181", surface="0181"): Decimal("19000.00"),
    validated_casilla_id("0184", surface="0184"): Decimal("17700.00"),
    validated_casilla_id("0185", surface="0185"): Decimal("5900.00"),
    validated_casilla_id("0186", surface="0186"): Decimal("3300.00"),
    validated_casilla_id("0193", surface="0193"): Decimal("3800.00"),
    validated_casilla_id("0194", surface="0194"): Decimal("7800.00"),
    validated_casilla_id("0202", surface="0202"): Decimal("6200.00"),
    validated_casilla_id("0203", surface="0203"): Decimal("1100.00"),
    validated_casilla_id("0205", surface="0205"): Decimal("1600.00"),
    validated_casilla_id("0206", surface="0206"): Decimal("1700.00"),
    validated_casilla_id("0208", surface="0208"): Decimal("7900.00"),
    validated_casilla_id("0217", surface="0217"): Decimal("2300.00"),
}

# Eight of those gasto boxes are casillas the registry declares
# ``input_kind = "bound"``, to the ledger-expense aggregation. Supplying them
# hand-types values the engine is meant to produce, which is a deliberate
# scoping choice here and not an oversight: this module exists to drive the
# INCOME leg through its binding, and building expense substrate for the same
# caso practico would enlarge it into a second, different claim. The gasto
# aggregation is therefore out of scope and is stated as such rather than left
# for a reader to discover — the runner refuses an undeclared bound input, so
# the boundary is enforced rather than merely documented.
_GASTO_LEG_REASON = (
    "gasto leg supplied from the manual's own per-box figures; this scenario "
    "drives the INCOME leg through its ledger binding and makes no claim about "
    "the expense aggregation"
)
_HAND_TYPED_BOUND_CASILLAS: dict[CasillaId, str] = {
    casilla_id: _GASTO_LEG_REASON
    for casilla_id in (
        validated_casilla_id("0186", surface="0186"),
        validated_casilla_id("0193", surface="0193"),
        validated_casilla_id("0194", surface="0194"),
        validated_casilla_id("0202", surface="0202"),
        validated_casilla_id("0203", surface="0203"),
        validated_casilla_id("0206", surface="0206"),
        validated_casilla_id("0208", surface="0208"),
        validated_casilla_id("0217", surface="0217"),
    )
}

# The two ingresos the manual states outside the invoiced lines. They are not
# bank movements, so the ledger chain never produces them; they enter the
# scenario as the manual's own figures and the registry's 0180 formula adds
# them to whatever the chain resolved.
_NON_LEDGER_INGRESO_INPUTS: dict[CasillaId, Decimal] = {
    validated_casilla_id("0175", surface="0175"): _AUTOCONSUMO,
    validated_casilla_id("0177", surface="0177"): _VARIACION_EXISTENCIAS,
}

_BASE_BINDINGS: dict[str, Decimal] = {
    "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
    "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
    "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
    "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
    "renta-2024-profile-incremento-guarderia": Decimal("0"),
    "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
    "renta-2024-profile-descendientes-guarderia": Decimal("0"),
    "renta-2024-profile-marriage-full-year": Decimal("0"),
    "renta-2024-profile-marriage-month-start": Decimal("0"),
    "renta-2024-profile-marriage-month-end": Decimal("0"),
    "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
    "renta-2024-profile-declaration-type": Decimal("1"),
    "renta-2024-profile-family-minor-children-in-unit": Decimal("0"),
    "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("0"),
}

_RELATIONS: dict[str, Decimal] = {
    "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
}


def _modelo_100_revision() -> ModeloRevision:
    """Return the committed Modelo 100 revision the chain's last link resolves against.

    Built through the real snapshot construction, so the binding the resolver
    matches is the one a production calculate would load. A hand-assembled
    revision could agree with this module and disagree with the filing.
    """
    modelo, catalogues = _committed_modelo("100")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=_FILING_YEAR,
        period=_PERIOD.registry_token,
    ).revision


def _income_row(
    reference: str,
    amount: Decimal,
    when: date,
    *,
    declares_substrate: bool = True,
) -> Transaction:
    """One of the example's income lines as a ledger row.

    ``amount`` is what the bank credited. For an exempt operation carrying no
    withholding that equals the base imponible, which is why the substrate-less
    variant below moves the grounding without moving the euros.
    """
    raw = RawTransaction(
        provider_transaction_id=reference,
        booked_date=when,
        value_date=when,
        amount=amount,
        currency="EUR",
        counterparty="Cliente consulta radiologica",
        description=reference,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(_FILING_YEAR, 12, 31, 9, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": reference},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": amount if declares_substrate else None,
            "iva_amount": None,
            "iva_rate": None,
            "iva_category": IvaCategory.DOMESTIC_EXEMPT if declares_substrate else None,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_FILING_YEAR, 12, 31, 10, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _aggregated(
    *,
    honorarios_declares_substrate: bool = True,
    honorarios_amount: Decimal = _HONORARIOS,
):
    """Drive the example's two income lines through the production aggregation."""
    catalogue = TransactionCatalogue.from_transactions(
        (
            _income_row(
                "honorarios-prestacion-servicios",
                honorarios_amount,
                date(_FILING_YEAR, 6, 30),
                declares_substrate=honorarios_declares_substrate,
            ),
            _income_row("conferencias-y-publicaciones", _CONFERENCIAS, date(_FILING_YEAR, 11, 15)),
        ),
    )
    return aggregate_renta_m100_income_ledger(catalogue, bucket_id=_BUCKET, period=_PERIOD)


def _bound_casilla_inputs(revision: ModeloRevision, resolved: dict[str, Decimal]) -> dict[CasillaId, Decimal]:
    """Materialise the resolved binding values onto the casillas the REGISTRY binds them to.

    The binding-to-casilla mapping is read off the revision rather than
    restated, so a registry change that repointed the ledger-income binding at
    a different box would move this module with it instead of leaving it
    asserting against a stale literal.
    """
    return {
        casilla.id: resolved[casilla.binding]
        for casilla in revision.casillas
        if casilla.input_kind is InputKind.BOUND and casilla.binding in resolved
    }


def _scenario(
    scenario_id: str,
    bound_inputs: dict[CasillaId, Decimal],
    *,
    expected_rendimiento_neto: Decimal,
) -> RegistryCalculationScenario:
    return RegistryCalculationScenario(
        id=scenario_id,
        modelo="100",
        revision="2024",
        filing_year=_FILING_YEAR,
        period="0A",
        inputs={**_GASTO_INPUTS, **_NON_LEDGER_INGRESO_INPUTS, **bound_inputs},
        binding_values=dict(_BASE_BINDINGS),
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        relation_values=dict(_RELATIONS),
        date_context={"filing_period": date(_FILING_YEAR, 12, 31)},
        date_binding_values={"renta-2024-profile-taxpayer-birth-date": date(1980, 6, 15)},
        expected_outputs=(
            RegistryScenarioExpectedOutput(
                target_casilla_id=_CASILLA_RENDIMIENTO_NETO_REDUCIDO,
                value=expected_rendimiento_neto,
                legal_refs=_LEGAL_REFS,
                source_refs=_SOURCE_REFS,
            ),
        ),
        notes=("raw_evidence_locator: corpus/manuals/renta/2024/part1/source.pdf.extracted.md#L19807-L19965",),
        hand_typed_bound_casillas=_HAND_TYPED_BOUND_CASILLAS,
        chain_resolved_bound_casillas={
            casilla_id: (
                "resolved by aggregate_renta_m100_income_ledger over the manual's two printed ingresos lines, "
                "then folded by resolve_ledger_renta_income_aggregation_binding_values through the revision's own "
                "renta-2024-ledger-income-0171 binding; supplied as an input only because the scenario harness has "
                "no separate channel for a bound value"
            )
            for casilla_id in bound_inputs
        },
    )


def _run(scenario: RegistryCalculationScenario) -> RegistryScenarioRunReport:
    return run_registry_calculation_scenario(
        scenario,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
    )


def test_the_ingresos_casilla_is_bound_not_a_hand_typed_input() -> None:
    """0171 must still be resolved by a binding for this module to mean anything.

    Everything below claims to exercise the aggregation and the binding
    resolver. If the registry ever reclassified 0171 as a manual input, those
    claims would silently become an assertion about a value this test typed in
    itself, and every case would keep passing. Reading the classification off
    the revision is what stops that from being invisible.
    """
    revision = _modelo_100_revision()

    casilla = next(item for item in revision.casillas if item.id == _CASILLA_INGRESOS_EXPLOTACION)

    assert casilla.input_kind is InputKind.BOUND
    assert casilla.binding == _INGRESOS_BINDING


def test_the_manual_states_the_activity_is_iva_exempt() -> None:
    """Zero cuota here is the manual's own legal statement, not an absent field.

    The example's nota (7) deduces the IVA soportado as a gasto because the
    activity is exempt and gives no right to deduct. Reading the component
    table rather than testing for a null ``iva_amount`` is what separates "this
    operation has no cuota" from "nobody recorded one", and the whole exempt
    case rests on that distinction.
    """
    assert category_cuota_is_zero_by_law(IvaCategory.DOMESTIC_EXEMPT, InvoiceKind.ISSUED)
    assert not category_cuota_is_zero_by_law(IvaCategory.DOMESTIC_GENERAL, InvoiceKind.ISSUED)


def test_the_two_printed_income_lines_fold_into_the_bound_casilla() -> None:
    """The chain resolves 0171 from the manual's two ingresos lines.

    Both links run for real: the classifier sets the grounding marker, and the
    resolver folds the resulting observations through the registry's own
    binding. The expected figure is the sum of two amounts the manual prints,
    not a subtotal the manual states, so this assertion is about the fold
    rather than about a published total — the published totals come next.
    """
    revision = _modelo_100_revision()
    aggregation = _aggregated()

    assert aggregation.issues == ()
    assert len(aggregation.observations) == 2
    assert all(
        observation.grounding is LedgerIncomeGrounding.SUBSTRATE_DECLARED for observation in aggregation.observations
    )
    assert all(
        observation.target_casilla_id == _CASILLA_INGRESOS_EXPLOTACION for observation in aggregation.observations
    )

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)

    assert resolved[_INGRESOS_BINDING] == _HONORARIOS + _CONFERENCIAS


def test_the_chain_reaches_the_manuals_printed_total_ingresos() -> None:
    """0180 = 138.400, the manual's own "Total ingresos" in the fiscal column.

    This is the first figure the manual states on its own account rather than
    as a line item, and it is the one that makes the fold checkable: the
    registry's 0180 formula adds the two non-bank ingresos the manual also
    states (autoconsumo 600, variación de existencias 3.000) to whatever the
    ledger chain resolved. Landing on 138.400 therefore constrains the chain's
    contribution to exactly 134.800 — an aggregation that folded a different
    measure would miss the published total rather than quietly agreeing with
    itself.
    """
    revision = _modelo_100_revision()
    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, _aggregated().observations)

    report = _run(
        _scenario(
            "m100-2024-exempt-worked-example-total-ingresos",
            _bound_casilla_inputs(revision, resolved),
            expected_rendimiento_neto=_RENDIMIENTO_NETO,
        ),
    )
    values = report.calculation.values

    assert values[_CASILLA_TOTAL_INGRESOS] == _TOTAL_INGRESOS
    assert values[_CASILLA_TOTAL_INGRESOS] - values[_CASILLA_INGRESOS_EXPLOTACION] == (
        _AUTOCONSUMO + _VARIACION_EXISTENCIAS
    ), "the published total exceeds the ledger contribution by exactly the two non-bank ingresos the manual states"
    assert values[_CASILLA_TOTAL_GASTOS] == _TOTAL_GASTOS


def test_the_chain_reaches_the_manuals_printed_rendimiento_neto() -> None:
    """0226 = 58.100 with the ingresos side supplied by the ledger chain.

    The manual prints 58.100 three times — "Rendimiento neto", "Rendimiento
    neto reducido" and "Rendimiento neto reducido total" — and this is the
    figure the whole caso práctico exists to produce. Reaching it with 0171
    resolved through the aggregation and the binding, rather than typed in,
    is what extends the existing grounding of this example down through the
    two links it previously stepped over.
    """
    revision = _modelo_100_revision()
    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, _aggregated().observations)

    report = _run(
        _scenario(
            "m100-2024-exempt-worked-example-rendimiento-neto",
            _bound_casilla_inputs(revision, resolved),
            expected_rendimiento_neto=_RENDIMIENTO_NETO,
        ),
    )

    assert_registry_scenario_matches(report)


def test_moving_one_invoice_moves_both_published_totals() -> None:
    """Anti-tautology: the change must enter at the INVOICE and survive both links.

    Every assertion above compares the engine against a constant the manual
    printed, and a chain that returned those constants regardless of what it
    aggregated would satisfy all of them. So one euro is added to one invoice
    and the whole chain is re-run from the ledger row upward — aggregation,
    binding resolution, formula chain — rather than the resolved value being
    edited after the fact.

    That distinction was measured, not assumed. An earlier version of this gate
    nudged the already-resolved binding value, and a deliberately
    constant-returning resolver passed it: the mutation never reached the link
    the gate claimed to cover. Entering at the invoice is what closes it.

    0226 moves by the full euro rather than a fraction because the 5 %
    gastos-de-difícil-justificación deduction is capped at 2.000 in this
    example and stays capped, so the extra ingreso passes through undiminished.
    """
    revision = _modelo_100_revision()

    def totals(scenario_id: str, honorarios_amount: Decimal) -> tuple[Decimal, Decimal]:
        aggregation = _aggregated(honorarios_amount=honorarios_amount)
        resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)
        values = _run(
            _scenario(
                scenario_id,
                _bound_casilla_inputs(revision, resolved),
                expected_rendimiento_neto=_RENDIMIENTO_NETO,
            ),
        ).calculation.values
        return values[_CASILLA_TOTAL_INGRESOS], values[_CASILLA_RENDIMIENTO_NETO_REDUCIDO]

    baseline_ingresos, baseline_rendimiento = totals(
        "m100-2024-exempt-worked-example-anti-tautology-baseline",
        _HONORARIOS,
    )
    nudged_ingresos, nudged_rendimiento = totals(
        "m100-2024-exempt-worked-example-anti-tautology-nudged",
        _HONORARIOS + Decimal("1.00"),
    )

    assert baseline_ingresos == _TOTAL_INGRESOS
    assert nudged_ingresos - baseline_ingresos == Decimal("1.00")
    assert nudged_rendimiento - baseline_rendimiento == Decimal("1.00")


def test_the_fully_declared_example_raises_no_ungrounded_advisory() -> None:
    """The manual's own scenario must not fire the screen.

    An advisory that reported the textbook case would fire on the ordinary
    exempt professional, which is the fastest way to teach an operator to
    ignore it — and the case below is exactly the one they would then miss.
    """
    revision = _modelo_100_revision()

    screened = ungrounded_ledger_renta_income_observations(revision, _aggregated().observations)

    assert screened.observations == ()


def test_an_unrecorded_base_is_surfaced_and_leaves_the_published_total_intact() -> None:
    """Losing the base sends the row to cash and fires the screen, without moving the euros.

    Both halves matter and neither is the other. The row degrades — its
    grounding drops to the cash fallback and the screen names it — so the
    operator can see that 0171 is no longer resting on recorded substrate. Yet
    0180 still reaches the manual's printed 138.400, because an exempt
    operation carrying no withholding is banked at exactly its base.

    That is why the visibility IS the safeguard here rather than a shortfall
    assertion: the same missing field costs the taxpayer nothing on this
    invoice and costs them the withheld amount twice over on a withheld one.
    Asserting a shortfall on this example would be asserting a number it does
    not produce.
    """
    revision = _modelo_100_revision()
    degraded = _aggregated(honorarios_declares_substrate=False)

    groundings = {observation.grounding for observation in degraded.observations}
    assert groundings == {LedgerIncomeGrounding.CASH_FALLBACK, LedgerIncomeGrounding.SUBSTRATE_DECLARED}

    screened = ungrounded_ledger_renta_income_observations(revision, degraded.observations)

    assert len(screened.observations) == 1
    assert screened.observations[0].target_casilla_id == _CASILLA_INGRESOS_EXPLOTACION
    assert "ingresos_integros_sum" in screened.facts

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, degraded.observations)
    values = _run(
        _scenario(
            "m100-2024-exempt-worked-example-unrecorded-base",
            _bound_casilla_inputs(revision, resolved),
            expected_rendimiento_neto=_RENDIMIENTO_NETO,
        ),
    ).calculation.values

    assert values[_CASILLA_TOTAL_INGRESOS] == _TOTAL_INGRESOS
