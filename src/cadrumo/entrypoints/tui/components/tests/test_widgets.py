"""Real behavioral proofs for the navigation and disclosure primitives.

Every assertion drives a real Textual `App`/pilot -- never a presence-only
check -- across narrow-terminal geometry and real keyboard focus movement,
since a `DataTable` swallowing `enter` in this same tree already
proved that a widget can render correctly and still be unusable by keyboard.
"""

from __future__ import annotations

from pathlib import Path
from typing import override

import pytest
import yaml
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from .....tests.terminal_sizes import SUPPORTED_TERMINAL_SIZE_IDS, SUPPORTED_TERMINAL_SIZES
from ..theme import BASE_CSS, CADRUMO_CSS_TOKENS, tokenised
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


@pytest.mark.asyncio
async def test_every_grouping_mechanism_separates_its_groups_by_the_same_distance() -> None:
    """Three ways to mark a group, one distance between them.

    This product marks a logical group three ways: a bordered panel with a
    border title, a `.cadrumo-heading` above its rows, and a collapsible
    `DisclosureGroup`. The affordances genuinely differ -- a panel is static, a
    disclosure collapses -- so having three is defensible. Having three
    DISTANCES is not: the operator reads separation, not mechanism, and a
    surface that mixes two of them at different gaps reads as one smeared list
    however correctly each group is titled.

    `DisclosureGroup` was the one that drifted. It declared no CSS at all and
    inherited Textual's default, so two titled groups sat flush against each
    other while panels and headings stood two rows apart. Measured from the
    mounted geometry rather than the stylesheet, because a declaration proves
    only that someone wrote it -- the gap that matters is the one painted.
    """
    section_gap = int(CADRUMO_CSS_TOKENS["cadrumo-section"])

    class _Probe(App[None]):
        CSS = BASE_CSS

        @override
        def compose(self) -> ComposeResult:
            yield DisclosureGroup(Static("uno"), title="Uno", collapsed=False, id="group-a")
            yield DisclosureGroup(Static("dos"), title="Dos", collapsed=False, id="group-b")
            yield Static("panel-a", classes="cadrumo-panel", id="panel-a")
            yield Static("panel-b", classes="cadrumo-panel", id="panel-b")

    app = _Probe()
    async with app.run_test(size=(80, 40)) as pilot:
        await pilot.pause()
        measured = {}
        for mechanism, first, second in (
            ("DisclosureGroup", "#group-a", "#group-b"),
            ("cadrumo-panel", "#panel-a", "#panel-b"),
        ):
            top = app.screen.query_one(first)
            bottom = app.screen.query_one(second)
            measured[mechanism] = bottom.region.y - (top.region.y + top.region.height)
        app.exit(None)

    for mechanism, gap in measured.items():
        assert gap == section_gap, (
            f"{mechanism} separates consecutive groups by {gap} rows, not the "
            f"{section_gap} the section token declares; measured {measured}"
        )


@pytest.mark.asyncio
async def test_a_source_card_title_is_separated_from_the_card_above_it() -> None:
    """Stacked source cards must not run into one another.

    The Profile manager stacks these, and each card is a group: a title, the
    sentence explaining it, and the button that acts on it. The title carried
    no rhythm, so the second card's title sat directly beneath the first
    card's action button and the panel read as one list of alternating
    sentences and buttons rather than two offers.

    Asserted from the mounted geometry because the Profile manager surface
    refuses to open standalone -- it needs an active profile pointer -- so
    this is where the rhythm can actually be observed. The asymmetry is the
    claim: a wider gap ABOVE binds the title away from the previous card, a
    narrower one BELOW binds it to its own description. Equal gaps leave it
    floating between the two.
    """
    section_gap = int(CADRUMO_CSS_TOKENS["cadrumo-section"])
    stack_gap = int(CADRUMO_CSS_TOKENS["cadrumo-stack"])

    class _Probe(App[None]):
        CSS = BASE_CSS

        @override
        def compose(self) -> ComposeResult:
            for name in ("Censo", "Historial"):
                yield SourceActionCard(
                    SourceActionDescriptor(
                        title=f"{name} de la AEAT",
                        description=f"Descripcion de {name}.",
                        action_label=f"Abrir {name}",
                    ),
                    id=f"card-{name.lower()}",
                )

    app = _Probe()
    async with app.run_test(size=(80, 30)) as pilot:
        await pilot.pause()
        titles = list(app.screen.query(".cadrumo-source-card-title"))
        margins = [(node.styles.margin.top, node.styles.margin.bottom) for node in titles]
        app.exit(None)

    assert len(titles) == 2, "the probe did not mount two cards, so it proves nothing"
    for top, bottom in margins:
        assert (top, bottom) == (section_gap, stack_gap), (
            f"a source card title carries {(top, bottom)} rather than the "
            f"{(section_gap, stack_gap)} rhythm, so it does not own its own description"
        )


@pytest.mark.asyncio
async def test_no_declared_action_label_wraps_its_control() -> None:
    """Every action button is the same height, in every locale.

    A label wider than the control cap wraps, and a wrapped label costs a row,
    so that one button becomes taller than the others and the action row goes
    ragged. The token table already argues this for `control-pad-x`; the cap
    was quietly breaking the same rule from the other side -- at 28 cells only
    one of the four AEAT actions fitted in ANY language, and two buttons in one
    column measured 3 and 5 rows tall.

    The consequence was not only visual. The taller neighbour reached far
    enough to consume a simulated press aimed at the button above it, which
    surfaced as a failure about a broken in-flight guard.

    Driven from the shipped catalogues rather than a sample string, because the
    binding constraint is whichever locale translates an action longest -- here
    Spanish and Catalan tie at 43 cells, and English, the language a developer
    reads while choosing a number, is nowhere near it.
    """
    catalogue_root = Path(__file__).resolve().parents[4] / "locales"
    labels: list[tuple[str, str, str]] = []
    for locale in ("es", "en", "ca", "hu"):
        raw = yaml.safe_load((catalogue_root / locale / "common.yml").read_text(encoding="utf-8"))
        for key, value in raw["tui"]["aeat_sync"]["action"].items():
            labels.append((locale, key, value))

    assert labels, "no action labels were read, so this proves nothing"

    class _Probe(App[None]):
        CSS = BASE_CSS + tokenised(".aeat-sync-operation { width: 100%; max-width: $cadrumo-control-max-width; }")

        @override
        def compose(self) -> ComposeResult:
            for index, (_locale, _key, text) in enumerate(labels):
                yield Button(text, id=f"probe-{index}", classes="aeat-sync-operation")

    app = _Probe()
    async with app.run_test(size=(80, 24 + 3 * len(labels))) as pilot:
        await pilot.pause()
        heights = {button.id: button.region.height for button in app.screen.query(Button)}
        app.exit(None)

    ragged = [
        f"{locale}:{key} ({len(text)} cells) -> {heights[f'probe-{index}']} rows"
        for index, (locale, key, text) in enumerate(labels)
        if heights[f"probe-{index}"] != 3
    ]
    assert not ragged, (
        "these action labels wrap their control, making that button taller than its siblings: " + ", ".join(ragged)
    )
