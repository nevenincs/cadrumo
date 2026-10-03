"""Invoice creation through the installed TUI's retained runtime session."""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from typing import NoReturn
from uuid import UUID

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....application.invoices.catalogue_add_operation import (
    INVOICE_ADD_OPERATION_DEFINITION_ID,
    INVOICE_ADD_VALIDATION_REFUSAL_CODE,
    InvoiceAddLine,
    InvoiceAddRequest,
    InvoiceAddResult,
)
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....application.operations.frontend_requests import (
    OperationObservationRefusalV1,
    OperationObservationSuccessV1,
)
from ....application.operations.public_scalar import PublicDecimal
from ....application.operations.registry import OperationFrontendProjection, OperationSchemaIdentityV1
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ....domain.invoices.errors import InvoiceValidationError
from ....entrypoints.tui.account import AccountSessionExpiredError
from ....entrypoints.tui.ledger.models import (
    LedgerInvoiceAddResultV1,
    LedgerInvoiceEntryV1,
)
from ....entrypoints.tui.operations.runtime_controller import RuntimeOperationController
from ..runtime_account_session import read_runtime_account_session

_DUPLICATE_INVOICE_TRANSLATION = "application.invoices.creation.errors.duplicate_invoice"
_INVALID_INVOICE_TRANSLATION = "errors.refused.refused_cli_validation_boundary"


class RuntimeInvoiceAddTuiDoorV1:
    """Submit the full invoice form to the one registered catalogue writer."""

    def __init__(self, client: RuntimeFrontendClient, *, profile_label: str) -> None:
        """Retain the exact TUI profile and session for this installed door."""
        if client.frontend is not OperationFrontendProjection.TUI or not profile_label:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._client = client
        self._profile_id = client.profile_id
        self._session_id = client.session_id
        self._profile_label = profile_label
        self._require_binding()

    def _require_binding(self) -> None:
        if (
            self._client.frontend is not OperationFrontendProjection.TUI
            or self._client.profile_id != self._profile_id
            or self._client.session_id != self._session_id
        ):
            raise AccountSessionExpiredError()
        read_runtime_account_session(
            self._client,
            profile_id=self._profile_id,
            session_id=self._session_id,
            profile_label=self._profile_label,
        )

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
        self._require_binding()
        if request.profile_id != self._profile_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        subject_ref = profile_operation_subject(str(self._profile_id))
        request_schema = OperationSchemaIdentityV1.from_model(
            schema_id=f"{INVOICE_ADD_OPERATION_DEFINITION_ID}.request",
            schema_version=1,
            model_type=InvoiceAddRequest,
        )
        deadline = time.monotonic() + 120
        controller: RuntimeOperationController | None = None
        terminal_projection: OperationPublicProjectionV1 | None = None
        try:
            controller = await RuntimeOperationController.submit(
                self._client,
                definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
                subject_ref=subject_ref,
                payload=request,
                expected_session_id=self._session_id,
                deadline=deadline,
            )
            await controller.start()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                observed = await controller.observe(0, page_limit=1)
                if isinstance(observed, OperationObservationRefusalV1):
                    raise RuntimeFrontendRefusedError(observed.code.value)
                if not isinstance(observed, OperationObservationSuccessV1):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                state = observed.projection
                if (
                    state.operation_id != controller.operation_id
                    or state.definition_id != INVOICE_ADD_OPERATION_DEFINITION_ID
                    or state.subject_ref != subject_ref
                    or state.definition_contract.request_schema != request_schema
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                if state.lifecycle is OperationLifecycle.TERMINAL:
                    terminal_projection = state
                    break
                await asyncio.sleep(min(0.05, remaining))

            condition = terminal_projection.terminal_condition
            if condition is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if condition is not OperationTerminalCondition.SUCCEEDED and not (
                condition is OperationTerminalCondition.REFUSED
                and terminal_projection.refusal_ref in terminal_projection.definition_contract.refusal_detail_codes
            ):
                raise RuntimeFrontendRefusedError(
                    terminal_projection.refusal_ref
                    or terminal_projection.failure_error_code
                    or "operation_not_successful"
                )
            result = await controller.read_settled_result(
                terminal_projection,
                InvoiceAddResult,
                result_version=1,
                allow_refusal_detail=True,
            )
            self._require_binding()
            self._validate_result(
                result,
                request=request,
                entry=entry,
                terminal_projection=terminal_projection,
            )
            if result.outcome == "validation_error":
                self._raise_validation_refusal(
                    result,
                    operation_id=str(controller.operation_id),
                    terminal_condition=condition,
                    effect=terminal_projection.effect,
                )
            return result
        except AccountSessionExpiredError as error:
            raise self._session_expired_with_receipt(controller, terminal_projection) from error
        except (RuntimeFrontendRefusedError, RuntimeRefusalError):
            # A runtime denial is ordinary only while the originating session remains live.
            try:
                self._require_binding()
            except AccountSessionExpiredError as error:
                raise self._session_expired_with_receipt(controller, terminal_projection) from error
            raise

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
        condition = terminal_projection.terminal_condition
        if result.outcome == "created":
            invoice = result.invoice
            if (
                condition is not OperationTerminalCondition.SUCCEEDED
                or terminal_projection.effect is not OperationEffect.UPDATED
                or terminal_projection.refusal_ref is not None
                or terminal_projection.result_ref is None
                or invoice is None
                or invoice.bucket_id is None
                or str(invoice.bucket_id) != str(request.profile_id)
                or invoice.kind is not entry.kind
                or invoice.invoice_number != entry.invoice_number
                or invoice.issued_at != entry.invoice_date
                or invoice.counterparty_name != entry.counterparty_name
                or invoice.counterparty_tax_id != entry.counterparty_nif
                or invoice.counterparty_country != entry.country_code
                or invoice.currency != entry.currency
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return
        if (
            condition is not OperationTerminalCondition.REFUSED
            or terminal_projection.effect is not OperationEffect.NONE
            or terminal_projection.refusal_ref != INVOICE_ADD_VALIDATION_REFUSAL_CODE
            or terminal_projection.result_ref is not None
            or result.invoice is not None
            or result.validation_code is None
            or (result.validation_code == "duplicate_invoice") != (result.invoice_id is not None)
        ):
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

    @staticmethod
    def _session_expired_with_receipt(
        controller: RuntimeOperationController | None,
        projection: OperationPublicProjectionV1 | None,
    ) -> AccountSessionExpiredError:
        """Keep a terminal write receipt visible when the retained session expires."""
        if controller is None:
            return AccountSessionExpiredError()
        condition = projection.terminal_condition if projection is not None else None
        effect = projection.effect if projection is not None else OperationEffect.UNKNOWN
        refusal_code = projection.refusal_ref if projection is not None else None
        return AccountSessionExpiredError(
            context={
                "operation_id": str(controller.operation_id),
                "terminal_condition": condition.value if condition is not None else "unknown",
                "effect": effect.value,
                "refusal_code": refusal_code,
            }
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
