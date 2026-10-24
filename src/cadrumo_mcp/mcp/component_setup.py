"""The setup tools: read, plan and run setup through the native component engine's ``components`` role.

The command line, the TUI, the desktop and this service read the same rows and
approve the same plan, because each one asks the same engine: this module runs
one command of the Cadrumo binary's ``components`` role through the shared
client and answers with the role's own codes plus their words in the profile's
language. It decides nothing about a component.

A setup is bound to a plan's digest. ``setup_plan`` returns the plan and its
digest for the person to approve; ``setup`` carries exactly that digest and the
role sets up only while the plan still has it, asking for no review of its own.
When the agent column starts a setup, the desktop's approval of the tool call
is the person's act. A call without a digest is refused before the role starts.
``setup_remove`` deletes the named items, as the command line's removal does,
and only with ``confirmed`` true: like the command line's ``--yes``, it is the
person's confirmation, and a call without it is refused before the role starts.

The role's byte figures are relayed as ``notifications/progress`` while the
call runs, when the client sent a progress token, and the reply carries the
last figure of each item. A setup of an item another process is already
setting up follows that setup: its figures are relayed the same way, the reply
is that setup's result, and ``followed`` names the item and the digest of the
plan it runs under. A call that is cancelled stops the role at its next
transfer chunk and returns only once the role has ended.

A refused operation whose verdict names a setup item's recovery action is
offered only as the item's current quick row allows, as every other surface
offers it: the action is named while the row's button can set the item up, the
row's own sentence is given while it cannot, and an unreadable status names
neither.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Sequence
from typing import Any, Final

from cadrumo.adapters.outbound.components.client import (
    ComponentsCancellation,
    ComponentsEventSink,
    ComponentsRequest,
    run_components_role,
)
from cadrumo.adapters.outbound.components.protocol import (
    ComponentsCommand,
    ComponentsEvent,
    ComponentsNoticeCode,
    ComponentsNoticeLine,
    ComponentsOutcome,
    ComponentsPlan,
    ComponentsProgressLine,
    ComponentsResultLine,
    ComponentsRow,
)
from cadrumo.application.dependency_contracts import DEPENDENCY_SETUP_RECOVERIES, DependencyItemKind
from cadrumo.application.dependency_registry import dependency_item_declarations
from cadrumo.application.dependency_wording import (
    dependency_failure_key,
    dependency_held_sentence,
    dependency_licence_notice,
    dependency_name_key,
    dependency_row_wording,
)
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.i18n.render import tr
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from .progress_relay import ProgressSink, component_progress

__all__ = ["SETUP_TOOLS", "gate_setup_actions", "run_setup_tool", "setup_request"]

SETUP_TOOLS: Final = frozenset({"setup_status", "setup_plan", "setup", "setup_remove"})
"""The tools served by the component engine rather than by a registered operation."""

_DIGEST: Final = re.compile(r"^[0-9a-f]{64}$")
_READ_TIMEOUT_S: Final = 30.0
"""A quick check or a plan reads local facts within seconds; this only stops a role that hangs."""


def _items(args: dict[str, Any]) -> tuple[DependencyItemKind, ...]:
    named = args.get("items", [])
    try:
        items = tuple(DependencyItemKind(value) for value in named)
    except ValueError:
        raise ValueError("unknown setup item") from None
    if len(set(items)) != len(items):
        raise ValueError("each setup item is named once")
    return items


def setup_request(name: str, args: dict[str, Any]) -> ComponentsRequest:
    """Return the role command one setup tool call asks for, refusing arguments the tool does not take.

    Raises:
        ValueError: An unknown or repeated item, a setup without the exact digest of an approved plan, or a
            removal without the person's confirmation or without an item.
    """
    items = _items(args)
    if name == "setup_status":
        if args.get("full") is True:
            return ComponentsRequest(ComponentsCommand.VERIFY, items=items)
        return ComponentsRequest(ComponentsCommand.STATUS, items=items)
    if name == "setup_plan":
        return ComponentsRequest(ComponentsCommand.PLAN, items=items)
    if name == "setup":
        digest = args.get("plan_digest")
        if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
            raise ValueError("a setup carries the plan_digest of the plan the person approved")
        return ComponentsRequest(ComponentsCommand.SETUP, items=items, approve=digest)
    if name == "setup_remove":
        if args.get("confirmed") is not True:
            raise ValueError("a removal carries the person's confirmation")
        if not items:
            raise ValueError("a removal names its items")
        return ComponentsRequest(ComponentsCommand.REMOVE, items=items)
    raise ValueError("not a setup tool")


def _declaration_name(item_id: str, language: str) -> str:
    declaration = next(item for item in dependency_item_declarations() if item.item_id == item_id)
    return tr(dependency_name_key(declaration), locale=language)


def _row(row: ComponentsRow, language: str) -> dict[str, Any]:
    status = row.status_row()
    declaration = next(item for item in dependency_item_declarations() if item.item_id == row.item_id)
    wording = dependency_row_wording(status, declaration, locale=language)
    words = {"name": wording.name, "sentence": wording.sentence}
    if wording.note is not None:
        words["note"] = wording.note
    if wording.action is not None:
        words["action"] = wording.action
    return {**row.model_dump(mode="json", exclude_none=True), "words": words}


def _notices(plan: ComponentsPlan, language: str) -> list[str]:
    notices: list[str] = []
    for entry in plan.entries:
        for part in entry.parts:
            notice = dependency_licence_notice(
                part_id=part.part_id,
                target_version=part.target_version,
                licence_name=None if part.licence is None else part.licence.name,
                advisories=part.advisories,
                locale=language,
            )
            if notice is not None and notice not in notices:
                notices.append(notice)
    return notices


def _reply(result: ComponentsResultLine, language: str, latest: dict[str, ComponentsProgressLine]) -> dict[str, Any]:
    reply: dict[str, Any] = {"outcome": result.outcome.value}
    if result.mode is not None:
        reply["mode"] = result.mode.value
    reply["rows"] = [_row(row, language) for row in result.rows]
    if result.setup_complete is not None:
        reply["setup_complete"] = result.setup_complete
    if result.plan is not None and result.plan_digest is not None:
        reply["plan"] = result.plan.model_dump(mode="json")
        reply["plan_digest"] = result.plan_digest
        reply["notices"] = _notices(result.plan, language)
    if result.command is ComponentsCommand.REMOVE and result.items is not None:
        reply["removed"] = list(result.items)
    if result.item_id is not None:
        reply["item_id"] = result.item_id
    if result.failure_category is not None:
        sentence = tr(dependency_failure_key(result.failure_category), locale=language)
        if result.item_id is not None:
            sentence = f"{_declaration_name(result.item_id, language)}: {sentence}"
        reply["failure_category"] = result.failure_category.value
        reply["failure"] = sentence
    if latest:
        reply["progress"] = [
            {"item_id": event.subject_code, "completed": event.completed, "total": event.total}
            for event in latest.values()
        ]
    return reply


async def _run(
    request: ComponentsRequest,
    *,
    on_event: ComponentsEventSink,
    cancellation: ComponentsCancellation,
    timeout: float | None,
) -> ComponentsResultLine:
    """Run ``request`` on a thread; a call that is cancelled stops the role and waits for it to end."""
    running = asyncio.ensure_future(
        asyncio.to_thread(run_components_role, request, on_event=on_event, cancellation=cancellation, timeout=timeout)
    )
    try:
        return await asyncio.shield(running)
    except asyncio.CancelledError as cancelled:
        cancellation.cancel()
        return await await_cancellation_complete(running, task_name="mcp-components-role", cancellation=cancelled)


async def run_setup_tool(request: ComponentsRequest, *, language: str, progress: ProgressSink | None) -> dict[str, Any]:
    """Run one setup tool's role command and answer with its codes and their words in ``language``.

    Raises:
        RefusalError: The role could not be started, broke its protocol, did
            not answer a read in time, or reported a completed setup of a plan
            other than the approved one.
    """
    loop = asyncio.get_running_loop()
    events: asyncio.Queue[ComponentsEvent | None] = asyncio.Queue()
    latest: dict[str, ComponentsProgressLine] = {}
    followed: list[dict[str, str]] = []

    def received(event: ComponentsEvent) -> None:
        try:
            loop.call_soon_threadsafe(events.put_nowait, event)
        except RuntimeError:
            return

    async def relay() -> None:
        while (event := await events.get()) is not None:
            if isinstance(event, ComponentsProgressLine):
                latest[event.subject_code] = event
            elif (
                isinstance(event, ComponentsNoticeLine)
                and event.notice_code is ComponentsNoticeCode.FOLLOWING
                and event.subject_code is not None
                and event.plan_digest is not None
            ):
                followed.append({"item_id": event.subject_code, "plan_digest": event.plan_digest})
            figure = component_progress(event)
            if progress is not None and figure is not None:
                await progress(figure)

    reads = request.command in {ComponentsCommand.STATUS, ComponentsCommand.PLAN}
    relaying = asyncio.ensure_future(relay())
    try:
        result = await _run(
            request,
            on_event=received,
            cancellation=ComponentsCancellation(),
            timeout=_READ_TIMEOUT_S if reads else None,
        )
    except BaseException:
        relaying.cancel()
        raise
    # Every event the role sent was queued before its result, so the end mark follows them.
    events.put_nowait(None)
    await relaying
    if (
        request.command in {ComponentsCommand.STATUS, ComponentsCommand.VERIFY}
        and result.outcome is not ComponentsOutcome.OK
    ):
        # A check always reports its rows; any other outcome is a broken exchange.
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if (
        request.command is ComponentsCommand.SETUP
        and result.outcome is ComponentsOutcome.COMPLETED
        and result.plan_digest is not None
        and result.plan_digest != request.approve
    ):
        # A completed setup ran exactly the approved plan, or the exchange is broken.
        raise RefusalError(RefusalCode.INVALID_FRAME)
    reply = _reply(result, language, latest)
    if followed:
        reply["followed"] = followed
    return reply


def _setup_item(action_id: str) -> str | None:
    return next(
        (item.item_id for item in dependency_item_declarations() if item.recovery_action_id == action_id),
        None,
    )


def gate_setup_actions(
    action_ids: Sequence[str], *, language: Callable[[], str]
) -> tuple[list[str], list[dict[str, str]]]:
    """Split recovery actions into those to name and the setup items held from setup, by their quick rows.

    An action that sets up no item is named as it is. A setup item's action is
    named while the item's quick row can set it up; while the row cannot, the
    item is returned with its row's sentence instead; and while the quick
    status cannot be read, neither is returned. The status is read at most
    once, and ``language`` only for a held item's sentence.
    """
    named: list[str] = []
    held: list[dict[str, str]] = []
    rows: dict[str, ComponentsRow] | None = None
    read = False
    for action_id in dict.fromkeys(action_ids):
        item_id = _setup_item(action_id)
        if item_id is None:
            named.append(action_id)
            continue
        if not read:
            read = True
            try:
                status = run_components_role(ComponentsRequest(ComponentsCommand.STATUS), timeout=_READ_TIMEOUT_S)
            except RefusalError:
                status = None
            if status is not None and status.outcome is ComponentsOutcome.OK:
                rows = {row.item_id: row for row in status.rows}
        row = None if rows is None else rows.get(item_id)
        if row is None:
            continue
        status_row = row.status_row()
        if status_row.recovery in DEPENDENCY_SETUP_RECOVERIES:
            named.append(action_id)
        else:
            declaration = next(item for item in dependency_item_declarations() if item.item_id == item_id)
            held.append(
                {
                    "recovery_action_id": action_id,
                    "item_id": item_id,
                    "state": status_row.state.value,
                    "sentence": dependency_held_sentence(status_row, declaration, locale=language()),
                }
            )
    return named, held
