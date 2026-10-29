"""Measure every ledger read the TUI Records screens call, at 30,000-transaction scale.

The Records workspace reaches the ledger only through registered read
operations. This module seeds one REAL profile -- registered and logged in
through the canonical credential path, with encrypted profile custody, the
operation journal and lease store of
:func:`~cadrumo.entrypoints.tests.registered_executor_case_support.conformance_operation_runtime`
-- with 30,000 synthetic transactions across ten filing years and
proportionate synthetic invoices, evidence, classification rules, usage
ratios, prorrata, inventory and capital-goods records. Each read is then
submitted to the canonical composed supervisor services a runtime door reaches
over native IPC: submission, start, settlement, then resolution of the
encrypted public result. The IPC hop itself is not measured. Nothing in the
measured path is a double.

The request shapes are the ones the TUI screens build: one 200-row
``ledger.list`` page, the health screen's period, the trace screen's single
entry, the registers' unparameterised lists. The workbench generation that
builds the Records projection is composed the way the runtime host composes
it for ``workbench.generation`` and projected through the same public
projection, because the conformance runtime binds no host reader for that
operation.

Every number is PROCESS CPU-time (all threads, so the supervisor's worker
threads count) and is printed with its wall-clock as diagnostics. No timing is
asserted: budgets are decided from these measurements. The assertions are
structural -- each read settled successfully, declared no effect, and returned
the projection type and shape its screen consumes.
"""

from __future__ import annotations

