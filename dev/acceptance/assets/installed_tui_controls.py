"""Bounded interaction with visible installed activity-asset TUI controls."""

from __future__ import annotations

import re
from time import monotonic
from typing import Any

from .installed_tui_contracts import InstalledAssetTuiError, _PublicAssetActionTransition


def _public_surface_diagnostic(pilot: Any) -> dict[str, object]:
    """Describe only public screen identity and widget IDs for a failed stage."""
    screen = pilot.app.screen
    ids: set[str] = set()
    for scope in (pilot.app, screen):
        for widget in scope.query("*"):
            widget_id: object = getattr(widget, "id", None)
            if isinstance(widget_id, str):
                ids.add(widget_id)
    return {
        "current_screen_class": type(screen).__name__,
        "current_screen_id": screen.id,
        "mounted_widget_ids": sorted(ids),
    }


async def _wait_for_public_selector(
    pilot: Any,
    selector: str,
    *,
    stage: str,
    timeout_seconds: float = 15.0,
) -> object:
    """Wait a bounded time for one visible public control."""
    from textual.css.query import NoMatches

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        try:
            return pilot.app.query_one(selector)
        except NoMatches:
            try:
                return pilot.app.screen.query_one(selector)
            except NoMatches:
                await pilot.pause()
    raise InstalledAssetTuiError(
        f"installed TUI did not expose {selector}",
        stage=stage,
        diagnostic=_public_surface_diagnostic(pilot),
    )


async def _wait_for_public_selector_absent(
    pilot: Any,
    selector: str,
    *,
    stage: str,
    timeout_seconds: float = 15.0,
) -> None:
    """Wait for a public control to disappear after its supported operation."""
    from textual.css.query import NoMatches

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        try:
            pilot.app.query_one(selector)
        except NoMatches:
            try:
                pilot.app.screen.query_one(selector)
            except NoMatches:
                return
        await pilot.pause()
    raise InstalledAssetTuiError(
        f"installed TUI did not complete the public operation for {selector}",
        stage=stage,
        diagnostic=_public_surface_diagnostic(pilot),
    )


async def _open_ledger_destination(*, pilot: Any) -> None:
    """Open Ledger through the public command palette, never a private route."""
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    await pilot.press("ctrl+p")
    await pilot.pause()
    try:
        query = pilot.app.screen.query_one(Input)
        results = pilot.app.screen.query_one(OptionList)
    except NoMatches as exc:
        raise InstalledAssetTuiError(
            "installed TUI did not expose its public command palette controls",
            stage="ledger_navigation",
            diagnostic=_public_surface_diagnostic(pilot),
        ) from exc
    query.value = "Ledger"
    deadline = monotonic() + 45.0
    while monotonic() < deadline:
        if results.option_count > 0:
            results.highlighted = 0
            await pilot.press("enter")
            await _wait_for_public_selector(pilot, "#ledger-navigation", stage="ledger_ready", timeout_seconds=45.0)
            return
        await pilot.pause()
    raise InstalledAssetTuiError(
        "installed TUI command palette did not offer Ledger",
        stage="ledger_navigation",
        diagnostic=_public_surface_diagnostic(pilot),
    )


def _safe_asset_result_state(rendered: str) -> str:
    """Classify a public result without retaining taxpayer-facing values or IDs."""
    parts = rendered.split("\t")
    if not rendered:
        return "empty"
    if parts[0] == "pending" and len(parts) == 2:
        return "pending"
    if parts[0] == "refused":
        return "refused"
    if parts[0] == "claim" and len(parts) == 3 and parts[2] in {"reused=false", "reused=true"}:
        return f"claim:{parts[2]}"
    if parts[0] in {"created", "corrected", "asset", "forecast", "filing_handoff"}:
        return parts[0]
    return "other"


def _asset_transition_diagnostic(
    *,
    pilot: Any,
    transition: _PublicAssetActionTransition,
    rendered: str,
) -> dict[str, object]:
    """Add only safe public action state to the existing surface diagnostic."""
    diagnostic = _public_surface_diagnostic(pilot)
    diagnostic.update(
        {
            "asset_action": transition.button_id,
            "asset_button_disabled_before": transition.button_disabled_before,
            "asset_result_before": _safe_asset_result_state(transition.result_before),
            "asset_result_after_activation": _safe_asset_result_state(transition.result_after_activation),
            "asset_result_last": _safe_asset_result_state(rendered),
        }
    )
    return diagnostic


