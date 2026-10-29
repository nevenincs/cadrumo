"""Read only the exact admitted operation result and suppress protected failure details."""

from typing import Protocol, cast

from ....application.live.notifications_read_operation import NotificationsListPublicResultV1
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ..operations.controller_port import OperationControllerPort
from .models import AeatSyncOperationRequestV1
from .workspace_rendering import notifications_list_summary


class NotificationsListResultReader(Protocol):
    """Typed public result door offered by the installed runtime handoff."""

    async def read_notifications_list_result(
        self, projection: OperationPublicProjectionV1, /
    ) -> NotificationsListPublicResultV1:
        """Read the exact settled notifications-list result."""
        ...


async def read_notifications_summary(
    request: AeatSyncOperationRequestV1 | None,
    operation_controller: OperationControllerPort | None,
    operation_projection: OperationPublicProjectionV1,
) -> tuple[str | None, bool]:
    """Read the safe list summary before the caller rebuilds the workspace snapshot."""
    notification_list = request is not None and (
        request.action.action_id == "operator.live.notifications.list"
        and request.operation == "live.notifications.list"
    )
    notification_summary: str | None = None
    result_failed = False
    if notification_list:
        if operation_controller is None:
            result_failed = True
        else:
            try:
                result = await cast(NotificationsListResultReader, operation_controller).read_notifications_list_result(
                    operation_projection
                )
                notification_summary = notifications_list_summary(result)
            except Exception:  # do not disclose protected operation result details
                result_failed = True

    return notification_summary, result_failed
