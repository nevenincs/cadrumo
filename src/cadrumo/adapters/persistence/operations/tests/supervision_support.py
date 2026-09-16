"""Drive one supervised operation from admission to its settled state, as a blocking caller does."""

from __future__ import annotations

from .....application.operations.errors import OperationUnsettledError
from .....application.operations.models import OperationId
from .....application.operations.persistence.journal import OperationPersistedSnapshot
from .....application.operations.supervisor import OperationSupervisor


async def run_to_settlement(supervisor: OperationSupervisor, operation_id: OperationId) -> OperationPersistedSnapshot:
    """Start ``operation_id`` and return what its supervised task concluded.

    When the task stopped without settling, the error that stopped it is raised,
    so a test asserts the stopping fault directly and the journal state
    separately; :class:`OperationUnsettledError` itself is covered by its own tests.
    """
    await supervisor.start(operation_id)
    try:
        return await supervisor.settled(operation_id)
    except OperationUnsettledError as unsettled:
        if unsettled.__cause__ is None:
            raise
        raise unsettled.__cause__ from unsettled


__all__ = ["run_to_settlement"]
