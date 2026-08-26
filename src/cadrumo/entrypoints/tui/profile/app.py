"""The five-stage profile journey shell: Overview, Get data, Required, Review, Ready.

This is presentation state, not a second persisted wizard
(`2026-08-11-tui-interface-adr` D6): the current stage and body content are
recomputed from the injected :class:`ProfilePresentationV1` on every
navigation, and the app itself decides nothing about requiredness,
applicability, or readiness -- it renders D6's already-classified fields
through :mod:`journey_status`.

Only the active stage's body is ever mounted. Moving stages does not hide
the previous body behind CSS; it removes it from the DOM entirely and
mounts the next one, so an inactive stage's content is neither visible nor
focus-reachable -- a `display: none` panel a screen reader or a stray Tab
press can still land on is exactly the keyboard trap this shell must not
build.
"""

from __future__ import annotations

from enum import IntEnum
from typing import ClassVar, override

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Footer, Static

from ....application.user_profile.presentation import ProfilePresentationV1
from ....core.i18n import tr
from ..components.theme import BASE_CSS, install_cadrumo_themes, toggle_appearance
from ..components.widgets import ContentScroll, StageNavigationStrip
from .journey_status import ReadyStageBody, compose_required_stage, overview_readiness_summary


class ProfileJourneyStage(IntEnum):
    """The five ordered stages of the guided profile journey (D6)."""

    OVERVIEW = 0
    GET_DATA = 1
    REQUIRED = 2
    REVIEW = 3
    READY = 4


_STAGE_LABEL_KEYS: dict[ProfileJourneyStage, str] = {
    ProfileJourneyStage.OVERVIEW: "profile.journey.stage.overview",
    ProfileJourneyStage.GET_DATA: "profile.journey.stage.get_data",
    ProfileJourneyStage.REQUIRED: "profile.journey.stage.required",
    ProfileJourneyStage.REVIEW: "profile.journey.stage.review",
    ProfileJourneyStage.READY: "profile.journey.stage.ready",
}

_LAST_STAGE = max(ProfileJourneyStage)


class ProfileJourneyApp(App[None]):
    """Compose the guided five-stage journey with only the active body mounted."""

    CSS = (
        BASE_CSS
        + """
    #journey-actions { height: auto; align-horizontal: right; margin: 1 0 0 0; }
    #journey-actions Button { margin: 0 0 0 1; }
    """
    )

    BINDINGS: ClassVar = [
        Binding("f3", "toggle_appearance", "", show=False),
        Binding("q", "quit", "", show=False),
    ]

    def __init__(self, presentation: ProfilePresentationV1) -> None:
        """Bind the journey to one already-built presentation projection."""
        super().__init__()
        self._presentation = presentation
        self._stage = ProfileJourneyStage.OVERVIEW

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="journey-shell"):
            yield self._build_stage_strip()
            with ContentScroll(id="journey-body-host"), Vertical(id="journey-body"):
                pass
            with Horizontal(id="journey-actions"):
                yield Button(tr("profile.journey.action.previous"), id="btn-journey-previous")
                yield Button(tr("profile.journey.action.next"), id="btn-journey-next")
        yield Footer()

    def on_mount(self) -> None:
        """Install the shared theme and mount the first stage's body."""
        install_cadrumo_themes(self)
        body = self.query_one("#journey-body", Vertical)
        body.mount_all(self._stage_widgets())
        self._sync_actions()

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance."""
        toggle_appearance(self)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Move exactly one stage per press, never past either end."""
        if event.button.id == "btn-journey-previous" and self._stage > ProfileJourneyStage.OVERVIEW:
            self._stage = ProfileJourneyStage(self._stage - 1)
            await self._recompose_stage()
        elif event.button.id == "btn-journey-next" and self._stage < _LAST_STAGE:
            self._stage = ProfileJourneyStage(self._stage + 1)
            await self._recompose_stage()

    def _build_stage_strip(self) -> StageNavigationStrip:
        return StageNavigationStrip(
            [tr(_STAGE_LABEL_KEYS[stage]) for stage in ProfileJourneyStage],
            current_index=int(self._stage),
            id="journey-stages",
        )

    async def _recompose_stage(self) -> None:
        shell = self.query_one("#journey-shell", Vertical)
        host = self.query_one("#journey-body-host", ContentScroll)
        await self.query_one("#journey-stages", StageNavigationStrip).remove()
        await shell.mount(self._build_stage_strip(), before=host)
        body = self.query_one("#journey-body", Vertical)
        await body.remove_children()
        await body.mount_all(self._stage_widgets())
        self._sync_actions()

    def _sync_actions(self) -> None:
        self.query_one("#btn-journey-previous", Button).disabled = self._stage == ProfileJourneyStage.OVERVIEW
        self.query_one("#btn-journey-next", Button).disabled = self._stage == _LAST_STAGE

    def _stage_widgets(self) -> list[Widget]:
        if self._stage is ProfileJourneyStage.OVERVIEW:
            return [Static(overview_readiness_summary(self._presentation), id="overview-summary", markup=False)]
        if self._stage is ProfileJourneyStage.GET_DATA:
            return [Static(tr("profile.journey.get_data.placeholder"), id="get-data-placeholder", markup=False)]
        if self._stage is ProfileJourneyStage.REQUIRED:
            return list(compose_required_stage(self._presentation))  # type: ignore[arg-type]
        if self._stage is ProfileJourneyStage.REVIEW:
            return [Static(tr("profile.journey.review.placeholder"), id="review-placeholder", markup=False)]
        return [ReadyStageBody(self._presentation, id="ready-stage-body")]


__all__ = ["ProfileJourneyApp", "ProfileJourneyStage"]
