"""A stand-in agent peer for the host's containment: read the frame, answer, await stop.

Modes: ``ready`` answers ready; ``future`` answers ready under a hosting
contract this host does not speak; ``refuse`` answers a refusal; ``silent`` never
answers. Every mode records what it received (provider ids and a digest of the
frame, never the frame), its environment and its arguments, and in ``ready``
mode starts a grandchild that only the job can end.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    """Run one mode against the record directory named on the command line."""
    mode, record = sys.argv[1], Path(sys.argv[2])
    frame = sys.stdin.buffer.readline()
    providers = sorted(json.loads(frame)["credentials"]) if frame.strip() else []
    grandchild = None
    if mode == "ready":
        grandchild = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(600)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    (record / "received.json").write_text(
        json.dumps(
            {
                "frame_sha256": hashlib.sha256(frame).hexdigest(),
                "providers": providers,
                "environment": dict(os.environ),
                "arguments": sys.argv,
                "grandchild": None if grandchild is None else grandchild.pid,
            }
        ),
        encoding="utf-8",
    )
    if mode == "ready":
        answer = {"event": "agent_ready", "gateway_port": 47001, "agent_version": "0.0.0-test", "hosting_contract": 1}
    elif mode == "future":
        answer = {"event": "agent_ready", "gateway_port": 47001, "agent_version": "9.0.0-test", "hosting_contract": 2}
    elif mode == "refuse":
        answer = {"event": "refused", "code": "provider_unsupported"}
    else:
        time.sleep(600)
        return
    sys.stdout.buffer.write(json.dumps(answer).encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()
    sys.stdin.buffer.read()
    (record / "stopped").write_text("stdin closed", encoding="utf-8")


if __name__ == "__main__":
    main()
