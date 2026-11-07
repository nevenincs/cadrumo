"""Shared fixtures for the Renta persona tests that run from registered operations to exported bytes.

One synthetic taxpayer per persona over one real encrypted store: the profile, the
payer certificates and absence attestations recorded through the registered
executors, the activity ledger, the Modelo 130 quarters, and the verify and export
steps. Expected figures live in the tests that assert them; nothing here computes
a tax amount.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.own_accounts import OwnAccountRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.tests.filed_observation_fixture import persist_filed_revision_observation
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.application.retencion_soportada_absence.contracts import (
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
)
from cadrumo.application.retencion_soportada_absence.executor import RetencionSoportadaAbsenceExecutor
from cadrumo.application.retencion_soportada_absence.requests import RetencionSoportadaAbsenceAttestRequest
from cadrumo.application.retencion_soportada_certificado.contracts import (
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
)
from cadrumo.application.retencion_soportada_certificado.executor import RetencionSoportadaCertificadoExecutor
from cadrumo.application.retencion_soportada_certificado.requests import RetencionSoportadaRecordRequest
from cadrumo.application.tests.operation_host_fakes import (
    IrreversibleSectionGrant,
    RecordingEvents,
    RecordingOperands,
    executor_context,
    profile_operation_request,
)
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.contribuyente.entity_type import EntityType
from cadrumo.domain.contribuyente.renta_codes import FiscalResidency
from cadrumo.domain.deadlines.models import IrpfEstimationRegime, IrpfIncomeCategory, IVARegime, TaxpayerProfile
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus
from cadrumo.domain.invoices.models import Invoice, InvoiceLine
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.schema import InvoiceKind, IvaCategory
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.renta.retencion_soportada import RetencionSoportadaOrigen
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.own_accounts import (
    OwnAccountDesignation,
    OwnAccountHolding,
    OwnAccountRegister,
    OwnAccountRole,
    OwnBankAccountDetails,
)
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.retencion_soportada_absence_composition import build_retencion_soportada_absence_ports
from cadrumo.entrypoints.retencion_soportada_certificado_composition import build_retencion_soportada_certificado_ports
from cadrumo.tests.env_scope import ready_clave_settings

from .general_iva_profile_facts_support import renta_single_taxpayer_facts
from .m130_m100_annual_support import (
    BUCKET_ID,
    FILE_AT,
    OPERATOR_SCOPE_PORTS,
    T0,
    TAX_ID,
    YEAR,
    calculate_revision_from_bucket_aggregation,
    expense_transaction,
    export_revision_for_test,
    m100_non_relation_zero_bindings,
    verify_revision_for_test,
)

__all__ = [
    "ACTIVITY_KEY",
    "ACTIVITY_KEY_CASILLA",
    "PAYER_A",
    "PAYER_B",
    "REFUND_IBAN",
    "ActivityExpense",
    "ActivityInvoice",
    "Persona",
    "attest_no_withholding",
    "calculate_and_file_quarter",
    "calculate_annual",
    "create_work",
    "record_certificate",
    "register_refund_account",
    "seed_activity_ledger",
    "seed_profile",
    "verify_and_export",
    "workflow_profile",
]

# Synthetic CIFs whose control digit is hand-derived: with every digit before it zero but the last, the
# odd-position doubling leaves 2 * d7 (digit-summed), so the control is (10 - 2 * d7) mod 10 -- 8 for 1, 6 for 2.
PAYER_A = "B00010090"
PAYER_B = "B00010165"
REFUND_IBAN = "ES9121000418450200051332"

#: The activity key an exported direct-estimation block requires and the operator states.
ACTIVITY_KEY_CASILLA: CasillaId = validated_casilla_id("0166")
ACTIVITY_KEY = "A05"

_CAPTURED = datetime(YEAR + 1, 1, 15, 9, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Persona:
    """The facts that tell the personas apart: what the taxpayer declares and under which method."""

    categories: str
    regime: str = "directa_normal"
    criterion: str | None = None
    activity_start: date = date(2020, 1, 1)
    iae_epigraph: str = "844"


@dataclass(frozen=True, slots=True)
class ActivityInvoice:
    """One issued invoice, its retention and the receipt that paid it net of that retention."""

    number: str
    issued: date
    paid: date
    base: Decimal
    iva: Decimal
    retention_rate: Decimal
    retention: Decimal

    @property
    def net_receipt(self) -> Decimal:
        return self.base + self.iva - self.retention


@dataclass(frozen=True, slots=True)
class ActivityExpense:
    """One deductible expense row of the activity, by its IVA-exclusive base."""

    key: str
    accrued: date
    paid: date
    category: str
    base: Decimal


def seed_profile(persona: Persona) -> None:
    """Store the complete profile of the persona's taxpayer in the active bucket."""
    criterion_facts = () if persona.criterion is None else _criterion_facts(persona)
    seed_test_profile_record(
        create_user_profile_record(
            context=profile_creation_context_for_test(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value=TAX_ID),
                    UserProfileFact(path="identity.name", value="Persona"),
                    UserProfileFact(path="identity.surnames", value="Renta Tester"),
                    UserProfileFact(path="activities.description", value="synthetic persona"),
                    UserProfileFact(path="activities.iae_epigraph", value=persona.iae_epigraph),
                    UserProfileFact(path="taxpayer_type.irpf_income_categories", value=persona.categories),
                    UserProfileFact(path="irpf.estimation_regime", value=persona.regime),
                    UserProfileFact(path="censo.activity_start_date", value=persona.activity_start),
                    *renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)),
                    *criterion_facts,
                )
            ),
            created_at=T0,
            updated_at=T0,
        )
    )


