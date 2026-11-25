"""Modelo 100 casilla 0599 takes the retención the taxpayer's issued invoices declare.

Casilla 0599 credits the retenciones and ingresos a cuenta borne on actividades
económicas (LIRPF art. 99; RIRPF arts. 95 and 108.4). The perceptor's own
issued invoice states the retención the client practised, so the ledger is the
value source. A figure reconstructed from invoice gross minus cash received is
not a recorded fact: it is reported with its count and amount and never added.
A row whose retención the substrate cannot determine is reported as unknown,
never as zero. Each row's retención follows its income into the ejercicio the
declared criterion imputes it to (LIRPF art. 14.1.b; RIRPF art. 79), so the
credit is filing grade: checking, export and local filing admit it.

Every case runs through the production resolver against the Modelo 100 and
Modelo 130 revisions of the published authority, so the bindings under test are
the ones the registry declares, not fixture copies of them.

Every figure is invoice arithmetic hand-derived in the constants below. Two
rates are used because one rate cannot tell a per-invoice read from one rate
applied to a total: 1.000,00 at 15 % and 500,00 at 7 % give 150,00 and 35,00,
and no single rate over the 1.500,00 combined base reproduces 185,00.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.aggregation import BindingSourceKind, BindingValueOutcome
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_grade_cap_reach import capped_binding_reach, snapshot_reach_date
from ....domain.calculations.registry.binding_targets import revision_bindings_by_id
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.calculation_revision_sources import CalculationSourceIssue
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.service import link_invoice
from ...actividad_asset.tests.register_support import MemoryRepository
from ...modelo.advisory_binding_value import add_advisory_binding_value_diagnostics
from ...modelo.bucket_unrouted_source_issues import unrouted_source_issues
from ...modelo.calculation_note_gate import (
    ModeloCalculationBlockedError,
    gate_refuses,
    require_work_unit_calculation_unblocked,
)
from ...modelo.calculation_screen import calculation_screen_stamp
from ...modelo.printed_boxes import snapshot_printed_boxes
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..source_mesh import CalculationSourceContext, CalculationSourceDiagnostic, CalculationSourceResolution
from .ledger_source_mesh_support import InMemoryTransactionCatalogueRepository, cash_criterion_profile
from .renta_income_aggregation_support import catalogue_read_ports, renta_income_aggregation_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "c4f1a2b3-5d6e-4f70-8a91-b2c3d4e5f607"
_CLOCK = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_ADVISORY_REASON = "advisory_binding_value"
_YEAR = newest_authored_edition("100")
_ACTIVITY_DATE = date(_YEAR, 3, 10)

_M100_RETENCIONES_ACTIVIDADES_CASILLA: CasillaId = validated_casilla_id(
    "0599",
    surface="_M100_RETENCIONES_ACTIVIDADES_CASILLA",
)
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="M130_RETENCIONES_CASILLA")
_DOMESTIC_GENERAL = IvaCategory("domestic_general")
_DOMESTIC_EXEMPT = IvaCategory("domestic_exempt")
_RENTA_INCOME = BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION

# Hand-derived: 1.000,00 base at the RIRPF art. 95.1 general 15 % leaves 150,00
# withheld; 1.000,00 + 210,00 IVA - 150,00 = 1.060,00 reaches the bank.
_PROFESIONAL_BASE = Decimal("1000.00")
_PROFESIONAL_RETENCION = Decimal("150.00")
_PROFESIONAL_CASH = Decimal("1060.00")
# Hand-derived: 500,00 base at the art. 95.1 new-professional 7 % leaves 35,00
# withheld; 500,00 + 105,00 IVA - 35,00 = 570,00 reaches the bank.
_REDUCED_BASE = Decimal("500.00")
_REDUCED_RETENCION = Decimal("35.00")
_REDUCED_CASH = Decimal("570.00")
# Hand-derived: 150,00 + 35,00.
_DECLARED_CREDIT = Decimal("185.00")

# Hand-derived inferred row: 2.000,00 base + 420,00 IVA = 2.420,00 invoiced, and
# 2.120,00 banked with no invoice to state the shortfall, so 300,00 is
# reconstructed. 300,00 is 15 % of the base, inside the supported rate.
_INFERRED_BASE = Decimal("2000.00")
_INFERRED_IVA = Decimal("420.00")
_INFERRED_CASH = Decimal("2120.00")
_INFERRED_RETENCION = Decimal("300.00")


def _transaction(
    *,
    provider_id: str,
    cash: Decimal,
    irpf_category: str | None = "actividad_economica",
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    iva_amount: Decimal | None = None,
    iva_category: IvaCategory | None = None,
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=_ACTIVITY_DATE,
        value_date=_ACTIVITY_DATE,
        amount=cash,
        currency="EUR",
        counterparty="Cliente SL",
        description="cobro factura",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(_YEAR, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": irpf_category,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": iva_category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_YEAR, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _issued_invoice(
    *,
    number: str,
    base: Decimal,
    linked_transaction_id: str,
    retention_amount: Decimal,
    retention_rate: Decimal,
) -> Invoice:
    rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), _ACTIVITY_DATE)
    assert rate is not None
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=base * rate,
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": number,
            "issued_at": _ACTIVITY_DATE,
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "bucket_id": _BUCKET,
            "base_total": base,
            "iva_total": line.iva_amount,
            "grand_total": base + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": _DOMESTIC_GENERAL,
            "retention_rate": retention_rate,
            "retention_amount": retention_amount,
            "linked_transaction_ids": (linked_transaction_id,),
        },
    )


def _declared_ledger(*extra: Transaction) -> tuple[TransactionCatalogue, InvoiceCatalogue]:
    """Two issued invoices whose retención each invoice states, at 15 % and 7 %, plus ``extra`` rows."""
    profesional = _transaction(provider_id="cobro-15", cash=_PROFESIONAL_CASH)
    reduced = _transaction(provider_id="cobro-07", cash=_REDUCED_CASH)
    invoices = (
        _issued_invoice(
            number="F-001",
            base=_PROFESIONAL_BASE,
            linked_transaction_id=profesional.transaction_id,
            retention_amount=_PROFESIONAL_RETENCION,
            retention_rate=Decimal("0.15"),
        ),
        _issued_invoice(
            number="F-002",
            base=_REDUCED_BASE,
            linked_transaction_id=reduced.transaction_id,
            retention_amount=_REDUCED_RETENCION,
            retention_rate=Decimal("0.07"),
        ),
    )
    catalogue = TransactionCatalogue.from_transactions((profesional, reduced, *extra))
    for invoice, transaction in zip(invoices, (profesional, reduced), strict=True):
        catalogue = link_invoice(catalogue, transaction.transaction_id, invoice.invoice_id)
    return catalogue, build_invoice_catalogue(invoices)


def _resolve(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    revision: ModeloRevision,
    modelo: str = "100",
    period_code: str = "0A",
) -> CalculationSourceResolution:
    repository = InMemoryTransactionCatalogueRepository(bucket_id=_BUCKET)
    repository.save(transactions)
    resolver = LedgerRentaIncomeAggregationSourceResolver(
        activity_asset_history_repository=MemoryRepository(),
        transaction_repository=repository,
        ports=catalogue_read_ports(invoices=invoices, transactions=transactions),
    )
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET,
            modelo=modelo,
            filing_year=_YEAR,
            period=renta_income_aggregation_period(_YEAR, period_code),
            revision=revision,
            profile=cash_criterion_profile(_YEAR),
        ),
    )


def _m100_revision() -> ModeloRevision:
    return published_snapshot("100", filing_year=_YEAR, period="0A").revision


def _casilla_0599_binding(revision: ModeloRevision) -> BindingId:
    """Return the binding the registry names for casilla 0599, asserting it is bound directly."""
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _M100_RETENCIONES_ACTIVIDADES_CASILLA)
    assert casilla.input_kind is InputKind.BOUND
    assert casilla.binding is not None
    return casilla.binding


def _credit_0599(resolution: CalculationSourceResolution, revision: ModeloRevision) -> Decimal:
    return resolution.binding_values[_casilla_0599_binding(revision)]


def _findings(resolution: CalculationSourceResolution, reason: str) -> list[CalculationSourceDiagnostic]:
    return [diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == reason]


def test_declared_retenciones_at_two_rates_reach_casilla_0599() -> None:
    """Both invoices' stated retención enters 0599, each at its own rate: 150,00 + 35,00."""
    transactions, invoices = _declared_ledger()
    revision = _m100_revision()

    resolution = _resolve(transactions, invoices, revision=revision)

    assert _credit_0599(resolution, revision) == _DECLARED_CREDIT
    assert not _findings(resolution, "inferred_retencion_excluded_from_credit")
    assert not _findings(resolution, "unresolved_retencion_substrate")


