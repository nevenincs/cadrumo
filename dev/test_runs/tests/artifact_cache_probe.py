"""A standalone command consumer of the shared source-scan cache."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from cadrumo.tests.run_artifact import RUN_ARTIFACT_ROOT_ENV, run_artifact_root
from dev.quality.shared_scan import shared_scan_result


def main() -> None:
    """Scan real input bytes without pytest initializing the process environment."""
    source = Path(sys.argv[1])
    result = shared_scan_result(
        "cli-cache-probe",
        root=source.parent,
        inputs=lambda: (source,),
        scanner="cli-cache-probe-v1",
        compute=lambda: tuple(source.read_text(encoding="utf-8").splitlines()),
    )
    print(
        json.dumps(
            {
                "lines": result,
                "artifact_environment": os.environ.get(RUN_ARTIFACT_ROOT_ENV),
                "logged_artifact_root": str(run_artifact_root())
                if bool(os.environ.get("CADRUMO_DEV_RUN_ROOT"))
                else None,
            }
        )
    )


if __name__ == "__main__":
    main()