def _criterion_facts(persona: Persona) -> tuple[UserProfileFact, ...]:
    """Declare the persona's imputation criterion for the ejercicio and the ones around it."""
    facts: list[UserProfileFact] = []
    for year in (YEAR - 1, YEAR, YEAR + 1):
        window = {"valid_from": date(year, 1, 1), "valid_to": date(year, 12, 31)}
        for path, value in (
            ("irpf.activity_income_imputation_criterion", persona.criterion),
            ("irpf.estimation_regime", persona.regime),
            ("irpf.codigo_comercio_accounting", False),
        ):
            facts.append(UserProfileFact.model_validate({"path": path, "value": value, **window}))
    return tuple(facts)


def workflow_profile(persona: Persona) -> TaxpayerProfile:
    """The workflow view of the persona's profile that verification and export read."""
    return TaxpayerProfile(
        tax_id=TAX_ID,
        entity_type=EntityType.from_registry("natural_person"),
        irpf_income_categories=frozenset(
            IrpfIncomeCategory.from_registry(token) for token in persona.categories.split(",")
        ),
        irpf_estimation_regime=IrpfEstimationRegime.from_registry(persona.regime),
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_professionals_with_retencion=False,
        art109_activity_income_withholding_ge_70pct=False,
        fiscal_residency=FiscalResidency.from_registry("resident_irpf"),
        pays_rent_with_retencion=False,
        pays_capital_income_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        monedas_virtuales_extranjero_above_threshold=False,
    )


def _run_registered(
    executor: RetencionSoportadaCertificadoExecutor | RetencionSoportadaAbsenceExecutor,
    definition_id: str,
    payload: BaseModel,
    operation: PinnedAuthorityOperation,
) -> str | OperationRefusalEvidence:
    context = executor_context(
        definition_id,
        profile_id=BUCKET_ID,
        operation=operation,
        cancellation=IrreversibleSectionGrant(),
        events=RecordingEvents(),
        operands=RecordingOperands("d" * 64),
    )
    request = profile_operation_request(payload, definition_id, BUCKET_ID)
    return asyncio.run(executor.execute(request, context))


