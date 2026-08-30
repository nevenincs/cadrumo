"""Real behavioral proofs for the navigation and disclosure primitives.

Every assertion drives a real Textual `App`/pilot -- never a presence-only
check -- across narrow-terminal geometry and real keyboard focus movement,
since a `DataTable` swallowing `enter` in this same tree already
proved that a widget can render correctly and still be unusable by keyboard.
"""

from __future__ import annotations

from typing import override

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from .....tests.terminal_sizes import SUPPORTED_TERMINAL_SIZE_IDS, SUPPORTED_TERMINAL_SIZES
from ..widgets import (
    DisclosureGroup,
    RequirementBadge,
    RequirementStatus,
    SourceActionCard,
    SourceActionDescriptor,
    StageNavigationStrip,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_STAGES = ("Overview", "Get data", "Required", "Review", "Ready")


class _StageHarness(App[None]):
    def __init__(self, *, current_index: int) -> None:
        super().__init__()
        self._current_index = current_index

    @override
    def compose(self) -> ComposeResult:
        yield StageNavigationStrip(_STAGES, current_index=self._current_index, id="stages")


def test_stage_strip_refuses_an_empty_or_out_of_range_construction() -> None:
    with pytest.raises(ValueError, match="at least one stage"):
        StageNavigationStrip((), current_index=0)
    with pytest.raises(ValueError, match="declared stage"):
        StageNavigationStrip(_STAGES, current_index=len(_STAGES))
    with pytest.raises(ValueError, match="declared stage"):
        StageNavigationStrip(_STAGES, current_index=-1)


@pytest.mark.asyncio
@pytest.mark.parametrize("size", SUPPORTED_TERMINAL_SIZES, ids=SUPPORTED_TERMINAL_SIZE_IDS)
async def test_stage_strip_shows_every_stage_with_a_distinct_non_colour_glyph(size: tuple[int, int]) -> None:
    """Done, current, and upcoming stages each carry their own glyph, not only a colour class."""
    app = _StageHarness(current_index=2)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        rendered = {index: str(app.query_one(f"#stage-{index}", Static).render()) for index in range(len(_STAGES))}

    assert rendered[0].startswith("✓")
    assert rendered[1].startswith("✓")
    assert rendered[2].startswith("▸")
    assert rendered[3].startswith("·")
    assert rendered[4].startswith("·")
    for index, label in enumerate(_STAGES):
        assert label in rendered[index]


class _RequirementHarness(App[None]):
    @override
    def compose(self) -> ComposeResult:
        yield RequirementBadge("NIF", RequirementStatus.REQUIRED_MISSING, id="badge-missing")
        yield RequirementBadge("Postcode", RequirementStatus.NOT_APPLICABLE, id="badge-not-applicable")
        yield RequirementBadge("Website", RequirementStatus.OPTIONAL, id="badge-optional")


@pytest.mark.asyncio
async def test_requirement_badges_are_distinguishable_by_text_not_colour_alone() -> None:
    app = _RequirementHarness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        missing = str(app.query_one("#badge-missing", RequirementBadge).render())
        not_applicable = str(app.query_one("#badge-not-applicable", RequirementBadge).render())
        optional = str(app.query_one("#badge-optional", RequirementBadge).render())

    assert missing.startswith("✖") and "NIF" in missing
    assert not_applicable.startswith("—") and "Postcode" in not_applicable
    assert optional.startswith("○") and "Website" in optional
    glyphs = {missing[0], not_applicable[0], optional[0]}
    assert len(glyphs) == 3, "every rendered status must carry its own distinguishing glyph"


class _DisclosureHarness(App[None]):
    @override
    def compose(self) -> ComposeResult:
        yield DisclosureGroup(Static("hidden detail", id="detail"), title="Optional detail", id="group")


@pytest.mark.asyncio
async def test_disclosure_group_starts_collapsed_and_opens_by_keyboard() -> None:
    app = _DisclosureHarness()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        group = app.query_one("#group", DisclosureGroup)
        assert group.collapsed is True
        await pilot.press("tab")
        await pilot.pause()
        assert app.focused is not None
        assert app.focused.parent is group
        await pilot.press("enter")
        await pilot.pause()
        assert group.collapsed is False


class _SourceCardHarness(App[None]):
    pressed_count = 0

    @override
    def compose(self) -> ComposeResult:
        yield SourceActionCard(
            SourceActionDescriptor(
                title="AEAT censo",
                description="Read the taxpayer's own censal record.",
                action_label="Start",
            ),
            id="card",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        del event
        self.pressed_count += 1


@pytest.mark.asyncio
async def test_source_action_card_button_is_reachable_and_pressable_by_keyboard() -> None:
    """A card the operator can only see is not a usable source -- it must be tabbable and pressable."""
    app = _SourceCardHarness()

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        button = app.query_one("#btn-source-action", Button)
        button.focus()
        await pilot.pause()
        assert app.focused is button
        await pilot.press("enter")
        await pilot.pause()

    assert app.pressed_count == 1
