"""The setup screen's door to the native component engine: status, full check and setup.

Every read and every setup runs one command of the Cadrumo binary's
``components`` role through the shared client, the engine the command line, MCP
and the desktop use, so every surface reads the same rows and approves the same
plan. The door decides nothing: rows, plan and outcome are the role's. Each
command runs on a thread of its own so the screen stays live. A caller that
leaves while a command runs stops it, and the call returns only once the role
has ended. Where this build has no Cadrumo binary the client answers that every
item is not in this build.
"""

from __future__ import annotations

import asyncio
from typing import Final, Protocol

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from ....adapters.outbound.components.client import (
    ComponentsCancellation,
    ComponentsEventSink,
    ComponentsRequest,
    ComponentsReviewer,
    run_components_role,
)
from ....adapters.outbound.components.protocol import (
    ComponentsAnswer,
    ComponentsCommand,
    ComponentsOutcome,
    ComponentsResultLine,
    ComponentsReviewLine,
)
from ....application.dependency_contracts import DependencyItemKind
from ....core.async_cleanup import await_cancellation_complete

__all__ = ["ComponentsSetupDoor", "SetupDoorPort", "SetupStatusReaderPort"]

_QUICK_TIMEOUT_S: Final = 30.0
"""A quick check answers within its 2 s bound; this only stops a role that hangs."""


class SetupStatusReaderPort(Protocol):
    """The quick setup status alone: what a surface reads before it offers an item's setup."""

    async def read_status(self) -> ComponentsResultLine:
        """Read every setup item's row from the quick check."""
        ...


class SetupDoorPort(SetupStatusReaderPort, Protocol):
    """What the setup screen asks of the component engine."""

    async def verify(
        self, items: tuple[DependencyItemKind, ...], *, on_event: ComponentsEventSink
    ) -> ComponentsResultLine:
        """Fully check the named items, every item when none is named."""
        ...

    async def set_up(
        self,
        items: tuple[DependencyItemKind, ...],
        *,
        approved: str | None,
        review: ComponentsReviewer,
        on_event: ComponentsEventSink,
        cancellation: ComponentsCancellation,
    ) -> ComponentsResultLine:
        """Set the named items up, every item that offers it when none is named, under an approval of their plan."""
        ...


async def _run(
    request: ComponentsRequest,
    *,
    on_event: ComponentsEventSink | None = None,
    review: ComponentsReviewer | None = None,
    cancellation: ComponentsCancellation | None = None,
    timeout: float | None = None,
) -> ComponentsResultLine:
    """Run ``request`` on a thread; a caller that is cancelled stops the role and waits for it to end."""
    stop = ComponentsCancellation() if cancellation is None else cancellation
    running = asyncio.ensure_future(
        asyncio.to_thread(
            run_components_role, request, on_event=on_event, review=review, cancellation=stop, timeout=timeout
        )
    )
    try:
        return await asyncio.shield(running)
    except asyncio.CancelledError as cancelled:
        stop.cancel()
        return await await_cancellation_complete(running, task_name="tui-components-role", cancellation=cancelled)


def _checked(result: ComponentsResultLine) -> ComponentsResultLine:
    if result.outcome is not ComponentsOutcome.OK:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return result


class ComponentsSetupDoor:
    """Reach the component engine through the components role of this build's Cadrumo binary."""

    async def read_status(self) -> ComponentsResultLine:
        """Read every item's row from the quick check: local facts only, no network and no model load."""
        return _checked(await _run(ComponentsRequest(ComponentsCommand.STATUS), timeout=_QUICK_TIMEOUT_S))

    async def verify(
        self, items: tuple[DependencyItemKind, ...], *, on_event: ComponentsEventSink
    ) -> ComponentsResultLine:
        """Run the full check of the named items, every item when none is named."""
        return _checked(await _run(ComponentsRequest(ComponentsCommand.VERIFY, items=items), on_event=on_event))

    async def set_up(
        self,
        items: tuple[DependencyItemKind, ...],
        *,
        approved: str | None,
        review: ComponentsReviewer,
        on_event: ComponentsEventSink,
        cancellation: ComponentsCancellation,
    ) -> ComponentsResultLine:
        """Run one setup; with ``approved`` the role sets up only that plan and asks for no review.

        A completed setup ran exactly the plan that was approved, here or by
        ``review``; a result that names another plan is a broken exchange.
        """
        reviewed: list[str] = [] if approved is None else [approved]

        def answer(line: ComponentsReviewLine) -> ComponentsAnswer:
            reviewed.append(line.plan_digest)
            return review(line)

        result = await _run(
            ComponentsRequest(ComponentsCommand.SETUP, items=items, approve=approved),
            on_event=on_event,
            review=answer,
            cancellation=cancellation,
        )
        if (
            result.outcome is ComponentsOutcome.COMPLETED
            and result.plan_digest is not None
            and reviewed
            and result.plan_digest != reviewed[-1]
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return result
