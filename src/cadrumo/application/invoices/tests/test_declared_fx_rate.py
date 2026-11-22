"""An operator-declared exchange rate converts a foreign invoice, and nothing else does it silently.

LIVA art. 79.Once binds a foreign invoice's euro base to the Banco de España
seller rate in force at chargeability, or the latest ECB rate (Directive
2006/112 art. 91(2)). When the provider publishes no rate the invoice is kept
unconverted and refused at calculation; the operator's statement of the rate is
the remedy. These tests drive the real builder, lifecycle correction and bulk
importer over the real :class:`Invoice` aggregate, and check the converted line
through the calculation screen that refuses an unconverted one.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.currency.models import EurRateLookup
from ....domain.currency.service import OPERATOR_DECLARED_RATE_SOURCE
from ....domain.currency.tests.fx_lookup import eur_rate_lookup
from ....domain.invoices.errors import InvoiceValidationError
from ....domain.invoices.models import Invoice
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.date_partition import LedgerDatePartition
from ....domain.transactions.models import TransactionCatalogue
from ...aggregation.errors import AggregationValidationError
from ...aggregation.modelo_bindings_invoice_iva import line_eur_amounts_or_refuse
from ..bulk_import import import_invoices_from_rows, read_bulk_invoice_import_source
from ..catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
from ..catalogue_creation_ports import CatalogueCreationPorts, CatalogueInvoiceRateProviderPort
from ..catalogue_lifecycle import CatalogueInvoicePatch, update_catalogue_invoice
from ..catalogue_lifecycle_ports import CatalogueLifecyclePorts
from ..catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..catalogue_update_operation import InvoiceUpdatePatch, InvoiceUpdateRequest
from .catalogue_creation_fakes import in_memory_catalogue_creation_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "47474747-4747-4747-8747-474747474747"
_DECLARED_RATE = Decimal("0.9250")
_PUBLISHED_RATE = Decimal("0.918273645")
_BASE = Decimal("1000.00")
_EURO_BASE = Decimal("925.00")
_PROVIDER_SOURCE = "deterministic-test"
_EURO_REFUSAL = "application.invoices.creation.errors.declared_fx_rate_on_euro_invoice"
_NOT_POSITIVE_REFUSAL = "application.invoices.creation.errors.declared_fx_rate_not_positive"


def _issue_date() -> date:
    return date(filing_year_envelope().horizon, 3, 14)


class _PublishingRateProvider:
    """A provider that does publish a USD rate on the issue date, so a declared rate must beat it."""

    @property
    def rate_source_id(self) -> str:
        return _PROVIDER_SOURCE

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        rate = _PUBLISHED_RATE if currency == "USD" and rate_date == _issue_date() else None
        return eur_rate_lookup(rate, rate_date=rate_date, source=self.rate_source_id)


def _invoice(
    *,
    currency: str,
    provider: CatalogueInvoiceRateProviderPort,
    declared_fx_rate: Decimal | None = None,
    number: str = "US-0031",
) -> Invoice:
    return build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Überseehandel GmbH",
        counterparty_tax_id="DE811907980",
        counterparty_country="DE",
        invoice_number=number,
        issued_at=_issue_date(),
        taxable_base=_BASE,
        iva_rate=None,
        currency=currency,
        declared_fx_rate=declared_fx_rate,
        rate_provider=provider,
    )


def test_a_declared_rate_converts_the_invoice_and_its_lines_and_names_the_operator() -> None:
    invoice = _invoice(currency="USD", provider=_PublishingRateProvider(), declared_fx_rate=_DECLARED_RATE)

    assert invoice.fx_rate == _DECLARED_RATE, "the declared rate must win over the published one"
    assert invoice.fx_rate_source == OPERATOR_DECLARED_RATE_SOURCE
    assert invoice.fx_rate_source != _PROVIDER_SOURCE
    assert invoice.fx_rate_date == invoice.issued_at
    assert invoice.fx_rate_observation_date is None
    assert invoice.base_total_eur == _EURO_BASE
    assert invoice.grand_total_eur == _EURO_BASE
    assert line_eur_amounts_or_refuse(invoice, 0, invoice.lines[0]) == (_EURO_BASE, Decimal("0.00"))


def test_a_euro_invoice_with_a_declared_rate_is_refused() -> None:
    with pytest.raises(InvoiceValidationError) as refused:
        _invoice(
            currency="EUR", provider=in_memory_catalogue_creation_ports().rate_provider, declared_fx_rate=_DECLARED_RATE
        )

    assert refused.value.translated_message == _EURO_REFUSAL


@pytest.mark.parametrize("declared", [Decimal("0"), Decimal("-0.9250")])
def test_a_declared_rate_that_is_not_above_zero_is_refused(declared: Decimal) -> None:
    with pytest.raises(InvoiceValidationError) as refused:
        _invoice(currency="USD", provider=_PublishingRateProvider(), declared_fx_rate=declared)

    assert refused.value.translated_message == _NOT_POSITIVE_REFUSAL
    assert refused.value.context == {"fx_rate": format(declared, "f")}


def test_without_a_published_or_declared_rate_the_invoice_stays_unconverted() -> None:
    invoice = _invoice(currency="USD", provider=in_memory_catalogue_creation_ports().rate_provider)

    assert (invoice.fx_rate, invoice.fx_rate_source, invoice.base_total_eur) == (None, None, None)
    with pytest.raises(AggregationValidationError):
        line_eur_amounts_or_refuse(invoice, 0, invoice.lines[0])


class _NoSealedRevisions:
    def sealed_revisions(self) -> tuple[()]:
        return ()


class _UnusedTransactionReader:
    def load(self) -> TransactionCatalogue:
        raise AssertionError("an exchange-rate correction must not read transactions")

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        raise AssertionError(f"an exchange-rate correction must not partition {start}..{end}")


def _lifecycle_ports(creation_ports: CatalogueCreationPorts) -> CatalogueLifecyclePorts:
    return CatalogueLifecyclePorts(
        read_ports=InvoiceCatalogueReadPorts(
            invoice_reader=creation_ports.invoice_repository,
            transaction_reader=_UnusedTransactionReader(),
        ),
        invoice_repository=creation_ports.invoice_repository,
        event_repository=creation_ports.event_repository,
        audit_commit=creation_ports.audit_commit,
        sealed_revisions=_NoSealedRevisions(),
        documents=creation_ports.documents,
    )


def _stored_unconverted() -> tuple[CatalogueCreationPorts, Invoice]:
    ports = in_memory_catalogue_creation_ports()
    invoice = _invoice(currency="USD", provider=ports.rate_provider)
    return ports, create_catalogue_invoice(invoice=invoice, ports=ports).invoice


def test_a_correction_declaring_the_rate_repairs_an_unconverted_invoice_for_the_screen() -> None:
    ports, stored = _stored_unconverted()
    with pytest.raises(AggregationValidationError):
        line_eur_amounts_or_refuse(stored, 0, stored.lines[0])

    patch = InvoiceUpdatePatch.from_patch(CatalogueInvoicePatch(declared_fx_rate=_DECLARED_RATE))
    wire = InvoiceUpdateRequest.model_validate_json(
        InvoiceUpdateRequest(profile_id=UUID(_BUCKET_ID), invoice_id=stored.invoice_id, patch=patch).model_dump_json()
    )
    corrected = update_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        invoice_id=stored.invoice_id,
        patch=wire.patch.to_patch(),
        ports=_lifecycle_ports(ports),
    ).invoice

    assert corrected.invoice_id == stored.invoice_id, "a rate is not part of the invoice identity"
    assert (corrected.fx_rate, corrected.fx_rate_source) == (_DECLARED_RATE, OPERATOR_DECLARED_RATE_SOURCE)
    assert corrected.fx_rate_date == stored.issued_at
    assert line_eur_amounts_or_refuse(corrected, 0, corrected.lines[0]) == (_EURO_BASE, Decimal("0.00"))
    assert ports.invoice_repository.load().get(stored.invoice_id) == corrected


def test_a_correction_declaring_a_rate_on_a_euro_invoice_is_refused_and_writes_nothing() -> None:
    ports = in_memory_catalogue_creation_ports()
    stored = create_catalogue_invoice(
        invoice=_invoice(currency="EUR", provider=ports.rate_provider), ports=ports
    ).invoice
    events = len(ports.event_repository.load().events)

    with pytest.raises(InvoiceValidationError) as refused:
        update_catalogue_invoice(
            bucket_id=_BUCKET_ID,
            invoice_id=stored.invoice_id,
            patch=CatalogueInvoicePatch(declared_fx_rate=_DECLARED_RATE),
            ports=_lifecycle_ports(ports),
        )

    assert refused.value.translated_message == _EURO_REFUSAL
    assert ports.invoice_repository.load().get(stored.invoice_id) == stored
    assert len(ports.event_repository.load().events) == events


def test_a_correction_cannot_clear_the_conversion_stamp() -> None:
    with pytest.raises(ValidationError):
        CatalogueInvoicePatch(declared_fx_rate=None)


def test_a_bulk_import_row_stating_a_rate_is_converted_and_a_euro_row_stating_one_is_refused(tmp_path: Path) -> None:
    issued = _issue_date().isoformat()
    source_path = tmp_path / "book.csv"
    source_path.write_text(
        "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,currency,fx_rate,country_code\n"
        f"DE811907980,Überseehandel GmbH,US-0040,{issued},1000.00,USD,0.9250,DE\n"
        f"DE811907980,Überseehandel GmbH,US-0041,{issued},1000.00,USD,,DE\n"
        f"DE811907980,Überseehandel GmbH,EU-0042,{issued},1000.00,EUR,0.9250,DE\n",
        encoding="utf-8",
    )
    ports = in_memory_catalogue_creation_ports()

    result = import_invoices_from_rows(
        read_bulk_invoice_import_source(source_path),
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        ports=ports,
    )

    assert (result.created, result.skipped_duplicate) == (2, 0)
    assert [(failure.row_number, failure.field) for failure in result.refused] == [(4, "invoice")]
    stored = {invoice.invoice_number: invoice for invoice in ports.invoice_repository.load()}
    declared = stored["US-0040"]
    assert (declared.fx_rate, declared.fx_rate_source) == (_DECLARED_RATE, OPERATOR_DECLARED_RATE_SOURCE)
    assert declared.base_total_eur == _EURO_BASE
    assert stored["US-0041"].fx_rate is None, "a blank rate cell leaves the provider's answer, here none"
    assert stored["US-0041"].base_total_eur is None
