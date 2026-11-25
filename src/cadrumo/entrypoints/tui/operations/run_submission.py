"""Submit an operation against its currently published contract."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from pydantic import BaseModel

from cadrumo_client.contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.operation_controller import OperationController

from ....core.async_cleanup import await_cancellation_complete
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from .catalogue import OperationCatalogueEntryV1
from .run_wording import failure_text

_CONTRACT_READ_SECONDS = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS


async def submit_operation(
    notice: Callable[[str], None],
    client: FrontendClient,
    entry: OperationCatalogueEntryV1,
    payload: BaseModel,
    subject: str,
    secret: bytearray | None,
    replay_key: str | None,
) -> OperationController | None:
    """Read the live contract before submitting the exact admitted request."""
    try:
        live = await await_cancellation_complete(
            asyncio.to_thread(client.contract, entry.definition_id, deadline=time.monotonic() + _CONTRACT_READ_SECONDS),
            task_name="tui-operation-run-contract",
        )
        if live != entry.contract:
            # The form was built from another contract than the runtime now serves.
            notice(tr("tui.operations.run.contract_changed"))
            return None
        return await OperationController.submit(
            client,
            definition_id=entry.definition_id,
            subject_ref=subject,
            payload=payload,
            expected_session_id=client.session_id,
            financial_input=entry.typed_operator_input,
            secret=secret,
            idempotency_key=replay_key,
        )
    except CadrumoError as error:
        notice(failure_text(error))
        return None
