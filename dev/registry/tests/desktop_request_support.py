"""Run the desktop Assets forms' own request builders, as they ship, from Python.

The window builds every create, correct, baja and forecast request from what a
person types, through its form fields and request builders. Both the contract
test and the creation corpus need the real output of those builders, so this
module bundles the frontend's entry with the frontend's own esbuild and runs it
under Node on the scenarios it is given. The payments a request names come in
with the scenarios: the caller supplies the ledger's own account of them, so a
request is built against a payment the register really holds.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from dev.paths import REPO_ROOT

FRONTEND = REPO_ROOT / "native" / "desktop" / "frontend"
ENTRY = FRONTEND / "tests" / "support" / "assetRequests.ts"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0

_BUNDLE_SCRIPT = """
const esbuild = require(process.argv[1]);
esbuild.buildSync({
  entryPoints: [process.argv[2]],
  outfile: process.argv[3],
  bundle: true,
  platform: "node",
  format: "cjs",
  tsconfig: process.argv[4],
  logLevel: "error",
});
"""


def node() -> str:
    """The Node program that runs the bundled builders."""
    found = shutil.which("node")
    if found is None:
        raise AssertionError("node is needed to run the desktop request builders, and was not found")
    return found


def bundle(work: Path) -> Path:
    """Bundle the frontend's request-builder entry into one CommonJS file under ``work``."""
    esbuild = FRONTEND / "node_modules" / "esbuild"
    if not esbuild.is_dir():
        raise AssertionError(f"the desktop frontend's dependencies are not installed under {FRONTEND}")
    out = work / "assetRequests.cjs"
    subprocess.run(  # noqa: S603 - fixed node program on repository files
        [node(), "-e", _BUNDLE_SCRIPT, str(esbuild), str(ENTRY), str(out), str(FRONTEND / "tsconfig.json")],
        check=True,
        capture_output=True,
        text=True,
        creationflags=NO_WINDOW,
    )
    return out


def run(
    built: Path,
    scenarios: list[dict[str, Any]],
    *,
    served: dict[str, Any],
    limits: dict[str, Any],
    candidate: dict[str, Any],
    further: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Run the bundled builders on ``scenarios``, keyed by each scenario's name."""
    done = subprocess.run(  # noqa: S603 - fixed node program on a bundle built above
        [node(), str(built)],
        input=json.dumps(
            {
                "served": served,
                "limits": limits,
                "candidate": candidate,
                "further": further,
                "scenarios": scenarios,
            }
        ),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        creationflags=NO_WINDOW,
    )
    return {item["id"]: item for item in json.loads(done.stdout)}
