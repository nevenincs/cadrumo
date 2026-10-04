"""Invoice creation through the installed TUI's retained runtime session."""

from __future__ import annotations

from decimal import Decimal
from typing import NoReturn
from uuid import UUID

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.invoices.catalogue_add_contracts import (
    INVOICE_ADD_OPERATION_DEFINITION_ID,
    INVOICE_ADD_VALIDATION_REFUSAL_CODE,
    InvoiceAddBusinessPremisesLease,
    InvoiceAddLine,
    InvoiceAddRequest,
    InvoiceAddResult,
)
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....application.operations.public_scalar import PublicDecimal
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.operations import (
    OperationEffect,
    OperationTerminalCondition,
)
from ....domain.invoices.business_premises import business_premises_lease_from_inputs
from ....domain.invoices.errors import InvoiceValidationError
from ....entrypoints.tui.ledger.models import (
    LedgerInvoiceAddResultV1,
    LedgerInvoiceEntryV1,
)
from ....entrypoints.tui.operations.runtime_profile_session import RuntimeProfileSession

_DUPLICATE_INVOICE_TRANSLATION = "application.invoices.creation.errors.duplicate_invoice"
_INVALID_INVOICE_TRANSLATION = "errors.refused.refused_cli_validation_boundary"


def _invoice_matches_request(result: InvoiceAddResult, request: InvoiceAddRequest, entry: LedgerInvoiceEntryV1) -> bool:
    invoice = result.invoice
    if invoice is None or invoice.bucket_id is None:
        return False
    return (
        str(invoice.bucket_id) == str(request.profile_id)
        and invoice.kind is entry.kind
        and invoice.invoice_number == entry.invoice_number
        and invoice.issued_at == entry.invoice_date
        and invoice.counterparty_name == entry.counterparty_name
        and invoice.counterparty_tax_id == entry.counterparty_nif
        and invoice.counterparty_country == entry.country_code
        and invoice.currency == entry.currency
    )


def _created_receipt_matches(
    terminal_projection: OperationPublicProjectionV1,
) -> bool:
    return (
        terminal_projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        and terminal_projection.effect is OperationEffect.UPDATED
        and terminal_projection.refusal_ref is None
        and terminal_projection.result_ref is not None
    )


def _validation_refusal_matches(result: InvoiceAddResult, terminal_projection: OperationPublicProjectionV1) -> bool:
    return (
        terminal_projection.terminal_condition is OperationTerminalCondition.REFUSED
        and terminal_projection.effect is OperationEffect.NONE
        and terminal_projection.refusal_ref == INVOICE_ADD_VALIDATION_REFUSAL_CODE
        and terminal_projection.result_ref is None
        and result.invoice is None
        and result.validation_code is not None
        and (result.validation_code == "duplicate_invoice") == (result.invoice_id is not None)
    )


