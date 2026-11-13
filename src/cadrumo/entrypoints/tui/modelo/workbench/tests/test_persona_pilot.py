"""Every return each canonical persona owes, taken through calculate, check and export in the Modelo workbench.

Each case replays one persona into its registered profile at every registry
horizon its returns are reported at, and drives each return it owes through the
workbench's own keys over that profile (see :mod:`.persona_pilot`). The figures
the workbench shows must equal the persona's stated values; an owed return with
grounded values must also check complete and export, as the persona table holds
it. With ``PERSONA_PILOT_OUT`` set, the persona's line and one line per return
are appended there in the frontend intake's shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ......tests.personas import persona_ids
from .persona_pilot import row_failures, run_persona, write_rows

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("persona_id", persona_ids())
def test_each_owed_return_matches_the_persona_in_the_workbench(tmp_path: Path, persona_id: str) -> None:
    loaded, rows = run_persona(persona_id, tmp_path)
    write_rows([loaded, *(row for _, row in rows)])

    failures = [failure for plan, row in rows for failure in row_failures(plan, row)]
    assert loaded.loads, f"{persona_id} did not load: {loaded.reason()}"
    assert rows, f"{persona_id} owes no return the workbench could take"
    assert not failures, "\n".join(failures)
