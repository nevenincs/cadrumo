"""One TUI runtime client pinned to the profile session it was admitted for."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Final
from uuid import UUID

from pydantic import BaseModel

from cadrumo.application.operations.error_detail import OperationErrorDetailKind
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.operations.outcome import OperationOutcomeUnknownError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_controller import OperationController, await_terminal_projection

from ..runtime_account_session import read_runtime_account_session, session_expired_with_receipt

_OPERATION_TIMEOUT_SECONDS = 120
#: Transport refusals that end the frontend's watch without saying how the operation settled.
_UNOBSERVED_SETTLEMENT: Final = frozenset(
    {
        RefusalCode.DEADLINE_EXCEEDED,
        RefusalCode.CONNECTION_CLOSED,
        RefusalCode.UNAVAILABLE,
        RefusalCode.DRAINING,
    }
)


class RuntimeProfileSession:
    """Submit registered operations only while the admitted profile session is still live."""

    def __init__(
        self,
        client: FrontendClient,
        *,
        profile_label: str,
        on_expired: Callable[[], None] = lambda: None,
    ) -> None:
        """Pin the client's profile and session, then require that they are currently live.

        ``on_expired`` runs when the pinned session is found lost, so a door can
        drop state it retained only for that session.
        """
        if client.frontend is not OperationFrontendProjection.TUI or not profile_label:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._client = client
        self._profile_id = client.profile_id
        self._session_id = client.session_id
        self._profile_label = profile_label
        self._on_expired = on_expired
        self.require_binding()

    @property
    def profile_id(self) -> UUID:
        """The profile this session was admitted for."""
        return self._profile_id

    @property
    def session_id(self) -> UUID:
        """The runtime session this connection was admitted under."""
        return self._session_id

    def require_binding(self) -> None:
        """Refuse unless the originating client still holds an unexpired session for its profile."""
        try:
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
        except AccountSessionExpiredError:
            self._on_expired()
            raise

    async def run_operation[ResultT: BaseModel](
        self,
        request: BaseModel,
        *,
        definition_id: str,
        result_type: type[ResultT],
        settle: Callable[[ResultT, OperationTerminalCondition, OperationPublicProjectionV1, str], None],
        admit: Callable[[OperationPublicProjectionV1], None] = lambda _terminal: None,
        result_version: int = 1,
        allow_refusal_detail: bool = False,
        explain_failure: bool = False,
    ) -> ResultT:
        """Submit, observe and read one typed terminal result in this session.

        ``admit`` inspects the terminal receipt before its result is read.
        ``settle`` receives the read result, the terminal condition, the receipt
        and the operation identifier once the session is confirmed live; it
        raises when the result disagrees with the receipt, or to surface a
        declared refusal. A denial is ordinary only while the originating
        session remains live, so a lost session reports the receipt it had.
        With ``explain_failure``, a refused or failed operation that recorded a
        registered error raises that error, so the screen can say why.

        Once the operation is submitted, a wait that ends before its settlement
        is observed, or a receipt that did not succeed yet reports an effect,
        raises :class:`OperationOutcomeUnknownError` rather than a refusal: the
        change may be saved, so a retry is not known to be safe.
        """
        # The binding check reads the session over IPC; on the loop it froze every key for the round trip.
        await asyncio.to_thread(self.require_binding)
        if getattr(request, "profile_id", None) != self._profile_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        subject_ref = profile_operation_subject(str(self._profile_id))
        request_schema = OperationSchemaIdentityV1.from_model(
            schema_id=f"{definition_id}.request",
            schema_version=1,
            model_type=type(request),
        )
        deadline = time.monotonic() + _OPERATION_TIMEOUT_SECONDS
        controller: OperationController | None = None
        terminal_projection: OperationPublicProjectionV1 | None = None
        try:
            controller = await OperationController.submit(
                self._client,
                definition_id=definition_id,
                subject_ref=subject_ref,
                payload=request,
                expected_session_id=self._session_id,
                deadline=deadline,
            )
            await controller.start()
            terminal_projection = await await_terminal_projection(
                controller,
                definition_id=definition_id,
                subject_ref=subject_ref,
                request_schema=request_schema,
                deadline=deadline,
            )
            return await self._read_settled_result(
                controller,
                terminal_projection,
                result_type=result_type,
                result_version=result_version,
                allow_refusal_detail=allow_refusal_detail,
                explain_failure=explain_failure,
                admit=admit,
                settle=settle,
            )
        except AccountSessionExpiredError as error:
            raise session_expired_with_receipt(controller, terminal_projection) from error
        except (FrontendRefusedError, RefusalError) as refusal:
            try:
                await asyncio.to_thread(self.require_binding)
            except AccountSessionExpiredError as error:
                raise session_expired_with_receipt(controller, terminal_projection) from error
            if (
                controller is not None
                and isinstance(refusal, RefusalError)
                and refusal.reason in _UNOBSERVED_SETTLEMENT
                and (terminal_projection is None or terminal_projection.effect is not OperationEffect.NONE)
            ):
                # A receipt that settled with no effect committed nothing, so only its transport failed.
                raise OperationOutcomeUnknownError(
                    operation_id=str(controller.operation_id),
                    effect=None if terminal_projection is None else terminal_projection.effect,
                ) from refusal
            raise

    async def _read_settled_result[ResultT: BaseModel](
        self,
        controller: OperationController,
        terminal: OperationPublicProjectionV1,
        *,
        result_type: type[ResultT],
        result_version: int,
        allow_refusal_detail: bool,
        explain_failure: bool,
        admit: Callable[[OperationPublicProjectionV1], None],
        settle: Callable[[ResultT, OperationTerminalCondition, OperationPublicProjectionV1, str], None],
    ) -> ResultT:
        condition = terminal.terminal_condition
        if condition is None:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        if condition is not OperationTerminalCondition.SUCCEEDED and not _refusal_detail_is_allowed(
            condition, terminal, allow_refusal_detail
        ):
            recorded = await self._recorded_error(controller, terminal) if explain_failure else None
            uncertain = terminal.effect is not OperationEffect.NONE
            if uncertain or recorded is not None:
                await asyncio.to_thread(self.require_binding)
            if uncertain:
                # Only a receipt that committed nothing is a refusal; any other effect leaves the change uncertain.
                raise OperationOutcomeUnknownError(
                    operation_id=str(controller.operation_id), effect=terminal.effect, reason=recorded
                )
            if recorded is not None:
                raise recorded
            raise FrontendRefusedError(
                terminal.refusal_ref or terminal.failure_error_code or "operation_not_successful"
            )
        admit(terminal)
        result = await controller.read_settled_result(
            terminal,
            result_type,
            result_version=result_version,
            allow_refusal_detail=allow_refusal_detail,
        )
        await asyncio.to_thread(self.require_binding)
        settle(result, condition, terminal, str(controller.operation_id))
        return result

    async def _recorded_error(
        self,
        controller: OperationController,
        terminal: OperationPublicProjectionV1,
    ) -> RecordedRegisteredError | None:
        """The executor's recorded registered error, if it recorded one."""
        detail = await controller.settled_error_detail(terminal)
        if detail is None or detail.kind is not OperationErrorDetailKind.REGISTERED_ERROR or detail.error_code is None:
            return None
        return RecordedRegisteredError(
            detail.error_code,
            context=detail.context_mapping(),
            translated_message=detail.message_key,
        )


def _refusal_detail_is_allowed(
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
    allow_refusal_detail: bool,
) -> bool:
    return (
        allow_refusal_detail
        and condition is OperationTerminalCondition.REFUSED
        and terminal.refusal_ref in terminal.definition_contract.refusal_detail_codes
    )