class RuntimeInvoiceAddTuiDoorV1:
    """Submit the full invoice form to the one registered catalogue writer."""

    def __init__(self, client: RuntimeFrontendClient, *, profile_label: str) -> None:
        """Retain the exact TUI profile and session for this installed door."""
        self._session = RuntimeProfileSession(client, profile_label=profile_label)
        self._profile_id = self._session.profile_id

    async def __call__(self, entry: LedgerInvoiceEntryV1) -> LedgerInvoiceAddResultV1:
        """Keep every parsed entry fact and disclose only the operation's typed result."""
        request = _request_from_entry(self._profile_id, entry)
        result = await self._execute(request, entry=entry)
        invoice = result.invoice
        if result.outcome != "created" or invoice is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return LedgerInvoiceAddResultV1(
            invoice_id=invoice.invoice_id,
            invoice_number=invoice.invoice_number,
            base_total=Decimal(invoice.base_total.decimal),
            iva_total=Decimal(invoice.iva_total.decimal),
            grand_total=Decimal(invoice.grand_total.decimal),
            currency=invoice.currency,
            euro_value_pending=result.euro_value_pending,
        )

    async def _execute(self, request: InvoiceAddRequest, *, entry: LedgerInvoiceEntryV1) -> InvoiceAddResult:
        """Submit, observe and disclose one typed terminal receipt in this session."""

        def settle(
            result: InvoiceAddResult,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            operation_id: str,
        ) -> None:
            self._validate_result(result, request=request, entry=entry, terminal_projection=terminal)
            if result.outcome == "validation_error":
                self._raise_validation_refusal(
                    result,
                    operation_id=operation_id,
                    terminal_condition=condition,
                    effect=terminal.effect,
                )

        return await self._session.run_operation(
            request,
            definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
            result_type=InvoiceAddResult,
            settle=settle,
            allow_refusal_detail=True,
        )

    @staticmethod
    def _validate_result(
        result: InvoiceAddResult,
        *,
        request: InvoiceAddRequest,
        entry: LedgerInvoiceEntryV1,
        terminal_projection: OperationPublicProjectionV1,
    ) -> None:
        """Correlate the typed invoice or refusal with its settled operation receipt."""
        if (
            result.profile_id != request.profile_id
            or terminal_projection.failure_error_code is not None
            or terminal_projection.diagnostic_ref is not None
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if result.outcome == "created":
            if not _created_receipt_matches(terminal_projection) or not _invoice_matches_request(
                result, request, entry
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return
        if not _validation_refusal_matches(result, terminal_projection):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

    @staticmethod
    def _raise_validation_refusal(
        result: InvoiceAddResult,
        *,
        operation_id: str,
        terminal_condition: OperationTerminalCondition,
        effect: OperationEffect,
    ) -> NoReturn:
        """Rebuild the established invoice validation refusal with its operation receipt."""
        if result.validation_code is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        context: dict[str, object] = {
            "operation_id": operation_id,
            "terminal_condition": terminal_condition.value,
            "effect": effect.value,
            "refusal_code": INVOICE_ADD_VALIDATION_REFUSAL_CODE,
        }
        if result.invoice_id is not None:
            context["invoice_id"] = result.invoice_id
        raise InvoiceValidationError(
            "Invoice creation was refused by validation.",
            context=context,
            translated_message=(
                _DUPLICATE_INVOICE_TRANSLATION
                if result.validation_code == "duplicate_invoice"
                else _INVALID_INVOICE_TRANSLATION
            ),
        )


def _request_from_entry(profile_id: UUID, entry: LedgerInvoiceEntryV1) -> InvoiceAddRequest:
    """Copy the complete parsed form into the operation's bounded private request."""
    return InvoiceAddRequest(
        profile_id=profile_id,
        kind=entry.kind,
        counterparty_name=entry.counterparty_name,
        counterparty_tax_id=entry.counterparty_nif,
        counterparty_country=entry.country_code,
        invoice_number=entry.invoice_number,
        issued_at=entry.invoice_date,
        taxable_base=_public_decimal(entry.taxable_base),
        iva_rate=_public_decimal(entry.iva_rate),
        currency=entry.currency,
        notes=entry.notes,
        iva_category=None if entry.iva_category is None else str(entry.iva_category),
        operation_type=entry.operation_type,
        operation_date=entry.operation_date,
        retention_rate=_public_decimal(entry.retention_rate),
        retention_amount=_public_decimal(entry.retention_amount),
        invoice_class=str(entry.invoice_class),
        series=entry.series,
        rectifies_invoice_number=entry.rectifies_invoice_number,
        recargo_amount=_public_decimal(entry.recargo_amount),
        business_premises_lease=InvoiceAddBusinessPremisesLease.from_domain(
            business_premises_lease_from_inputs(
                lease_selected=entry.arrendamiento_local_negocio,
                situacion_inmueble=entry.situacion_inmueble,
                referencia_catastral=entry.referencia_catastral,
            )
        ),
        lines=tuple(
            InvoiceAddLine(
                description=line.description,
                quantity=PublicDecimal(decimal=str(line.quantity)),
                unit_price=PublicDecimal(decimal=str(line.unit_price)),
                subtotal=PublicDecimal(decimal=str(line.subtotal)),
                iva_rate=line.iva_rate,
                iva_amount=PublicDecimal(decimal=str(line.iva_amount)),
                spending_category_id=line.spending_category_id,
                oss_rate_kind=line.oss_rate_kind,
            )
            for line in entry.lines
        ),
    )


def _public_decimal(value: Decimal | None) -> PublicDecimal | None:
    return None if value is None else PublicDecimal(decimal=str(value))


def compose_runtime_invoice_add_door(
    *, client: RuntimeFrontendClient, profile_label: str
) -> RuntimeInvoiceAddTuiDoorV1:
    """Bind the invoice form to the runtime client retained by its workbench."""
    return RuntimeInvoiceAddTuiDoorV1(client, profile_label=profile_label)


__all__ = ["RuntimeInvoiceAddTuiDoorV1", "compose_runtime_invoice_add_door"]
