"""The ledger entry options through the installed TUI's retained runtime session.

A form's link pickers offer only what ``ledger.entry-options`` serves for the
exact profile. The read is released only when its result names the profile
asked, under a receipt that changed nothing.
"""

from __future__ import annotations

from cadrumo.application.ledger.entry_options_operation import (
    LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
    LedgerEntryOptionsProjection,
    LedgerEntryOptionsRequest,
)
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import output_language
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from .operations.runtime_profile_session import RuntimeProfileSession


class RuntimeLedgerEntryOptionsTuiDoorV1:
    """Read the exact profile's entry options in the current output language."""

    def __init__(self, client: FrontendClient, *, profile_label: str) -> None:
        """Pin the originating profile and session for every read."""
        self._session = RuntimeProfileSession(client, profile_label=profile_label)

    async def __call__(self) -> LedgerEntryOptionsProjection:
        """Read the options and refuse a result its receipt does not support."""
        request = LedgerEntryOptionsRequest(
            profile_id=self._session.profile_id, output_language=OutputLanguage(output_language())
        )

        def settle(
            result: LedgerEntryOptionsProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not (
                result.profile_id == request.profile_id
                and condition is OperationTerminalCondition.SUCCEEDED
                and terminal.refusal_ref is None
                and terminal.effect is OperationEffect.NONE
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
            result_type=LedgerEntryOptionsProjection,
            settle=settle,
            explain_failure=True,
        )


__all__ = ["RuntimeLedgerEntryOptionsTuiDoorV1"]
