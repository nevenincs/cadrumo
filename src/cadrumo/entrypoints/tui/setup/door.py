"""The setup screen's door to the runtime: the status, verification and setup operations.

Every read and every setup goes through the runtime's registered
``dependencies.*`` operations on the signed-in profile's connection, the same
operations the command line and MCP submit, so all three make the same
decision. A runtime that cannot be reached is a typed refusal the screen
reports; nothing here starts, recovers or manages the runtime.
"""

from __future__ import annotations

import time
from typing import Final, Protocol

from pydantic import BaseModel

from cadrumo_client.contracts.operation_ids import DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.operation_controller import OperationController, await_terminal_projection

from ....application.dependency_contracts import DependencyCheckMode
from ....application.dependency_setup_operation import (
    DEPENDENCIES_OPERATION_SUBJECT,
    DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
    DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID,
    DependencySetupRequest,
    DependencySetupResultV1,
    DependencyStatusRequest,
    DependencyStatusResultV1,
    DependencyVerifyRequest,
)
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....application.operations.schema_identity import OperationSchemaIdentityV1
from ..operations.controller_port import OperationControllerPort

__all__ = ["RuntimeSetupDoor", "SetupDoorPort", "SetupStatusReaderPort"]

_QUICK_DEADLINE_S: Final = 60.0
_FULL_DEADLINE_S: Final = 900.0


class SetupStatusReaderPort(Protocol):
    """The setup status read alone: what a surface reads before it offers an item's setup."""

    async def read_status(self, mode: DependencyCheckMode) -> DependencyStatusResultV1:
        """Read every setup item's row in ``mode``."""
        ...


class SetupDoorPort(SetupStatusReaderPort, Protocol):
    """What the setup screen asks of the runtime."""

    async def verify(self, item_ids: tuple[str, ...] | None) -> DependencyStatusResultV1:
        """Fully check the named items, every item when ``None``."""
        ...

    async def start_setup(self, item_ids: tuple[str, ...] | None) -> OperationControllerPort:
        """Submit and start a setup; its plan review is answered in the operation modal."""
        ...

    async def setup_result(
        self, controller: OperationControllerPort, projection: OperationPublicProjectionV1
    ) -> DependencySetupResultV1:
        """Read a settled setup's result."""
        ...


def _request_schema(definition_id: str, model: type[BaseModel]) -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1.from_model(
        schema_id=definition_id + ".request", schema_version=1, model_type=model
    )


class RuntimeSetupDoor:
    """Reach the setup operations through one signed-in runtime connection."""

    def __init__(self, client: FrontendClient) -> None:
        """Bind the connection every request is sent on."""
        self._client = client

    async def _read(
        self, definition_id: str, payload: DependencyStatusRequest | DependencyVerifyRequest, deadline_s: float
    ) -> DependencyStatusResultV1:
        controller = await OperationController.submit(
            self._client,
            definition_id=definition_id,
            subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
            payload=payload,
            expected_session_id=self._client.session_id,
        )
        await controller.start()
        projection = await await_terminal_projection(
            controller,
            definition_id=definition_id,
            subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
            request_schema=_request_schema(definition_id, type(payload)),
            deadline=time.monotonic() + deadline_s,
        )
        return await controller.read_settled_result(projection, DependencyStatusResultV1, result_version=1)

    async def read_status(self, mode: DependencyCheckMode) -> DependencyStatusResultV1:
        """Read every item's row; the quick check reads local facts only."""
        deadline = _QUICK_DEADLINE_S if mode is DependencyCheckMode.QUICK else _FULL_DEADLINE_S
        return await self._read(
            DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID, DependencyStatusRequest(mode=mode), deadline
        )

    async def verify(self, item_ids: tuple[str, ...] | None) -> DependencyStatusResultV1:
        """Run the full check of the named items."""
        return await self._read(
            DEPENDENCIES_VERIFY_OPERATION_DEFINITION_ID, DependencyVerifyRequest(item_ids=item_ids), _FULL_DEADLINE_S
        )

    async def start_setup(self, item_ids: tuple[str, ...] | None) -> OperationControllerPort:
        """Submit and start one setup; the runtime raises its plan for review before anything moves."""
        controller = await OperationController.submit(
            self._client,
            definition_id=DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID,
            subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
            payload=DependencySetupRequest(item_ids=item_ids),
            expected_session_id=self._client.session_id,
        )
        await controller.start()
        return controller

    async def setup_result(
        self, controller: OperationControllerPort, projection: OperationPublicProjectionV1
    ) -> DependencySetupResultV1:
        """Read the settled setup's result through current disclosure."""
        if not isinstance(controller, OperationController):
            raise TypeError("a setup started by this door is read through its own controller")
        return await controller.read_settled_result(projection, DependencySetupResultV1, result_version=1)