def _calculated(
    operation: PinnedAuthorityOperation, resolution: CalculationSourceResolution
) -> tuple[CalculationSourceResolution, tuple[CalculationSourceIssue, ...]]:
    """Run the post-merge emission and the durable projection a calculation persists."""
    snapshot = operation.snapshot("100", filing_year=_YEAR, period="0A")
    emitted = add_advisory_binding_value_diagnostics(snapshot, resolution, operation=operation)
    persisted = unrouted_source_issues(emitted.diagnostics, snapshot_printed_boxes(operation, snapshot))
    return emitted, persisted


def _refused_reasons(
    operation: PinnedAuthorityOperation, issues: tuple[CalculationSourceIssue, ...]
) -> set[str] | None:
    """The reasons check, export and recording refuse with, or ``None`` when each admits the revision."""
    snapshot = operation.snapshot("100", filing_year=_YEAR, period="0A")
    period = Period.from_year_and_code(_YEAR, "0A")
    revision_id = str(snapshot.revision.id)
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET, modelo="100", filing_year=_YEAR, period=period, revision_id=revision_id
        ),
        bucket_id=_BUCKET,
        modelo=ModeloCode("100"),
        filing_year=_YEAR,
        period=period,
        revision_id=revision_id,
        name=f"100-{_YEAR}-0A",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    stamp = calculation_screen_stamp(snapshot, operation=operation)
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_issues=issues,
            filing_instance_evidence=None,
            source_provenance=(),
            screen_stamp=stamp,
        ),
        work_unit_id=unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="100", revision_id=revision_id, modelo_year=_YEAR, period="0A"
        ),
        state=CalculationRevisionState.BORRADOR,
        casilla_values={},
        observations=(),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
        source_issues=issues,
        screen_stamp=stamp,
        verified_at=None,
        verified_by=None,
        filed_at=None,
        filed_by=None,
    )
    refusals: list[set[str]] = []
    for action in ("verify", "export", "file"):
        try:
            require_work_unit_calculation_unblocked(
                work_unit=unit, revision=revision, action=action, operation=operation
            )
        except ModeloCalculationBlockedError as refused:
            refusals.append(set(str((refused.context or {})["reasons"]).split(",")))
    if not refusals:
        return None
    assert len(refusals) == 3, "check, export and recording decide together"
    assert all(refusal == refusals[0] for refusal in refusals)
    return refusals[0]


