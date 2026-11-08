"""The Libro de facturas drives Modelo 303; linked bank movements are its payments.

A taxpayer classifies the quarter's bank movements as business, records the
quarter's invoices and links each invoice to the movement that paid it. No
movement carries a base, rate or cuota of its own: the invoice is the IVA
document (LIVA art. 75 for accrual, art. 97 and RIVA art. 99 for deduction),
and the movement only evidences payment.

The figures are a miniature of an independent oracle computed from official
instructions alone, never from this application: 303 2025 1T declares base
6000.00 and cuota 1260.00 at 21 % (07, 09), a deductible domestic base 2550.00
with cuota 535.50 (28, 29), an intra-community supply of 1500.00 (59), and a
result of 724.50 (46, 71).

Real encrypted store, real published authority, real calculation engine, real
reciprocal link. No doubles.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from cadrumo.adapters.persistence.profile.catalogue_creation import build_catalogue_creation_ports
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.application.invoices.catalogue_creation import build_catalogue_invoice
from cadrumo.application.invoices.transaction_linking import link_invoice_transaction_catalogues
from cadrumo.application.ledger.preflight import (
    LedgerPreflightIssueReason,
    LedgerPreflightReport,
    preflight_ledger_tax_readiness,
)
from cadrumo.application.modelo.action_errors import ModeloLedgerPreflightBlockedError
from cadrumo.application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.calculation_operation import ModeloWorkCalculateExecutor
from cadrumo.application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
    ModeloWorkCalculateRequest,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.next_step import OperationOpenMovementStepV1
from cadrumo.application.tests.operation_host_fakes import (
    IrreversibleSectionGrant,
    RecordingEvents,
    RecordingOperands,
    executor_context,
)
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.errors.error_codes import ErrorCategory, get_registered_error_code
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.invoices.catalogue import InvoiceCatalogue
from cadrumo.domain.invoices.models import Invoice
from cadrumo.domain.iva.schema import InvoiceKind, IvaCategory
from cadrumo.domain.iva_compensation.reconciliation import (
    IvaCompensationAuthoritySource,
    IvaCompensationReconciliationDecision,
)
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.ready_profile_support import seed_ready_profile
from .ready_profile_taxpayer import ready_profile_tax_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET = "44444444-4444-4444-8444-444444444303"
_YEAR = 2025
_T0 = datetime(2025, 4, 2, 9, 0, tzinfo=UTC)
_T1 = datetime(2025, 4, 2, 10, 0, tzinfo=UTC)

#: Issued invoices: number, date, counterparty, tax id, country, base, rate %, retención.
_ISSUED: tuple[tuple[str, date, str, str, str, Decimal, Decimal | None, Decimal], ...] = (
    ("2025-001", date(2025, 1, 15), "Alfa SL", "B81000010", "ES", Decimal("2000.00"), Decimal("21"), Decimal("300.00")),
    ("2025-002", date(2025, 1, 31), "Kunde GmbH", "DE123456788", "DE", Decimal("1500.00"), None, Decimal("0")),
    ("2025-003", date(2025, 2, 14), "Beta SL", "B81000028", "ES", Decimal("2000.00"), Decimal("21"), Decimal("300.00")),
    ("2025-004", date(2025, 3, 14), "Alfa SL", "B81000010", "ES", Decimal("2000.00"), Decimal("21"), Decimal("300.00")),
)
#: Received invoices, same shape.
_RECEIVED: tuple[tuple[str, date, str, str, str, Decimal, Decimal | None, Decimal], ...] = (
    (
        "CLO-2025-001",
        date(2025, 1, 5),
        "Cloud Ejemplo SA",
        "A81000051",
        "ES",
        Decimal("250.00"),
        Decimal("21"),
        Decimal("0"),
    ),
    (
        "INM-2025-001",
        date(2025, 1, 20),
        "Inmobiliaria Ficticia SL",
        "B81000044",
        "ES",
        Decimal("500.00"),
        Decimal("21"),
        Decimal("95.00"),
    ),
    (
        "CLO-2025-002",
        date(2025, 2, 5),
        "Cloud Ejemplo SA",
        "A81000051",
        "ES",
        Decimal("250.00"),
        Decimal("21"),
        Decimal("0"),
    ),
    (
        "INM-2025-002",
        date(2025, 2, 20),
        "Inmobiliaria Ficticia SL",
        "B81000044",
        "ES",
        Decimal("500.00"),
        Decimal("21"),
        Decimal("95.00"),
    ),
    (
        "GES-2025-001",
        date(2025, 2, 28),
        "Gestoría Ejemplo SLP",
        "B81000069",
        "ES",
        Decimal("300.00"),
        Decimal("21"),
        Decimal("45.00"),
    ),
    (
        "CLO-2025-003",
        date(2025, 3, 5),
        "Cloud Ejemplo SA",
        "A81000051",
        "ES",
        Decimal("250.00"),
        Decimal("21"),
        Decimal("0"),
    ),
    (
        "INM-2025-003",
        date(2025, 3, 20),
        "Inmobiliaria Ficticia SL",
        "B81000044",
        "ES",
        Decimal("500.00"),
        Decimal("21"),
        Decimal("95.00"),
    ),
)

#: The oracle's 303 2025 1T, from official instructions only. The form prints the
#: régimen general result as [46]; the registry holds it as a computed box under its role.
_ORACLE: dict[str, Decimal] = {
    "07": Decimal("6000.00"),
    "09": Decimal("1260.00"),
    "28": Decimal("2550.00"),
    "29": Decimal("535.50"),
    "iva.resultado-regimen-general": Decimal("724.50"),
    "59": Decimal("1500.00"),
    "71": Decimal("724.50"),
}


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        yield profile.repository


def _invoice(
    row: tuple[str, date, str, str, str, Decimal, Decimal | None, Decimal],
    *,
    kind: InvoiceKind,
) -> Invoice:
    number, issued_at, name, tax_id, country, base, rate, retention = row
    intra_community = country != "ES"
    return build_catalogue_invoice(
        bucket_id=_BUCKET,
        kind=kind,
        counterparty_name=name,
        counterparty_tax_id=tax_id,
        counterparty_country=country,
        invoice_number=number,
        issued_at=issued_at,
        taxable_base=base,
        iva_rate=rate,
        currency="EUR",
        retention_amount=retention or None,
        iva_category=IvaCategory("intra_community_service_supply") if intra_community else None,
        rate_provider=build_catalogue_creation_ports(bucket_id=_BUCKET).rate_provider,
    )


#: The expense category the person gives each supplier's movements, as in APP-QA.
_EXPENSE_CATEGORY = {
    "CLO": SpendingCategory.from_registry("software_suscripcion"),
    "INM": SpendingCategory.from_registry("arrendamiento_local"),
    "GES": SpendingCategory.from_registry("asesoria_fiscal"),
}


def _movement(invoice: Invoice) -> Transaction:
    """The bank movement that paid ``invoice``: business, and no IVA figure of its own."""
    retention = invoice.retention_amount or Decimal("0")
    issued = invoice.kind is InvoiceKind.ISSUED
    gross = invoice.grand_total - retention
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"banco-{invoice.invoice_number}",
                booked_date=invoice.issued_at,
                value_date=invoice.issued_at,
                amount=gross,
                currency="EUR",
                counterparty=invoice.counterparty_name,
                description=f"{'TRANSF RECIBIDA' if issued else 'PAGO'} {invoice.counterparty_name} {invoice.invoice_number}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="e" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=_T0,
                    provider_name="banco-sintetico",
                ),
                raw_fields={"source_kind": "ledger_transaction"},
            ),
            "direction": TransactionDirection.INCOMING if issued else TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": None if issued else _EXPENSE_CATEGORY[invoice.invoice_number.split("-", 1)[0]],
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _wallet_decision(operation: PinnedAuthorityOperation) -> IvaCompensationReconciliationDecision:
    del operation
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=ready_profile_tax_id(),
        target_year=_YEAR,
        target_period=Period.from_year_and_code(_YEAR, "1T"),
        target_registry_snapshot_ref=published_authority_operation()
        .snapshot("303", filing_year=_YEAR, period="1T")
        .snapshot_ref,
        source_registry_snapshot_refs=(),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0.00"),
        wallet_amount=Decimal("0.00"),
        local_recurrence_amount=None,
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity="aeat_wallet_validated",
        wallet_captured_at=_T1,
        authority_sources=(
            IvaCompensationAuthoritySource(
                source_kind="aeat_wallet",
                amount=Decimal("0.00"),
                source_locator="aeat-wallet:synthetic-fixture",
                captured_at=_T1,
                registry_snapshot_refs=(),
            ),
        ),
        decided_at=_T1,
    )


@dataclass(frozen=True)
class _Quarter:
    """The seeded quarter: its stores, work unit and the wallet decision calculation reads."""

    work_unit: WorkUnit
    work_units: WorkUnitCatalogueRepository
    calculations: CalculationRevisionCatalogueRepository
    events: BucketEventHistoryRepository
    transactions: TransactionCatalogueRepository
    invoices: InvoiceCatalogueRepository
    decision: IvaCompensationReconciliationDecision
    movement_by_invoice: dict[str, str]


def _seed_linked_quarter(
    secure_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
    received: tuple[tuple[str, date, str, str, str, Decimal, Decimal | None, Decimal], ...] = _RECEIVED,
) -> _Quarter:
    seed_ready_profile(bucket_id=_BUCKET, at=_T0)
    wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    decision = _wallet_decision(operation)
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(decision)

    invoices = InvoiceCatalogue()
    transactions = TransactionCatalogue()
    movement_by_invoice: dict[str, str] = {}
    for kind, rows in ((InvoiceKind.ISSUED, _ISSUED), (InvoiceKind.RECEIVED, received)):
        for row in rows:
            invoice = _invoice(row, kind=kind)
            movement = _movement(invoice)
            invoices = InvoiceCatalogue.model_validate({"invoices": {**invoices.invoices, invoice.invoice_id: invoice}})
            transactions = TransactionCatalogue.model_validate(
                {**{t.transaction_id: t for t in transactions.values()}, movement.transaction_id: movement},
            )
            linked = link_invoice_transaction_catalogues(
                invoices,
                transactions,
                invoice_id=invoice.invoice_id,
                transaction_id=movement.transaction_id,
            )
            invoices, transactions = linked.invoices, linked.transactions
            movement_by_invoice[invoice.invoice_number] = movement.transaction_id
    invoice_repo.save(invoices)
    tx_repo.save(transactions)

    snapshot = published_authority_operation().snapshot("303", filing_year=_YEAR, period="1T")
    work_unit = create_work_unit(
        bucket_id=_BUCKET,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=event_repo),
        clock=_T0,
        operation=operation,
    )
    return _Quarter(
        work_unit=work_unit,
        work_units=wu_repo,
        calculations=cr_repo,
        events=event_repo,
        transactions=tx_repo,
        invoices=invoice_repo,
        decision=decision,
        movement_by_invoice=movement_by_invoice,
    )


def _calculate(quarter: _Quarter, *, operation: PinnedAuthorityOperation) -> BucketAggregationCalculationResult:
    with calculation_ports_for_test(
        bucket_id=_BUCKET,
        work_unit_repository=quarter.work_units,
        calculation_repository=quarter.calculations,
        bucket_event_repository=quarter.events,
        transaction_repository=quarter.transactions,
        invoice_repository=quarter.invoices,
    ) as ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            quarter.work_unit.work_unit_id,
            actor="operator-A",
            binding_values={
                "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
                "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
            },
            iva_compensation_decision=quarter.decision,
            ports=ports,
            filing_instance_evidence=general_m303_filing_evidence(
                quarter.work_unit.period, reference="test:invoice-iva-source", operation=operation
            ),
            clock=_T1,
        )


def _calculate_linked_quarter(
    secure_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> BucketAggregationCalculationResult:
    return _calculate(_seed_linked_quarter(secure_objects, operation=operation), operation=operation)


def _readiness(quarter: _Quarter, *, operation: PinnedAuthorityOperation) -> LedgerPreflightReport:
    """The ledger's own readiness verdict, read through the check every readiness surface uses."""
    with calculation_ports_for_test(
        bucket_id=_BUCKET,
        work_unit_repository=quarter.work_units,
        calculation_repository=quarter.calculations,
        bucket_event_repository=quarter.events,
        transaction_repository=quarter.transactions,
        invoice_repository=quarter.invoices,
    ) as ports:
        return preflight_ledger_tax_readiness(
            bucket_id=_BUCKET,
            period=quarter.work_unit.period,
            usage_ratio_profile_loader=ports.usage_ratio_profile_loader,
            invoice_reader=quarter.invoices,
            operation=operation,
            transaction_repository=quarter.transactions,
        )


