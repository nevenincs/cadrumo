"""Test-time guards shared by every TUI suite."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from textual.pilot import Pilot

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _clicks_must_land(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail a test whose simulated click did not reach its target.

    `Pilot.click` returns whether the press landed on the widget it was aimed
    at, and every call site in these suites discards that answer. A click that
    lands on whatever is painted at those coordinates instead -- because a
    layout change pushed the target under another widget, or left it only
    partly on screen -- then produces a failure at some later assertion about
    behaviour that never ran. That reads as a broken feature and costs the
    reader the real cause; it did exactly that here, where six rows of new
    section heading moved a button and the failure looked like a broken
    in-flight guard.

    A fully off-screen target already raises `OutOfBounds`, so this covers the
    quiet half. Tests that mean to click empty space can call
    `Pilot.click` through `pilot.app` or assert the boolean themselves.
    """
    original = Pilot.click

    async def guarded(self: Pilot[Any], *args: Any, **kwargs: Any) -> bool:
        landed = await original(self, *args, **kwargs)
        if not landed:
            target = args[0] if args else kwargs.get("widget")
            raise AssertionError(
                f"the simulated click on {target!r} did not land on it -- something else "
                f"is painted at those coordinates, so the handler under test never ran"
            )
        return landed

    monkeypatch.setattr(Pilot, "click", guarded)
    yield