def test_the_activity_credit_is_filing_grade_and_cites_its_imputation(operation: PinnedAuthorityOperation) -> None:
    """The 0599 binding carries no cap, and cites the provisions that place its year."""
    snapshot = operation.snapshot("100", filing_year=_YEAR, period="0A")
    bindings = revision_bindings_by_id(snapshot.revision)
    credit = bindings[_casilla_0599_binding(snapshot.revision)]
    assert credit.grade_cap is None
    assert {"rd-439-2007:art-79", "rd-439-2007:art-7", "ley-35-2006:art-14"} <= set(credit.legal_refs)
    assert not capped_binding_reach(
        snapshot.revision, authority=operation, effective_date=snapshot_reach_date(snapshot)
    )


def test_a_declared_credit_is_calculated_and_admitted_at_check_export_and_recording(
    operation: PinnedAuthorityOperation,
) -> None:
    """185,00 resolves with no advisory note, and check, export and recording admit it."""
    transactions, invoices = _declared_ledger()
    revision = _m100_revision()

    resolution = _resolve(transactions, invoices, revision=revision)

    assert _credit_0599(resolution, revision) == _DECLARED_CREDIT
    emitted, persisted = _calculated(operation, resolution)
    assert not [item for item in emitted.diagnostics if item.reason == _ADVISORY_REASON]
    assert _refused_reasons(operation, persisted) is None


