"""Installed TUI admission and exact-client runtime lifetime.

Only profile discovery and first-profile registration use the local bootstrap
adapters. Every existing-profile session proves its credential to the verified
runtime. The frontend never inherits registration or ambient local custody.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from logging import WARNING
from typing import TYPE_CHECKING
from uuid import UUID

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ...adapters.local_runtime.runtime_client import open_installed_runtime_client
from ...adapters.local_runtime.runtime_credentials import open_installed_credential_client
from ...adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from ...adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ...application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from ...application.operator_output.runtime_remedies import runtime_unavailable_remedy
from ...application.runtime.contracts import RuntimeRefusalError
from ...application.user_profile.login_interaction import (
    ProfileLoginInventoryState,
    ProfileLoginInventoryV1,
    observe_profile_login_inventory,
)
from ...application.user_profile.profile_record_repository import close_active_profile_record_session
from ...core.async_cleanup import AsyncResourceCleanupError
from ...core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language
from ...core.logging import get_logger
from ..adapter_composition import profile_adapter_composition
from .account import AccountRecomposeReasonV1, AccountRecomposeRequiredV1
from .launcher import run_precomposed_runtime_root_session
from .runtime_admission import runtime_login_session
from .runtime_workbench import RuntimeWorkbenchRoot
from .secret.automation_requester import RuntimeAutomationRequesterScreen
from .secret.runtime_login_contracts import RuntimeLoginMethod

if TYPE_CHECKING:
    from textual.app import AutopilotCallbackType

SESSION_COMPLETED = 0
"""The operator ended or abandoned the session."""

SESSION_INVENTORY_UNAVAILABLE = 1
"""Profile discovery or runtime admission could not be served truthfully."""

_LOGGER = get_logger(__name__)


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
        diagnostic_event(_LOGGER, "tui_registration_opened", fields={"stage": "bootstrap_registration"})
        outcome = run_credential_screen(
            RegistrationScreen(
                assess=assess_profile_password,
                register=build_profile_registration_attempt,
                enroll_recovery=build_profile_recovery_enrollment_attempt,
            )
        )
        diagnostic_event(
            _LOGGER,
            "tui_registration_closed",
            fields={
                "outcome": "profile_created" if outcome is not None else "abandoned",
                "profile_persisted": outcome is not None,
            },
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
    operation_contracts: Callable[[], OperationPublicContractSetV1],
    choose_profile: bool,
    headless: bool,
    auto_pilot: AutopilotCallbackType | None,
) -> AccountRecomposeRequiredV1 | None:
    """Own login, one immutable root and its cleanup before any fresh choice."""

    def requester_for_login(profile_id: UUID) -> RuntimeAutomationRequesterScreen:
        return RuntimeAutomationRequesterScreen(
            profile_id=profile_id,
            contracts=operation_contracts(),
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
                    contracts=operation_contracts(),
                    secrets_store=store,
                    client=client,
                    fresh_credential_client=fresh_credential_client,
                )

            app = RuntimeRestrictedSessionApp(
                handoff.client,
                profile_label=handoff.profile_label,
                requester_factory=requester_for_api,
            )
            return await app.run_async(headless=headless, auto_pilot=auto_pilot)

        async def open_recovery_client() -> RuntimeFrontendClient:
            return await _open_client(handoff.profile_id)

        def requester_for_human(client: RuntimeFrontendClient) -> RuntimeAutomationRequesterScreen:
            if client is not handoff.client:
                raise ValueError("requester requires the original human client")
            return RuntimeAutomationRequesterScreen(
                profile_id=handoff.profile_id,
                contracts=operation_contracts(),
                secrets_store=installed_automation_secret_store(),
                open_client=_open_client,
                reviewer_client=client,
            )

        root = RuntimeWorkbenchRoot(
            handoff.client,
            profile_label=handoff.profile_label,
            output_language=OutputLanguage(output_language()),
            open_recovery_client=open_recovery_client,
            requester_factory=requester_for_human,
        )
        return await run_precomposed_runtime_root_session(load_root=root.load, headless=headless, auto_pilot=auto_pilot)


def _unavailable_inventory(inventory: ProfileLoginInventoryV1) -> int | None:
    if inventory.state not in {ProfileLoginInventoryState.CONCURRENT_CHANGE, ProfileLoginInventoryState.DEGRADED}:
        return None
    diagnostic_event(
        _LOGGER,
        "tui_inventory_refused",
        fields={"outcome": "refused", "reason_code": inventory.reason_code},
        level=WARNING,
    )
    sys.stderr.write(f"{inventory.reason_code}\n")
    return SESSION_INVENTORY_UNAVAILABLE


def _registration_completed(headless: bool) -> bool:
    return False if headless else _run_registration_screen()


def _runtime_session_refusal(error: RuntimeFrontendRefusedError | RuntimeRefusalError) -> int:
    if any(
        isinstance(error.__dict__.get(name), AsyncResourceCleanupError)
        for name in ("async_cleanup_error", "cleanup_error")
    ):
        # A numeric refusal cannot retain an unsettled native owner.
        raise error
    reason = error.reason if isinstance(error, RuntimeFrontendRefusedError) else error.reason.value
    diagnostic_event(
        _LOGGER,
        "tui_runtime_session_refused",
        fields={**diagnostic_error_fields(error), "outcome": "refused", "reason_code": reason},
        level=WARNING,
        primary_error=error,
    )
    sys.stderr.write(f"{reason}\n")
    if remedy := runtime_unavailable_remedy(reason):
        sys.stderr.write(f"{remedy}\n")
    return SESSION_INVENTORY_UNAVAILABLE


def _attempt_runtime_session(
    inventory: ProfileLoginInventoryV1,
    operation_contracts: Callable[[], OperationPublicContractSetV1],
    choose_profile: bool,
    headless: bool,
    auto_pilot: AutopilotCallbackType | None,
) -> AccountRecomposeRequiredV1 | int | None:
    try:
        return asyncio.run(
            _run_runtime_session(
                inventory,
                operation_contracts=operation_contracts,
                choose_profile=choose_profile,
                headless=headless,
                auto_pilot=auto_pilot,
            )
        )
    except (RuntimeFrontendRefusedError, RuntimeRefusalError) as error:
        return _runtime_session_refusal(error)


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
    contracts: OperationPublicContractSetV1 | None = None

    def operation_contracts() -> OperationPublicContractSetV1:
        nonlocal contracts
        if contracts is None:
            from ..operation_composition import build_production_operation_registry

            contracts = build_production_operation_registry().public_contract_set
        return contracts

    choose_profile = False
    with profile_adapter_composition():
        _release_bootstrap_custody()
        while True:
            inventory = observe_profile_login_inventory()
            diagnostic_event(
                _LOGGER,
                "tui_inventory_observed",
                fields={"inventory_state": inventory.state.value, "profile_count": len(inventory.choices)},
            )
            unavailable = _unavailable_inventory(inventory)
            if unavailable is not None:
                return unavailable
            if inventory.state is ProfileLoginInventoryState.EMPTY:
                if not _registration_completed(headless):
                    return SESSION_COMPLETED
                diagnostic_event(
                    _LOGGER,
                    "tui_registration_runtime_admission_pending",
                    fields={"profile_persisted": True, "stage": "runtime_admission"},
                )
                continue
            if headless and auto_pilot is None:
                return SESSION_COMPLETED
            recompose = _attempt_runtime_session(
                inventory,
                operation_contracts,
                choose_profile,
                headless,
                auto_pilot,
            )
            if isinstance(recompose, int):
                return recompose
            if recompose is None:
                return SESSION_COMPLETED
            choose_profile = recompose.reason is AccountRecomposeReasonV1.CHANGE_USER
            diagnostic_event(_LOGGER, "tui_session_recompose_requested", fields={"reason_code": recompose.reason.value})


__all__ = ["SESSION_COMPLETED", "SESSION_INVENTORY_UNAVAILABLE", "run_installed_workbench_session"]
