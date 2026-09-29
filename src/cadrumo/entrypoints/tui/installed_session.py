"""Installed TUI admission and exact-client runtime lifetime.

Only profile discovery and first-profile registration use the local bootstrap
adapters. Every existing-profile session proves its credential to the verified
runtime. The frontend never inherits registration or ambient local custody.
"""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING
from uuid import UUID

from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ...adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ...application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from ...application.runtime.contracts import RuntimeRefusalError
from ...application.user_profile.login_interaction import (
    ProfileLoginInventoryState,
    ProfileLoginInventoryV1,
    observe_profile_login_inventory,
)
from ...application.user_profile.profile_record_repository import close_active_profile_record_session
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language
from ..adapter_composition import profile_adapter_composition
from ..operation_composition import build_production_operation_registry
from .account import AccountRecomposeReasonV1, AccountRecomposeRequiredV1
from .launcher import run_precomposed_runtime_root_session
from .runtime_admission import runtime_login_session
from .runtime_workbench import RuntimeWorkbenchRoot
from .secret.automation_requester import RuntimeAutomationRequesterScreen
from .secret.runtime_login import RuntimeLoginMethod

if TYPE_CHECKING:
    from textual.app import AutopilotCallbackType

SESSION_COMPLETED = 0
"""The operator ended or abandoned the session."""

SESSION_INVENTORY_UNAVAILABLE = 1
"""Profile discovery or runtime admission could not be served truthfully."""


def _release_bootstrap_custody() -> None:
    """Drop local key/record ownership without altering another runtime lease."""
    try:
        close_active_profile_record_session()
    finally:
        close_active_bucket_session()


def _run_registration_screen() -> bool:
    """Create the first profile, finish recovery, then release bootstrap custody."""
    from ...core.credentials import assess_profile_password
    from .secret.credentials import run_credential_screen
    from .secret.registration import (
        RegistrationScreen,
        build_profile_recovery_enrollment_attempt,
        build_profile_registration_attempt,
    )

    try:
        outcome = run_credential_screen(
            RegistrationScreen(
                assess=assess_profile_password,
                register=build_profile_registration_attempt,
                enroll_recovery=build_profile_recovery_enrollment_attempt,
            )
        )
        return outcome is not None
    finally:
        _release_bootstrap_custody()


async def _open_client(profile_id: UUID) -> RuntimeFrontendClient:
    return await open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.TUI)


async def _open_credential_client(profile_id: UUID, credential_reference: UUID) -> RuntimeFrontendClient:
    return await open_installed_credential_client(
        profile_id=profile_id,
        credential_reference=credential_reference,
        frontend=OperationFrontendProjection.TUI,
    )


async def _run_runtime_session(
    inventory: ProfileLoginInventoryV1,
    *,
    operation_contracts: OperationPublicContractSetV1,
    choose_profile: bool,
    headless: bool,
    auto_pilot: AutopilotCallbackType | None,
) -> AccountRecomposeRequiredV1 | None:
    """Own login, one immutable root and its cleanup before any fresh choice."""

    def requester_for_login(profile_id: UUID) -> RuntimeAutomationRequesterScreen:
        return RuntimeAutomationRequesterScreen(
            profile_id=profile_id,
            contracts=operation_contracts,
            secrets_store=installed_automation_secret_store(),
            open_client=_open_client,
        )

    async with runtime_login_session(
        choices=inventory.choices,
        open_client=_open_client,
        open_credential_client=_open_credential_client,
        requester_factory=requester_for_login,
        preselected=None if choose_profile else inventory.preselected_profile_id,
        headless=headless,
        auto_pilot=auto_pilot,
    ) as handoff:
        if handoff is None:
            return None
        if handoff.method in {RuntimeLoginMethod.API_KEY, RuntimeLoginMethod.API_REFERENCE}:
            from .runtime_session import RuntimeRestrictedSessionApp

            def requester_for_api(client: RuntimeFrontendClient) -> RuntimeAutomationRequesterScreen:
                store = installed_automation_secret_store()

                def fresh_credential_client(
                    profile_id: UUID, credential_reference: UUID, timeout: float
                ) -> RuntimeFrontendClient:
                    return asyncio.run(
                        open_installed_credential_client(
                            profile_id=profile_id,
                            credential_reference=credential_reference,
                            frontend=OperationFrontendProjection.TUI,
                            timeout=timeout,
                            secrets_store=store,
                        )
                    )

                return RuntimeAutomationRequesterScreen(
                    profile_id=client.profile_id,
                    contracts=operation_contracts,
                    secrets_store=store,
                    client=client,
                    fresh_credential_client=fresh_credential_client,
                )

            return await RuntimeRestrictedSessionApp(
                handoff.client,
                profile_label=handoff.profile_label,
                requester_factory=requester_for_api,
            ).run_async(headless=headless, auto_pilot=auto_pilot)

        async def open_recovery_client() -> RuntimeFrontendClient:
            return await _open_client(handoff.profile_id)

        root = RuntimeWorkbenchRoot(
            handoff.client,
            profile_label=handoff.profile_label,
            output_language=OutputLanguage(output_language()),
            open_recovery_client=open_recovery_client,
        )
        return await run_precomposed_runtime_root_session(load_root=root.load, headless=headless, auto_pilot=auto_pilot)


def run_installed_workbench_session(
    *,
    headless: bool = False,
    auto_pilot: AutopilotCallbackType | None = None,
) -> int:
    """Alternate owned runtime sessions and fresh, non-authenticating inventory.

    A bare headless self-test never waits for a credential. An explicit
    autopilot may drive the same real login and root screens used interactively.
    Profile switching discards the former connection before rereading choices.
    """
    choose_profile = False
    with profile_adapter_composition():
        _release_bootstrap_custody()
        operation_contracts = build_production_operation_registry().public_contract_set
        while True:
            inventory = observe_profile_login_inventory()
            if inventory.state in {ProfileLoginInventoryState.CONCURRENT_CHANGE, ProfileLoginInventoryState.DEGRADED}:
                sys.stderr.write(f"{inventory.reason_code}\n")
                return SESSION_INVENTORY_UNAVAILABLE
            if inventory.state is ProfileLoginInventoryState.EMPTY:
                if headless or not _run_registration_screen():
                    return SESSION_COMPLETED
                continue
            if headless and auto_pilot is None:
                return SESSION_COMPLETED
            try:
                recompose = asyncio.run(
                    _run_runtime_session(
                        inventory,
                        operation_contracts=operation_contracts,
                        choose_profile=choose_profile,
                        headless=headless,
                        auto_pilot=auto_pilot,
                    )
                )
            except (RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
                reason = error.reason if isinstance(error, RuntimeFrontendRefusedError) else error.reason.value
                sys.stderr.write(f"{reason}\n")
                return SESSION_INVENTORY_UNAVAILABLE
            if recompose is None:
                return SESSION_COMPLETED
            choose_profile = recompose.reason is AccountRecomposeReasonV1.CHANGE_USER


__all__ = ["SESSION_COMPLETED", "SESSION_INVENTORY_UNAVAILABLE", "run_installed_workbench_session"]
