"""M130 actividad income contract tests for IRPF category and taxable-base projection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ._secure_objects_fixtures import SECURE_OBJECTS_BUCKET_ID, secure_objects

__all__ = ["secure_objects"]

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from ....domain.calculations.registry.ledger_bindings import resolve_ledger_renta_income_aggregation_binding_values
from ....domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.models import TransactionCatalogue
from ....domain.transactions.retencion_parameters import load_retencion_actividades_rates
from .._modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from .._renta_income_ledger import RentaIncomeLedgerAggregationIssueReason, aggregate_renta_income_ledger
from .._source_mesh import CalculationSourceContext, CalculationSourceDiagnostic, CalculationSourceResolution
from ._renta_income_aggregation_support import (
    _M130_INGRESOS_CASILLA,
    _M130_RETENCIONES_BINDING,
    _M130_RETENCIONES_CASILLA,
    _Q1_2024,
    _actividad_transaction,
    _period,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M130_INCOME_SOURCE_REFS = ("aeat-modelo-130-instructions",)
_M130_INGRESOS_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"
_M130_INGRESOS_LEGAL_REFS = (
    "rd-439-2007:art-110",
    "orden-eha-672-2007:art-1",
    "ley-35-2006:art-99",
    "rd-439-2007:art-95",
    "ley-35-2006:art-27",
    "ley-35-2006:art-28",
)
_M130_RETENCIONES_LEGAL_REFS = (
    "rd-439-2007:art-110",
    "orden-eha-672-2007:art-1",
    "ley-35-2006:art-99",
    "rd-439-2007:art-95",
)


def _m130_renta_income_binding(
    binding_id: str,
    *,
    fact: str,
    legal_refs: tuple[str, ...],
) -> DataBindingDefinition:
    return DataBindingDefinition(
        id=binding_id,
        source=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        selector={"modelo": "130", "target_casilla_id": "01", "fact": fact},
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=legal_refs,
        source_refs=_M130_INCOME_SOURCE_REFS,
    )


def _m130_casilla(casilla_id: str) -> CasillaDefinition:
    """Minimal casilla declaration for this fixture's synthetic revision.

    Declaring both casillas 01 and 06 keeps the fixture realistic relative
    to the committed registry's revision, even though the T-05 cross-check
    that validates the output casilla runs at snapshot-build time
    (`domain.renta.retenciones_routing_integrity`), not against this
    hand-built revision -- see that module's own test file for that
    coverage.
    """
    return CasillaDefinition(
        id=casilla_id,
        number=casilla_id,
        localization_keys=("test.schema.casilla.label",),
        section=("test",),
        legal_refs=_M130_INCOME_SOURCE_REFS,
        source_refs=_M130_INCOME_SOURCE_REFS,
    )


def _m130_2026_q1_revision() -> ModeloRevision:
    return ModeloRevision(
        id="2019-y-siguientes",
        localization_key="test.schema.revision.2019-y-siguientes.label",
        valid_from=date(2019, 1, 1),
        period_selector=PeriodSelector(year_from=2019, periods=("1T", "2T", "3T", "4T")),
        legal_refs=_M130_INGRESOS_LEGAL_REFS,
        source_refs=_M130_INCOME_SOURCE_REFS,
        casillas=(_m130_casilla(_M130_INGRESOS_CASILLA), _m130_casilla(_M130_RETENCIONES_CASILLA)),
        bindings=(
            _m130_renta_income_binding(
                _M130_INGRESOS_BINDING,
                fact="ingresos_integros_sum",
                legal_refs=_M130_INGRESOS_LEGAL_REFS,
            ),
            _m130_renta_income_binding(
                _M130_RETENCIONES_BINDING,
                fact="withheld_amount_sum",
                legal_refs=_M130_RETENCIONES_LEGAL_REFS,
            ),
        ),
    )


# contract: irpf_category filter + taxable_base_sum fact
# Grounded in RD 439/2007 art. 110.2 — only actividades económicas feed M130.
# ---------------------------------------------------------------------------


def test_irpf_actividad_economica_flows_despite_unclassified_business() -> None:
    """irpf_category='actividad_economica' is the M130 eligibility gate.

    RD 439/2007 art. 110.2: pagos fraccionados apply to rendimientos de
    actividades económicas.  A transaction explicitly tagged as
    irpf_category='actividad_economica' must flow to casilla 01 even when
    business_classification has not yet been resolved (UNCLASSIFIED).

    This is the root-cause regression: Andrea's transactions had
    irpf_category set but business_classification=UNCLASSIFIED, causing
    _income_business_amount to return None and casilla 01 to be 0.
    """
    # Amount matches the AEAT professional-services income example: a single
    # quarterly invoice of 3000 EUR from estimación directa simplified.
    amount = Decimal("3000.00")
    tx = _actividad_transaction(
        "ae-001",
        value_date=date(2024, 2, 1),
        amount=amount,
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    assert len(result.observations) == 1, result
    assert result.observations[0].gross_amount == amount
    assert result.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == amount
    assert result.issues == ()


def test_trabajo_income_excluded_from_m130() -> None:
    """irpf_category='trabajo' transactions are excluded from M130 casillas.

    Rendimientos del trabajo (nóminas) are never subject to M130 pagos
    fraccionados — only actividades económicas trigger M130 (RD 439/2007
    art. 110.1). The pipeline must reject trabajo entries with TRABAJO_INCOME
    reason so they do not inflate casilla 01.
    """
    nomina = _actividad_transaction(
        "nomina-001",
        value_date=date(2024, 1, 31),
        amount=Decimal("2500.00"),
        irpf_category="trabajo",
        business_classification=BusinessClassification.BUSINESS,
    )
    actividad = _actividad_transaction(
        "ae-002",
        value_date=date(2024, 1, 15),
        amount=Decimal("1800.00"),
    )
    catalogue = TransactionCatalogue.from_transactions((nomina, actividad))

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    assert len(result.observations) == 1
    assert result.observations[0].transaction_id == actividad.transaction_id
    assert len(result.issues) == 1
    assert result.issues[0].reason == RentaIncomeLedgerAggregationIssueReason.TRABAJO_INCOME
    assert result.issues[0].transaction_id == nomina.transaction_id
    # casilla 01 only reflects the actividad transaction
    assert result.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == Decimal("1800.00")


def test_taxable_base_amount_populated_when_set() -> None:
    """RentaIncomeObservation carries taxable_base_amount when transaction has taxable_base.

    The taxable_base_sum fact path lets the registry resolver sum the
    IVA-exclusive base imponible rather than gross_amount.  When a transaction
    carries taxable_base, the observation's taxable_base_amount must equal it.
    """
    # Professional invoice: 1000 EUR net + 210 EUR IVA = 1210 EUR gross.
    # The IRPF base (taxable_base) is the IVA-exclusive 1000 EUR.
    gross = Decimal("1210.00")
    taxable = Decimal("1000.00")
    tx = _actividad_transaction(
        "ae-inv-001",
        value_date=date(2024, 3, 15),
        amount=gross,
        taxable_base=taxable,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    assert len(result.observations) == 1
    obs = result.observations[0]
    assert obs.gross_amount == gross
    assert obs.taxable_base_amount == taxable


def test_net_paid_professional_invoice_derives_withheld_amount_for_m130() -> None:
    """Professional invoice withholding is the invoice gross minus bank cash.

    Fixture: 2000 base + 420 IVA - 300 IRPF withholding = 2120 bank receipt.
    Modelo 130 casilla 06 is the cumulative withholding amount, while casilla
    01 remains the IVA-exclusive income base. These two expectations come from
    the invoice arithmetic and the AEAT casilla roles, not from the resolver
    implementation.
    """
    tx = _actividad_transaction(
        "ae-net-paid",
        value_date=date(2024, 3, 15),
        amount=Decimal("2120.00"),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("420.00"),
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    aggregation = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)
    assert len(aggregation.observations) == 1
    observation = aggregation.observations[0]
    assert observation.taxable_base_amount == Decimal("2000.00")
    assert observation.withheld_amount == Decimal("300.00")

    revision = _m130_2026_q1_revision()
    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)
    assert aggregation.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == Decimal("2000.00")
    assert resolved[_M130_RETENCIONES_BINDING] == Decimal("300.00")


def test_a_mixed_classified_activity_receipt_is_undivided_at_the_binding() -> None:
    """Partial affectation divides assets, never an activity receipt.

    LIRPF art. 29.2 limits partial affectation to "elementos patrimoniales que
    sirvan sólo parcialmente al objeto de la actividad económica", reaching the
    rendimiento neto through the deductibility of those assets' gastos. No rule
    in arts. 27-30 divides an INGRESO by a usage percentage, and RIRPF art. 95.1
    fixes the retención "sobre los ingresos íntegros satisfechos" — the payment
    as made, carrying no affectation term. So a 50 %-affected taxpayer invoicing
    a client declares the whole invoice and claims the whole withholding.

    Asserted at the BINDING level because that is where a filing reads the
    figures: casilla 01 and the retenciones binding, not the observation alone.

    The same invoice as the BUSINESS case above (2000 base + 420 IVA - 300
    retención = 2120 banked), so the two classifications are asserted EQUAL
    rather than each against its own expectation — a rule that divided the
    income but not the withholding would break the equality and the internal
    15 % coherence at once.
    """
    invoiced_base = Decimal("2000.00")
    banked = Decimal("2120.00")
    withheld = Decimal("300.00")

    def resolved_pair(
        provider_id: str,
        *,
        business_classification: BusinessClassification,
        business_pct: Decimal | None = None,
    ) -> tuple[Decimal, Decimal]:
        tx = _actividad_transaction(
            provider_id,
            value_date=date(2024, 3, 15),
            amount=banked,
            taxable_base=invoiced_base,
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("420.00"),
            business_classification=business_classification,
            business_pct=business_pct,
        )
        aggregation = aggregate_renta_income_ledger(
            TransactionCatalogue.from_transactions((tx,)),
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            period=_Q1_2024,
        )
        resolved = resolve_ledger_renta_income_aggregation_binding_values(
            _m130_2026_q1_revision(),
            aggregation.observations,
        )
        return (
            aggregation.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA],
            resolved[_M130_RETENCIONES_BINDING],
        )

    business_income, business_retencion = resolved_pair(
        "ae-business-undivided",
        business_classification=BusinessClassification.BUSINESS,
    )
    mixed_income, mixed_retencion = resolved_pair(
        "ae-mixed-half-affected",
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.50"),
    )

    # The invoice, not the affectation, is what reaches the casillas.
    assert (business_income, business_retencion) == (invoiced_base, withheld)
    assert (mixed_income, mixed_retencion) == (invoiced_base, withheld)

    # Coherent as a pair: 300,00 IS the art. 95.1 general 15 % of the income
    # declared beside it. Halving the income while claiming the whole
    # withholding would present a 30 % rate no article fixes.
    assert mixed_retencion == mixed_income * load_retencion_actividades_rates().general_rate
    assert mixed_income != invoiced_base * Decimal("0.50"), "a receipt is not divided by affectation"


def test_income_source_resolver_projects_withheld_amount_to_m130_casilla_06(
    secure_objects: SecureObjectRepository,
) -> None:
    tx = _actividad_transaction(
        "ae-net-paid-resolver",
        value_date=date(2026, 3, 15),
        amount=Decimal("2120.00"),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("420.00"),
    )
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((tx,)))
    context = CalculationSourceContext(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=_period(2026, "1T"),
        revision=_m130_2026_q1_revision(),
    )

    resolution = LedgerRentaIncomeAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
    ).resolve(context)

    assert resolution.binding_values[_M130_RETENCIONES_BINDING] == Decimal("300.00")
    assert resolution.bound_inputs_by_casilla_id[_M130_RETENCIONES_CASILLA] == Decimal("300.00")


def test_a_revision_without_the_retenciones_binding_surfaces_the_lost_credit(
    secure_objects: SecureObjectRepository,
) -> None:
    """The dropped retención reaches the operator, and no other screen reports it.

    Same substrate as the test above -- a net-paid professional invoice carrying
    300,00 of retención -- against a revision declaring only the income binding.
    Every row is still consumed for its income, so the row-keyed screens stay
    silent; without the quantity screen the whole credit would vanish from the
    form with a clean calculation on both sides.
    """
    tx = _actividad_transaction(
        "ae-net-paid-unrouted-retencion",
        value_date=date(2026, 3, 15),
        amount=Decimal("2120.00"),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("420.00"),
    )
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((tx,)))
    income_only = _m130_revision_without_the_retenciones_binding()
    context = CalculationSourceContext(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=_period(2026, "1T"),
        revision=income_only,
    )

    resolution = LedgerRentaIncomeAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
    ).resolve(context)

    advisories = [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]
    assert len(advisories) == 1, "a dropped retenciones binding must surface exactly one advisory"
    assert "withheld_amount_sum" in advisories[0].message
    assert "300.00" in advisories[0].message, "the advisory must name the amount the taxpayer loses"
    # Attributed like every sibling diagnostic in this resolver's envelope, so
    # an agent can trace the advisory to the source that raised it.
    assert advisories[0].resolver_id == "ledger_renta_income_aggregation"
    # The reason must NOT collapse into the row-keyed screen's: an operator has
    # to distinguish "no binding consumes this row" from "this row is consumed
    # but its withholding reaches nothing", and the row screen is silent here by
    # construction, so a shared reason would make its silence read as agreement.
    assert not [diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "unrouted_observation"], (
        "the quantity advisory must carry its own reason, not the row screen's"
    )
    # Non-blocking: the income still resolves, so calculate succeeds and the
    # operator sees the gap rather than a refusal.
    assert resolution.binding_values[_M130_INGRESOS_BINDING] == Decimal("2000.00")

    # Silence control: with the binding present the retención is drawn and the
    # advisory must not fire, or it would fire on every correct M130 filing.
    complete = LedgerRentaIncomeAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
    ).resolve(
        CalculationSourceContext(
            bucket_id=SECURE_OBJECTS_BUCKET_ID,
            modelo="130",
            filing_year=2026,
            period=_period(2026, "1T"),
            revision=_m130_2026_q1_revision(),
        ),
    )
    assert not [
        diagnostic for diagnostic in complete.diagnostics if diagnostic.reason == "unrouted_declarable_quantity"
    ]


def test_casilla_projection_uses_base_for_tagged_and_gross_for_untagged() -> None:
    """Casilla 01 projection carries computable income, never IVA-inclusive gross.

    A tagged professional invoice (1000 base +
    210 IVA = 1210 gross) plus an untagged 500 receipt. Casilla 01 must
    project 1500 (base + gross fallback) — not 1710 (gross sum, an IVA
    over-declaration) and not 1000 (base-only, dropping the untagged
    receipt). Mirrors the registry's ``ingresos_integros_sum`` fact so the
    projection and the binding resolver cannot drift.
    """
    tagged = _actividad_transaction(
        "ae-tagged",
        value_date=date(2024, 2, 10),
        amount=Decimal("1210.00"),
        taxable_base=Decimal("1000.00"),
    )
    untagged = _actividad_transaction(
        "ae-untagged",
        value_date=date(2024, 3, 5),
        amount=Decimal("500.00"),
        taxable_base=None,
    )
    catalogue = TransactionCatalogue.from_transactions((tagged, untagged))

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    # Field-selection wiring contract: tagged row contributes its declared
    # IVA-exclusive base, untagged row its gross transfer amount. The
    # inequality guard proves the selection is live (a gross-summing
    # regression would produce the IVA-inflated total instead).
    projected = result.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA]
    assert tagged.taxable_base is not None
    assert projected == tagged.taxable_base + untagged.raw.amount
    assert projected != tagged.raw.amount + untagged.raw.amount


def test_anti_tautology_irpf_category_controls_flow() -> None:
    """Anti-tautology: changing irpf_category changes which transactions flow.

    If the irpf_category filter were ignored, both test scenarios would
    produce the same casilla 01 total.  The inequality below fails if the
    filter has no effect.
    """
    amount = Decimal("5000.00")

    # Scenario A: one actividad + one trabajo — only actividad should flow
    actividad = _actividad_transaction(
        "ae-a",
        value_date=date(2024, 2, 15),
        amount=amount,
        irpf_category="actividad_economica",
    )
    trabajo = _actividad_transaction(
        "trab-a",
        value_date=date(2024, 2, 15),
        amount=amount,
        irpf_category="trabajo",
        business_classification=BusinessClassification.BUSINESS,
    )
    catalogue_a = TransactionCatalogue.from_transactions((actividad, trabajo))
    result_a = aggregate_renta_income_ledger(catalogue_a, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    # Scenario B: both transactions as actividad — both should flow
    actividad_b1 = _actividad_transaction(
        "ae-b1",
        value_date=date(2024, 2, 15),
        amount=amount,
        irpf_category="actividad_economica",
    )
    actividad_b2 = _actividad_transaction(
        "ae-b2",
        value_date=date(2024, 2, 15),
        amount=amount,
        irpf_category="actividad_economica",
    )
    catalogue_b = TransactionCatalogue.from_transactions((actividad_b1, actividad_b2))
    result_b = aggregate_renta_income_ledger(catalogue_b, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    casilla_a = result_a.casilla_aggregation.casilla_values.get(_M130_INGRESOS_CASILLA, Decimal("0"))
    casilla_b = result_b.casilla_aggregation.casilla_values.get(_M130_INGRESOS_CASILLA, Decimal("0"))

    assert casilla_a != casilla_b, (
        f"Anti-tautology failure: both scenarios produced casilla_01={casilla_a}; irpf_category filter has no effect"
    )
    # Scenario A: only actividad flows
    assert casilla_a == amount
    # Scenario B: both flow
    assert casilla_b == amount * 2


# ---------------------------------------------------------------------------


def _ungrounded_diagnostics(
    resolution: CalculationSourceResolution,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Every ungrounded-substrate advisory on a resolution, keyed on the reason code."""
    return tuple(
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "ungrounded_income_substrate"
    )


