"""Shared resolvers, repositories and invoice builders for the ledger source-mesh tests."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import cache
from typing import override

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import (
    published_revision,
    published_snapshot,
    published_supported_filing_years,
)

from ....core.period import Period
from ....core.secure_object_write import SecureObjectWrite
from ....domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.authored_editions import (
    newest_authored_editions,
    open_ended_revision,
    revision_covering,
)
from ....domain.categories.spending_category import SpendingCategory
from ....domain.contribuyente.inventory.records import InventoryLedgerDocument
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import InvoiceOperationDateRole, IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind as CatalogueInvoiceKind
from ....domain.modelos.work_unit import WorkUnit
from ....domain.prorrata_register.register import ProrrataRegister
from ....domain.renta.actividad_asset.claims import AmortizationClaim
from ....domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from ....domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from ....domain.renta.retencion_soportada import RetencionSoportadaRecord
from ....domain.transactions.date_partition import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
)
from ....domain.transactions.dates import transaction_eligible_date_span, transaction_filing_date
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.usage_ratios.model import UsageRatioProfile
from ....domain.user_profile.tests.imputation_criterion_facts import cash_criterion_facts
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...actividad_asset.history import ActivityAssetHistory, ActivityAssetHistoryClaimResult
from ...invoices.catalogue_reads_ports import InvoiceCatalogueReader, InvoiceCatalogueReadPorts
from ...modelo.work_profile import ModeloWorkProfile
from ...persistence_errors import PersistenceDegradationError
from ..ledger_membership import LedgerMembershipPorts, LedgerSourceMembership, collect_ledger_membership
from ..modelo_bindings_iva import LedgerIvaAggregationSourceResolver
from ..modelo_bindings_renta_expenses import (
    LedgerRentaGastosEstimacionDirectaAggregationSourceResolver,
    LedgerRentaGastosPagoFraccionadoAggregationSourceResolver,
)
from ..retencion_soportada_repository import RetencionSoportadaPorts
from ..source_mesh import (
    CalculationSourceContext,
    CalculationSourceResolution,
)
from .ledger_transaction_support import (
    ledger_raw_transaction,
)
from .usage_ratio_support import no_stored_usage_ratios

_YEAR = newest_authored_edition("100")
_PRIOR_YEAR = newest_authored_editions("100", 2)[0]
_M130_REVISION_ID = str(open_ended_revision("130").id)

BUCKET_ID = "28282828-2828-4828-8828-282828282828"


class _EmptyInvoiceCatalogueReader:
    def load(self) -> InvoiceCatalogue:
        return InvoiceCatalogue()


class _EmptyTransactionCatalogueReader:
    def load(self) -> TransactionCatalogue:
        return TransactionCatalogue()

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        return TransactionCatalogue()

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return LedgerDatePartition(in_window=TransactionCatalogue(), index_complete=True)


class EmptyActivityAssetHistoryRepository:
    def load(self) -> ActivityAssetHistory:
        return ActivityAssetHistory()

    def append_revision(self, revision: ActivityAssetRevision) -> ActivityAssetHistory:
        del revision
        raise AssertionError("empty resolver repository is read-only")

    def apply(self, mutation: Callable[[ActivityAssetHistory], ActivityAssetHistory]) -> ActivityAssetHistory:
        del mutation
        raise AssertionError("empty resolver repository is read-only")

    def record_claim(
        self,
        claim: AmortizationClaim,
        *,
        expected_history: ActivityAssetHistory | None = None,
        recorded_at: datetime | None = None,
    ) -> ActivityAssetHistoryClaimResult:
        del claim, expected_history, recorded_at
        raise AssertionError("empty resolver repository is read-only")


class StaticActivityAssetHistoryRepository(EmptyActivityAssetHistoryRepository):
    def __init__(self, history: ActivityAssetHistory) -> None:
        self._history = history

    @override
    def load(self) -> ActivityAssetHistory:
        return self._history


def cash_criterion_profile(*years: int, extra_facts: tuple[UserProfileFact, ...] = ()) -> ModeloWorkProfile:
    """A complete profile that elected the cash criterion for ``years``; needs the leased authority operation."""
    operation = governed_facts_in_scope()
    if not isinstance(operation, PinnedAuthorityOperation):
        raise LookupError("a cash-criterion profile requires a leased authority operation in scope")
    return ModeloWorkProfile(
        record=create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="X0001500M"),
                *extra_facts,
                *cash_criterion_facts(*years),
            ),
            context=operation.profile_create_context(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )


def empty_catalogue_read_ports() -> InvoiceCatalogueReadPorts:
    return InvoiceCatalogueReadPorts(
        invoice_reader=_EmptyInvoiceCatalogueReader(),
        transaction_reader=_EmptyTransactionCatalogueReader(),
    )


def prior_m303_snapshot_ref():
    return published_snapshot("303", filing_year=_YEAR, period="4T").snapshot_ref


class InMemoryTransactionCatalogueRepository:
    """Inward fake for the transaction read capability used by resolver tests."""

    def __init__(self, *, bucket_id: str) -> None:
        self._bucket_id = bucket_id
        self._catalogue = TransactionCatalogue()

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def exists(self) -> bool:
        return bool(self._catalogue.transactions)

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        requested = frozenset(transaction_ids)
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self._catalogue if transaction.transaction_id in requested
        )

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self._catalogue if start <= transaction_filing_date(transaction) <= end
        )

    def save(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in self._catalogue.values():
            earliest, latest = transaction_eligible_date_span(transaction)
            if earliest <= end and latest >= start:
                in_window.append(transaction)
            else:
                out_of_window.append(
                    OutOfWindowTransactionIndexEntry(
                        transaction_id=transaction.transaction_id,
                        filing_date=transaction_filing_date(transaction),
                    ),
                )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=False,
        )


class InMemoryInvoiceCatalogueRepository:
    """Inward fake for the invoice catalogue read capability."""

    def __init__(self) -> None:
        self._catalogue = InvoiceCatalogue()

    def load(self) -> InvoiceCatalogue:
        return self._catalogue

    def save(self, catalogue: InvoiceCatalogue) -> None:
        self._catalogue = catalogue


class InMemoryProrrataRegisterRepository:
    """Inward fake for the bucket-scoped prorrata read capability."""

    def __init__(self, *, bucket_id: str, register: ProrrataRegister | None = None) -> None:
        self._bucket_id = bucket_id
        self._register = register or ProrrataRegister()

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def load(self) -> ProrrataRegister:
        return self._register

    def load_revisioned(self) -> tuple[ProrrataRegister, str]:
        return self._register, "fixture-revision"

    def to_secure_object_write(
        self,
        register: ProrrataRegister,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        del register, expected_revision_id
        raise AssertionError("source-mesh prorrata fake does not support secure-object writes")

    def save(self, register: ProrrataRegister) -> None:
        self._register = register


def catalogue_read_ports(
    *,
    invoice_repository: InMemoryInvoiceCatalogueRepository,
    transaction_repository: InMemoryTransactionCatalogueRepository,
) -> InvoiceCatalogueReadPorts:
    return InvoiceCatalogueReadPorts(
        invoice_reader=invoice_repository,
        transaction_reader=transaction_repository,
    )


def empty_invoice_repository() -> InMemoryInvoiceCatalogueRepository:
    return InMemoryInvoiceCatalogueRepository()


def empty_prorrata_repository() -> InMemoryProrrataRegisterRepository:
    return InMemoryProrrataRegisterRepository(bucket_id=BUCKET_ID)


def prorrata_repository_holding(register: ProrrataRegister) -> InMemoryProrrataRegisterRepository:
    return InMemoryProrrataRegisterRepository(bucket_id=BUCKET_ID, register=register)


def ledger_iva_resolver(
    *,
    transaction_repository: InMemoryTransactionCatalogueRepository,
    invoice_repository: InMemoryInvoiceCatalogueRepository,
    prorrata_register_repository: InMemoryProrrataRegisterRepository,
) -> LedgerIvaAggregationSourceResolver:
    return LedgerIvaAggregationSourceResolver(
        transaction_repository=transaction_repository,
        invoice_catalogue_read_ports=catalogue_read_ports(
            invoice_repository=invoice_repository,
            transaction_repository=transaction_repository,
        ),
        prorrata_register_repository=prorrata_register_repository,
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=BUCKET_ID,
    )


@cache
def ledger_source_mesh_revision(modelo: str, revision_id: str) -> ModeloRevision:
    return published_revision(modelo, revision_id)


@cache
def m100_revision(year: int) -> ModeloRevision:
    return published_snapshot("100", filing_year=year, period="0A").revision


@cache
def m303_revision() -> ModeloRevision:
    return published_snapshot("303", filing_year=_YEAR, period="1T").revision


def ledger_source_mesh_invoice(tx_id: str, *, bucket_id: str = BUCKET_ID) -> Invoice:
    line = InvoiceLine(
        description="Asesoria fiscal",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=Decimal("21.00"),
    )
    return Invoice.model_validate(
        {
            "bucket_id": bucket_id,
            "kind": CatalogueInvoiceKind.RECEIVED,
            "invoice_number": f"INV-{tx_id}",
            "issued_at": date(_YEAR, 4, 1),
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": (tx_id,),
        },
    )


def domestic_iva_invoice(
    invoice_number: str,
    *,
    kind: CatalogueInvoiceKind,
    issued_at: date,
    taxable_base: Decimal,
    iva_amount: Decimal,
    bucket_id: str = BUCKET_ID,
    linked_transaction_ids: tuple[str, ...] = (),
    operation_date: date | None = None,
    counterparty_country: str = "ES",
    counterparty_tax_id: str = "B00015016",
) -> Invoice:
    line = InvoiceLine(
        description="Operacion interior con IVA",
        quantity=Decimal("1"),
        unit_price=taxable_base,
        subtotal=taxable_base,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=iva_amount,
    )
    return Invoice.model_validate(
        {
            "bucket_id": bucket_id,
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": issued_at,
            "counterparty_name": "Cliente ES" if kind is CatalogueInvoiceKind.ISSUED else "Proveedor ES",
            "counterparty_tax_id": counterparty_tax_id,
            "counterparty_country": counterparty_country,
            "base_total": taxable_base,
            "iva_total": iva_amount,
            "grand_total": taxable_base + iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": linked_transaction_ids,
            **(
                {}
                if operation_date is None
                else {
                    "operation_date": operation_date,
                    "operation_date_role": InvoiceOperationDateRole.from_registry("OPERATION_PERFORMED"),
                }
            ),
        },
    )


def exempt_intracommunity_invoice(
    invoice_number: str,
    *,
    kind: CatalogueInvoiceKind,
    issued_at: date,
    taxable_base: Decimal,
) -> Invoice:
    """An entrega intracomunitaria exenta: a real base, and no cuota at all."""
    line = InvoiceLine(
        description="Entrega intracomunitaria exenta",
        quantity=Decimal("1"),
        unit_price=taxable_base,
        subtotal=taxable_base,
        iva_rate=IvaRate.from_registry("RATE_0"),
        iva_amount=Decimal("0"),
    )
    return Invoice.model_validate(
        {
            "bucket_id": BUCKET_ID,
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": issued_at,
            "counterparty_name": "Kunde GmbH",
            "counterparty_tax_id": "DE345678901",
            "counterparty_country": "DE",
            "base_total": taxable_base,
            "iva_total": Decimal("0"),
            "grand_total": taxable_base,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
        },
    )


def machine_asset(transaction_id: str) -> ActivityAssetRevision:
    """A 1.000 EUR machine whose acquisition transaction the register names."""
    return ActivityAssetRevision(
        asset_id="machine-2025",
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=transaction_id,
            invoice_evidence_id="invoice-machine-2025",
            evidence_fingerprint="9" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("1000.00"),
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="ledger-business-allocation",
        ),
        in_service_date=date(_YEAR, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.LINEAR,
            authority_class_key="maquinaria",
        ),
    )


def machine_claim(asset: ActivityAssetRevision) -> AmortizationClaim:
    """The whole-2025 charge: 1.000 x 12 % maquinaria linear coefficient = 120,00."""
    return AmortizationClaim(
        asset_id=asset.asset_id,
        asset_revision_id=asset.revision_id,
        asset_kind=asset.asset_kind,
        tax_year=_YEAR,
        covered_from=date(_YEAR, 1, 1),
        covered_until=date(_YEAR, 12, 31) + timedelta(days=1),
        amount=Decimal("120.00"),
        schedule_fingerprint="8" * 64,
        authority_generation="published-test-generation",
        source_reference=f"modelo-100:{_YEAR}:parameter:maquinaria",
        creating_operation="record-amortization",
    )


def machine_acquisition_transaction(
    category: str,
    *,
    provider_id: str = "machine-acquisition",
    amount: Decimal = Decimal("1210.00"),
    taxable_base: Decimal = Decimal("1000.00"),
    iva_amount: Decimal = Decimal("210.00"),
    year: int = _YEAR,
) -> Transaction:
    """The purchase itself: 1.000,00 base plus 210,00 IVA soportado, paid from the bank."""
    return Transaction.model_validate(
        {
            "raw": ledger_raw_transaction(
                provider_id,
                booked_date=date(year, 4, 5),
                amount=amount,
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "purchase_invoice_evidence_id": None,
            "category_id": SpendingCategory.from_registry(category).value,
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "classified_at": datetime(year, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def renta_expense_binding_id(revision: ModeloRevision, casilla_id: str) -> BindingId:
    return next(
        binding.id
        for binding in revision.bindings
        if str(binding.source) == "ledger_renta_gastos_estimacion_directa_aggregation"
        and str(getattr(binding.provider, "target_casilla_id", None)) == casilla_id
    )


def m130_binding_id(revision: ModeloRevision) -> BindingId:
    return next(
        binding.id
        for binding in revision.bindings
        if str(binding.source) == "ledger_renta_gastos_pago_fraccionado_aggregation"
    )


def register_asset(
    asset_id: str,
    *,
    transaction_id: str,
    basis: Decimal = Decimal("12000.00"),
    in_service: date = date(_YEAR, 1, 1),
    kind: AssetKind = AssetKind.MATERIAL,
    election: ActivityAssetAmortizationElection | None = None,
) -> ActivityAssetRevision:
    """An element at a 10 % linear coefficient unless told otherwise."""
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=transaction_id,
            invoice_evidence_id=f"invoice-{asset_id}",
            evidence_fingerprint="d" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=kind,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=basis,
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="ledger-business-allocation",
        ),
        in_service_date=in_service,
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
        acquired_condition=AcquiredCondition.NEW,
        amortization=election
        or ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.LINEAR,
            authority_class_key="mobiliario",
            linear_coefficient=Decimal("0.10"),
        ),
    )


def register_claim(
    asset: ActivityAssetRevision,
    *,
    amount: Decimal,
    tax_year: int = _YEAR,
    covered_from: date | None = None,
    covered_until: date | None = None,
) -> AmortizationClaim:
    return AmortizationClaim(
        asset_id=asset.asset_id,
        asset_revision_id=asset.revision_id,
        asset_kind=asset.asset_kind,
        tax_year=tax_year,
        covered_from=covered_from or date(tax_year, 1, 1),
        covered_until=covered_until or date(tax_year + 1, 1, 1),
        amount=amount,
        schedule_fingerprint="e" * 64,
        authority_generation="published-test-generation",
        source_reference=f"modelo-100:{tax_year}:parameter:{asset.asset_id}",
        creating_operation="record-amortization",
        method=asset.amortization.method,
    )


def free_election() -> ActivityAssetAmortizationElection:
    return ActivityAssetAmortizationElection(
        regime=DirectEstimationRegime.NORMAL,
        method=AmortizationMethod.RESEARCH_DEVELOPMENT_FREE,
        research_development_evidence_reference="evidence:research-project",
    )


def resolve_m130(
    history: ActivityAssetHistory,
    period: str,
    *,
    rows: tuple[Transaction, ...] = (),
    profile: ModeloWorkProfile | None = None,
    invoices: InvoiceCatalogueReader | None = None,
    year: int = _YEAR,
) -> CalculationSourceResolution:
    profile = profile or cash_criterion_profile(year)
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    tx_repo.save(TransactionCatalogue.from_transactions(rows))
    return LedgerRentaGastosPagoFraccionadoAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_reader=invoices or empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
        usage_ratio_profile_loader=no_stored_usage_ratios,
        activity_asset_history_repository=StaticActivityAssetHistoryRepository(history),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="130",
            filing_year=year,
            period=Period.from_year_and_code(year, period),
            revision=ledger_source_mesh_revision("130", _M130_REVISION_ID),
            profile=profile,
        ),
    )


def resolve_m100(
    history: ActivityAssetHistory,
    *,
    rows: tuple[Transaction, ...] = (),
    profile: ModeloWorkProfile | None = None,
    year: int = _YEAR,
    invoices: InvoiceCatalogueReader | None = None,
    prorrata_register: ProrrataRegister | None = None,
) -> CalculationSourceResolution:
    profile = profile or cash_criterion_profile(year)
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    tx_repo.save(TransactionCatalogue.from_transactions(rows))
    return LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
        ports=InvoiceCatalogueReadPorts(
            invoice_reader=invoices or InMemoryInvoiceCatalogueRepository(),
            transaction_reader=tx_repo,
        ),
        prorrata_register_repository=prorrata_repository_holding(prorrata_register or ProrrataRegister()),
        usage_ratio_profile_loader=lambda *, bucket_id, operation: UsageRatioProfile(),
        activity_asset_history_repository=StaticActivityAssetHistoryRepository(history),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=year,
            period=Period.from_year_and_code(year, "0A"),
            revision=m100_revision(year),
            profile=profile,
        ),
    )


def m130_box(resolution: CalculationSourceResolution) -> Decimal:
    return resolution.binding_values[m130_binding_id(ledger_source_mesh_revision("130", _M130_REVISION_ID))]


def reasons(resolution: CalculationSourceResolution) -> list[str]:
    return [item.reason for item in resolution.diagnostics]


PRIOR_YEAR_ROW_NOTE = "source_issue"


def prior_year_purchase() -> Transaction:
    """The purchase behind a default ``register_asset`` element, booked before the year under calculation.

    Its only trace on a return is the ``PRIOR_YEAR_ROW_NOTE`` saying the row falls outside the period.
    """
    return machine_acquisition_transaction(
        "hardware_amortizable",
        amount=Decimal("14520.00"),
        taxable_base=Decimal("12000.00"),
        iva_amount=Decimal("2520.00"),
        year=_PRIOR_YEAR,
    )


class UnreadableActivityAssetHistoryRepository(EmptyActivityAssetHistoryRepository):
    @override
    def load(self) -> ActivityAssetHistory:
        raise PersistenceDegradationError("activity_asset_history_load")


def filing_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return tuple(range(support.years[0], newest_authored_edition("100") + 1))


AMORTIZABLE_CATEGORIES = ("hardware_amortizable", "mobiliario_amortizable", "amortizacion_vivienda_afecto")


class EmptyInventoryRepository:
    def load(self) -> InventoryLedgerDocument:
        return InventoryLedgerDocument()


class EmptyInvestmentRegisterRepository:
    def load(self) -> BienesInversionIvaRegister:
        return BienesInversionIvaRegister()

    def add(self, record: BienInversionIvaRecord) -> BienesInversionIvaRegister:
        del record
        raise AssertionError("membership reads never write the investment register")


class EmptyRetencionSoportadaRecords:
    def load_records(self, ejercicio: int) -> tuple[RetencionSoportadaRecord, ...]:
        del ejercicio
        return ()


def empty_retencion_soportada_ports() -> RetencionSoportadaPorts:
    """Return suffered-withholding ports with no payer record and no absence attestation."""
    return RetencionSoportadaPorts(repository=EmptyRetencionSoportadaRecords())


def activity_asset_ledger_membership(
    work_unit: WorkUnit,
    history: ActivityAssetHistory,
    tx_repo: InMemoryTransactionCatalogueRepository,
    *,
    modelo: str,
    period_code: str,
) -> LedgerSourceMembership:
    """Assemble the real register membership for cross-seam drift proofs."""
    ports = LedgerMembershipPorts(
        transaction_repository=tx_repo,
        invoice_catalogue_read_ports=catalogue_read_ports(
            invoice_repository=empty_invoice_repository(),
            transaction_repository=tx_repo,
        ),
        prorrata_register_repository=empty_prorrata_repository(),
        bienes_inversion_repository=EmptyInvestmentRegisterRepository(),
        activity_asset_history_repository=StaticActivityAssetHistoryRepository(history),
        usage_ratio_profile_loader=no_stored_usage_ratios,
        inventory_repository=EmptyInventoryRepository(),
        retencion_soportada_ports=empty_retencion_soportada_ports(),
    )
    resolver = (
        LedgerRentaGastosEstimacionDirectaAggregationSourceResolver
        if modelo == "100"
        else LedgerRentaGastosPagoFraccionadoAggregationSourceResolver
    )
    membership: LedgerSourceMembership = collect_ledger_membership(
        context=CalculationSourceContext(
            bucket_id=BUCKET_ID,
            work_unit_id=work_unit.work_unit_id,
            modelo=modelo,
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, period_code),
            revision=ledger_source_mesh_revision(
                modelo, str(revision_covering("100", _YEAR).id) if modelo == "100" else _M130_REVISION_ID
            ),
        ),
        work_unit=work_unit,
        ports=ports,
        selected=frozenset(resolver.owned_sources),
    )
    assert membership.available
    return membership