import asyncio
import statistics
import tempfile
import time
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Final
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from cadrumo.application.bienes_inversion.declare_command import (
    BienInversionDeclarationCommand,
    build_bien_inversion_record,
)
from cadrumo.application.bienes_inversion.registered_requests import BienesInversionListRequest
from cadrumo.application.bienes_inversion.registered_result_contracts import BienesInversionListProjection
from cadrumo.application.bienes_inversion.service import BienesInversionRegisterService
from cadrumo.application.inventory.registered_projections import InventoryListProjection
from cadrumo.application.inventory.registered_requests import InventoryListRequest
from cadrumo.application.inventory.service import InventoryService
from cadrumo.application.invoices.catalogue_read_operation import (
    InvoiceListProjection,
    InvoiceListRequest,
    InvoiceViewProjection,
    InvoiceViewRequest,
)
from cadrumo.application.ledger.check_operation import LedgerCheckRequest
from cadrumo.application.ledger.evidence import PurchaseInvoiceEvidenceService
from cadrumo.application.ledger.evidence_followup_contracts import (
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceAttachmentQueueProjection,
    LedgerEvidenceAttachmentQueueRequest,
    LedgerEvidenceConsentListProjection,
    LedgerEvidenceConsentListRequest,
    LedgerEvidenceReviewListProjection,
    LedgerEvidenceReviewListRequest,
    LedgerEvidenceReviewViewRequest,
)
from cadrumo.application.ledger.evidence_read_operation import (
    LedgerEvidenceListProjection,
    LedgerEvidenceListRequest,
    LedgerEvidenceQueryProjection,
    LedgerEvidenceQueryRequest,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRequest,
    LedgerEvidenceViewSuccess,
)
from cadrumo.application.ledger.evidence_review_summaries import LedgerEvidenceReviewSummaryProjection
from cadrumo.application.ledger.history_operation import LedgerHistoryRequest
from cadrumo.application.ledger.list_operation import LedgerListRequest
from cadrumo.application.ledger.llm_diagnostics import DEFAULT_LOW_CONFIDENCE_THRESHOLD
from cadrumo.application.ledger.llm_diagnostics_operation import (
    LedgerLlmDiagnosticsProjection,
    LedgerLlmDiagnosticsRequest,
)
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand
from cadrumo.application.ledger.participation_operation import LedgerParticipationRequest
from cadrumo.application.ledger.preflight_operation import LedgerPreflightRequest
from cadrumo.application.ledger.ratios_contracts import (
    LedgerRatiosEligibleProjection,
    LedgerRatiosEligibleRequest,
    LedgerRatiosListProjection,
    LedgerRatiosListRequest,
)
from cadrumo.application.ledger.review_operation import LedgerReviewRequest
from cadrumo.application.ledger.rule_contracts import LedgerRuleListRequest
from cadrumo.application.ledger.status_operation import LedgerStatusRequest
from cadrumo.application.ledger.tests.manual_transaction_support import create_manual_transaction
from cadrumo.application.ledger.track_operation import LedgerTrackRequest
from cadrumo.application.ledger.usage_ratio_repository import save_usage_ratio_profile
from cadrumo.application.ledger.view_operation import LedgerViewRequest
from cadrumo.application.operations.composition import OperationComposedServices
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.overview.home import HomeAccountSession, HomeSessionPosture
from cadrumo.application.prorrata_register.operation_requests import ProrrataListRequest
from cadrumo.application.prorrata_register.projection_contracts import ProrrataListProjection
from cadrumo.application.workbench_generation_projection import project_workbench_generation
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.ledger_sort import LedgerSortField
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.period import Period
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.categories.spending_category_catalogue import require_spending_category
from cadrumo.domain.invoices.catalogue import InvoiceCatalogue
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus
from cadrumo.domain.invoices.models import Invoice, InvoiceLine
from cadrumo.domain.iva.schema import InvoiceKind
from cadrumo.domain.transactions.classification_rule import LedgerClassificationRule
from cadrumo.domain.transactions.enums import (
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.usage_ratios.model import UsageRatioProfile
from cadrumo.domain.user_profile.values import UserProfileFact
from cadrumo.entrypoints.adapter_composition_ports import (
    build_bienes_inversion_repository,
    build_inventory_service_ports,
    build_prorrata_register_repository,
)
from cadrumo.entrypoints.adapter_composition_work_ports import build_ledger_evidence_ports
from cadrumo.entrypoints.ledger_action_composition import compose_ledger_action_ports
from cadrumo.entrypoints.tests.evidence_followup_operation_test_support import (
    prepare_evidence_followup_conformance_case,
)
from cadrumo.entrypoints.tests.prorrata_operation_test_support import prepare_prorrata_operation_conformance_case
from cadrumo.entrypoints.tests.registered_executor_case_support import (
    OperationRuntimeCloseWitness,
    conformance_operation_runtime,
)
from cadrumo.entrypoints.workbench_generation_composition import compose_secure_workbench_generation_provider

pytestmark = [pytest.mark.integration, pytest.mark.perf, pytest.mark.serial, pytest.mark.hex_entrypoint]

_TOTAL_TRANSACTIONS: Final = 30_000
_FILING_YEARS: Final = 10
_TRANSACTIONS_PER_YEAR: Final = _TOTAL_TRANSACTIONS // _FILING_YEARS
#: Ten complete filing years ending in the current one, so every seeded row is
#: in the past and every measured period is one the registry supports.
_FIRST_YEAR: Final = 2017
_LAST_YEAR: Final = _FIRST_YEAR + _FILING_YEARS - 1
#: Invoices and registers resolve governed facts, which the registry answers
#: only from its supported-filing-year floor; those families span the
#: supported years inside the ledger's ten.
_FIRST_SUPPORTED_YEAR: Final = 2022
_SUPPORTED_YEARS: Final = tuple(range(_FIRST_SUPPORTED_YEAR, _LAST_YEAR + 1))
#: One row in ten is left unreviewed, so review surfaces carry real work.
_UNREVIEWED_EVERY: Final = 10
#: Proportions per ten-year ledger: one invoice per ten bank rows, one stored
#: evidence document per hundred, a working rule set, one inventory and one
#: capital good per supported year.
_INVOICES: Final = _TOTAL_TRANSACTIONS // 10
_EVIDENCE_DOCUMENTS: Final = _TOTAL_TRANSACTIONS // 100
_RULES: Final = 25
_RATIO_YEAR: Final = 2025
#: Taxable bases spread over 10.00 to 4,010.00 EUR.
_AMOUNT_SPREAD_CENTS: Final = 400_000
_CENT: Final = Decimal("0.01")
#: The Records list and bulk screens read one page of this size.
_PAGE_SIZE: Final = 200
_SAMPLES: Final = 5
_MEASURED_PERIOD: Final = Period.from_year_and_code(_LAST_YEAR, "3T")
_ACTOR: Final = "ledger-tui-reads-benchmark"
_ACTOR_REF: Final = "benchmark:ledger-tui-reads"

_PROFILE_FACTS: Final = (
    UserProfileFact(path="identity.name", value="Escala"),
    UserProfileFact(path="identity.surnames", value="Lectura Prueba"),
    UserProfileFact(path="activities.description", value="design services"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
    UserProfileFact(path="censo.activity_start_date", value=date(2016, 1, 1)),
)


# ---------------------------------------------------------------------------
# Seeding (untimed setup)
# ---------------------------------------------------------------------------


def _dates_across_year(year: int, count: int) -> Iterator[date]:
    start = date(year, 1, 1)
    span_days = (date(year, 12, 31) - start).days
    for i in range(count):
        yield start + timedelta(days=(i * span_days) // max(count - 1, 1))


def _base_and_iva(idx: int, *, stride: int) -> tuple[Decimal, Decimal]:
    """A spread taxable base and its 21 % IVA, so amounts rarely coincide.

    Identical amounts would make every invoice a reconciliation candidate for
    every bank row, a degenerate ledger no operator holds.
    """
    base = (Decimal(1_000 + (idx * stride) % _AMOUNT_SPREAD_CENTS) / 100).quantize(_CENT)
    return base, (base * Decimal("0.21")).quantize(_CENT, rounding=ROUND_HALF_UP)


def _synthetic_transaction(idx: int, *, booked: date) -> Transaction:
    """One bank row: classified business spending or income, or left for review."""
    base, iva = _base_and_iva(idx, stride=7_919)
    raw = RawTransaction(
        provider_transaction_id=f"tui-reads-row-{idx:06d}",
        booked_date=booked,
        value_date=booked,
        amount=base + iva,
        currency="EUR",
        counterparty=f"Proveedor Escala {idx % 37:02d} SL",
        description=f"tui reads benchmark row {idx}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=idx + 1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(booked.year, booked.month, booked.day, 12, 0, tzinfo=UTC),
            provider_name="tui reads benchmark provider",
        ),
        raw_fields={"Concepto": f"row {idx}"},
    )
    direction = TransactionDirection.OUTGOING if idx % 3 else TransactionDirection.INCOMING
    if idx % _UNREVIEWED_EVERY == 0:
        return Transaction.model_validate(
            {
                "raw": raw,
                "direction": direction,
                "group_label": None,
                "source_jurisdiction": "ES",
                "business_classification": BusinessClassification.NOT_YET_PROCESSED,
                "business_pct": None,
                "purchase_invoice_evidence_id": None,
                "lifecycle_state": TransactionLifecycleState.ACTIVE,
            },
        )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": "material_oficina",
            "taxable_base": base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(booked.year, booked.month, booked.day, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _seed_transactions(bucket_id: str) -> None:
    transactions: list[Transaction] = []
    idx = 0
    for year in range(_FIRST_YEAR, _LAST_YEAR + 1):
        for booked in _dates_across_year(year, _TRANSACTIONS_PER_YEAR):
            transactions.append(_synthetic_transaction(idx, booked=booked))
            idx += 1
    TransactionCatalogueRepository(bucket_id=bucket_id).save(TransactionCatalogue.from_transactions(transactions))


def _seed_selected_entry(bucket_id: str, operation: PinnedAuthorityOperation) -> str:
    """Create the one entry the trace screens open, through the manual-add path that records its events."""
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=bucket_id,
            booked_date=date(_LAST_YEAR, 8, 14),
            amount=Decimal("242.00"),
            direction=TransactionDirection.OUTGOING,
            description="tui reads benchmark selected entry",
            business_classification=BusinessClassification.NOT_YET_PROCESSED,
            actor=_ACTOR,
        ),
        ports=compose_ledger_action_ports(bucket_id=bucket_id, operation=operation),
        occurred_at=now(),
    )
    return created.ref.transaction_id


def _synthetic_invoice(idx: int, *, bucket_id: str) -> Invoice:
    year = _SUPPORTED_YEARS[idx % len(_SUPPORTED_YEARS)]
    issued_at = date(year, 1 + idx % 9, 1 + idx % 28)
    kind = InvoiceKind.RECEIVED if idx % 2 else InvoiceKind.ISSUED
    base, iva = _base_and_iva(idx, stride=104_729)
    return Invoice.model_validate(
        {
            "kind": kind,
            "bucket_id": bucket_id,
            "invoice_number": f"TUI-READS-{year}-{idx:05d}",
            "issued_at": issued_at,
            "counterparty_name": f"Contraparte Escala {idx % 53:02d} SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": base,
            "iva_total": iva,
            "grand_total": base + iva,
            "currency": "EUR",
            "payment_status": PaymentStatus.PAID,
            "lines": (
                InvoiceLine(
                    description=f"Servicio escala {idx}",
                    quantity=Decimal("1"),
                    unit_price=base,
                    subtotal=base,
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    iva_amount=iva,
                ),
            ),
        }
    )


def _seed_invoices(bucket_id: str) -> str:
    invoices = [_synthetic_invoice(idx, bucket_id=bucket_id) for idx in range(_INVOICES)]
    InvoiceCatalogueRepository(bucket_id=bucket_id).save(
        InvoiceCatalogue(invoices={invoice.invoice_id: invoice for invoice in invoices})
    )
    return invoices[-1].invoice_id


def _seed_evidence(bucket_id: str, directory: Path) -> str:
    """Store synthetic purchase-invoice documents; returns the last evidence id."""
    service = PurchaseInvoiceEvidenceService(ports=build_ledger_evidence_ports(bucket_id=bucket_id))
    evidence_id = ""
    for idx in range(_EVIDENCE_DOCUMENTS):
        source = directory / f"tui-reads-evidence-{idx:04d}.pdf"
        source.write_bytes(
            b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n"
            + f"% tui reads benchmark document {idx}\n".encode()
            + b"trailer<</Root 1 0 R>>\n%%EOF\n"
        )
        evidence_id = service.add(bucket_id=bucket_id, source_path=source).record.evidence_id
    return evidence_id


def _seed_rules(bucket_id: str) -> None:
    repository = LedgerClassificationRuleRepository(bucket_id=bucket_id)
    for idx in range(_RULES):
        repository.save(
            LedgerClassificationRule.create(
                description_pattern=f"^tui reads benchmark row {idx}\\d*$",
                classification=BusinessClassification.BUSINESS,
                category_id="material_oficina",
                priority=100 + idx,
                actor=_ACTOR,
            )
        )


def _seed_ratios(bucket_id: str, operation: PinnedAuthorityOperation) -> None:
    category = require_spending_category("vehiculo_combustible", authority=operation)
    save_usage_ratio_profile(UsageRatioProfile(ratios={category: Decimal("0.50")}), bucket_id=bucket_id)


def _seed_registers(profile_id: UUID, operation: PinnedAuthorityOperation) -> None:
    bucket_id = str(profile_id)
    prepare_prorrata_operation_conformance_case(
        "ledger.prorrata.list",
        profile_id,
        repository_factory=build_prorrata_register_repository,
        operation=operation,
    )
    inventory = InventoryService(ports=build_inventory_service_ports(bucket_id=bucket_id))
    for year in _SUPPORTED_YEARS:
        inventory.create(
            bucket_id=bucket_id,
            actividad_id=f"tui-reads-inventory-{year}",
            year=year,
            valuation_method="fifo",
            opening_stock=Decimal("0"),
            actor=_ACTOR,
        )
    capital_goods = BienesInversionRegisterService(repository=build_bienes_inversion_repository(bucket_id=bucket_id))
    with validating_governed_facts(operation):
        for year in _SUPPORTED_YEARS:
            capital_goods.declare(
                build_bien_inversion_record(
                    BienInversionDeclarationCommand(
                        identifier=f"tui-reads-bien-{year}",
                        description=f"Bien de inversion {year}",
                        acquisition_year=year,
                        acquisition_ledger_id=f"tui-reads-bien-{year}-ledger",
                        cuota_soportada=Decimal("2100.00"),
                        prorrata_inicial_pct=Decimal("60"),
                        kind="mueble",
                        art108_elegible=True,
                        prorrata_sector_id="sector-tui-reads",
                    ),
                )
            )


# ---------------------------------------------------------------------------
# Measured reads
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LedgerTuiWorld:
    """The seeded profile, its composed supervisor, and the identities the screens open."""

    services: OperationComposedServices
    registry: OperationRegistry
    profile_id: UUID
    operation: PinnedAuthorityOperation
    selected_transaction_id: str
    invoice_id: str
    evidence_id: str
    review_request: LedgerEvidenceReviewViewRequest


@dataclass(frozen=True, slots=True)
class ReadCase:
    """One TUI read: its operation, the request its screen builds, and the shape the screen relies on."""

    name: str
    definition_id: str
    request: Callable[[LedgerTuiWorld], BaseModel]
    shape: Callable[[LedgerTuiWorld, BaseModel], None]
    #: The public projection the screen's door resolves, where it differs from
    #: the registered execution result.
    projection: type[BaseModel] | None = None


@dataclass(frozen=True, slots=True)
class ReadMeasurement:
    """CPU and wall samples for one case, in submission order."""

    name: str
    cpu: tuple[float, ...]
    wall: tuple[float, ...]

    @property
    def cpu_p95(self) -> float:
        """Nearest-rank 95th percentile of the CPU samples."""
        return _p95(self.cpu)

    def line(self) -> str:
        """Render the diagnostic row."""
        return (
            f"[bench] {self.name}: n={len(self.cpu)} cpu_p95={self.cpu_p95:.3f}s "
            f"cpu_mean={statistics.mean(self.cpu):.3f}s cpu_min={min(self.cpu):.3f}s "
            f"wall_p95={_p95(self.wall):.3f}s wall_mean={statistics.mean(self.wall):.3f}s (wall advisory)"
        )


def _p95(samples: tuple[float, ...]) -> float:
    """Nearest-rank 95th percentile, no interpolation."""
    ordered = sorted(samples)
    return ordered[max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))]


