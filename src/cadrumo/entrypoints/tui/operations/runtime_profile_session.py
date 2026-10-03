"""One TUI runtime client pinned to the profile session it was admitted for."""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID

from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....application.operations.registry import OperationFrontendProjection, OperationSchemaIdentityV1
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.operations import OperationTerminalCondition, profile_operation_subject
from ..account import AccountSessionExpiredError
from ..runtime_account_session import read_runtime_account_session, session_expired_with_receipt
from .runtime_controller import RuntimeOperationController, await_terminal_projection

_OPERATION_TIMEOUT_SECONDS = 120


class RuntimeProfileSession:
    """Submit registered operations only while the admitted profile session is still live."""

    def __init__(
        self,
        client: RuntimeFrontendClient,
        *,
        profile_label: str,
        on_expired: Callable[[], None] = lambda: None,
    ) -> None:
        """Pin the client's profile and session, then require that they are currently live.

        ``on_expired`` runs when the pinned session is found lost, so a door can
        drop state it retained only for that session.
        """
        if client.frontend is not OperationFrontendProjection.TUI or not profile_label:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
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
    ) -> ResultT:
        """Submit, observe and read one typed terminal result in this session.

        ``admit`` inspects the terminal receipt before its result is read.
        ``settle`` receives the read result, the terminal condition, the receipt
        and the operation identifier once the session is confirmed live; it
        raises when the result disagrees with the receipt, or to surface a
        declared refusal. A denial is ordinary only while the originating
        session remains live, so a lost session reports the receipt it had.
        """
        self.require_binding()
        if getattr(request, "profile_id", None) != self._profile_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        subject_ref = profile_operation_subject(str(self._profile_id))
        request_schema = OperationSchemaIdentityV1.from_model(
            schema_id=f"{definition_id}.request",
            schema_version=1,
            model_type=type(request),
        )
        deadline = time.monotonic() + _OPERATION_TIMEOUT_SECONDS
        controller: RuntimeOperationController | None = None
        terminal_projection: OperationPublicProjectionV1 | None = None
        try:
            controller = await RuntimeOperationController.submit(
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
                admit=admit,
                settle=settle,
            )
        except AccountSessionExpiredError as error:
            raise session_expired_with_receipt(controller, terminal_projection) from error
        except (RuntimeFrontendRefusedError, RuntimeRefusalError):
            try:
                self.require_binding()
            except AccountSessionExpiredError as error:
                raise session_expired_with_receipt(controller, terminal_projection) from error
            raise

    async def _read_settled_result[ResultT: BaseModel](
        self,
        controller: RuntimeOperationController,
        terminal: OperationPublicProjectionV1,
        *,
        result_type: type[ResultT],
        result_version: int,
        allow_refusal_detail: bool,
        admit: Callable[[OperationPublicProjectionV1], None],
        settle: Callable[[ResultT, OperationTerminalCondition, OperationPublicProjectionV1, str], None],
    ) -> ResultT:
        condition = terminal.terminal_condition
        if condition is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if condition is not OperationTerminalCondition.SUCCEEDED and not _refusal_detail_is_allowed(
            condition, terminal, allow_refusal_detail
        ):
            raise RuntimeFrontendRefusedError(
                terminal.refusal_ref or terminal.failure_error_code or "operation_not_successful"
            )
        admit(terminal)
        result = await controller.read_settled_result(
            terminal,
            result_type,
            result_version=result_version,
            allow_refusal_detail=allow_refusal_detail,
        )
        self.require_binding()
        settle(result, condition, terminal, str(controller.operation_id))
        return result


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
