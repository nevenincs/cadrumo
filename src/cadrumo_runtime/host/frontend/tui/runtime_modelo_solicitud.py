"""The Modelo 360 solicitud register through the installed TUI's retained runtime session."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from cadrumo.application.modelo.m360_solicitud_input import Modelo360ProfileInput
from cadrumo.application.modelo.m360_solicitud_operation import (
    MODELO_360_SOLICITUD_OPERATION_DEFINITION_ID,
    Modelo360SolicitudRequest,
    Modelo360SolicitudResult,
)
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.i18n.render import tr
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.entrypoints.tui.ledger.tools import LedgerToolV1
from cadrumo.entrypoints.tui.modelo.m360_solicitud import Modelo360SolicitudDoorV1, solicitud_360_tool
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from .operations.runtime_profile_session import RuntimeProfileSession


def _result_matches(
    result: Modelo360SolicitudResult,
    request: Modelo360SolicitudRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """Whether the masked result answers exactly the request under its settled receipt."""
    expected_effect = OperationEffect.UPDATED if result.changed else OperationEffect.NONE
    return (
        result.profile_id == request.profile_id
        and result.action == request.action
        and result.filing_year == request.filing_year
        and condition is OperationTerminalCondition.SUCCEEDED
        and terminal.refusal_ref is None
        and terminal.effect is expected_effect
        and not (request.action == "list" and result.changed)
    )


def read_solicitud_facts(path: str) -> Modelo360ProfileInput:
    """Validate one operator-named JSON facts file; its content is never echoed."""
    try:
        return Modelo360ProfileInput.model_validate_json(Path(path).expanduser().read_text(encoding=UTF_8_ENCODING))
    except OSError:
        raise ValueError(tr("tui.modelo.m360_solicitud.source_unreadable", path=path)) from None
    except ValidationError as error:
        raise ValueError(tr("tui.modelo.m360_solicitud.source_invalid", path=path, count=error.error_count())) from None


class RuntimeModelo360SolicitudTuiDoorV1:
    """Submit solicitud requests for the exact TUI profile and session this door was built for."""

    def __init__(self, client: FrontendClient, *, profile_label: str) -> None:
        """Pin the admitted profile and session for every request."""
        self._session = RuntimeProfileSession(client, profile_label=profile_label)

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    async def __call__(self, request: Modelo360SolicitudRequest) -> Modelo360SolicitudResult:
        """Run one request and refuse a result its terminal receipt does not support."""

        def settle(
            result: Modelo360SolicitudResult,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not _result_matches(result, request, condition, terminal):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=MODELO_360_SOLICITUD_OPERATION_DEFINITION_ID,
            result_type=Modelo360SolicitudResult,
            settle=settle,
            explain_failure=True,
        )

    async def read_facts(self, path: str) -> Modelo360ProfileInput:
        """Read the facts file off the event loop and validate it as the command line does."""
        return await asyncio.to_thread(read_solicitud_facts, path)


def compose_modelo_solicitud_tools(client: FrontendClient, profile_label: str) -> tuple[LedgerToolV1, ...]:
    """Offer the Modelo 360 solicitudes, bound to the workbench's session."""
    door: Modelo360SolicitudDoorV1 = RuntimeModelo360SolicitudTuiDoorV1(client, profile_label=profile_label)
    return (solicitud_360_tool(door),)


__all__ = ["RuntimeModelo360SolicitudTuiDoorV1", "compose_modelo_solicitud_tools", "read_solicitud_facts"]