async def _activate_public_button(
    *,
    pilot: Any,
    selector: str,
    stage: str,
    capture_asset_result: bool = True,
) -> _PublicAssetActionTransition:
    """Activate one visible button and retain a safe before/after state receipt."""
    from textual.widgets import Button, Static

    button = await _wait_for_public_selector(pilot, selector, stage=stage)
    if not isinstance(button, Button):
        raise InstalledAssetTuiError(
            "installed TUI control has an unexpected type",
            stage=stage,
            diagnostic=_public_surface_diagnostic(pilot),
        )
    result = await _wait_for_public_selector(pilot, "#asset-result", stage=stage) if capture_asset_result else None
    if result is not None and not isinstance(result, Static):
        raise InstalledAssetTuiError(
            "installed TUI asset result control has an unexpected type",
            stage=stage,
            diagnostic=_public_surface_diagnostic(pilot),
        )
    result_before = str(result.render()).strip() if result is not None else ""
    button_disabled_before = button.disabled
    if button_disabled_before:
        raise InstalledAssetTuiError(
            "installed TUI asset action is disabled before public keyboard activation",
            stage=stage,
            diagnostic=_public_surface_diagnostic(pilot),
        )
    button.focus()
    await pilot.press("enter")
    await pilot.pause()
    return _PublicAssetActionTransition(
        button_id=button.id or selector.removeprefix("#"),
        result_before=result_before,
        result_after_activation=str(result.render()).strip() if result is not None else "",
        button_disabled_before=button_disabled_before,
    )


async def _set_public_input(*, pilot: Any, selector: str, value: str, stage: str) -> None:
    """Enter a synthetic value through one visible Textual Input control."""
    from textual.widgets import Input

    field = await _wait_for_public_selector(pilot, selector, stage=stage)
    if not isinstance(field, Input):
        raise InstalledAssetTuiError(
            "installed TUI control has an unexpected type",
            stage=stage,
            diagnostic=_public_surface_diagnostic(pilot),
        )
    field.value = value
    await pilot.pause()


def _asset_result_matches(
    rendered: str, expected_prefix: str, expected_suffix: str | None, changed_from_prior_result: bool
) -> bool:
    return (
        changed_from_prior_result
        and rendered.startswith(expected_prefix)
        and (expected_suffix is None or rendered.endswith(expected_suffix))
    )


async def _wait_for_asset_result(
    *,
    pilot: Any,
    expected_prefix: str,
    expected_suffix: str | None = None,
    stage: str,
    transition: _PublicAssetActionTransition | None = None,
    timeout_seconds: float = 45.0,
) -> str:
    """Wait for one public asset action result without preserving raw errors."""
    from textual.widgets import Static

    result = await _wait_for_public_selector(pilot, "#asset-result", stage=stage)
    if not isinstance(result, Static):
        raise InstalledAssetTuiError(
            "installed TUI asset result control has an unexpected type",
            stage=stage,
            diagnostic=_public_surface_diagnostic(pilot),
        )
    deadline = monotonic() + timeout_seconds
    changed_from_prior_result = transition is None
    rendered = ""
    while monotonic() < deadline:
        rendered = str(result.render()).strip()
        if transition is not None and rendered != transition.result_before:
            changed_from_prior_result = True
        if rendered.startswith("refused\t"):
            raise InstalledAssetTuiError(
                "installed TUI asset action displayed a refusal",
                stage=stage,
                diagnostic=(
                    _asset_transition_diagnostic(pilot=pilot, transition=transition, rendered=rendered)
                    if transition is not None
                    else _public_surface_diagnostic(pilot)
                ),
            )
        if _asset_result_matches(rendered, expected_prefix, expected_suffix, changed_from_prior_result):
            # Let the message handler that published the visible result return
            # before the next keyboard action is sent.  This matters for a
            # replay against an encrypted history, whose thread can complete
            # immediately before the Textual handler unwinds.
            await pilot.pause()
            return rendered
        await pilot.pause()
    raise InstalledAssetTuiError(
        "installed TUI asset action did not publish its expected public result",
        stage=stage,
        diagnostic=(
            _asset_transition_diagnostic(pilot=pilot, transition=transition, rendered=rendered)
            if transition is not None
            else _public_surface_diagnostic(pilot)
        ),
    )


async def _wait_for_current_revision_id(*, pilot: Any, stage: str, timeout_seconds: float = 45.0) -> str:
    """Read a canonical immutable revision ID from the public screen projection."""
    from textual.widgets import Static

    current = await _wait_for_public_selector(pilot, "#asset-current-revision-id", stage=stage)
    if not isinstance(current, Static):
        raise InstalledAssetTuiError(
            "installed TUI current-revision control has an unexpected type",
            stage=stage,
            diagnostic=_public_surface_diagnostic(pilot),
        )
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        rendered = str(current.render()).strip()
        match = re.fullmatch(r"current_revision_id\t([0-9a-f]{64})", rendered)
        if match is not None:
            return str(match.group(1))
        await pilot.pause()
    raise InstalledAssetTuiError(
        "installed TUI did not expose the current immutable revision identity",
        stage=stage,
        diagnostic=_public_surface_diagnostic(pilot),
    )


async def _open_activity_asset_screen(*, pilot: Any) -> None:
    """Reach the public asset screen with the visible Ledger action button."""
    await _activate_public_button(
        pilot=pilot,
        selector="#ledger-activity-assets",
        stage="asset_screen_ready",
        capture_asset_result=False,
    )
    await _wait_for_public_selector(pilot, "#asset-id", stage="asset_screen_ready", timeout_seconds=45.0)
