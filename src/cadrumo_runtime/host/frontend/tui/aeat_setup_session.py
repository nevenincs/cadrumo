"""Open only the requested profile's protected AEAT editor."""

from __future__ import annotations

import asyncio
import time
from uuid import UUID

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.language_resolver import adopt_profile_output_language
from cadrumo.application.user_profile.login_interaction import observe_profile_login_inventory
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import output_language, profile_output_language_precedence
from cadrumo.core.logging import get_logger
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.profile.aeat_auth_setup import AeatAuthSetupScreen
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_client.transport.profile_language import read_profile_language

from .profile.manager_client import ProfileManagerClientComposition
from .runtime_admission import runtime_login_session
from .secret.runtime_login_contracts import RuntimeLoginMethod


async def _run(profile_id: UUID) -> int:
    inventory = await asyncio.to_thread(observe_profile_login_inventory)
    choices = tuple(choice for choice in inventory.choices if choice.profile_id == str(profile_id))
    if len(choices) != 1:
        raise FrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)

    async def open_client(requested: UUID) -> FrontendClient:
        if requested != profile_id:
            raise FrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
        return await open_installed_client(profile_id=profile_id, frontend=OperationFrontendProjection.TUI)

    # Receipt/password proof remains owned by the real login UI. No agent
    # attendance, credential value, or declared profile id authenticates it.
    async with runtime_login_session(
        choices=choices, open_client=open_client, preselected=str(profile_id), auto_resume=True
    ) as handoff:
        if handoff is None:
            return 0
        if handoff.profile_id != profile_id or handoff.method not in {
            RuntimeLoginMethod.PASSWORD,
            RuntimeLoginMethod.RECEIPT,
        }:
            raise FrontendRefusedError(AccessDenialCode.PERSON_ACT_REQUIRED.value)
        preference = await asyncio.to_thread(read_profile_language, handoff.client)
        adopt_profile_output_language(preference.language)
        door = ProfileManagerClientComposition(
            handoff.client,
            profile_label=handoff.profile_label,
            output_language=OutputLanguage(output_language()),
        ).auth_setup()
        await ScreenHostApp(AeatAuthSetupScreen(door)).run_async()
        return 0


def run_aeat_setup_session(profile_id: UUID) -> int:
    """Retain exact human admission and cleanup for the standalone editor."""
    started = time.monotonic()
    with profile_adapter_composition(), profile_output_language_precedence():
        try:
            return asyncio.run(_run(profile_id))
        finally:
            diagnostic_event(
                get_logger(__name__),
                "aeat_setup_session_closed",
                fields={"elapsed_seconds": round(time.monotonic() - started, 3)},
            )
