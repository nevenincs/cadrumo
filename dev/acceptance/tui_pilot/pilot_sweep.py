"""Collector of the TUI column: every return the persona table reports for each persona, driven through the workbench.

This module is not a test of the suite. A run names it explicitly to pytest, which collects it in spite of its
name; the suite never does. Each case replays one persona and drives each return the persona table's rows file
(``TUI_PILOT_TABLE_ROWS``) reports for it through the Modelo workbench's own keys (see :mod:`.pilot`). With
``PERSONA_PILOT_OUT`` set, the persona's line and one line per return are appended there in the frontend intake's
shape, each as soon as it is known, with ``PERSONA_PILOT_TREE`` as the tree it ran. A case fails when the persona
does not load, owes nothing the table reports, or a reported row differs from the table's row; a crash inside one
return is that return's row and does not end the persona's other returns.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.tests.personas import persona_ids

from .pilot import run_failures, run_persona

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("persona_id", persona_ids())
def test_each_reported_return_matches_the_table_in_the_workbench(tmp_path: Path, persona_id: str) -> None:
    """Replay one persona and drive every return the table reports for it through the workbench."""
    run = run_persona(persona_id, tmp_path)

    failures = run_failures(run)
    if not run.loaded.loads:
        pytest.fail(f"{persona_id} did not load: {run.loaded.reason()}")
    if not run.reported:
        pytest.fail(f"the table reports no return of {persona_id}")
    if failures:
        pytest.fail("\n".join(failures))