def _period() -> PublicPeriod:
    return PublicPeriod.from_period(_MEASURED_PERIOD)


def _attribute(projection: BaseModel, name: str) -> object:
    value: object = getattr(projection, name)
    return value


def _owned(world: LedgerTuiWorld, projection: BaseModel) -> None:
    assert _attribute(projection, "profile_id") == world.profile_id


def _rows(projection: BaseModel, name: str) -> tuple[object, ...]:
    value = _attribute(projection, name)
    assert isinstance(value, tuple)
    return value


def _unfiltered_page(world: LedgerTuiWorld, projection: BaseModel) -> None:
    _owned(world, projection)
    assert len(_rows(projection, "rows")) == _PAGE_SIZE
    assert _attribute(projection, "total") == _TOTAL_TRANSACTIONS + 1


def _period_page(world: LedgerTuiWorld, projection: BaseModel) -> None:
    _owned(world, projection)
    total = _attribute(projection, "total")
    assert isinstance(total, int)
    assert _PAGE_SIZE < total < _TRANSACTIONS_PER_YEAR
    assert len(_rows(projection, "rows")) == _PAGE_SIZE


def _single_entry(world: LedgerTuiWorld, projection: BaseModel) -> None:
    _owned(world, projection)
    transaction = _attribute(projection, "transaction")
    assert isinstance(transaction, BaseModel)
    assert _attribute(transaction, "transaction_id") == world.selected_transaction_id


