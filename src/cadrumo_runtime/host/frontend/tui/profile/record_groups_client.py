"""The record-group read of the profile manager over one exact authenticated client session.

Each page is the registered ``user-profile.record-groups`` read, submitted in
the pinned profile session and released only when its result names the profile,
kind and cursor asked, under a receipt that changed nothing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.user_profile.record_group_contracts import (
    PROFILE_RECORD_GROUPS_OPERATION_DEFINITION_ID,
    ProfileRecordGroupKind,
    ProfileRecordGroupsProjection,
    ProfileRecordGroupsRequest,
    ProfileRecordGroupsResult,
)
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.entrypoints.tui.profile.record_groups import RecordGroupsPin
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from ..operations.runtime_profile_session import RuntimeProfileSession


def record_groups_settled(
    request: ProfileRecordGroupsRequest,
    result: ProfileRecordGroupsResult,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """Whether a page answers exactly the profile, kind and cursor asked, under a receipt that changed nothing."""
    return (
        result.profile_id == request.profile_id
        and result.group_kind is request.group_kind
        and result.cursor == request.cursor
        and condition is OperationTerminalCondition.SUCCEEDED
        and terminal.refusal_ref is None
        and terminal.effect is OperationEffect.NONE
    )


class RecordGroupsClient:
    """The record-group port of one pinned profile manager composition."""

    def __init__(self, client: FrontendClient, *, profile_label: str, language: Callable[[], OutputLanguage]) -> None:
        """Bind the client and the current output language; the session is pinned at the first read."""
        self._client = client
        self._profile_label = profile_label
        self._language = language
        self._session: RuntimeProfileSession | None = None

    async def read(
        self, group_kind: ProfileRecordGroupKind, *, cursor: int, pin: RecordGroupsPin | None
    ) -> ProfileRecordGroupsResult:
        """Read one page of ``group_kind``'s groups, continuing at ``pin`` when one is given."""
        session = self._session
        if session is None:
            # Pinning reads the session over IPC, which must not hold the event loop.
            session = await asyncio.to_thread(RuntimeProfileSession, self._client, profile_label=self._profile_label)
            self._session = session
        request = ProfileRecordGroupsRequest(
            profile_id=session.profile_id,
            group_kind=group_kind,
            cursor=cursor,
            expected_revision=None if pin is None else pin.record_revision,
            expected_content_digest=None if pin is None else pin.content_digest,
            expected_ledger_digest=None if pin is None else pin.ledger_digest,
            output_language=self._language(),
        )

        def settle(
            result: ProfileRecordGroupsProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not record_groups_settled(request, result, condition, terminal):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await session.run_operation(
            request,
            definition_id=PROFILE_RECORD_GROUPS_OPERATION_DEFINITION_ID,
            result_type=ProfileRecordGroupsProjection,
            settle=settle,
            explain_failure=True,
        )


__all__ = ["RecordGroupsClient", "record_groups_settled"]