def test_a_proven_zero_over_rows_without_withholding_passes(operation: PinnedAuthorityOperation) -> None:
    """An activity receipt that carries no retención is a proven zero, and nothing is refused."""
    paid_in_full = _transaction(
        provider_id="cobro-integro",
        cash=_INFERRED_BASE + _INFERRED_IVA,
        taxable_base=_INFERRED_BASE,
        iva_rate=Decimal("0.21"),
        iva_amount=_INFERRED_IVA,
    )
    transactions = TransactionCatalogue.from_transactions((paid_in_full,))
    revision = _m100_revision()

    resolution = _resolve(transactions, InvoiceCatalogue(), revision=revision)

    assert _credit_0599(resolution, revision) == Decimal("0")
    assert resolution.value_outcomes[_casilla_0599_binding(revision)] is BindingValueOutcome.PROVEN_ZERO
    emitted, persisted = _calculated(operation, resolution)
    assert not [item for item in emitted.diagnostics if item.reason == _ADVISORY_REASON]
    assert _refused_reasons(operation, persisted) is None


def test_an_inferred_row_raises_the_advisory_and_leaves_0599_unchanged() -> None:
    """A net-paid receipt with no invoice stating its retención is reported, not added.

    Its 300,00 is reconstructed from 2.420,00 invoiced minus 2.120,00 banked, so
    0599 stays at the declared 185,00 and the finding names one row and 300,00.
    """
    inferred = _transaction(
        provider_id="cobro-inferido",
        cash=_INFERRED_CASH,
        taxable_base=_INFERRED_BASE,
        iva_rate=Decimal("0.21"),
        iva_amount=_INFERRED_IVA,
    )
    transactions, invoices = _declared_ledger(inferred)
    revision = _m100_revision()

    resolution = _resolve(transactions, invoices, revision=revision)

    assert _credit_0599(resolution, revision) == _DECLARED_CREDIT
    excluded = _findings(resolution, "inferred_retencion_excluded_from_credit")
    assert len(excluded) == 1
    assert excluded[0].message.startswith("1 issued-invoice row(s)")
    assert f"{_INFERRED_RETENCION} EUR" in excluded[0].message
    assert inferred.transaction_id in excluded[0].message
    assert not _findings(resolution, "unresolved_retencion_substrate")


@pytest.mark.parametrize(
    ("label", "cash", "taxable_base", "iva_category"),
    [
        # No base and no invoice: nothing determines the retención.
        ("no_substrate", Decimal("400.00"), None, None),
        # 2.000,00 exempt base banked as 1.000,00 would imply 50 % withheld,
        # above every supported activity rate, so the inference is refused.
        ("refused_above_supported_rate", Decimal("1000.00"), Decimal("2000.00"), _DOMESTIC_EXEMPT),
    ],
)
def test_an_undeterminable_retencion_is_unresolved_never_zero(
    label: str,
    cash: Decimal,
    taxable_base: Decimal | None,
    iva_category: IvaCategory | None,
) -> None:
    """A row whose retención is unknown is reported as unresolved and adds nothing to 0599."""
    unknown = _transaction(
        provider_id=f"cobro-{label}",
        cash=cash,
        taxable_base=taxable_base,
        iva_category=iva_category,
    )
    transactions, invoices = _declared_ledger(unknown)
    revision = _m100_revision()

    resolution = _resolve(transactions, invoices, revision=revision)

    assert _credit_0599(resolution, revision) == _DECLARED_CREDIT
    unresolved = _findings(resolution, "unresolved_retencion_substrate")
    assert len(unresolved) == 1
    assert unresolved[0].message.startswith("1 issued-invoice row(s)")
    assert unknown.transaction_id in unresolved[0].message
    assert not _findings(resolution, "inferred_retencion_excluded_from_credit")


