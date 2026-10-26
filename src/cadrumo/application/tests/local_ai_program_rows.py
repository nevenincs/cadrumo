"""The local AI program's status row, as the components role reports it, for application tests.

Application tests read the row through the contract every surface decodes it
into; the decoder and the role's recorded output have their own tests.
"""

from __future__ import annotations

from typing import Final

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..dependency_contracts import (
    DependencyCheckMode,
    DependencyItemKind,
    DependencyRecoveryAction,
    DependencyStaleReason,
    DependencyState,
    DependencyStatusRow,
)
from ..provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID

__all__ = ["LOCAL_AI_VERSION", "local_ai_row"]

LOCAL_AI_VERSION: Final = "0.40.10"


def local_ai_row(state: DependencyState) -> DependencyStatusRow:
    """The local AI's quick-status row in ``state``, with the one button the role offers an item not usable."""
    usable = state in {DependencyState.READY, DependencyState.STALE}
    return DependencyStatusRow(
        item_id="local_ai",
        kind=DependencyItemKind.LOCAL_AI,
        mode=DependencyCheckMode.QUICK,
        state=state,
        stale_reason=DependencyStaleReason.PROGRAM_TOO_OLD if state is DependencyState.STALE else None,
        failure_category=DependencyFailureCategory.PROGRAM_MISSING if state is DependencyState.FAILED else None,
        version=LOCAL_AI_VERSION,
        recovery=None if usable else DependencyRecoveryAction.SET_UP_IN_DESKTOP,
        recovery_action_id=None if usable else LOCAL_AI_PROVISION_ACTION_ID,
    )
