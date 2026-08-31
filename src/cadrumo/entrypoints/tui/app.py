"""The root navigation join for one dedicated TUI session.

An area is mounted here only once it exposes a host-agnostic screen and its
cohort is green. Neither condition holds for any area yet: the profile,
secret and flow areas each expose a Textual application rather than a
mountable screen, and the Modelo area, which does expose screens, is held
back by its own cohort gate. This root therefore mounts no area and says so
on screen, rather than offering navigation to a destination that does not
exist.

The session's composed operation services are held here so that an area
receives them at mount time without reaching for a global; nothing in this
module constructs them, and nothing here wires a concrete adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Static

from ...core.i18n import tr
from .components.theme import BASE_CSS, install_cadrumo_themes, toggle_appearance, tokenised

if TYPE_CHECKING:
    from ...application.operations.composition import OperationComposedServices


class CadrumoTuiApp(App[None]):
    """Host one composed TUI session and whichever areas are joinable."""

    CSS = tokenised(BASE_CSS)

    BINDINGS: ClassVar = [
        Binding("f3", "toggle_appearance", "", show=False),
        Binding("q", "quit", "", show=False),
    ]

    def __init__(self, *, services: OperationComposedServices) -> None:
        """Bind the root to the operation services composed for this session."""
        super().__init__()
        self._services = services

    @property
    def services(self) -> OperationComposedServices:
        """The composed operation services an area receives when it mounts."""
        return self._services

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="root-shell"):
            yield Static(tr("tui.root.title"), id="root-title", markup=False)
            yield Static(tr("tui.root.no_areas"), id="root-no-areas", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        """Install the shared appearance for this session."""
        install_cadrumo_themes(self)

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance."""
        toggle_appearance(self)


__all__ = ["CadrumoTuiApp"]