def test_cash_fallback_income_raises_the_ungrounded_substrate_advisory(
    secure_objects: SecureObjectRepository,
) -> None:
    """A row with no declared base must SAY so, not just quietly contribute cash.

    This is the safety net for the defect the whole campaign turns on: no inbound
    statement adapter populates ``taxable_base``, so an untagged activity receipt
    reaches casilla 01 through the ``ingresos_integros_sum`` fallback carrying the
    bank-credited figure -- net of any retención practicada, and IVA-inclusive
    where IVA was charged. The fallback is deliberately KEPT (dropping the row
    would under-declare by its whole value), so the advisory is the only thing
    standing between the operator and a silently mis-measured income casilla.

    Asserted on the machine-readable ``reason`` rather than the message prose:
    the wording is operator-facing copy and may be rephrased or localised, but
    the reason code is the contract.
    """
    tx = _actividad_transaction(
        "ae-cash-fallback-advisory",
        value_date=date(2026, 3, 15),
        amount=Decimal("1700.00"),
        taxable_base=None,
    )
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((tx,)))
    context = CalculationSourceContext(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=_period(2026, "1T"),
        revision=_m130_2026_q1_revision(),
    )

    resolution = LedgerRentaIncomeAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
    ).resolve(context)

    advisories = _ungrounded_diagnostics(resolution)
    assert len(advisories) == 1, "a base-less income row must raise exactly one ungrounded-substrate advisory"
    assert advisories[0].source_kind == "ledger_renta_income_aggregation"
    # The row still contributes -- the advisory reports a measurement risk, it does
    # not exclude. Proving both halves together is the point: an advisory that fired
    # while the row was dropped would describe a different, safer bug.
    assert resolution.binding_values[_M130_INGRESOS_BINDING] == Decimal("1700.00")