def _box(box: str) -> CasillaId:
    return validated_casilla_id(box, surface="test casilla id")


def test_linked_invoices_drive_the_quarter_to_the_oracle(
    secure_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Every movement is linked and carries no IVA figure; the invoices alone reach the oracle."""
    result = _calculate_linked_quarter(secure_objects, operation=operation)
    values = result.revision.casilla_values

    declared = {box: Decimal(str(values[_box(box)])) for box in _ORACLE}
    assert declared == _ORACLE


def test_each_invoice_is_declared_once_and_no_movement_is_a_source(
    secure_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The invoices are the IVA sources; the movements that paid them contribute nothing."""
    result = _calculate_linked_quarter(secure_objects, operation=operation)

    iva_sources = {
        provenance.source_ref
        for provenance in result.revision.source_provenance
        if provenance.contributor_source_kind == "ledger_iva_aggregation"
    }
    assert iva_sources
    assert all(source.startswith("invoice:") for source in iva_sources), sorted(iva_sources)
    assert len({source.split(":")[1] for source in iva_sources}) == len(_ISSUED) + len(_RECEIVED)


#: A received invoice whose line reaches the escaso valor threshold of LIVA art. 108.Dos.5.º:
#: from its figures alone the good may be a bien de inversión, so the invoice cannot ground
#: the deduction family and the person classifies the movement that paid it.
_EQUIPMENT = (
    "CLO-2025-004",
    date(2025, 3, 10),
    "Cloud Ejemplo SA",
    "A81000051",
    "ES",
    Decimal("3005.06"),
    Decimal("21"),
    Decimal("0"),
)


def test_readiness_and_calculation_refuse_the_same_movement(
    secure_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """The ledger never calls a quarter ready that calculation then refuses, and both name the movement."""
    quarter = _seed_linked_quarter(secure_objects, operation=operation, received=(*_RECEIVED, _EQUIPMENT))
    paying = quarter.movement_by_invoice[_EQUIPMENT[0]]

    report = _readiness(quarter, operation=operation)
    with pytest.raises(ModeloLedgerPreflightBlockedError) as refused:
        _calculate(quarter, operation=operation)

    assert not report.ready
    assert [(issue.transaction_id, issue.reason) for issue in report.issues] == [
        (paying, LedgerPreflightIssueReason.INVOICE_DEDUCTION_FAMILY_UNRESOLVED)
    ]
    step = refused.value.operation_next_step(OutputLanguage.ES)
    assert isinstance(step, OperationOpenMovementStepV1)
    assert step.transaction_id == paying
    assert refused.value.translated_message == "application.modelo.errors.ledger_preflight_blocked_movement"
    assert not quarter.calculations.load(operation=operation).revisions


def test_a_blocked_calculate_settles_refused_and_reports_no_effect(
    secure_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """A blocked ledger is a refusal that wrote nothing, so the window never says records may have changed."""
    quarter = _seed_linked_quarter(secure_objects, operation=operation, received=(*_RECEIVED, _EQUIPMENT))
    events = RecordingEvents()
    context = executor_context(
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        profile_id=_BUCKET,
        operation=operation,
        cancellation=IrreversibleSectionGrant(),
        events=events,
        operands=RecordingOperands("e" * 64),
    )

    with calculation_ports_for_test(
        bucket_id=_BUCKET,
        work_unit_repository=quarter.work_units,
        calculation_repository=quarter.calculations,
        bucket_event_repository=quarter.events,
        transaction_repository=quarter.transactions,
        invoice_repository=quarter.invoices,
    ) as ports:
        executor = ModeloWorkCalculateExecutor(
            calculation_action_ports_factory=lambda **_composition: ports,
            attachment_store_factory=lambda _bucket_id: AttachmentStore(),
        )
        request = OperationRequest(
            definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
            subject_ref=quarter.work_unit.work_unit_id,
            payload=ModeloWorkCalculateRequest(
                work_unit_id=quarter.work_unit.work_unit_id,
                actor="operator-A",
                ordinary_m303_filing_evidence=ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
                    joint_return_elected=False
                ),
            ),
        )
        with pytest.raises(ModeloLedgerPreflightBlockedError) as refused:
            asyncio.run(executor.execute(request, context))

    assert get_registered_error_code(refused.value).category is ErrorCategory.REFUSED
    assert events.effects == []
    assert not quarter.calculations.load(operation=operation).revisions
