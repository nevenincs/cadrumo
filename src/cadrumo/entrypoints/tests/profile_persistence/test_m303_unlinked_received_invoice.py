"""A received invoice no movement pays yet still deducts its IVA in the quarter.

LIVA art. 99.Uno deducts the input IVA in the period it is borne, on holding the
factura (art. 97), whether or not the bill has been paid: the payment movement is
no part of the deduction. APP-QA recorded one received, confirmed invoice with its
PDF stored and no movement linked, and the Modelo 303 for 2026 1T refused instead
of deducting it.

The expected boxes come from the official 303 instructions alone: a domestic
deductible base of 300.00 at 21 % gives cuota 63.00 in boxes 28 and 29, with no
IVA devengado the régimen general result is -63.00 (46), and so is the result
(71). The supplier's retención is income-tax withholding (Modelo 111) and leaves
every IVA box as it is.

Real encrypted store, real published authority, real calculation engine. No doubles.
"""

from __future__ import annotations

from collections.abc import Iterator
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
from cadrumo.application.invoices.catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.attachments.enums import AttachmentKind, AttachmentSource
from cadrumo.domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.iva.schema import InvoiceKind
from cadrumo.domain.iva_compensation.reconciliation import (
    IvaCompensationAuthoritySource,
    IvaCompensationReconciliationDecision,
)
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.ready_profile_support import seed_ready_profile
from .ready_profile_taxpayer import ready_profile_tax_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET = "44444444-4444-4444-8444-444444442026"
_YEAR = 2026
_T0 = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 4, 2, 10, 0, tzinfo=UTC)

#: The boxes the official instructions give for the quarter.
_EXPECTED: dict[str, Decimal] = {
    "28": Decimal("300.00"),
    "29": Decimal("63.00"),
    "iva.resultado-regimen-general": Decimal("-63.00"),
    "71": Decimal("-63.00"),
}


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        yield profile.repository


def _wallet_decision() -> IvaCompensationReconciliationDecision:
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


def _box(box: str) -> CasillaId:
    return validated_casilla_id(box, surface="test casilla id")


def test_an_unlinked_received_invoice_deducts_its_iva_in_the_quarter(
    secure_objects: SecureObjectRepository,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    seed_ready_profile(bucket_id=_BUCKET, at=_T0)
    work_units = WorkUnitCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    calculations = CalculationRevisionCatalogueRepository(objects=secure_objects)
    events = BucketEventHistoryRepository(objects=secure_objects)
    transactions = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    decision = _wallet_decision()
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(decision)

    catalogue_ports = build_catalogue_creation_ports(bucket_id=_BUCKET)
    created = create_catalogue_invoice(
        invoice=build_catalogue_invoice(
            bucket_id=_BUCKET,
            kind=InvoiceKind.RECEIVED,
            counterparty_name="Asesoría Ejemplo SLP",
            counterparty_tax_id="B81000069",
            counterparty_country="ES",
            invoice_number="SLP-2026-QA1",
            issued_at=date(_YEAR, 2, 10),
            taxable_base=Decimal("300.00"),
            iva_rate=Decimal("21"),
            currency="EUR",
            retention_amount=Decimal("45.00"),
            rate_provider=catalogue_ports.rate_provider,
            operation=operation,
        ),
        ports=catalogue_ports,
    )
    add_attachment(
        AttachmentStore(objects=secure_objects),
        content=AttachmentBytesContent(data=b"%PDF-1.4 synthetic factura SLP-2026-QA1"),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="operator-evidence",
            mime_type="application/pdf",
            captured_at=_T0,
            bucket_id=_BUCKET,
            link_invoice_ids=(created.invoice.invoice_id,),
        ),
    )
    assert len(transactions.load()) == 0

    snapshot = published_authority_operation().snapshot("303", filing_year=_YEAR, period="1T")
    work_unit = create_work_unit(
        bucket_id=_BUCKET,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(work_unit_repository=work_units, bucket_event_repository=events),
        clock=_T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET,
        work_unit_repository=work_units,
        calculation_repository=calculations,
        bucket_event_repository=events,
        transaction_repository=transactions,
        invoice_repository=invoices,
    ) as ports:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            actor="operator-A",
            binding_values={
                "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
                "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
            },
            iva_compensation_decision=decision,
            ports=ports,
            filing_instance_evidence=general_m303_filing_evidence(
                work_unit.period, reference="test:unlinked-received-invoice", operation=operation
            ),
            clock=_T1,
        )

    values = result.revision.casilla_values
    declared = {box: Decimal(str(values[_box(box)])) for box in _EXPECTED}
    assert declared == _EXPECTED