def test_substrate_declared_income_raises_no_ungrounded_advisory(
    secure_objects: SecureObjectRepository,
) -> None:
    """The control: an advisory that always fires is indistinguishable from a broken one.

    A tagged invoice declares its base, so the income measure is grounded and the
    operator must NOT be warned. Without this case the test above passes just as
    happily against a resolver that appends the advisory unconditionally, which
    would train operators to ignore it -- the failure mode the aggregate-not-
    per-row projection was designed to avoid in the first place.
    """
    tx = _actividad_transaction(
        "ae-substrate-declared-control",
        value_date=date(2026, 3, 15),
        amount=Decimal("2120.00"),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("420.00"),
    )
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((tx,)))
    context = CalculationSourceContext(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=_period(2026, "1T"),
        revision=_m130_2026_q1_revision(),
    )

    resolution = LedgerRentaIncomeAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
    ).resolve(context)

    assert _ungrounded_diagnostics(resolution) == (), (
        "a row declaring its taxable_base is grounded and must raise no ungrounded-substrate advisory"
    )
    assert resolution.binding_values[_M130_INGRESOS_BINDING] == Decimal("2000.00")


def test_many_ungrounded_rows_raise_one_advisory_not_one_each(
    secure_objects: SecureObjectRepository,
) -> None:
    """Three base-less rows must produce ONE advisory carrying their summed cash.

    The projection is deliberately per-aggregation rather than per-row, because an
    alert that fires once per transaction is an alert operators learn to skip. This
    pins that decision so a later refactor cannot quietly turn it back into a
    per-row emitter while every other assertion in this file keeps passing.
    """
    transactions = tuple(
        _actividad_transaction(
            f"ae-ungrounded-{index}",
            value_date=date(2026, 3, 10 + index),
            amount=Decimal("500.00"),
            taxable_base=None,
        )
        for index in range(3)
    )
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions(transactions))
    context = CalculationSourceContext(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        modelo="130",
        filing_year=2026,
        period=_period(2026, "1T"),
        revision=_m130_2026_q1_revision(),
    )

    resolution = LedgerRentaIncomeAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
    ).resolve(context)

    advisories = _ungrounded_diagnostics(resolution)
    assert len(advisories) == 1, "three ungrounded rows must fold into one advisory, not three"
    assert resolution.binding_values[_M130_INGRESOS_BINDING] == Decimal("1500.00")


def _m130_revision_without_the_retenciones_binding() -> ModeloRevision:
    """The same revision with only the ingresos binding declared.

    Every row is still consumed -- for its income -- so both row-keyed screens
    stay silent. The retención the rows carry reaches nothing.
    """
    full = _m130_2026_q1_revision()
    return full.model_copy(
        update={
            "bindings": tuple(binding for binding in full.bindings if binding.id != _M130_RETENCIONES_BINDING),
        },
    )
