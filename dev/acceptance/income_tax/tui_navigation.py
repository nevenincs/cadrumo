"""Bounded public workbench navigation and refresh observation for installed income-tax journeys."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any

from .tui_checkbox import _tick
from .tui_contracts import TuiJourneyError, TuiOperationBinding
from .tui_readback import _query_visible_tui_control, _rendered_text, _stack_text, workbench_notice
from .tui_selectors import (
    _COUNT_PLACEHOLDER,
    _DATE_PLACEHOLDER,
    _EXPORT_PATH,
    _EXPORT_RESULT_CLOSE,
    _OFFERED_STEP_ACTIONS,
    _OFFERED_STEP_KEYS,
    _RESULT_STATEMENT_CLOSE,
    _REVIEW_ACKNOWLEDGE,
    _REVIEW_APPLY,
    _REVIEW_FINDINGS,
    _REVIEW_KEY,
    WORKBENCH_NEXT,
    WORKBENCH_NOTICE,
)

if TYPE_CHECKING:
    from textual.pilot import Pilot
    from textual.widget import Widget

    from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen


async def wait_for_workbench(pilot: Pilot[Any], *, seconds: float = 300.0) -> ModeloWorkbenchScreen:
    """Wait until the declaration's workbench is the top screen and has read its form.

    The workbench reads its form off the event loop, so the screen appears
    before it can be acted on.  A read the workbench itself reports as failed
    is refused at once rather than waited out.
    """
    from textual.css.query import NoMatches

    from cadrumo.core.i18n.render import tr
    from cadrumo.entrypoints.tui.modelo.workbench import screen as workbench_screen

    read_failed = tr("tui.modelo.workbench.read_failed")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        # The top of the stack is the screen on display; unlike ``app.screen`` it is
        # typed ``Screen[Any]``, which a workbench screen can narrow.
        screen = pilot.app.screen_stack[-1]
        if isinstance(screen, workbench_screen.ModeloWorkbenchScreen):
            if screen.form is not None:
                return screen
            try:
                loading = _rendered_text(screen.query_one("#wb-loading"))
            except NoMatches:
                loading = ""
            if loading == read_failed:
                raise TuiJourneyError("the declaration's workbench could not read its form")
        await pilot.pause(0.2)
    raise TuiJourneyError(
        f"the declaration's workbench did not read its form within {seconds:.0f}s "
        f"(top screen {type(pilot.app.screen).__name__})"
    )


async def open_workbench_export(pilot: Pilot[Any], *, output_path: str, maximum_polls: int = 600) -> None:
    """Open the workbench's export dialog with its own key and name the destination.

    The dialog is only offered for a verified declaration; the workbench's
    own refusal is reported instead of being waited out.
    """
    from textual.css.query import NoMatches
    from textual.widgets import Input

    _require_fresh_notice(pilot, label="modelo.export")
    await pilot.press("e")
    for _ in range(maximum_polls):
        try:
            destination = pilot.app.screen.query_one(_EXPORT_PATH, Input)
        except NoMatches:
            notice = _stack_text(pilot, WORKBENCH_NOTICE)
            if notice:
                raise TuiJourneyError(f"the workbench did not open its export dialog: {notice[:240]}") from None
            await pilot.pause()
            continue
        destination.value = output_path
        return
    raise TuiJourneyError("the workbench did not open its export dialog")


async def acknowledge_export_result(pilot: Pilot[Any], *, maximum_polls: int = 600) -> None:
    """Close the statement a finished export shows before the workbench moves on."""
    from textual.css.query import NoMatches

    for _ in range(maximum_polls):
        try:
            close = pilot.app.screen.query_one(_EXPORT_RESULT_CLOSE)
        except NoMatches:
            await pilot.pause()
            continue
        close.focus()
        await pilot.press("enter")
        for _ in range(maximum_polls):
            if not pilot.app.screen.query(_EXPORT_RESULT_CLOSE):
                return
            await pilot.pause()
        raise TuiJourneyError("the export statement did not close")
    raise TuiJourneyError("the finished export did not show its statement")


def workbench_offers(pilot: Pilot[Any], step: str) -> bool:
    """Whether the workbench on top offers ``step`` on its next-step line, with the key it shows for it."""
    return _offered_step_pattern(step).match(_offered_line(pilot)) is not None


async def open_review_ready_to_apply(pilot: Pilot[Any], *, seconds: float = 300.0) -> None:
    """Open the review of the staged changes with its key and, when it asks, acknowledge it.

    The workbench checks the changes with the application before the review
    opens; a finding that would refuse them keeps Apply unavailable, and is
    reported as the review states it.  Apply itself is left to the caller.
    """
    from textual.css.query import NoMatches
    from textual.widgets import Button, Checkbox

    await pilot.press(_REVIEW_KEY)
    deadline = time.monotonic() + seconds
    while True:
        try:
            apply = pilot.app.screen.query_one(_REVIEW_APPLY, Button)
        except NoMatches:
            if time.monotonic() > deadline:
                raise TuiJourneyError(
                    f"the workbench opened no review of its changes (notice {workbench_notice(pilot)[:200]!r})"
                ) from None
            await pilot.pause()
            continue
        break
    review = pilot.app.screen
    acknowledge = next(iter(review.query(_REVIEW_ACKNOWLEDGE).results(Checkbox)), None)
    if acknowledge is not None and not acknowledge.value and not await _tick(pilot, acknowledge):
        raise TuiJourneyError("the review's acknowledgement did not take")
    while apply.disabled:
        if time.monotonic() > deadline:
            findings = _stack_text(pilot, _REVIEW_FINDINGS)
            raise TuiJourneyError(f"the review never allowed applying the changes (findings {findings[:300]!r})")
        await pilot.pause()


async def wait_for_tui_refresh(
    pilot: Pilot[Any],
    *,
    binding: TuiOperationBinding,
    maximum_polls: int = 600,
) -> None:
    """Require the workbench back on top after a succeeded lifecycle action, with its re-read settled.

    The workbench stays open after an operation and reads the declaration
    again; the wait ends only once that read, and any other work the screen
    started, has finished.  After a recalculation the workbench states which
    boxes now read differently; that statement is closed as a filer closes it.
    """
    from textual.css.query import NoMatches

    if binding.refresh_result_id is None:
        raise TuiJourneyError(f"{binding.operation_id} has no installed refresh target")
    for _ in range(maximum_polls):
        try:
            close = pilot.app.screen.query_one(_RESULT_STATEMENT_CLOSE)
        except NoMatches:
            pass
        else:
            close.focus()
            await pilot.press("enter")
            await pilot.pause()
            continue
        try:
            pilot.app.screen.query_one(binding.refresh_result_id)
        except NoMatches:
            await pilot.pause()
            continue
        if all(worker.is_finished for worker in pilot.app.workers):
            return
        await pilot.pause()
    raise TuiJourneyError(f"{binding.operation_id} did not reach its refreshed TUI destination")


def _require_fresh_notice(pilot: Pilot[Any], *, label: str, selector: str | None = WORKBENCH_NOTICE) -> None:
    """Refuse to start an operation while the workbench still shows an earlier notice."""
    if selector is None:
        return
    notice = _stack_text(pilot, selector)
    if notice:
        raise TuiJourneyError(
            f"{label} would start under an earlier workbench notice; open the declaration afresh first "
            f"(notice {notice[:120]!r})"
        )


def _require_offered_step(pilot: Pilot[Any], *, step: str) -> None:
    """Require the workbench to offer ``step`` as the one its next-step key runs."""
    if not workbench_offers(pilot, step):
        raise TuiJourneyError(
            f"the workbench does not offer {step} as its next step (it offers {_offered_line(pilot)[:200]!r})"
        )


def _offered_line(pilot: Pilot[Any]) -> str:
    """Read the next-step line of the workbench on top, or nothing while another screen is on top."""
    from textual.css.query import NoMatches

    try:
        return _rendered_text(pilot.app.screen.query_one(WORKBENCH_NEXT))
    except NoMatches:
        return ""


def _offered_step_pattern(step: str) -> re.Pattern[str]:
    """The next-step line that offers ``step``, from the catalogue, with any count or date left open.

    Recording the filing is offered on its own line once a file made from the
    current calculation exists, naming the day that file was created.
    """
    key = _OFFERED_STEP_KEYS.get(step)
    if key is None:
        raise TuiJourneyError(f"the workbench offers no step named {step!r}")
    return re.compile(_next_line_source(_OFFERED_STEP_ACTIONS.get(step, step), key))


def _next_line_source(action: str, key: str) -> str:
    """The regular expression for the next-step line offering ``action``, matching any count and any date."""
    from cadrumo.core.i18n.render import tr

    line = tr(
        "tui.modelo.workbench.next_line",
        action=tr(f"tui.modelo.workbench.next.{action}", count=_COUNT_PLACEHOLDER, date=_DATE_PLACEHOLDER),
        key=key,
    )
    source = re.escape(line).replace(_COUNT_PLACEHOLDER, r"\d+")
    return source.replace(_DATE_PLACEHOLDER, r".+?")


async def _wait_for_visible_tui_control(pilot: Pilot[Any], selector: str, *, maximum_polls: int) -> Widget:
    """Wait until a control is on the top screen."""
    from textual.css.query import NoMatches

    for _ in range(maximum_polls):
        try:
            return _query_visible_tui_control(pilot, selector)
        except NoMatches:
            await pilot.pause()
    raise TuiJourneyError(f"installed TUI did not show {selector}")