def _history(world: LedgerTuiWorld, projection: BaseModel) -> None:
    _owned(world, projection)
    assert _attribute(projection, "transaction_id") == world.selected_transaction_id
    assert _rows(projection, "events")


def _counted(name: str, expected: int) -> Callable[[LedgerTuiWorld, BaseModel], None]:
    def check(world: LedgerTuiWorld, projection: BaseModel) -> None:
        _owned(world, projection)
        assert _attribute(projection, name) == expected

    return check


def _listed(name: str, expected: int) -> Callable[[LedgerTuiWorld, BaseModel], None]:
    def check(world: LedgerTuiWorld, projection: BaseModel) -> None:
        _owned(world, projection)
        assert len(_rows(projection, name)) == expected

    return check


def _health(world: LedgerTuiWorld, projection: BaseModel) -> None:
    _owned(world, projection)
    checked = _attribute(projection, "checked_transaction_count")
    assert isinstance(checked, int)
    assert checked > 0


def _evidence_view(world: LedgerTuiWorld, projection: BaseModel) -> None:
    _owned(world, projection)
    assert isinstance(_attribute(projection, "outcome"), LedgerEvidenceViewSuccess)


def _pending(name: str) -> Callable[[LedgerTuiWorld, BaseModel], None]:
    def check(world: LedgerTuiWorld, projection: BaseModel) -> None:
        _owned(world, projection)
        assert _rows(projection, name)

    return check


