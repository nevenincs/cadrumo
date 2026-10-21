"""Submit one profile operation, watch it in the operation modal, and hand on its success."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import BaseModel
from textual.screen import Screen

from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.operation_controller import OperationController

from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....core.errors.error_codes import resolve_error_message
from ....core.errors.hierarchy import CadrumoError
from ....core.operations import OperationTerminalCondition, profile_operation_subject
from .modal import OperationModal, OperationModalSettledOutcomeV1

type SucceededOperationReader = Callable[[OperationController, OperationPublicProjectionV1], Coroutine[Any, Any, None]]


async def submit_watched_profile_operation(
    screen: Screen[Any],
    client: FrontendClient,
    *,
    definition_id: str,
    payload: BaseModel,
    notice: Callable[[str], None],
    read_succeeded: SucceededOperationReader,
    result_group: str,
) -> None:
    """Start one operation on the client's profile and read its result only once it succeeded.

    A refused submission is said on ``notice``; any other settlement leaves the
    modal's own terminal wording as the operator's answer.
    """
    try:
        controller = await OperationController.submit(
            client,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(client.profile_id)),
            payload=payload,
            expected_session_id=client.session_id,
        )
        await controller.start()
    except CadrumoError as error:
        notice(resolve_error_message(error))
        return

    def settled(outcome: object) -> None:
        if not isinstance(outcome, OperationModalSettledOutcomeV1):
            return
        projection = outcome.view_model.projection
        if projection.terminal_condition is OperationTerminalCondition.SUCCEEDED:
            screen.run_worker(read_succeeded(controller, projection), group=result_group)

    screen.app.push_screen(OperationModal(controller), settled)


__all__ = ["SucceededOperationReader", "submit_watched_profile_operation"]
