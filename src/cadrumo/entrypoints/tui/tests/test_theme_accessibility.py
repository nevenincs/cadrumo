"""No meaning on these surfaces is carried by colour alone.

The property, stated so it is testable rather than aspirational: switching the
appearance may change how the surface LOOKS and must change nothing an
operator has to READ or REACH. So the text a destination paints, the controls
it mounts, and the order those controls are reached in are compared between
the two shipped themes and must be identical.

WHAT THIS PROVES, AND WHAT IT CANNOT, stated plainly because the difference is
easy to blur and the blurred version would be a false reassurance. It proves
that appearance is not load-bearing: no glyph and no control appears, vanishes,
changes wording or changes position because of the theme. That catches a theme
whose palette makes text unreadable and drops it from the frame, a layout that
reflows under one appearance, and a status whose WORDING differs between them.

It does NOT prove that every state has a non-colour cue. A validation failure
signalled only by a red border renders identical glyphs under both themes and
passes here. That property is not decidable from two frames of the same state
-- it needs a comparison between the FAILING and PASSING states, not between
two appearances of one state -- so it belongs to a different gate and is not
claimed by this one. Reading a green here as "every state is legible without
colour" would be exactly the wrong-subject error the gate-integrity audit
collects.

The palette control below is still required: without it, a product that ignored
the appearance setting entirely would satisfy every comparison in this module
by rendering one theme twice.

The existing visual suite already proves each of its nine enrolled surfaces
RENDERS under both appearances. That is a liveness check on the compositor and
a different property from this one; it would pass on a surface whose only
validation cue is a red border. None of the six routed workspace destinations
is enrolled there in any case.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest

from ....tests.modelo_workspace_session import real_workspace_inspection_result
from ....tests.terminal_sizes import TERMINAL_ORDINARY
from ..components.host import ScreenHostApp
from ..components.theme import (
    CADRUMO_DARK,
    CADRUMO_DARK_THEME_NAME,
    CADRUMO_LIGHT,
    CADRUMO_LIGHT_THEME_NAME,
)
from ..modelo.routes import MODELO_WORKSPACE_DESTINATIONS
from ..modelo.view.controller import ModeloWorkspaceReadSession, admit_workspace_session
from ..modelo.view.models import ModeloWorkspaceDestinationIdV1

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_THEMES = (CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME)
_DESTINATIONS = [
    pytest.param(destination_id, id=destination_id.rsplit(".", 1)[-1])
    for destination_id in MODELO_WORKSPACE_DESTINATIONS
]


@pytest.fixture(scope="module")
def workspace_session(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ModeloWorkspaceReadSession]:
    """One admitted session, read-only for every assertion in this module."""
    root = tmp_path_factory.mktemp("themed")
    with real_workspace_inspection_result(root) as seeded:
        session, refusal = admit_workspace_session(seeded.result)
        assert refusal is None, f"expected an admitted projection, got: {refusal}"
        assert session is not None
        yield session


_TEXT_NODE = re.compile(r">([^<>]*)</text>")


async def _observe(
    destination_id: ModeloWorkspaceDestinationIdV1, session: ModeloWorkspaceReadSession, theme: str
) -> tuple[tuple[str, ...], tuple[str | None, ...]]:
    """Return one destination's readable glyphs and keyboard order under a theme.

    Read from the exported frame's TEXT NODES rather than from each widget's
    renderable. A renderable stringifies to an object repr carrying a memory
    address, so comparing those compares identities and differs on every run --
    it would fail whatever the themes did, which is a test that cannot pass
    rather than a gate that can fail. The exported frame is also the honest
    subject: it is what the compositor actually put on the screen, after
    layout and clipping, which is what an operator reads.
    """
    app = ScreenHostApp(MODELO_WORKSPACE_DESTINATIONS[destination_id](session))
    async with app.run_test(size=TERMINAL_ORDINARY) as pilot:
        # The theme must be active BEFORE the destination mounts, and a fresh
        # screen is pushed to guarantee it. The shared host resolves the theme
        # inside its own on_mount and only then pushes, so simply assigning
        # `app.theme` afterwards re-applies CSS to a screen whose mount-time
        # work already ran under the default appearance -- which makes both
        # observations identical whatever the themes do. That is not a
        # theoretical ordering concern: written the other way round, this
        # module passed with theme-dependent WORDING injected into a
        # destination header.
        app.theme = theme
        await pilot.pause()
        await app.push_screen(MODELO_WORKSPACE_DESTINATIONS[destination_id](session))
        await pilot.pause()
        glyphs: tuple[str, ...] = tuple(str(match.group(1)) for match in _TEXT_NODE.finditer(app.export_screenshot()))
        focus_ids: list[str | None] = []
        for widget in app.screen.focus_chain:
            widget_id = widget.id
            assert widget_id is None or isinstance(widget_id, str), (
                f"a focusable widget reported a non-string id: {widget_id!r}"
            )
            focus_ids.append(widget_id)
        order: tuple[str | None, ...] = tuple(focus_ids)
        app.exit(None)
    return glyphs, order


@pytest.mark.asyncio
@pytest.mark.parametrize("destination_id", _DESTINATIONS)
async def test_a_destination_reads_and_navigates_identically_under_both_themes(
    destination_id: ModeloWorkspaceDestinationIdV1,
    workspace_session: ModeloWorkspaceReadSession,
) -> None:
    """Appearance may change the palette; it may not change the content."""
    light_text, light_order = await _observe(destination_id, workspace_session, _THEMES[0])
    dark_text, dark_order = await _observe(destination_id, workspace_session, _THEMES[1])

    assert light_order == dark_order, (
        f"{destination_id} offers a different keyboard order per theme: {light_order} vs {dark_order}"
    )
    differing = [pair for pair in zip(light_text, dark_text, strict=False) if pair[0] != pair[1]]
    assert not differing, (
        f"{destination_id} paints different text per theme, so something is being said with colour "
        f"in one and words in the other: {differing[:3]}"
    )
    assert len(light_text) == len(dark_text), (
        f"{destination_id} mounts {len(light_text)} widgets under one theme and {len(dark_text)} under the other"
    )


def test_the_two_themes_are_actually_different_palettes() -> None:
    """The control for every assertion above.

    Identical text across themes proves nothing if the themes are the same
    theme. This fails if the two shipped appearances ever converge, which
    would otherwise turn this whole module green and meaningless -- the
    classic shape of a gate that passes because its stimulus stopped varying.
    """
    assert CADRUMO_LIGHT.name != CADRUMO_DARK.name, "the two appearances are one theme under two names"
    assert CADRUMO_LIGHT.dark != CADRUMO_DARK.dark, "both appearances declare the same lightness"
    assert CADRUMO_LIGHT.background != CADRUMO_DARK.background, (
        "the two appearances share a background, so switching between them changes nothing to compare"
    )
