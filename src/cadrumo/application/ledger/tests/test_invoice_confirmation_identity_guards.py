"""Confirmation identity guards refuse a second statement about one document."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest

from ....application.exchange_rate_provider import exchange_rate_provider
from ....application.invoices.catalogue_creation import build_catalogue_invoice
from ....application.invoices.catalogue_creation_ports import (
    CatalogueCreationPorts,
    CatalogueInvoiceAuditCommitPort,
    CatalogueInvoiceEventRepositoryPort,
    CatalogueInvoiceRateProviderPort,
)
from ....application.ledger import invoice_confirmation as confirmation
from ....application.ledger.confirm_establishment import ConfirmedEstablishment
from ....application.ledger.establishment_ladder import CounterpartyEstablishment
from ....application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ....application.ledger.invoice_confirmation_ports import InvoiceConfirmationPorts
from ....application.ledger.invoice_draft_records import InvoiceDraft
from ....application.ledger.preconditions import LedgerPreconditionCondition
from ....application.wizard import status as wizard_status
from ....application.workflow import persistence as workflow_persistence
from ....core.config import Settings
from ....domain.attachments.protocols import AttachmentStoreProtocol
from ....domain.calculations.registry import authority as registry_authority
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.iva_schema_vocabulary import require_iva_regime
from ....domain.deadlines.models import TaxpayerProfile
from ....domain.invoices.errors import InvoiceValidationError
from ....domain.invoices.models import Invoice, InvoiceCatalogue
from ....domain.iva.classification import InvoiceKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "20202020-2020-4202-8202-202020202020"
_ATTACHMENT = "a" * 64
_COUNTERPARTY = "B12345674"


class _InvoiceRepository:
    def __init__(self, catalogue: InvoiceCatalogue) -> None:
        self.catalogue = catalogue

    def load(self) -> InvoiceCatalogue:
        return self.catalogue

    def mutate(self, mutation: Callable[[InvoiceCatalogue], InvoiceCatalogue]) -> InvoiceCatalogue:
        raise AssertionError("these confirmation paths must not mutate the invoice catalogue")


class _AttachmentManifestStore:
    def __init__(self, linked_invoice_ids: tuple[str, ...]) -> None:
        self.linked_invoice_ids = linked_invoice_ids

    def load_manifest(self, _attachment_id: str) -> object:
        return SimpleNamespace(linked_invoice_ids=self.linked_invoice_ids)


def _invoice(invoice_number: str, *, operation: PinnedAuthorityOperation) -> Invoice:
    return build_catalogue_invoice(
        bucket_id=_BUCKET,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Proveedor Ejemplo SL",
        counterparty_tax_id=_COUNTERPARTY,
        counterparty_country="ES",
        invoice_number=invoice_number,
        issued_at=date(2026, 3, 10),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=exchange_rate_provider(),
        operation=operation,
    )


def _preparation(draft: InvoiceDraft) -> confirmation._InvoiceConfirmationPreparation:
    return confirmation._InvoiceConfirmationPreparation(
        settings=cast(Settings, object()),
        draft=draft,
        blockers=(),
        attachment_id=_ATTACHMENT,
        establishment=ConfirmedEstablishment(counterparty=CounterpartyEstablishment()),
        operator_overrides={},
        operator_restated_amounts=False,
    )


def _persist_with_existing_invoice(
    *,
    candidate: Invoice,
    stored: Invoice,
    calls: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> confirmation.InvoiceConfirmationResult:
    repository = _InvoiceRepository(InvoiceCatalogue(invoices={stored.invoice_id: stored}))
    store = _AttachmentManifestStore((stored.invoice_id,))
    record = SimpleNamespace(confirmation_id="f" * 16, assertions=())
    monkeypatch.setattr(
        confirmation,
        "link_attachment_invoice",
        lambda *_args, **_kwargs: calls.append("link"),
    )
    monkeypatch.setattr(
        confirmation,
        "_record_confirmed_summary_on_evidence",
        lambda **_kwargs: calls.append("summary"),
    )
    monkeypatch.setattr(
        confirmation,
        "_written_confirmation_record",
        lambda **_kwargs: calls.append("audit") or record,
    )
    confirmation.InvoiceConfirmationResult.model_rebuild(
        _types_namespace={"ConfirmedEstablishment": ConfirmedEstablishment},
    )
    ports = CatalogueCreationPorts(
        invoice_repository=repository,
        event_repository=cast(CatalogueInvoiceEventRepositoryPort, object()),
        audit_commit=cast(CatalogueInvoiceAuditCommitPort, object()),
        rate_provider=cast(CatalogueInvoiceRateProviderPort, object()),
    )

    return confirmation._persist_confirmed_invoice(
        candidate=candidate,
        preparation=_preparation(InvoiceDraft(invoice_number=candidate.invoice_number)),
        bucket_id=_BUCKET,
        evidence_id=None,
        confirmed_by="operator",
        resolutions=(),
        catalogue_creation_ports=ports,
        invoice_confirmation_ports=InvoiceConfirmationPorts(
            attachment_store=cast(AttachmentStoreProtocol, store),
        ),
        evidence_ports=cast(confirmation.LedgerEvidencePorts, object()),
    )


def test_identical_reconfirmation_returns_the_existing_invoice_without_creating_another_invoice(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = _invoice("F-2026-0142", operation=operation)
    calls: list[str] = []

    result = _persist_with_existing_invoice(
        candidate=stored,
        stored=stored,
        calls=calls,
        monkeypatch=monkeypatch,
    )

    assert result.invoice is stored
    assert result.created is False
    assert result.confirmation_id == "f" * 16
    assert calls == ["link", "summary", "audit"]


def test_same_document_with_a_different_invoice_number_refuses_before_any_write(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = _invoice("F-2026-0142", operation=operation)
    candidate = _invoice("RESTATED-0142", operation=operation)
    assert candidate.invoice_id != stored.invoice_id
    writes: list[str] = []
    repository = _InvoiceRepository(InvoiceCatalogue(invoices={stored.invoice_id: stored}))
    store = _AttachmentManifestStore((stored.invoice_id,))
    ports = CatalogueCreationPorts(
        invoice_repository=repository,
        event_repository=cast(CatalogueInvoiceEventRepositoryPort, object()),
        audit_commit=cast(CatalogueInvoiceAuditCommitPort, object()),
        rate_provider=cast(CatalogueInvoiceRateProviderPort, object()),
    )
    monkeypatch.setattr(confirmation, "link_attachment_invoice", lambda *_args, **_kwargs: writes.append("link"))
    monkeypatch.setattr(
        confirmation, "_record_confirmed_summary_on_evidence", lambda **_kwargs: writes.append("summary")
    )
    monkeypatch.setattr(confirmation, "_written_confirmation_record", lambda **_kwargs: writes.append("record"))

    with pytest.raises(InvoiceValidationError, match="invoice_number"):
        confirmation._persist_confirmed_invoice(
            candidate=candidate,
            preparation=_preparation(InvoiceDraft(invoice_number=candidate.invoice_number)),
            bucket_id=_BUCKET,
            evidence_id=None,
            confirmed_by="operator",
            resolutions=(),
            catalogue_creation_ports=ports,
            invoice_confirmation_ports=InvoiceConfirmationPorts(
                attachment_store=cast(AttachmentStoreProtocol, store),
            ),
            evidence_ports=cast(confirmation.LedgerEvidencePorts, object()),
        )

    assert tuple(repository.catalogue) == (stored,)
    assert writes == []


@pytest.mark.parametrize("supplied_tax_id", [None, _COUNTERPARTY])
def test_confirmation_boundary_refuses_a_reader_or_operator_self_counterparty(
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
    supplied_tax_id: str | None,
) -> None:
    with validating_governed_facts(operation):
        profile = TaxpayerProfile(tax_id=_COUNTERPARTY, iva_regime=require_iva_regime("GENERAL"))

    @contextmanager
    def authority_operation() -> Iterator[object]:
        yield SimpleNamespace(profile_schema=lambda: object())

    monkeypatch.setattr(
        registry_authority,
        "bundled_indexed_authority",
        lambda: SimpleNamespace(operation=authority_operation),
    )
    monkeypatch.setattr(
        workflow_persistence,
        "workflow_state_repository",
        lambda: SimpleNamespace(load=lambda: object()),
    )
    monkeypatch.setattr(
        wizard_status,
        "load_active_taxpayer_profile",
        lambda _state, *, schema: profile,
    )
    draft = InvoiceDraft(
        supplier_tax_id=_COUNTERPARTY,
        supplier_name="El propio contribuyente",
        invoice_number="F-2026-0142",
        invoice_date="2026-03-10",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
    )

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as refusal:
        confirmation._build_confirmed_invoice_candidate(
            bucket_id=_BUCKET,
            kind=InvoiceKind.RECEIVED,
            counterparty_country="ES",
            counterparty_tax_id=supplied_tax_id,
            counterparty_name="El propio contribuyente",
            invoice_number=None,
            invoice_date=None,
            taxable_base=None,
            iva_rate=None,
            iva_amount=None,
            currency=None,
            iva_category=None,
            operation_type=None,
            operation_date=None,
            retention_rate=None,
            retention_amount=None,
            recargo_amount=None,
            invoice_class=None,
            supply_nature=None,
            series=None,
            rectifies_invoice_number=None,
            notes="",
            catalogue_creation_ports=cast(CatalogueCreationPorts, object()),
            preparation=_preparation(draft),
        )

    verdict = refusal.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == LedgerPreconditionCondition.EVIDENCE_COUNTERPARTY_VALID.value
    assert any(evidence.values.get("counterparty_is_filer") is True for evidence in verdict.evidence)
