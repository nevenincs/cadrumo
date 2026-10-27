"""Compose setup from the admitted profile's registered operations."""

from __future__ import annotations

import time
from dataclasses import dataclass
from uuid import UUID

from textual.screen import Screen

from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.operation_controller import OperationController, await_terminal_projection

from ....application.components_operations import (
    COMPONENTS_OPERATION_SUBJECT,
    COMPONENTS_SETUP_OPERATION_ID,
    COMPONENTS_STATUS_OPERATION_ID,
    COMPONENTS_VERIFY_OPERATION_ID,
    ProvisionMutationRequest,
    ProvisionReadRequest,
    ProvisionResult,
)
from ....application.dependency_contracts import DependencyItemKind
from ....application.operations.models import OperationId
from ..navigation import TuiScreenContextV1
from .focus import setup_item_focus
from .screen import SetupScreen


@dataclass(frozen=True, slots=True)
class SetupOperations:
    """Keep all component requests on the captured signed-in session."""

    client: FrontendClient
    session_id: UUID

    async def read_status(self) -> ProvisionResult:
        """Run the quick local status operation and read its typed result."""
        controller = await OperationController.submit(
            self.client,
            definition_id=COMPONENTS_STATUS_OPERATION_ID,
            subject_ref=COMPONENTS_OPERATION_SUBJECT,
            payload=ProvisionReadRequest(),
            expected_session_id=self.session_id,
        )
        contract = controller.definition_contract
        if contract is None:
            raise ValueError("submitted status has no registered contract")
        await controller.start()
        projection = await await_terminal_projection(
            controller,
            definition_id=COMPONENTS_STATUS_OPERATION_ID,
            subject_ref=COMPONENTS_OPERATION_SUBJECT,
            request_schema=contract.request_schema,
            deadline=time.monotonic() + 30,
        )
        return await controller.read_registered_result(projection, ProvisionResult)

    async def review(self, operation_id: OperationId) -> OperationController:
        """Observe an existing reference; runtime claim is still required before answering."""
        return OperationController(self.client, operation_id, self.session_id)

    async def submit(self, *, verify: bool, items: tuple[DependencyItemKind, ...]) -> OperationController:
        """Submit full checking or browser-only setup; the modal owns its controls."""
        return await OperationController.submit(
            self.client,
            definition_id=COMPONENTS_VERIFY_OPERATION_ID if verify else COMPONENTS_SETUP_OPERATION_ID,
            subject_ref=COMPONENTS_OPERATION_SUBJECT,
            payload=ProvisionReadRequest(items=items) if verify else ProvisionMutationRequest(),
            expected_session_id=self.session_id,
        )

    def __call__(self, context: TuiScreenContextV1, /) -> Screen[None]:
        """Open setup only through the admitted destination."""
        if context.destination != "workbench.setup":
            raise ValueError("setup requires its exact destination")
        return SetupScreen(self, focus_item=setup_item_focus(context))
