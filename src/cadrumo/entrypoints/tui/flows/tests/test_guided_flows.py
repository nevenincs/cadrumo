"""Real proofs that the guided-flow shell renders section stages honestly.

Every test drives the real `FlowTuiApp` through Textual's headless Pilot
over a real multi-section `FlowDefinition`. The load-bearing claim is D6's
own boundary for this Wave: the stage strip renders exactly the sections
`FlowDefinition` declares, in the definition's own order, and advances
only when the real flow engine's own cursor crosses a section boundary --
never a locally re-derived notion of "which section comes next".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml
from pydantic import BaseModel

from .....application.flows.definition import CopyRef, FlowChoice, FlowDefinition, FlowPage, FlowSection
from .....core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from .....core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from .....tests.locales_root_fixture import locales_root_scope
from ..app import FlowTuiApp

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_entrypoint,
]

_TERMINAL_SIZE = (140, 60)

_COPY_CATALOGUE: dict[str, object] = {
    "flows": {
        "guided": {
            "flow_title": "GUIDED-FLOW-TITLE",
            "section_one": "First stage",
            "section_two": "Second stage",
            "prompt_one": "PROMPT-ONE",
            "prompt_two": "PROMPT-TWO",
        },
        "tui": {
            "header": "{flow} / {position} / {total} / {section}",
            "header_single_section": "{flow} / {position} / {total}",
        },
        "review": {"header_tui_stage_label": "Review"},
    },
}


class _Answers(BaseModel):
    """Trivial answers model; only its type identity is consumed."""


def _copy(ref: str) -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=ref)


@pytest.fixture(autouse=True)
def _flow_copy_catalogue(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Resolve every ref this module's definition declares against a fixture
    catalogue -- copy resolution refuses an unresolvable key rather than
    rendering blank, so this proves the strip's labels come from the
    definition's own titles, not a fallback string."""
    root = tmp_path_factory.mktemp("guided-flow-locales")
    payload = yaml.safe_dump(_COPY_CATALOGUE, allow_unicode=True)
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        (root / f"{language}.yml").write_text(payload, encoding="utf-8")
    with locales_root_scope(root):
        yield


def _two_section_definition() -> FlowDefinition:
    """Two sections, one page each -- the minimum shape a stage advance needs."""
    return FlowDefinition(
        id="flows.test.guided",
        title=_copy("flows.guided.flow_title"),
        description=_copy("flows.guided.flow_title"),
        sections=(
            FlowSection(
                id="s1",
                title=_copy("flows.guided.section_one"),
                items=(
                    FlowPage(
                        id="p1", widget=FlowWidgetKind.TEXT, prompt=_copy("flows.guided.prompt_one"), answer_type=str
                    ),
                ),
            ),
            FlowSection(
                id="s2",
                title=_copy("flows.guided.section_two"),
                items=(
                    FlowPage(
                        id="p2",
                        widget=FlowWidgetKind.SELECT,
                        prompt=_copy("flows.guided.prompt_two"),
                        choices=(
                            FlowChoice(value="a", label=_copy("flows.guided.prompt_two")),
                            FlowChoice(value="b", label=_copy("flows.guided.prompt_two")),
                        ),
                        answer_type=str,
                    ),
                ),
            ),
        ),
        answers_model=_Answers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.AVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


def _app() -> FlowTuiApp:
    return FlowTuiApp(_two_section_definition(), mode=FlowMode.MODIFY)


def _rendered_stage(app: FlowTuiApp, index: int) -> str:
    from textual.widgets import Static

    return str(app.screen.query_one(f"#stage-{index}", Static).render())


@pytest.mark.asyncio
async def test_the_strip_declares_one_stage_per_section_in_declared_order(tmp_path: Path) -> None:
    del tmp_path
    app = _app()
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        assert "First stage" in _rendered_stage(app, 0)
        assert "Second stage" in _rendered_stage(app, 1)


@pytest.mark.asyncio
async def test_the_strip_advances_only_when_the_real_engine_cursor_crosses_a_section(tmp_path: Path) -> None:
    del tmp_path
    app = _app()
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        assert _rendered_stage(app, 0).startswith("▸")
        assert _rendered_stage(app, 1).startswith("·")

        # p1 is a required TEXT page; answering and advancing crosses into s2.
        await pilot.press(*"ada")
        await pilot.click("#btn-next")
        await pilot.pause()

        assert _rendered_stage(app, 0).startswith("✓")
        assert _rendered_stage(app, 1).startswith("▸")


@pytest.mark.asyncio
async def test_going_back_returns_the_strip_to_the_prior_section(tmp_path: Path) -> None:
    del tmp_path
    app = _app()
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        await pilot.press(*"ada")
        await pilot.click("#btn-next")
        await pilot.pause()
        assert _rendered_stage(app, 1).startswith("▸")

        await pilot.press("escape")
        await pilot.pause()

        assert _rendered_stage(app, 0).startswith("▸")
        assert _rendered_stage(app, 1).startswith("·")


@pytest.mark.asyncio
async def test_the_review_screen_shows_every_section_plus_review_as_the_final_stage(tmp_path: Path) -> None:
    del tmp_path
    app = _app()
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        await pilot.press(*"ada")
        await pilot.click("#btn-next")
        await pilot.pause()
        await pilot.press("1")
        await pilot.pause()

        assert app.screen.query("#review-table")
        assert _rendered_stage(app, 0).startswith("✓")
        assert _rendered_stage(app, 1).startswith("✓")
        assert _rendered_stage(app, 2).startswith("▸")
        assert "Review" in _rendered_stage(app, 2)