def record_certificate(
    operation: PinnedAuthorityOperation,
    *,
    directory: Path,
    payer: str,
    income_class: RetencionSoportadaClase,
    retencion: str,
    importe_integro: str,
    ingreso_a_cuenta: str = "0.00",
    repercutido: str = "0.00",
    valoracion_especie: str = "0.00",
) -> None:
    """Record one payer's certificate file through the registered operation and require it to be stored."""
    name = f"certificate-{payer}-{income_class.value}.pdf"
    (directory / name).write_bytes(f"%PDF-1.4 synthetic payer certificate {payer} {income_class.value}".encode())
    outcome = _run_registered(
        RetencionSoportadaCertificadoExecutor(
            build_retencion_soportada_certificado_ports,
            definition_id=RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
        ),
        RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
        RetencionSoportadaRecordRequest(
            profile_id=UUID(BUCKET_ID),
            ejercicio=YEAR,
            income_class=income_class,
            payer_tax_id=payer,
            importe_integro_dinerario=PublicDecimal(decimal=importe_integro),
            valoracion_especie=PublicDecimal(decimal=valoracion_especie),
            retencion=PublicDecimal(decimal=retencion),
            ingreso_a_cuenta=PublicDecimal(decimal=ingreso_a_cuenta),
            ingreso_a_cuenta_repercutido=PublicDecimal(decimal=repercutido),
            origin=RetencionSoportadaOrigen.PAYER_CERTIFICATE,
            source_path=name,
            source_directory=str(directory),
        ),
        operation,
    )
    assert not isinstance(outcome, OperationRefusalEvidence), outcome


def attest_no_withholding(operation: PinnedAuthorityOperation, income_class: RetencionSoportadaClase) -> None:
    """Attest through the registered operation that no payer withheld on one income class of the ejercicio."""
    outcome = _run_registered(
        RetencionSoportadaAbsenceExecutor(
            build_retencion_soportada_absence_ports,
            definition_id=RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
        ),
        RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
        RetencionSoportadaAbsenceAttestRequest(
            profile_id=UUID(BUCKET_ID),
            ejercicio=YEAR,
            income_class=income_class,
            note="Synthetic note: no payer withheld on this income.",
        ),
        operation,
    )
    assert not isinstance(outcome, OperationRefusalEvidence), outcome


def _provenance(sha: str) -> RawProvenance:
    return RawProvenance(
        source_path=Path(__file__),
        source_sha256=sha * 64,
        source_row_index=1,
        source_format=SourceFormat.CSV,
        ingested_at=T0,
        provider_name="CSV provider",
    )


def _receipt(invoice: ActivityInvoice, invoice_id: str | None) -> Transaction:
    """The bank receipt that settled ``invoice`` net of its retention, tagged with the invoice's IVA-exclusive base."""
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"cobro-{invoice.number}",
                booked_date=invoice.paid,
                value_date=invoice.paid,
                amount=invoice.net_receipt,
                currency="EUR",
                counterparty="Cliente SL",
                description=f"cobro {invoice.number}",
                provenance=_provenance("e"),
                raw_fields={},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": "actividad_economica",
            "taxable_base": invoice.base,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": T0,
            "classified_by": "manual",
            "invoice_id": invoice_id,
        },
    )


def _invoice(invoice: ActivityInvoice, receipt_id: str) -> Invoice:
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": invoice.number,
            "issued_at": invoice.issued,
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "bucket_id": BUCKET_ID,
            "base_total": invoice.base,
            "iva_total": invoice.iva,
            "grand_total": invoice.base + invoice.iva,
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="Servicios profesionales",
                    quantity=Decimal("1"),
                    unit_price=invoice.base,
                    subtotal=invoice.base,
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    iva_amount=invoice.iva,
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory("domestic_general"),
            "retention_rate": invoice.retention_rate,
            "retention_amount": invoice.retention,
            "linked_transaction_ids": (receipt_id,),
        },
    )


def _expense(expense: ActivityExpense) -> Transaction:
    row = expense_transaction(
        expense.key,
        value_date=expense.paid,
        category=SpendingCategory.from_registry(expense.category),
        taxable_base=expense.base,
    )
    return row.model_copy(update={"accrual_date": expense.accrued})


def seed_activity_ledger(
    objects: SecureObjectRepository, invoices: Iterable[ActivityInvoice], expenses: Iterable[ActivityExpense]
) -> None:
    """Persist the activity's issued invoices with their linked receipts, and its expense rows."""
    rows: list[Transaction] = []
    issued: list[Invoice] = []
    for item in invoices:
        placeholder = _receipt(item, None)
        invoice = _invoice(item, placeholder.transaction_id)
        issued.append(invoice)
        rows.append(_receipt(item, invoice.invoice_id))
    rows.extend(_expense(expense) for expense in expenses)
    TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=objects).save(
        TransactionCatalogue.from_transactions(rows)
    )
    InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=objects).save(build_invoice_catalogue(issued))


