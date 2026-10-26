"""Wait for an installation act screen to answer the act it started."""

from __future__ import annotations

from textual.pilot import Pilot

from cadrumo.entrypoints.tui.installation.act_screen import InstallationActScreen
from cadrumo.entrypoints.tui.tests.settling import settle_until


async def act_settled(pilot: Pilot[None], screen: InstallationActScreen) -> None:
    """Wait until the act the screen started has an answer and its controls are back."""

    def done() -> bool:
        worker = screen._act_worker
        return worker is not None and worker.is_finished and not screen._busy

    await settle_until(pilot, done, "the act worker to finish and the screen's controls to return", workers=False)
