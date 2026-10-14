"""Start the runtime server adapter's detached child from a synthetic launcher and record both process ids."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from cadrumo.adapters.outbound.model_runtime.process_control import spawn_runtime_server

#: The file the launcher's working directory must hold. The adapter starts
#: ``<executable> serve``, so an interpreter given this script stands in for a
#: runtime server that stays up until something ends it.
SERVER_SCRIPT_NAME = "serve"
SERVER_SCRIPT = "import time\ntime.sleep(120)\n"


def _main(record: Path) -> None:
    server = spawn_runtime_server(Path(sys.executable), dict(os.environ))
    record.write_text(json.dumps({"launcher": os.getpid(), "server": server}), encoding="utf-8")


if __name__ == "__main__":
    _main(Path(sys.argv[1]))
