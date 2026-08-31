"""Real behavior proof for the public journal and replay devtool modules.

The public-module ownership and import-graph proof for the whole devtools
package lives in the development test tree's
``test_public_devtool_homes.py``: it is a repo-wide scan across
``src/cadrumo``, ``dev`` and ``packaging`` together, so it cannot mean the
same thing scoped to ``src`` alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..journal import Session, read_session, write_session
from ..replay import replay, screenshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_public_journal_and_replay_modules_render_the_live_registration_surface(tmp_path: Path) -> None:
    """Persist, replay, and export one real compositor frame through public homes."""
    session = Session(surface="registration", width=100, height=30, theme="dark", locale="en")
    journal_path = tmp_path / "session.jsonl"
    write_session(journal_path, session)

    restored = read_session(journal_path)
    assert restored == session

    frame = replay(restored)
    assert frame.surface == session.surface
    assert frame.width == session.width
    assert frame.height == session.height
    assert frame.text
    assert frame.chain

    screenshot_path = tmp_path / "frame.svg"
    assert screenshot(restored, str(screenshot_path)) == str(screenshot_path)
    assert "<svg" in screenshot_path.read_text(encoding="utf-8")
