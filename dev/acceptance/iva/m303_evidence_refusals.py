"""Public installed M303 terminal refusal review and bounded notice diagnostics."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    public_surface_diagnostic,
    query_public_selector,
)
from dev.acceptance.income_tax.tui_selectors import WORKBENCH_NOTICE

from .m303_evidence_contracts import TuiOutcome

if TYPE_CHECKING:
    from cadrumo.entrypoints.tui.operations.modal import OperationModal


def _rendered(widget: object) -> str:
    render = getattr(widget, "render", None)
    return str(render()).strip() if callable(render) else ""


def _notice_key(pilot: Any, selector: str, candidates: Sequence[str]) -> str | None:
    """Name the catalogue key whose rendering is the visible notice, never the text itself."""
    from textual.widgets import Static

    from cadrumo.core.i18n.render import tr

    text = _rendered(query_public_selector(pilot, selector, Static))
    return next((key for key in candidates if tr(key) == text), None if not text else "unrecognised")


async def _apply_enabled_refusal_review(pilot: Any, screen: OperationModal) -> bool:
    """Apply the enabled public operation review once and retain its submission observation."""
    from textual.css.query import NoMatches
    from textual.widgets import Button

    try:
        apply = screen.query_one("#btn-operation-apply", Button)
    except NoMatches:
        apply = None
    if apply is not None and not apply.disabled:
        apply.focus()
        await pilot.press("enter")
        return True
    return False


def _refusal_notice_stack(pilot: Any) -> list[str]:
    """Retain bounded screen and notice diagnostics when no terminal notice is visible."""
    from textual.css.query import NoMatches
    from textual.widgets import Static

    stack: list[str] = []
    for layer in pilot.app.screen_stack:
        try:
            layer_notice = _rendered(layer.query_one(WORKBENCH_NOTICE, Static))
        except NoMatches:
            layer_notice = None
        stack.append(f"{type(layer).__name__}:{layer_notice!r}")
    return stack


async def _settle_expected_refusal(pilot: Any, *, activation_id: str, step: str, refusal_key: str) -> TuiOutcome:
    """Drive one operation the product must refuse and read the refusal where the product leaves it.

    The operation modal dismisses itself as soon as the operation is terminal, so
    a refusal settled after Apply is observed on the workbench notice: the
    sentence saying the operation did not complete, followed by the registry's
    public explanation.
    """
    import time

    from textual.css.query import NoMatches
    from textual.widgets import Button, Static

    from cadrumo.core.i18n.render import tr
    from cadrumo.entrypoints.tui.operations.modal import OperationModal

    not_done = tr("tui.modelo.workbench.operation.not_done")
    query_public_selector(pilot, activation_id, Button).focus()
    await pilot.press("enter")
    applied = False
    modal_seen = False
    notice = ""
    deadline = time.monotonic() + 300.0
    while time.monotonic() < deadline:
        screen = pilot.app.screen
        if isinstance(screen, OperationModal):
            modal_seen = True
            if not applied:
                applied = await _apply_enabled_refusal_review(pilot, screen)
        else:
            try:
                notice = _rendered(screen.query_one(WORKBENCH_NOTICE, Static))
            except NoMatches:
                notice = ""
            if notice:
                break
        await pilot.pause(0.2)
    if not notice:
        # Which screen held which notice, and whether the modal was ever seen,
        # separates "the operation never started" from "its notice landed on a
        # screen below the top one" -- the two causes need opposite fixes.
        stack = _refusal_notice_stack(pilot)
        raise InstalledTuiChildError(
            f"installed TUI {step} left no workbench notice (modal_seen={modal_seen}, applied={applied}, "
            f"stack={stack})",
            diagnostic=public_surface_diagnostic(pilot),
        )
    if notice != f"{not_done} {tr(refusal_key)}":
        # The notice is the only place the product explains a non-refusal; a
        # bare sentence would send the reader to the operation journal.
        raise InstalledTuiChildError(
            f"installed TUI {step} expected refusal {refusal_key}, workbench notice was {notice[:400]!r}",
            diagnostic=public_surface_diagnostic(pilot),
        )
    return TuiOutcome(step=step, terminal_condition="refused", visible_notice_key=refusal_key)


def _visible_refusal(pilot: Any) -> str:
    """Name what the operator can see after a non-succeeded operation: the modal receipt or the workbench notice."""
    from textual.css.query import NoMatches

    for selector in ("#operation-modal-receipt", WORKBENCH_NOTICE):
        try:
            text = _rendered(pilot.app.screen.query_one(selector))
        except NoMatches:
            continue
        if text:
            return f"{selector}={text[:400]!r}"
    return "no visible reason"