def _review_summary(world: LedgerTuiWorld, projection: BaseModel) -> None:
    _owned(world, projection)
    assert _attribute(projection, "evidence_reference") == world.review_request.evidence_reference


def _invoice_view(world: LedgerTuiWorld, projection: BaseModel) -> None:
    _owned(world, projection)
    assert _attribute(projection, "invoice_id") == world.invoice_id


def _participation(world: LedgerTuiWorld, projection: BaseModel) -> None:
    _owned(world, projection)
    assert _attribute(projection, "transaction_id") == world.selected_transaction_id


def _review(world: LedgerTuiWorld, projection: BaseModel) -> None:
    _owned(world, projection)
    assert len(_rows(projection, "rows")) > _TOTAL_TRANSACTIONS // _UNREVIEWED_EVERY // 2


READ_CASES: Final[tuple[ReadCase, ...]] = (
    ReadCase(
        "ledger.list.unfiltered_page",
        "ledger.list",
        lambda w: LedgerListRequest(profile_id=w.profile_id, limit=_PAGE_SIZE),
        _unfiltered_page,
    ),
    ReadCase(
        "ledger.list.period_page",
        "ledger.list",
        lambda w: LedgerListRequest(
            profile_id=w.profile_id,
            filters=(f"period={_MEASURED_PERIOD.registry_token}", f"year={_LAST_YEAR}"),
            limit=_PAGE_SIZE,
            sort_by=LedgerSortField.DATE,
        ),
        _period_page,
    ),
    ReadCase(
        "ledger.view",
        "ledger.view",
        lambda w: LedgerViewRequest(profile_id=w.profile_id, transaction_prefix=w.selected_transaction_id),
        _single_entry,
    ),
    ReadCase(
        "ledger.history",
        "ledger.history",
        lambda w: LedgerHistoryRequest(profile_id=w.profile_id, transaction_prefix=w.selected_transaction_id),
        _history,
    ),
    ReadCase(
        "ledger.track",
        "ledger.track",
        lambda w: LedgerTrackRequest(profile_id=w.profile_id, transaction_prefix=w.selected_transaction_id),
        _single_entry,
    ),
    ReadCase(
        "ledger.status.period",
        "ledger.status",
        lambda w: LedgerStatusRequest(profile_id=w.profile_id, period=_period()),
        _health,
    ),
    ReadCase(
        "ledger.check.period",
        "ledger.check",
        lambda w: LedgerCheckRequest(profile_id=w.profile_id, period=_period()),
        _health,
    ),
    ReadCase(
        "ledger.preflight.period",
        "ledger.preflight",
        lambda w: LedgerPreflightRequest(profile_id=w.profile_id, period=_period()),
        _health,
    ),
    ReadCase(
        "ledger.invoice.list",
        "ledger.invoice.list",
        lambda w: InvoiceListRequest(profile_id=w.profile_id),
        _listed("invoices", _INVOICES),
        InvoiceListProjection,
    ),
    ReadCase(
        "ledger.invoice.view",
        "ledger.invoice.view",
        lambda w: InvoiceViewRequest(profile_id=w.profile_id, invoice_id=w.invoice_id),
        _invoice_view,
        InvoiceViewProjection,
    ),
    ReadCase(
        "ledger.evidence.list",
        "ledger.evidence.list",
        lambda w: LedgerEvidenceListRequest(profile_id=w.profile_id),
        _counted("count", _EVIDENCE_DOCUMENTS + 1),
        LedgerEvidenceListProjection,
    ),
    ReadCase(
        "ledger.evidence.query",
        "ledger.evidence.query",
        lambda w: LedgerEvidenceQueryRequest(profile_id=w.profile_id),
        _counted("count", _EVIDENCE_DOCUMENTS + 1),
        LedgerEvidenceQueryProjection,
    ),
    ReadCase(
        "ledger.evidence.view",
        "ledger.evidence.view",
        lambda w: LedgerEvidenceViewRequest(profile_id=w.profile_id, evidence_id=w.evidence_id),
        _evidence_view,
        LedgerEvidenceViewProjection,
    ),
    ReadCase(
        "ledger.evidence.attachment_queue",
        "ledger.evidence.attachment_queue",
        lambda w: LedgerEvidenceAttachmentQueueRequest(profile_id=w.profile_id),
        _pending("rows"),
        LedgerEvidenceAttachmentQueueProjection,
    ),
    ReadCase(
        "ledger.evidence.review.list",
        "ledger.evidence.review.list",
        lambda w: LedgerEvidenceReviewListRequest(profile_id=w.profile_id),
        _pending("rows"),
        LedgerEvidenceReviewListProjection,
    ),
    ReadCase(
        "ledger.evidence.review.summary",
        "ledger.evidence.review.summary",
        lambda w: w.review_request,
        _review_summary,
        LedgerEvidenceReviewSummaryProjection,
    ),
    ReadCase(
        "ledger.evidence.consent.list",
        "ledger.evidence.consent.list",
        lambda w: LedgerEvidenceConsentListRequest(profile_id=w.profile_id),
        _owned,
        LedgerEvidenceConsentListProjection,
    ),
    ReadCase(
        "ledger.rule.list",
        "ledger.rule.list",
        lambda w: LedgerRuleListRequest(profile_id=w.profile_id),
        _listed("rules", _RULES),
    ),
    ReadCase(
        "ledger.ratios.list",
        "ledger.ratios.list",
        lambda w: LedgerRatiosListRequest(profile_id=w.profile_id, year=_RATIO_YEAR),
        _counted("count", 1),
        LedgerRatiosListProjection,
    ),
    ReadCase(
        "ledger.ratios.eligible",
        "ledger.ratios.eligible",
        lambda w: LedgerRatiosEligibleRequest(profile_id=w.profile_id, year=_RATIO_YEAR),
        _pending("rows"),
        LedgerRatiosEligibleProjection,
    ),
    ReadCase(
        "ledger.participation",
        "ledger.participation",
        lambda w: LedgerParticipationRequest(profile_id=w.profile_id, transaction_prefix=w.selected_transaction_id),
        _participation,
    ),
    ReadCase(
        "ledger.prorrata.list",
        "ledger.prorrata.list",
        lambda w: ProrrataListRequest(profile_id=w.profile_id),
        _pending("entries"),
        ProrrataListProjection,
    ),
    ReadCase(
        "ledger.bienes_inversion.list",
        "ledger.bienes_inversion.list",
        lambda w: BienesInversionListRequest(profile_id=w.profile_id),
        _listed("rows", len(_SUPPORTED_YEARS)),
        BienesInversionListProjection,
    ),
    ReadCase(
        "ledger.inventory.list",
        "ledger.inventory.list",
        lambda w: InventoryListRequest(profile_id=w.profile_id),
        _listed("rows", len(_SUPPORTED_YEARS)),
        InventoryListProjection,
    ),
    ReadCase(
        "ledger.review",
        "ledger.review",
        lambda w: LedgerReviewRequest(profile_id=w.profile_id),
        _review,
    ),
    ReadCase(
        "ledger.llm-diagnostics",
        "ledger.llm-diagnostics",
        lambda w: LedgerLlmDiagnosticsRequest(
            profile_id=w.profile_id,
            low_confidence_threshold=PublicDecimal(decimal=str(DEFAULT_LOW_CONFIDENCE_THRESHOLD)),
        ),
        _owned,
        LedgerLlmDiagnosticsProjection,
    ),
)