def test_employment_and_non_activity_rows_never_reach_0599() -> None:
    """A salary receipt and an uncategorised receipt add nothing and raise no retención finding."""
    employment = _transaction(provider_id="nomina", cash=Decimal("1800.00"), irpf_category="rendimientos_trabajo")
    uncategorised = _transaction(provider_id="sin-categoria", cash=Decimal("500.00"), irpf_category=None)
    transactions, invoices = _declared_ledger(employment, uncategorised)
    revision = _m100_revision()

    resolution = _resolve(transactions, invoices, revision=revision)

    assert _credit_0599(resolution, revision) == _DECLARED_CREDIT
    assert not _findings(resolution, "inferred_retencion_excluded_from_credit")
    assert not _findings(resolution, "unresolved_retencion_substrate")


def test_the_unrouted_quantity_screen_is_silent_for_modelo_100() -> None:
    """The retención reaches 0599, so the screen that refuses an unrouted quantity stays silent.

    Teeth: the same rows against the published revision with the 0599 binding
    removed raise ``unrouted_declarable_quantity`` for the whole 185,00, and the
    calculation-note gate refuses on it.
    """
    transactions, invoices = _declared_ledger()
    revision = _m100_revision()

    assert not _findings(_resolve(transactions, invoices, revision=revision), "unrouted_declarable_quantity")

    binding_id = _casilla_0599_binding(revision)
    stripped = revision.model_copy(
        update={
            "bindings": tuple(binding for binding in revision.bindings if binding.id != binding_id),
            "casillas": tuple(
                casilla.model_copy(update={"input_kind": InputKind.MANUAL, "binding": None})
                if casilla.id == _M100_RETENCIONES_ACTIVIDADES_CASILLA
                else casilla
                for casilla in revision.casillas
            ),
        },
    )
    unrouted = _findings(_resolve(transactions, invoices, revision=stripped), "unrouted_declarable_quantity")
    assert len(unrouted) == 1
    assert f"{_DECLARED_CREDIT} EUR of 'declared_withheld_amount_sum'" in unrouted[0].message
    assert gate_refuses(unrouted[0].reason, _RENTA_INCOME)


def test_0599_agrees_with_the_fourth_quarter_modelo_130_casilla_06() -> None:
    """The annual credit equals the cumulative fourth-quarter Modelo 130 casilla 06 over the same ledger.

    Both are compared with the hand-derived 185,00 rather than with each other's
    output, and the inferred row is present so the comparison covers what both
    leave out as well as what both take.
    """
    inferred = _transaction(
        provider_id="cobro-inferido",
        cash=_INFERRED_CASH,
        taxable_base=_INFERRED_BASE,
        iva_rate=Decimal("0.21"),
        iva_amount=_INFERRED_IVA,
    )
    transactions, invoices = _declared_ledger(inferred)
    m100 = _m100_revision()

    annual = _resolve(transactions, invoices, revision=m100)
    fourth_quarter = _resolve(
        transactions,
        invoices,
        revision=published_snapshot("130", filing_year=_YEAR, period="4T").revision,
        modelo="130",
        period_code="4T",
    )

    assert _credit_0599(annual, m100) == _DECLARED_CREDIT
    assert fourth_quarter.bound_inputs_by_casilla_id[_M130_RETENCIONES_CASILLA] == _DECLARED_CREDIT
