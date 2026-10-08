"""Own bank account setup through the installed TUI's retained runtime session."""

from __future__ import annotations

from uuid import UUID

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.own_account_operation import (
    LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
    LedgerOwnAccountRequest,
    LedgerOwnAccountResult,
)
from ...application.operations.frontend_projection import OperationPublicProjectionV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition
from .ledger.own_accounts import LedgerOwnAccountDoorV1
from .operations.runtime_profile_session import RuntimeProfileSession

_READ_ACTIONS = frozenset({"list", "show"})


def _result_matches(
    result: LedgerOwnAccountResult,
    request: LedgerOwnAccountRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """Whether the masked result answers exactly the request under its settled receipt."""
    expected_effect = OperationEffect.UPDATED if result.changed else OperationEffect.NONE
    names_account = request.own_account_id is not None or request.action == "add"
    return (
        result.profile_id == request.profile_id
        and result.action == request.action
        and condition is OperationTerminalCondition.SUCCEEDED
        and terminal.refusal_ref is None
        and terminal.effect is expected_effect
        and (request.own_account_id is None or result.own_account_id == request.own_account_id)
        and (not names_account or result.own_account_id is not None)
        and not (request.action in _READ_ACTIONS and result.changed)
    )


class RuntimeOwnAccountTuiDoorV1:
    """Submit own-account requests for the exact TUI profile and session this door was built for."""

    def __init__(self, client: RuntimeFrontendClient, *, profile_label: str) -> None:
        """Pin the admitted profile and session for every request."""
        self._session = RuntimeProfileSession(client, profile_label=profile_label)

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    async def __call__(self, request: LedgerOwnAccountRequest) -> LedgerOwnAccountResult:
        """Run one request and refuse a result its terminal receipt does not support."""

        def settle(
            result: LedgerOwnAccountResult,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not _result_matches(result, request, condition, terminal):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=LEDGER_OWN_ACCOUNT_OPERATION_DEFINITION_ID,
            result_type=LedgerOwnAccountResult,
            settle=settle,
            explain_failure=True,
        )


def compose_runtime_own_account_door(*, client: RuntimeFrontendClient, profile_label: str) -> LedgerOwnAccountDoorV1:
    """Bind the own-account screen to the runtime client retained by its workbench."""
    return RuntimeOwnAccountTuiDoorV1(client, profile_label=profile_label)


__all__ = ["RuntimeOwnAccountTuiDoorV1", "compose_runtime_own_account_door"]