async def _submit_and_resolve(world: LedgerTuiWorld, case: ReadCase) -> BaseModel:
    """Submit, start, settle and resolve one read through the canonical composed supervisor."""
    services = world.services
    submitted = await services.submission.submit(
        OperationRequest(
            definition_id=case.definition_id,
            subject_ref=profile_operation_subject(str(world.profile_id)),
            payload=case.request(world),
        ),
        actor_ref=_ACTOR_REF,
    )
    assert submitted.receipt.secret_requirement is None
    operation_id = submitted.receipt.operation_id
    await services.submission.start(operation_id)
    await services.submission.settled(operation_id)
    observed = await services.observation.observe(
        OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=256)
    )
    assert isinstance(observed, OperationObservationSuccessV1)
    settled = observed.projection
    assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED, (
        f"{case.name} settled {settled.terminal_condition} ({settled.refusal_ref or settled.failure_error_code})"
    )
    assert settled.effect is OperationEffect.NONE
    definition = world.registry.lookup(case.definition_id)
    contract = world.registry.lookup_public_contract(case.definition_id)
    result_type = case.projection or definition.result_type
    assert contract.result_schema is not None
    assert result_type is not None
    resolved = await services.result.resolve(
        OperationResultProjectionRequestV1(
            operation_id=operation_id,
            terminal_revision=settled.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=contract.result_schema,
        ),
        result_type,
    )
    assert isinstance(resolved, OperationResultProjectionSuccessV1)
    result = resolved.projection
    assert isinstance(result, result_type)
    return result


