"""Owner-only executor contracts for registered application operations.

Application definition owners import these canonical protocols here.  Inbound
frontends consume only :mod:`cadrumo.application.operations`, whose facade
does not expose executor runtime authority.
"""

from ._executor import (
    OperationEventEmitter,
    OperationExecutor,
    OperationExecutorContext,
    OperationInteractionAccess,
    OperationResumableExecutor,
    OperationResumeCheckpoint,
)

__all__ = [
    "OperationEventEmitter",
    "OperationExecutor",
    "OperationExecutorContext",
    "OperationInteractionAccess",
    "OperationResumableExecutor",
    "OperationResumeCheckpoint",
]
