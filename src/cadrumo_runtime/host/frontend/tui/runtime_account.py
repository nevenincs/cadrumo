"""Account controls tied to one runtime lease and its owning frontend."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.credentials import assess_profile_password
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.entrypoints.tui.account import (
    AccountDirectSessionActionV1,
    AccountFactoriesV1,
    AccountProfileFactoryV1,
    AccountRecomposeReasonV1,
    AccountRecomposeRequiredV1,
)
from cadrumo.entrypoints.tui.components.theme import toggle_appearance
from cadrumo.entrypoints.tui.profile.overview import ProfileManagerScreen
from cadrumo.entrypoints.tui.secret.passphrase import PassphraseChangeAttempt, PassphraseChangeRefusal, PassphraseScreen
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.profile_mutations import ProfileMutationRunError
from cadrumo_client.transport.profile_password_rotation import run_profile_password_rotation

from .runtime_access_management import RecoveryClientOpener, RuntimeAccessManagementScreen

if TYPE_CHECKING:
    from cadrumo_client.transport.frontend_client import FrontendClient

    from .secret.automation_requester import HumanAutomationRequesterFactory


def compose_runtime_account_factories(
    client: FrontendClient,
    *,
    profile: AccountProfileFactoryV1,
    open_recovery_client: RecoveryClientOpener,
    requester_factory: HumanAutomationRequesterFactory | None = None,
    onboarding_pending: bool = False,
) -> AccountFactoriesV1:
    """Compose controls without acquiring a profile or constructing local custody.

    Direct closure is the runtime's current-session lock. The outer login
    scope owns closing the connection and any later profile selection. Independent
    grants are not changed by this session control.
    """
    if client.frontend is not OperationFrontendProjection.TUI:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    profile_id, session_id = client.profile_id, client.session_id

    def require_binding() -> None:
        if (
            client.profile_id != profile_id
            or client.session_id != session_id
            or client.frontend is not OperationFrontendProjection.TUI
        ):
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    def close_for(reason: AccountRecomposeReasonV1) -> AccountDirectSessionActionV1:
        async def complete() -> AccountRecomposeRequiredV1:
            require_binding()
            acknowledgement = await await_cancellation_complete(
                asyncio.to_thread(
                    client.human_sign_out if reason is AccountRecomposeReasonV1.SIGNED_OUT else client.lock
                ),
                task_name="tui-runtime-account-close",
            )
            if session_id not in acknowledgement.session_ids:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            return AccountRecomposeRequiredV1(reason=reason)

        return AccountDirectSessionActionV1(complete=complete)

    def access() -> RuntimeAccessManagementScreen:
        require_binding()
        return RuntimeAccessManagementScreen(
            client, open_recovery_client=open_recovery_client, requester_factory=requester_factory
        )

    def password() -> PassphraseScreen:
        require_binding()

        async def open_fresh() -> FrontendClient:
            return await open_recovery_client()

        def rotate(current: str, replacement: str, confirmation: str) -> PassphraseChangeAttempt:
            require_binding()
            try:
                completed = run_profile_password_rotation(
                    client,
                    current_passphrase=bytearray(current, "utf-8"),
                    new_passphrase=bytearray(replacement, "utf-8"),
                    new_passphrase_confirmation=bytearray(confirmation, "utf-8"),
                    fresh_client=lambda: asyncio.run(open_fresh()),
                )
            except ProfileMutationRunError as error:
                if (
                    error.terminal_condition is OperationTerminalCondition.REFUSED
                    and error.effect is OperationEffect.NONE
                ):
                    return PassphraseChangeAttempt(
                        expected_refusal=PassphraseChangeRefusal(message_key="flows.passphrase.refusal.change_failed")
                    )
                raise
            return PassphraseChangeAttempt(outcome=completed.outcome)

        return PassphraseScreen(assess=assess_profile_password, rotate=rotate)

    def language(screen: ProfileManagerScreen) -> None:
        require_binding()
        screen.action_choose_language()

    return AccountFactoriesV1(
        profile=profile,
        change_user=lambda: close_for(AccountRecomposeReasonV1.CHANGE_USER),
        password=password,
        appearance=toggle_appearance,
        language=language,
        sign_out=lambda: close_for(AccountRecomposeReasonV1.SIGNED_OUT),
        access=access,
        onboarding_pending=onboarding_pending,
        subscribe_retirement=client.subscribe_session_retirement,
        subscribe_notices=client.subscribe_lifecycle_notices,
    )