def run_case_once(world: LedgerTuiWorld, case: ReadCase) -> BaseModel:
    """One complete TUI read of ``case``; the unit every sample times."""
    projection = asyncio.run(_submit_and_resolve(world, case))
    case.shape(world, projection)
    return projection


def build_workbench_generation_once(world: LedgerTuiWorld) -> BaseModel:
    """Compose and capture one generation the way the runtime host does, then project it publicly."""
    with override_settings(cadrumo_output_language=OutputLanguage.ES.value):
        provider = compose_secure_workbench_generation_provider(
            profile_id=str(world.profile_id),
            operation=world.operation,
            operation_contracts=world.registry.public_contract_set,
            account_session_reader=lambda: HomeAccountSession(
                posture=HomeSessionPosture.ACTIVE,
                profile_label="ledger tui reads benchmark",
                expires_at=now() + timedelta(hours=1),
            ),
        )
        generation = provider()
    assert generation.ledger.projection is not None
    projection = project_workbench_generation(world.profile_id, generation)
    assert projection.profile_id == world.profile_id
    return projection


def _measure(name: str, call: Callable[[], object]) -> ReadMeasurement:
    cpu: list[float] = []
    wall: list[float] = []
    for _ in range(_SAMPLES):
        wall_started = time.perf_counter()
        cpu_started = time.process_time()
        call()
        cpu.append(time.process_time() - cpu_started)
        wall.append(time.perf_counter() - wall_started)
    return ReadMeasurement(name=name, cpu=tuple(cpu), wall=tuple(wall))


