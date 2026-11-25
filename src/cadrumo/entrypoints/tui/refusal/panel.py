"""One refusal, as served: its words, then its ways out in served order, or the words saying there is none.

The panel authors no wording of its own beyond two chrome reasons. A way out
the backend served no words for gets no control, never an invented label and
never a command line. A way out no admitted TUI destination hosts is shown
with its served words, disabled, beside the generic reason. A way served as
needing arguments is marked so and never presented as certain. A terminal or
operator-decision outcome is its served words and no control. The panel never
submits: choosing a control posts the intent to open its destination, and the
host that admits destinations opens it.

A surface shows a refusal through a :class:`RefusalSlot`, which asks its host
for the router of the destinations it admits; a host that admits none leaves
every way out disabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Protocol, override, runtime_checkable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Static

from ....core.i18n.render import tr
from ..components.language import localized
from ..components.theme import tokenised
from .intent import RefusalIntentV1, RefusalRouterV1, no_route
from .served import RefusalWayRoleV1, ServedRefusalV1, ServedWordsV1, refusal_ways

_CONDITIONAL_MARK = " …"
"""Appended to a control served as needing arguments; the panel's note says what it means."""


@dataclass(frozen=True, slots=True)
class RefusalControlV1:
    """One control the panel draws, in served order."""

    role: RefusalWayRoleV1
    words: ServedWordsV1
    conditional: bool
    #: ``None`` when no admitted destination hosts the action: drawn disabled.
    intent: RefusalIntentV1 | None


def refusal_controls(refusal: ServedRefusalV1, route: RefusalRouterV1) -> tuple[RefusalControlV1, ...]:
    """Return one control per served way out that the backend worded, in served order."""
    controls: list[RefusalControlV1] = []
    for way in refusal_ways(refusal):
        if way.words is None:
            continue
        controls.append(
            RefusalControlV1(role=way.role, words=way.words, conditional=way.conditional, intent=route(way))
        )
    return tuple(controls)


class RefusalPanel(Vertical):
    """Render one served refusal and offer its ways out without submitting anything."""

    DEFAULT_CSS: ClassVar[str] = tokenised("""
    RefusalPanel { height: auto; padding: $cadrumo-space-0 $cadrumo-space-1; }
    RefusalPanel .refusal-actions { height: auto; }
    RefusalPanel .refusal-action { margin-right: $cadrumo-space-1; }
    RefusalPanel .refusal-note { color: $text-muted; }
    """)

    class ActionChosen(Message):
        """The operator chose a routable way out; the host opens its destination."""

        def __init__(self, intent: RefusalIntentV1) -> None:
            """Carry the intent the chosen control resolved to."""
            super().__init__()
            self.intent = intent

    def __init__(
        self,
        refusal: ServedRefusalV1,
        *,
        route: RefusalRouterV1,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Retain the served refusal and resolve its controls once."""
        super().__init__(id=id, classes=classes)
        self._refusal = refusal
        self._controls = refusal_controls(refusal, route)

    @property
    def controls(self) -> tuple[RefusalControlV1, ...]:
        """Return the controls the panel draws, in served order."""
        return self._controls

    @override
    def compose(self) -> ComposeResult:
        refusal = self._refusal
        if refusal.refusal_words is not None:
            yield Static(refusal.refusal_words.words, id="refusal-words", markup=False)
        if refusal.no_recovery_words is not None:
            yield Static(refusal.no_recovery_words.words, id="refusal-no-recovery", markup=False)
        if not self._controls:
            return
        with Horizontal(classes="refusal-actions"):
            for index, control in enumerate(self._controls):
                label = control.words.words + (_CONDITIONAL_MARK if control.conditional else "")
                yield Button(
                    label,
                    id=f"refusal-action-{index}",
                    name=control.role,
                    variant="primary" if control.role == "primary" else "default",
                    disabled=control.intent is None,
                    classes="refusal-action",
                )
        if any(control.conditional for control in self._controls):
            yield localized(
                Static(tr("tui.refusal.action_needs_details"), id="refusal-needs-details", classes="refusal-note"),
                "tui.refusal.action_needs_details",
            )
        if any(control.intent is None for control in self._controls):
            yield localized(
                Static(tr("tui.refusal.action_unroutable"), id="refusal-unroutable", classes="refusal-note"),
                "tui.refusal.action_unroutable",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Post the chosen control's intent; a disabled control never reaches here."""
        button_id = event.button.id or ""
        if not button_id.startswith("refusal-action-"):
            return
        event.stop()
        intent = self._controls[int(button_id.removeprefix("refusal-action-"))].intent
        if intent is not None:
            self.post_message(self.ActionChosen(intent))


@runtime_checkable
class RefusalHostV1(Protocol):
    """The app that admits destinations and opens the one a chosen way out leads to."""

    async def refusal_router(self, refusal: ServedRefusalV1, /) -> RefusalRouterV1:
        """Return the router of the destinations this host admits for ``refusal``'s ways out."""
        ...


class RefusalSlot(Vertical):
    """The place a surface shows its current refusal, or nothing.

    Showing the refusal already shown changes nothing, so a surface may show
    it again on every repaint without rebuilding the panel.
    """

    DEFAULT_CSS: ClassVar[str] = """
    RefusalSlot { height: auto; }
    """

    def __init__(
        self, refusal: ServedRefusalV1 | None = None, *, id: str | None = None, classes: str | None = None
    ) -> None:
        """Hold ``refusal`` to show once mounted, or start empty."""
        super().__init__(id=id, classes=classes)
        self._refusal: ServedRefusalV1 | None = refusal
        self._showing = False

    @property
    def refusal(self) -> ServedRefusalV1 | None:
        """Return the refusal shown, or held to be shown once mounted, or ``None``."""
        return self._refusal

    def on_mount(self) -> None:
        """Show the refusal given before the slot was mounted."""
        self._showing = True
        if self._refusal is not None:
            self.run_worker(self._replace(self._refusal), group="refusal-slot", exclusive=True)

    def show(self, refusal: ServedRefusalV1 | None) -> None:
        """Show ``refusal`` in place of whatever was shown, or nothing for ``None``."""
        if refusal == self._refusal:
            return
        if not self._showing:
            self._refusal = refusal
            return
        self._refusal = refusal
        self.run_worker(self._replace(refusal), group="refusal-slot", exclusive=True)

    async def _replace(self, refusal: ServedRefusalV1 | None) -> None:
        route: RefusalRouterV1 = no_route
        host = self.app
        if refusal is not None and isinstance(host, RefusalHostV1):
            route = await host.refusal_router(refusal)
        await self.remove_children()
        if refusal is not None:
            await self.mount(RefusalPanel(refusal, route=route))


__all__ = ["RefusalControlV1", "RefusalHostV1", "RefusalPanel", "RefusalSlot", "refusal_controls"]