def create_work(objects: SecureObjectRepository, *, modelo: str, period: str, revision_id: str | None = None) -> str:
    """Create (or reuse) the work unit of one modelo and period of the ejercicio and return its id."""
    units = WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=objects)
    with bundled_indexed_authority().operation() as operation:
        selected = revision_id or operation.snapshot(modelo, filing_year=YEAR, period=period).revision.id
        return create_work_unit(
            bucket_id=BUCKET_ID,
            modelo=modelo,
            filing_year=YEAR,
            period=Period.from_year_and_code(YEAR, period),
            revision_id=selected,
            ports=WorkLifecyclePorts(
                work_unit_repository=units,
                bucket_event_repository=BucketEventHistoryRepository(objects=objects),
            ),
            operation=operation,
            clock=T0,
        ).work_unit_id


def calculate_and_file_quarter(objects: SecureObjectRepository, period: str) -> CalculationRevision:
    """Calculate one Modelo 130 quarter from the ledger and file it locally, so the next quarter carries it."""
    units = WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=objects)
    work_unit_id = create_work(objects, modelo="130", period=period, revision_id="2019-y-siguientes")
    revision = calculate_revision_from_bucket_aggregation(
        work_unit_id,
        casilla_inputs={validated_casilla_id("16"): Decimal("0"), validated_casilla_id("18"): Decimal("0")},
        work_unit_repository=units,
        clock=T0,
    ).revision
    persist_filed_revision_observation(
        revision=revision,
        work_unit=units.load().work_units[work_unit_id],
        repository=CalculationObservationRepository(objects=objects),
        captured_at=FILE_AT,
        iva_compensation_history_repository=IvaCompensationHistoryRepository(),
    )
    return revision


def calculate_annual(
    objects: SecureObjectRepository,
    *,
    casilla_inputs: dict[CasillaId, Decimal] | None = None,
    text_casilla_inputs: dict[CasillaId, str] | None = None,
    binding_values: dict[str, Decimal] | None = None,
) -> CalculationRevision:
    """Run the live annual Modelo 100 calculation over the seeded bucket and return its revision."""
    work_unit_id = create_work(objects, modelo="100", period="0A")
    return calculate_revision_from_bucket_aggregation(
        work_unit_id,
        casilla_inputs=casilla_inputs,
        text_casilla_inputs=text_casilla_inputs,
        binding_values={**m100_non_relation_zero_bindings(), **(binding_values or {})},
        work_unit_repository=WorkUnitCatalogueRepository(bucket_id=BUCKET_ID, objects=objects),
        clock=T0,
    ).revision


def register_refund_account(objects: SecureObjectRepository) -> None:
    """Designate a Spanish own account to receive a refund, as the export's account page needs."""

    def change(register: OwnAccountRegister) -> OwnAccountRegister:
        account_id = register.next_account_id()
        return register.with_new_account(
            OwnBankAccountDetails(label="Devolución", holding=OwnAccountHolding.TITULAR, iban=REFUND_IBAN)
        ).with_designation(OwnAccountDesignation(role=OwnAccountRole.REFUND, own_account_id=account_id))

    OwnAccountRepository(objects=objects).mutate(change)


def verify_and_export(
    revision: CalculationRevision, objects: SecureObjectRepository, output: Path, persona: Persona
) -> bytes:
    """Require complete verification of ``revision``, export it locally and return the written bytes."""
    report = verify_revision_for_test(
        revision.calculation_revision_id,
        actor="renta-persona",
        workflow_profile=workflow_profile(persona),
        settings=ready_clave_settings(TAX_ID),
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )
    assert report.granted_verificado_completo is True, report.findings
    receipt = export_revision_for_test(
        ModeloExportCommand(
            calculation_revision_id=revision.calculation_revision_id, output_path=output, actor="renta-persona"
        ),
        workflow_profile=workflow_profile(persona),
        export_ports=modelo_export_ports_for_test(bucket_id=BUCKET_ID, taxpayer_tax_id=TAX_ID, secure_objects=objects),
    )
    payload = output.read_bytes()
    assert receipt.byte_size == len(payload)
    return payload
