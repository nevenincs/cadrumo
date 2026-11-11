"""Build the exact requests of the ledger, evidence, invoice, inventory and activity-asset operations."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...application.actividad_asset.operation_dtos import (
    ActivityAssetCorrectionRevisionSnapshot,
    ActivityAssetDisposalSnapshot,
    ActivityAssetRevisionSnapshot,
    ScheduledAmortizationChargeSnapshot,
)
from ...application.inventory.tests.registered_operation_conformance_support import (
    prepare_inventory_operation_conformance_case,
)
from ...application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
from ...application.invoices.catalogue_read_operation import INVOICE_LIST_OPERATION_DEFINITION_ID
from ...application.invoices.catalogue_remove_operation import INVOICE_REMOVE_OPERATION_DEFINITION_ID
from ...application.invoices.catalogue_update_operation import (
    INVOICE_UPDATE_OPERATION_DEFINITION_ID,
    InvoiceUpdatePatch,
)
from ...application.invoices.figures_preview_contracts import InvoiceFiguresPreviewLine
from ...application.ledger.action_ports import LedgerActionPorts
from ...application.ledger.actions_import import LedgerProviderID
from ...application.ledger.actions_split_merge import split_transaction
from ...application.ledger.classify_requests import LedgerClassifyPatch
from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_mutation_operation import LedgerEvidenceUpdatePatch
from ...application.ledger.llm_classification import reject_llm_suggestion
from ...application.ledger.llm_classification_ports import LLMClassificationSuggestion
from ...application.ledger.models import (
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionResult,
    SplitChildCommand,
)
from ...application.ledger.tests.manual_transaction_support import create_manual_transaction
from ...application.ledger.update_contracts import LedgerUpdatePatch
from ...application.operations.public_period import PublicPeriod
from ...application.operations.public_scalar import PublicDecimal
from ...core.ledger_known_values import LedgerKnownValueKind
from ...core.ledger_sort import LedgerSortField
from ...core.period import Period
from ...core.time.clock import now
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.enums import IvaRate, PaymentStatus
from ...domain.invoices.models import Invoice, InvoiceLine
from ...domain.iva.schema import InvoiceKind
from ...domain.renta.actividad_asset.disposal import ActivityAssetDisposalReason
from ...domain.renta.actividad_asset.lifecycle import AssetKind
from ...domain.renta.actividad_asset.register_records import ActivityAssetDescriptorFacts
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.own_accounts import OwnAccountHolding
from ..adapter_composition_ports import build_bienes_inversion_repository, build_inventory_service_ports
from ..adapter_composition_work_ports import build_ledger_evidence_ports
from ..ledger_action_composition import compose_ledger_action_ports
from . import modelo_operation_test_support
from .activity_asset_operation_test_support import (
    activity_asset_revision,
    seed_acquisition_transaction,
    seed_activity_asset,
)
from .prorrata_bienes_operation_test_support import prepare_bienes_inversion_operation_conformance_case
from .registered_executor_payload_context import PayloadBuilder, PayloadContext, PayloadResult
from .registered_executor_scenario_constants import LEDGER_LIST_PRIVATE_FILTER_SENTINEL, OWN_ACCOUNT_SYNTHETIC_IBAN
from .registered_executor_seeding_support import seed_conformance_invoice, seeded_ledger_track_transaction_id

_EVIDENCE_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def _seed_unprocessed_outgoing(
    ctx: PayloadContext, ports: LedgerActionPorts, *, booked_date: date, amount: str, description: str
) -> ManualLedgerTransactionResult:
    """Create one unclassified manual outgoing row through the real ledger action."""
    return create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=str(ctx.profile_id),
            booked_date=booked_date,
            amount=Decimal(amount),
            direction=TransactionDirection.OUTGOING,
            description=description,
            business_classification=BusinessClassification.NOT_YET_PROCESSED,
            actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        ),
        ports=ports,
        occurred_at=now(),
    )


def _ledger_counterparty(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "action": "confirm",
            "tax_identifier": "B00015016",
            "territorial_scope": "es_canarias",
            "asserted_by": "operator:registered-executor-conformance",
            "note": "synthetic supervisor conformance assertion",
        },
    )


def _ledger_own_account(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "action": "add",
            "label": "synthetic conformance account",
            "holding": OwnAccountHolding.TITULAR,
            "iban": OWN_ACCOUNT_SYNTHETIC_IBAN,
        },
    )


def _ledger_remove(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    created = _seed_unprocessed_outgoing(
        ctx, ports, booked_date=date(2025, 1, 15), amount="12.00", description="conformance removal dry run seed"
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "transaction_id": created.ref.transaction_id,
            "reason": "synthetic conformance dry run",
            "dry_run": True,
        },
    )


def _ledger_allocate(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    created = _seed_unprocessed_outgoing(
        ctx,
        ports,
        booked_date=date(2025, 1, 17),
        amount="20.00",
        description="conformance business-share allocation seed",
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "transaction_id": created.ref.transaction_id,
            "business_pct": "0.5",
        },
    )


def _ledger_classify_single(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    created = _seed_unprocessed_outgoing(
        ctx,
        ports,
        booked_date=date(2025, 1, 19),
        amount="22.00",
        description="conformance single classification seed",
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "transaction_id": created.ref.transaction_id,
            "patch": LedgerClassifyPatch(business_classification="BUSINESS"),
            "patch_fields": ("business_classification",),
        },
    )


def _ledger_classify_bulk(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    created_valid = _seed_unprocessed_outgoing(
        ctx,
        ports,
        booked_date=date(2025, 1, 20),
        amount="23.00",
        description=f"conformance bulk classification valid {ctx.profile_id.hex}",
    )
    created_invalid = _seed_unprocessed_outgoing(
        ctx,
        ports,
        booked_date=date(2025, 1, 20),
        amount="24.00",
        description=f"conformance bulk classification invalid {ctx.profile_id.hex}",
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "csv_text": (
                "transaction_id,classification,iva_category\n"
                f"{created_valid.ref.transaction_id},BUSINESS,domestic_general\n"
                f"{created_invalid.ref.transaction_id},BUSINESS,not-a-declared-category\n"
            ),
            "actor": None,
        },
    )


def _ledger_evidence_add(ctx: PayloadContext) -> PayloadResult:
    evidence_file = ctx.tmp_path / "conformance-purchase-invoice-add.pdf"
    evidence_file.write_bytes(_EVIDENCE_PDF)
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "source_path": str(evidence_file),
            "source_directory": str(ctx.tmp_path),
        },
    )


def _ledger_evidence_stored(ctx: PayloadContext) -> PayloadResult:
    evidence_file = ctx.tmp_path / "conformance-purchase-invoice.pdf"
    evidence_file.write_bytes(_EVIDENCE_PDF)
    evidence = PurchaseInvoiceEvidenceService(
        ports=build_ledger_evidence_ports(bucket_id=str(ctx.profile_id)),
    ).add(bucket_id=str(ctx.profile_id), source_path=evidence_file)
    values: dict[str, object] = {"profile_id": ctx.profile_id}
    if ctx.definition_id == "ledger.evidence.view":
        values["evidence_id"] = evidence.record.evidence_id
    if ctx.definition_id == "ledger.evidence.update":
        values.update(
            evidence_id=evidence.record.evidence_id,
            patch=LedgerEvidenceUpdatePatch(supplier="Conformance Supplier"),
            patch_fields=("supplier",),
        )
    if ctx.definition_id == "ledger.evidence.remove":
        values["evidence_id"] = evidence.record.evidence_id
    return ctx.request(ctx.profile_subject, values)


def _ledger_split_manual(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    created = _seed_unprocessed_outgoing(
        ctx, ports, booked_date=date(2025, 1, 21), amount="20.00", description="conformance manual split seed"
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "transaction_id": created.ref.transaction_id,
            "children": (
                {"amount": "8", "description": "first split child"},
                {"amount": "12", "description": "second split child"},
            ),
            "reason": "synthetic conformance split",
        },
    )


def _ledger_merge(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    created = _seed_unprocessed_outgoing(
        ctx, ports, booked_date=date(2025, 1, 22), amount="20.00", description="conformance manual merge seed"
    )
    split = split_transaction(
        bucket_id=str(ctx.profile_id),
        transaction_id=created.ref.transaction_id,
        children=(
            SplitChildCommand(amount=Decimal("8"), description="first merge child"),
            SplitChildCommand(amount=Decimal("12"), description="second merge child"),
        ),
        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        reason="synthetic conformance merge seed",
        ports=ports,
        occurred_at=now(),
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "child_ids": split.child_transaction_ids,
            "reason": "synthetic conformance merge",
        },
    )


def _ledger_update(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    created = _seed_unprocessed_outgoing(
        ctx, ports, booked_date=date(2025, 1, 18), amount="21.00", description="conformance ledger update seed"
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "transaction_id": created.ref.transaction_id,
            "patch": LedgerUpdatePatch(description="updated through registered operation"),
            "patch_fields": ("description",),
        },
    )


def _ledger_reset(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    _seed_unprocessed_outgoing(
        ctx, ports, booked_date=date(2025, 1, 16), amount="13.00", description="conformance catalogue reset seed"
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "reason": "synthetic conformance reset",
            "dry_run": False,
        },
    )


def _ledger_import(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "files": (ctx.tmp_path / "missing.csv",),
            "provider": LedgerProviderID.CSV,
            "dry_run": True,
            "verify": False,
            "verify_source": None,
            "period": None,
        },
    )


def _ledger_add(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "booked_date": "2025-01-20",
            "amount": "23.00",
            "direction": TransactionDirection.OUTGOING,
            "description": "conformance manual add",
        },
    )


def _ledger_status(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "period": None})


def _ledger_check(ctx: PayloadContext) -> PayloadResult:
    absent_transaction_id = "f" * 64
    invoice = Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": str(ctx.profile_id),
            "invoice_number": "CHECK-2025-001",
            "issued_at": date(2025, 5, 1),
            "counterparty_name": "Conformance Supplier",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": (absent_transaction_id,),
            "lines": (
                InvoiceLine(
                    description="Conformance invoice link",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    subtotal=Decimal("100.00"),
                    iva_rate=IvaRate.from_registry("RATE_21"),
                    iva_amount=Decimal("21.00"),
                ),
            ),
        }
    )
    InvoiceCatalogueRepository(bucket_id=str(ctx.profile_id)).save(
        InvoiceCatalogue(invoices={invoice.invoice_id: invoice})
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "period": PublicPeriod.from_period(Period.from_year_and_code(2026, "1T")),
        },
    )


def _ledger_preflight(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=str(ctx.profile_id),
            booked_date=date(2026, 1, 15),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="conformance preflight selected-period issue",
            business_classification=BusinessClassification.BUSINESS,
            category_id=None,
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
            actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        ),
        ports=ports,
        occurred_at=now(),
    )
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=str(ctx.profile_id),
            booked_date=date(2026, 4, 15),
            amount=Decimal("242.00"),
            direction=TransactionDirection.OUTGOING,
            description="conformance preflight outside-period issue",
            business_classification=BusinessClassification.BUSINESS,
            category_id=None,
            taxable_base=Decimal("200.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("42.00"),
            actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        ),
        ports=ports,
        occurred_at=now() + timedelta(seconds=1),
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "period": PublicPeriod.from_period(Period.from_year_and_code(2026, "1T")),
        },
    )


def _ledger_history(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    created = _seed_unprocessed_outgoing(
        ctx, ports, booked_date=date(2025, 1, 15), amount="12.00", description="conformance history seed"
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "transaction_prefix": created.ref.transaction_id[:12],
            "include_split_siblings": False,
        },
    )


def _ledger_view(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    created = _seed_unprocessed_outgoing(
        ctx, ports, booked_date=date(2025, 1, 15), amount="12.00", description="conformance view seed"
    )
    reject_llm_suggestion(
        LLMClassificationSuggestion(
            transaction_id=created.ref.transaction_id,
            provenance="llm:conformance:test-model",
            classification=BusinessClassification.BUSINESS,
            confidence=Decimal("0.9"),
            reason="conformance suggestion",
        ),
        bucket_id=str(ctx.profile_id),
        reason="operator rejected the conformance suggestion",
        actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
        source_command="conformance ledger view seed",
        transaction_repository=ports.transaction_repository,
        bucket_event_repository=ports.bucket_event_repository,
        occurred_at=now(),
    )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "transaction_prefix": created.ref.transaction_id[:12],
        },
    )


def _ledger_track(ctx: PayloadContext) -> PayloadResult:
    transaction_id = seeded_ledger_track_transaction_id(ctx.profile_id, operation=ctx.operation)
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "transaction_prefix": transaction_id[:12],
        },
    )


def _ledger_rule_trial(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {"profile_id": ctx.profile_id, "description_pattern": "[unclosed", "transaction_ids": ("0" * 64,)},
    )


def _ledger_invoice_match(ctx: PayloadContext) -> PayloadResult:
    # A link naming records the conformance profile does not hold is judged as not found.
    return ctx.request(
        ctx.profile_subject,
        {"profile_id": ctx.profile_id, "judge": ({"transaction_id": "a" * 64, "invoice_id": "b" * 64},)},
    )


def _ledger_invoice_duplicate(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {"profile_id": ctx.profile_id, "kind": InvoiceKind.RECEIVED, "invoice_number": "CONFORMANCE-NONE"},
    )


def _ledger_split_check(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "transaction_id": "0" * 64,
            "parts": ({"amount": "1", "description": "first"}, {"description": "second"}),
        },
    )


def _ledger_staged_check(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "rows": ({"transaction_id": "0" * 64, "cells": ({"field": "notes", "value": "x"},)},),
            "drafts": ({"key": "draft", "fields": ()},),
            "categories": (),
        },
    )


def _ledger_entry_options(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id})


def _ledger_known_values(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    for index, description in enumerate(("known value kept", "KNOWN VALUE KEPT", "known value other")):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=str(ctx.profile_id),
                booked_date=date(2025, 1 + index, 15),
                amount=Decimal(10 + index),
                direction=TransactionDirection.OUTGOING,
                description=description,
                business_classification=BusinessClassification.NOT_YET_PROCESSED,
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            ),
            ports=ports,
            occurred_at=now() + timedelta(seconds=index),
        )
    return ctx.request(
        ctx.profile_subject,
        {"profile_id": ctx.profile_id, "kinds": (LedgerKnownValueKind.DESCRIPTION,)},
    )


def _ledger_list(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    for index, (booked_date, description) in enumerate(
        (
            (date(2025, 1, 15), "ledger list page A"),
            (date(2025, 2, 15), "ledger list page B"),
            (date(2025, 3, 15), "ledger list page C"),
            (date(2025, 4, 15), "ledger list outside period"),
        )
    ):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=str(ctx.profile_id),
                booked_date=booked_date,
                amount=Decimal(10 + index),
                direction=TransactionDirection.OUTGOING,
                description=description,
                business_classification=BusinessClassification.NOT_YET_PROCESSED,
                group_label=LEDGER_LIST_PRIVATE_FILTER_SENTINEL,
                actor=modelo_operation_test_support.MODELO_OPERATION_TEST_ACTOR,
            ),
            ports=ports,
            occurred_at=now() + timedelta(seconds=index),
        )
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "filters": ("period=1T", "year=2025", "classification=not_yet_processed"),
            "group": LEDGER_LIST_PRIVATE_FILTER_SENTINEL,
            "limit": 2,
            "offset": 1,
            "sort_by": LedgerSortField.DESCRIPTION,
        },
    )


def _ledger_inventory(ctx: PayloadContext) -> PayloadResult:
    inventory_case = prepare_inventory_operation_conformance_case(
        ctx.definition_id, ctx.profile_id, ports_factory=build_inventory_service_ports
    )
    inventory_payload = inventory_case.request
    assert isinstance(inventory_payload, BaseModel)
    assert isinstance(inventory_payload, ctx.definition.request_type)
    return ctx.profile_subject, inventory_payload, None


def _ledger_bienes_inversion(ctx: PayloadContext) -> PayloadResult:
    bienes_case = prepare_bienes_inversion_operation_conformance_case(
        ctx.definition_id,
        ctx.profile_id,
        repository_factory=build_bienes_inversion_repository,
        operation=ctx.operation,
    )
    assert isinstance(bienes_case.request, ctx.definition.request_type)
    return ctx.profile_subject, bienes_case.request, None


def _ledger_actividad_asset_create(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "revision": ActivityAssetRevisionSnapshot.from_domain(
                activity_asset_revision(
                    "conformance-create",
                    acquisition_transaction_id=seed_acquisition_transaction(ctx.profile_id, operation=ctx.operation),
                )
            ),
            "descriptor": ActivityAssetDescriptorFacts(name="Conformance element", serial_number="SN-1"),
        },
    )


def _ledger_actividad_asset(ctx: PayloadContext) -> PayloadResult:
    action = ctx.definition_id.rsplit(".", 1)[1]
    asset_seed = seed_activity_asset(
        ctx.profile_id,
        operation=ctx.operation,
        asset_id=f"conformance-{action}",
        include_claim=action in {"filing-handoff", "timeline"},
    )
    values: dict[str, object] = {"profile_id": ctx.profile_id}
    if action in {"inspect", "plan", "timeline"}:
        values["asset_id"] = asset_seed.revision.asset_id
    elif action == "describe":
        values.update(
            asset_id=asset_seed.revision.asset_id,
            descriptor=ActivityAssetDescriptorFacts(name="Conformance element", serial_number="SN-1"),
        )
    elif action in {"dispose", "disposal-calculate"}:
        values.update(
            asset_id=asset_seed.revision.asset_id,
            disposal=ActivityAssetDisposalSnapshot(
                disposal_date=date(2025, 6, 30),
                reason=ActivityAssetDisposalReason.SALE,
                proceeds=PublicDecimal(decimal="250.00"),
                transmission_costs=PublicDecimal(decimal="10.00"),
            ),
        )
    elif action == "form-options":
        values.update(asset_kind=AssetKind.MATERIAL, tax_year=2025)
    elif action in {"list", "acquisition-candidates"}:
        pass
    elif action == "correct":
        values["revision"] = ActivityAssetCorrectionRevisionSnapshot.from_domain(
            activity_asset_revision(
                asset_seed.revision.asset_id,
                acquisition_transaction_id=asset_seed.acquisition_transaction_id,
                revision_number=2,
                supersedes_revision_id=asset_seed.revision.revision_id,
            )
        )
    elif action == "forecast":
        values.update(
            asset_id=asset_seed.revision.asset_id, covered_from=date(2025, 1, 1), covered_until=date(2026, 1, 1)
        )
    elif action == "claim":
        values.update(
            forecast=ScheduledAmortizationChargeSnapshot.from_domain(asset_seed.forecast),
        )
    else:
        values.update(tax_year=2025, m130_period="4T")
    return ctx.request(ctx.profile_subject, values)


def _ledger_invoice_add(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "kind": InvoiceKind.RECEIVED,
            "counterparty_name": "Conformance Supplier",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "invoice_number": "CONFORMANCE-INVOICE-2025-ADD",
            "issued_at": date(2025, 5, 1),
            "taxable_base": {"decimal": "100.00"},
            "iva_rate": {"decimal": "21"},
            "currency": "EUR",
        },
    )


def _ledger_invoice_preview(ctx: PayloadContext) -> PayloadResult:
    return ctx.request(
        ctx.profile_subject,
        {
            "profile_id": ctx.profile_id,
            "kind": InvoiceKind.RECEIVED,
            "counterparty_name": "Conformance Supplier",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "invoice_number": "CONFORMANCE-INVOICE-2025-PREVIEW",
            "issued_at": date(2025, 5, 1),
            "currency": "EUR",
            "lines": (
                InvoiceFiguresPreviewLine(
                    key="a",
                    description="Conformance service",
                    quantity=PublicDecimal(decimal="1"),
                    unit_price=PublicDecimal(decimal="100.00"),
                    iva_rate="RATE_21",
                ),
            ),
        },
    )


def _ledger_invoice_stored(ctx: PayloadContext) -> PayloadResult:
    invoice = seed_conformance_invoice(ctx.profile_id)
    values: dict[str, object] = {"profile_id": ctx.profile_id}
    if ctx.definition_id == INVOICE_LIST_OPERATION_DEFINITION_ID:
        values["kind"] = None
    elif ctx.definition_id in {
        INVOICE_REMOVE_OPERATION_DEFINITION_ID,
        INVOICE_UPDATE_OPERATION_DEFINITION_ID,
    }:
        values["invoice_id"] = invoice.invoice_id
        if ctx.definition_id == INVOICE_UPDATE_OPERATION_DEFINITION_ID:
            values["patch"] = InvoiceUpdatePatch.from_patch(
                CatalogueInvoicePatch.model_validate(
                    {"counterparty_name": "Updated conformance supplier", "retention_amount": Decimal("0.00")}
                )
            )
    else:
        values["invoice_id"] = invoice.invoice_id
    return ctx.request(ctx.profile_subject, values)


def _ledger_participation(ctx: PayloadContext) -> PayloadResult:
    transaction_id = seeded_ledger_track_transaction_id(ctx.profile_id, operation=ctx.operation)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id, "transaction_prefix": transaction_id[:12]})


def _ledger_participation_rebuild(ctx: PayloadContext) -> PayloadResult:
    seeded_ledger_track_transaction_id(ctx.profile_id, operation=ctx.operation)
    return ctx.request(ctx.profile_subject, {"profile_id": ctx.profile_id})


def _ledger_review(ctx: PayloadContext) -> PayloadResult:
    ports = compose_ledger_action_ports(bucket_id=str(ctx.profile_id), operation=ctx.operation)
    created = _seed_unprocessed_outgoing(
        ctx, ports, booked_date=date(2025, 1, 15), amount="21.00", description="conformance review seed"
    )
    return ctx.request(
        ctx.profile_subject,
        {"profile_id": ctx.profile_id, "transaction_prefix": created.ref.transaction_id[:12]},
    )


LEDGER_BUILDERS: dict[str, PayloadBuilder] = {
    "ledger.counterparty": _ledger_counterparty,
    "ledger.own_account": _ledger_own_account,
    "ledger.remove": _ledger_remove,
    "ledger.allocate": _ledger_allocate,
    "ledger.classify.single": _ledger_classify_single,
    "ledger.classify.bulk": _ledger_classify_bulk,
    "ledger.evidence.add": _ledger_evidence_add,
    "ledger.evidence.list": _ledger_evidence_stored,
    "ledger.evidence.view": _ledger_evidence_stored,
    "ledger.evidence.update": _ledger_evidence_stored,
    "ledger.evidence.remove": _ledger_evidence_stored,
    "ledger.split.manual": _ledger_split_manual,
    "ledger.merge": _ledger_merge,
    "ledger.update": _ledger_update,
    "ledger.reset": _ledger_reset,
    "ledger.import": _ledger_import,
    "ledger.add": _ledger_add,
    "ledger.status": _ledger_status,
    "ledger.check": _ledger_check,
    "ledger.preflight": _ledger_preflight,
    "ledger.history": _ledger_history,
    "ledger.view": _ledger_view,
    "ledger.track": _ledger_track,
    "ledger.entry-options": _ledger_entry_options,
    "ledger.rule.trial": _ledger_rule_trial,
    "ledger.invoice.duplicate": _ledger_invoice_duplicate,
    "ledger.invoice.match": _ledger_invoice_match,
    "ledger.split.check": _ledger_split_check,
    "ledger.staged.check": _ledger_staged_check,
    "ledger.known-values": _ledger_known_values,
    "ledger.list": _ledger_list,
    "ledger.inventory.list": _ledger_inventory,
    "ledger.inventory.create": _ledger_inventory,
    "ledger.inventory.movement.add": _ledger_inventory,
    "ledger.inventory.valuation.preview": _ledger_inventory,
    "ledger.inventory.closing-authority.record": _ledger_inventory,
    "ledger.inventory.inspect": _ledger_inventory,
    "ledger.inventory.describe": _ledger_inventory,
    "ledger.inventory.correct": _ledger_inventory,
    "ledger.inventory.movement.correct": _ledger_inventory,
    "ledger.inventory.movement.reverse": _ledger_inventory,
    "ledger.inventory.retire": _ledger_inventory,
    "ledger.inventory.restore": _ledger_inventory,
    "ledger.bienes_inversion.list": _ledger_bienes_inversion,
    "ledger.bienes_inversion.declare": _ledger_bienes_inversion,
    "ledger.actividad-asset.create": _ledger_actividad_asset_create,
    "ledger.actividad-asset.inspect": _ledger_actividad_asset,
    "ledger.actividad-asset.correct": _ledger_actividad_asset,
    "ledger.actividad-asset.forecast": _ledger_actividad_asset,
    "ledger.actividad-asset.claim": _ledger_actividad_asset,
    "ledger.actividad-asset.filing-handoff": _ledger_actividad_asset,
    "ledger.actividad-asset.describe": _ledger_actividad_asset,
    "ledger.actividad-asset.dispose": _ledger_actividad_asset,
    "ledger.actividad-asset.disposal-calculate": _ledger_actividad_asset,
    "ledger.actividad-asset.list": _ledger_actividad_asset,
    "ledger.actividad-asset.plan": _ledger_actividad_asset,
    "ledger.actividad-asset.timeline": _ledger_actividad_asset,
    "ledger.actividad-asset.form-options": _ledger_actividad_asset,
    "ledger.actividad-asset.acquisition-candidates": _ledger_actividad_asset,
    "ledger.invoice.add": _ledger_invoice_add,
    "ledger.invoice.preview": _ledger_invoice_preview,
    "ledger.invoice.list": _ledger_invoice_stored,
    "ledger.invoice.view": _ledger_invoice_stored,
    "ledger.invoice.remove": _ledger_invoice_stored,
    "ledger.invoice.update": _ledger_invoice_stored,
    "ledger.participation": _ledger_participation,
    "ledger.participation.rebuild": _ledger_participation_rebuild,
    "ledger.review": _ledger_review,
}