@contextmanager
def ledger_tui_world(tmp_path: Path) -> Generator[LedgerTuiWorld]:
    """Register, log in and seed one profile, then yield its composed supervisor."""
    with (
        bundled_indexed_authority().operation() as operation,
        conformance_operation_runtime(tmp_path / "runtime", cleanup=OperationRuntimeCloseWitness()) as (
            driver,
            registry,
            profile_id,
        ),
    ):
        bucket_id = str(profile_id)
        upsert_test_profile_facts(profile_id, _PROFILE_FACTS)
        _seed_transactions(bucket_id)
        selected = _seed_selected_entry(bucket_id, operation)
        invoice_id = _seed_invoices(bucket_id)
        documents = tmp_path / "documents"
        documents.mkdir()
        evidence_id = _seed_evidence(bucket_id, documents)
        followup = prepare_evidence_followup_conformance_case(
            LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID, profile_id=profile_id, operation=operation
        )
        assert isinstance(followup.request, LedgerEvidenceReviewViewRequest)
        _seed_rules(bucket_id)
        _seed_ratios(bucket_id, operation)
        _seed_registers(profile_id, operation)
        yield LedgerTuiWorld(
            services=driver.services,
            registry=registry,
            profile_id=profile_id,
            operation=operation,
            selected_transaction_id=selected,
            invoice_id=invoice_id,
            evidence_id=evidence_id,
            review_request=followup.request,
        )


@pytest.fixture(scope="module")
def world() -> Iterator[LedgerTuiWorld]:
    """One seeded profile shared by every measured read; seeding is untimed setup."""
    with (
        tempfile.TemporaryDirectory(prefix="cadrumo-tui-reads-bench-") as tmp_dir,
        ledger_tui_world(Path(tmp_dir)) as seeded,
    ):
        yield seeded


def test_seeded_profile_holds_the_documented_volume(world: LedgerTuiWorld) -> None:
    """The ledger really holds 30,000 seeded rows over ten years plus the selected entry."""
    catalogue = TransactionCatalogueRepository(bucket_id=str(world.profile_id)).load()
    assert len(catalogue) == _TOTAL_TRANSACTIONS + 1
    years = {transaction.raw.booked_date.year for transaction in catalogue.values()}
    assert years == set(range(_FIRST_YEAR, _LAST_YEAR + 1))


@pytest.mark.parametrize("case", READ_CASES, ids=lambda case: case.name)
def test_tui_read_reports_cpu_at_scale(world: LedgerTuiWorld, case: ReadCase) -> None:
    """Report one TUI read's CPU cost at 30,000 rows; every sample must settle with its screen's shape."""
    measurement = _measure(case.name, lambda: run_case_once(world, case))
    print("\n" + measurement.line())


def test_workbench_generation_reports_cpu_at_scale(world: LedgerTuiWorld) -> None:
    """Report the cost of the generation that builds the Records projection at 30,000 rows."""
    measurement = _measure("workbench.generation", lambda: build_workbench_generation_once(world))
    print("\n" + measurement.line())
