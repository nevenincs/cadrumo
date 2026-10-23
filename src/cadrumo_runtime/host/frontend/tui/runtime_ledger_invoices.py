"""Invoice book import and the invoice wizard through the installed TUI's retained runtime session.

The registered import has no dry run. Its review is therefore read here, on
the host: the typed file is resolved, measured and digested off the event
loop, and the import is submitted with that digest so the worker refuses a
file whose bytes changed after the operator reviewed it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

from cadrumo.application.invoices.catalogue_intake_contracts import (
    INVOICE_IMPORT_OPERATION_DEFINITION_ID,
    INVOICE_WIZARD_OPERATION_DEFINITION_ID,
    InvoiceImportProjection,
    InvoiceImportRequest,
    InvoiceWizardOutcome,
    InvoiceWizardRequest,
)
from cadrumo.application.invoices.catalogue_intake_refusal import INVOICE_WIZARD_VALIDATION_REFUSAL_CODE
from cadrumo.application.ledger.workspace import LedgerWorkspaceArea
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.core.hashing import sha256_file
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.invoices.errors import InvoiceValidationError
from cadrumo.entrypoints.tui.ledger.invoices_import import LedgerInvoiceImportScreen, LedgerInvoiceImportSourceV1
from cadrumo.entrypoints.tui.ledger.invoices_wizard import LedgerInvoiceWizardScreen
from cadrumo.entrypoints.tui.ledger.tools import LedgerToolV1
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from .operations.runtime_profile_session import RuntimeProfileSession


def _read_invoice_import_source(source_path: str) -> LedgerInvoiceImportSourceV1:
    """Resolve the typed file and digest its bytes; blocking, so callers run it off the event loop."""
    path = Path(source_path).expanduser().resolve(strict=True)
    if not path.is_file():
        raise IsADirectoryError(str(path))
    return LedgerInvoiceImportSourceV1(
        source_path=str(path),
        file_name=path.name,
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
    )


def _import_effect(result: InvoiceImportProjection) -> OperationEffect:
    if result.created == 0:
        return OperationEffect.NONE
    return OperationEffect.PARTIAL if result.refused else OperationEffect.UPDATED


class RuntimeLedgerInvoiceImportTuiDoorV1:
    """Review and import invoice books for the exact TUI profile and session."""

    def __init__(self, client: FrontendClient, *, profile_label: str) -> None:
        """Pin the admitted profile and session for every import."""
        self._session = RuntimeProfileSession(client, profile_label=profile_label)

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    async def preview(self, source_path: str) -> LedgerInvoiceImportSourceV1:
        """Find the typed file on the host and digest it off the event loop; nothing is submitted."""
        # The binding check reads the session over IPC; it never runs on the event loop.
        await asyncio.to_thread(self._session.require_binding)
        try:
            return await asyncio.to_thread(_read_invoice_import_source, source_path)
        except OSError as error:
            raise InvoiceValidationError(
                translated_message="application.invoices.bulk_import.errors.file_read_failed",
                context={"path_name": Path(source_path).name, "error_type": type(error).__name__},
            ) from error

    async def apply(self, request: InvoiceImportRequest) -> InvoiceImportProjection:
        """Import the reviewed file; a request without the reviewed digest is never sent."""
        if request.source_sha256 is None:
            raise RefusalError(RefusalCode.INVALID_FRAME)

        def settle(
            result: InvoiceImportProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not (
                condition is OperationTerminalCondition.SUCCEEDED
                and terminal.refusal_ref is None
                and terminal.failure_error_code is None
                and terminal.effect is _import_effect(result)
                and result.profile_id == request.profile_id
                and result.source_sha256 == request.source_sha256
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=INVOICE_IMPORT_OPERATION_DEFINITION_ID,
            result_type=InvoiceImportProjection,
            settle=settle,
            explain_failure=True,
        )


class RuntimeLedgerInvoiceWizardTuiDoorV1:
    """Record one invoice through the wizard for the exact TUI profile and session."""

    def __init__(self, client: FrontendClient, *, profile_label: str) -> None:
        """Pin the admitted profile and session for every entry."""
        self._session = RuntimeProfileSession(client, profile_label=profile_label)

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    async def __call__(self, request: InvoiceWizardRequest) -> InvoiceWizardOutcome:
        """Return the recorded invoice, or the owner's field refusals with nothing written."""

        def settle(
            result: InvoiceWizardOutcome,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if result.profile_id != request.profile_id or terminal.failure_error_code is not None:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            if result.outcome == "refused":
                if not (
                    condition is OperationTerminalCondition.REFUSED
                    and terminal.refusal_ref == INVOICE_WIZARD_VALIDATION_REFUSAL_CODE
                    and terminal.effect is OperationEffect.NONE
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                return
            recorded = result.result
            if (
                recorded is None
                or condition is not OperationTerminalCondition.SUCCEEDED
                or terminal.refusal_ref is not None
                or terminal.effect
                is not (OperationEffect.NONE if recorded.already_existed else OperationEffect.UPDATED)
                or recorded.invoice.kind is not request.kind
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=INVOICE_WIZARD_OPERATION_DEFINITION_ID,
            result_type=InvoiceWizardOutcome,
            settle=settle,
            allow_refusal_detail=True,
            explain_failure=True,
        )


def compose_invoices_tools(client: FrontendClient, profile_label: str) -> tuple[LedgerToolV1, ...]:
    """The overview's invoice import and invoice wizard tools, bound to the workbench's runtime session."""
    import_door = RuntimeLedgerInvoiceImportTuiDoorV1(client, profile_label=profile_label)
    wizard_door = RuntimeLedgerInvoiceWizardTuiDoorV1(client, profile_label=profile_label)
    return (
        LedgerToolV1(
            key="ledger.tool.invoices.import",
            label_key="tui.ledger.invoices.import.tool",
            area=LedgerWorkspaceArea.OVERVIEW,
            build=lambda controller: LedgerInvoiceImportScreen(controller, import_door),
        ),
        LedgerToolV1(
            key="ledger.tool.invoices.wizard",
            label_key="tui.ledger.invoices.wizard.tool",
            area=LedgerWorkspaceArea.OVERVIEW,
            build=lambda controller: LedgerInvoiceWizardScreen(controller, wizard_door),
        ),
    )


__all__ = [
    "RuntimeLedgerInvoiceImportTuiDoorV1",
    "RuntimeLedgerInvoiceWizardTuiDoorV1",
    "compose_invoices_tools",
]
