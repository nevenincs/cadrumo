"""`setup` starts on an interpreter that has no project dependencies installed.

`just setup` runs `python -m dev.init all` with `uv run --isolated --no-project`,
because the environment it creates does not exist yet. Everything that runs on
that interpreter before the sync - the shared dev path bootstrap and the
`env/.env` preflight - must therefore stay within the standard library and the
import-light product modules. A pydantic import there kills setup with
`ModuleNotFoundError` on every fresh checkout, CI included, while every test run
from the synchronized environment still passes.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest

from cadrumo.core.storage_environment import STORAGE_ROOT
from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Run in a fresh interpreter so this process's own imports cannot mask the
#: child's. Prints the third-party modules the bootstrap loaded.
_PROBE = """
import sys
from pathlib import Path
import dev._paths
from dev.env._dotenv import provision
import dev.init.plan
root = Path(sys.argv[1])
(root / "env").mkdir()
(root / "env" / ".env.example").write_text("KEY=\\n", encoding="utf-8")
status = provision(root, None)
loaded = sorted(name for name in ("pydantic", "pydantic_settings") if name in sys.modules)
print(status, ",".join(loaded))
"""


def test_the_pre_sync_bootstrap_loads_no_project_dependency(tmp_path: Path) -> None:
    """Importing the dev bootstrap and provisioning `env/.env` loads no third-party model library.

    Proved able to fail: restoring the taxonomy import in
    `cadrumo.core.storage_environment.prepare_temporary_directory`, and
    separately restoring the Google client staging call at the end of
    `dev.env._dotenv.provision`, each made this test alone fail on its
    `pydantic` assertion; reverting each made it pass.
    """
    # Pytest's run scratch makes the bootstrap skip temporary-root preparation,
    # so the child runs without it, against a storage root of its own.
    environment = {name: value for name, value in os.environ.items() if name != "CADRUMO_TEST_RUN_SCRATCH"}
    environment[STORAGE_ROOT.variable] = str(tmp_path / "storage")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    result = run_command(
        [sys.executable, "-c", _PROBE, str(checkout)],
        cwd=REPO_ROOT,
        environment=environment,
        errors="replace",
        timeout_seconds=120,
    )
    assert result.returncode == 0, result.stderr
    status, _, loaded = result.stdout.strip().rpartition("\n")[2].partition(" ")
    assert status == "0", result.stdout
    assert loaded == "", f"the pre-sync bootstrap imported {loaded}"
