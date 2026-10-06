"""Proof execution and verified-client custody for runtime login."""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING
from uuid import UUID

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.operations.registry import OperationFrontendProjection
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.profile_access import RuntimeProfileStatus, status_admits_session
from ....application.user_profile.login_session import ProfileReceiptRefusedError
from ....core.async_cleanup import AsyncResourceCleanupError, await_cancellation_complete, close_async_resources
from ....core.time.clock import now
from .runtime_login_contracts import RuntimeLoginHandoff, RuntimeLoginMethod
from .runtime_login_session import LoginAttemptState, open_to_completion

if TYPE_CHECKING:
    from .runtime_login import RuntimeLoginScreen


class RuntimeLoginAttemptMixin:
    """Own proof execution, admission, cancellation, and connection custody."""

    async def _close_untransferred(
        self: RuntimeLoginScreen, client: RuntimeFrontendClient, *, primary_error: BaseException | None
    ) -> None:
        """Keep each candidate in the existing pool until its native close succeeds."""

        async def close_candidate() -> None:
            await asyncio.to_thread(client.close)

        owner = self._retain_cleanup_owner(id(client), close_candidate)
        cancellation = primary_error if isinstance(primary_error, asyncio.CancelledError) else None
        interrupted_failure = None if cancellation is None else cancellation.__dict__.get("cleanup_error")
        if isinstance(interrupted_failure, BaseException) and not isinstance(
            interrupted_failure, AsyncResourceCleanupError
        ):
            primary_error = interrupted_failure
        await close_async_resources(
            owner, task_name="tui-runtime-login-close", primary_error=primary_error, cancellation=cancellation
        )

    async def _open_attempt_client(
        self: RuntimeLoginScreen,
        profile_id: UUID,
        method: RuntimeLoginMethod,
        proof: bytearray | None,
        reference: UUID | None,
    ) -> tuple[RuntimeFrontendClient, asyncio.CancelledError | None]:
        if method is not RuntimeLoginMethod.API_REFERENCE:
            return await open_to_completion(self._open_client, profile_id)
        opener = self._open_credential_client
        if opener is None or reference is None or proof is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

        async def open_reference(selected: UUID) -> RuntimeFrontendClient:
            try:
                return await opener(selected, reference)
            except BaseException as error:
                self._retain_reference_cleanup(error)
                raise

        return await open_to_completion(open_reference, profile_id)

    async def _login_status(
        self: RuntimeLoginScreen,
        client: RuntimeFrontendClient,
        method: RuntimeLoginMethod,
        proof: bytearray | None,
        *,
        persist_receipt: bool = False,
    ) -> RuntimeProfileStatus:
        if method is RuntimeLoginMethod.API_REFERENCE:
            return await await_cancellation_complete(
                asyncio.to_thread(client.status), task_name="tui-runtime-login-reference-status"
            )
        if method is RuntimeLoginMethod.RECEIPT:
            if proof is not None:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return await await_cancellation_complete(
                asyncio.to_thread(client.resume_receipt), task_name="tui-runtime-login-receipt"
            )
        if proof is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        exchange = (
            asyncio.to_thread(client.login_password, proof, persist_receipt=persist_receipt)
            if method is RuntimeLoginMethod.PASSWORD
            else asyncio.to_thread(client.login_api_key, proof)
        )
        return await await_cancellation_complete(exchange, task_name="tui-runtime-login-proof")

    def _accepted_handoff(
        self: RuntimeLoginScreen,
        profile_id: UUID,
        label: str,
        method: RuntimeLoginMethod,
        status: RuntimeProfileStatus,
        client: RuntimeFrontendClient,
    ) -> RuntimeLoginHandoff | None:
        access = status.status
        if (
            access.session_id is None
            or not status_admits_session(
                access,
                profile_id=profile_id,
                session_id=access.session_id,
                at=now(),
                requires_automation_grant=method in {RuntimeLoginMethod.API_KEY, RuntimeLoginMethod.API_REFERENCE},
            )
            or access.session_id != client.session_id
        ):
            return None
        handoff = RuntimeLoginHandoff(
            profile_id=profile_id, profile_label=label, method=method, status=status, client=client
        )
        # Textual may only resolve a future or queue an async callback;
        # neither proves the receiving owner accepted the live client.
        if not self._accept_handoff(handoff):
            return None
        self._transferred = True
        return handoff

    async def _perform_login_attempt(
        self: RuntimeLoginScreen,
        profile_id: UUID,
        label: str,
        method: RuntimeLoginMethod,
        proof: bytearray | None,
        reference: UUID | None,
        state: LoginAttemptState,
        *,
        persist_receipt: bool = False,
    ) -> None:
        state.client, interrupted_open = await self._open_attempt_client(profile_id, method, proof, reference)
        if interrupted_open is not None:
            raise interrupted_open
        if not self._active():
            return
        client = state.client
        if client.profile_id != profile_id or client.frontend is not OperationFrontendProjection.TUI:
            self._status_refused()
            return
        status = await self._login_status(client, method, proof, persist_receipt=persist_receipt)
        # Erase the proof before any receiving owner or dismissal callback runs.
        if proof is not None:
            proof[:] = bytes(len(proof))
            if self._pending_proof is proof:
                self._pending_proof = None
        if not self._active():
            return
        handoff = self._accepted_handoff(profile_id, label, method, status, client)
        if handoff is None:
            self._status_refused()
            return
        state.transferred = True
        await await_cancellation_complete(self.dismiss(handoff), task_name="tui-runtime-login-dismiss")

    def _handle_login_failure(self: RuntimeLoginScreen, error: BaseException, *, transferred: bool) -> bool:
        if isinstance(error, (RuntimeFrontendRefusedError, RuntimeRefusalError, ProfileReceiptRefusedError)):
            code = error.reason if isinstance(error, RuntimeFrontendRefusedError) else error.reason.value
            sign_in = error.sign_in if isinstance(error, RuntimeFrontendRefusedError) else None
            if sign_in is not None:
                code = sign_in.binding or sign_in.reason
            if isinstance(error, ProfileReceiptRefusedError) and error.binding is not None:
                code = error.binding
            self._status_refused(code, remaining_seconds=None if sign_in is None else sign_in.remaining_seconds)
            return False
        if isinstance(error, asyncio.CancelledError):
            return True
        if not transferred:
            self._status_refused()
        return False

    async def _attempt(
        self: RuntimeLoginScreen,
        profile_id: UUID,
        label: str,
        method: RuntimeLoginMethod,
        proof: bytearray | None,
        reference: UUID | None,
        *,
        persist_receipt: bool = False,
    ) -> None:
        """Retain every opened client until closed or explicitly handed off."""
        state = LoginAttemptState()
        try:
            try:
                await self._perform_login_attempt(
                    profile_id, label, method, proof, reference, state, persist_receipt=persist_receipt
                )
            except (
                RuntimeFrontendRefusedError,
                RuntimeRefusalError,
                ProfileReceiptRefusedError,
                asyncio.CancelledError,
                Exception,
            ) as error:
                state.primary_error = error
                if self._handle_login_failure(error, transferred=state.transferred):
                    raise
            finally:
                if proof is not None:
                    proof[:] = bytes(len(proof))
                    if self._pending_proof is proof:
                        self._pending_proof = None
                if state.client is not None and not state.transferred:
                    await self._close_untransferred(
                        state.client,
                        primary_error=state.primary_error if state.primary_error is not None else sys.exception(),
                    )
        finally:
            self._busy = False
            if self._active():
                self._controls()
