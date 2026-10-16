"""A stand-in agent peer for the host's containment: read the frame, answer, await stop.

Modes: ``ready`` answers ready; ``chatty`` fills its standard error far past a
pipe's capacity and then answers ready; ``future`` answers ready under a hosting
contract this host does not speak; ``refuse`` answers a refusal; ``silent`` never
answers. Every one of these records what it received (provider ids and a digest
of the frame, never the frame), its environment and its arguments, and in
``ready`` mode starts a grandchild that only the job can end.

The ``native_*`` modes act as the native interpreter host does when it refuses
a launch: they read nothing, write to standard error and exit before any ready
line. ``native_refusal`` writes noise and then the host's refusal line and exits
125; ``native_unreadable`` exits 125 after a last line that is not the host's;
``native_other_exit`` writes the host's line but exits 1, which is not a refusal
by the host.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Final

NATIVE_REFUSAL_SUBJECT: Final = "SLOT_NAME"
NATIVE_REFUSAL_LINE: Final = (
    b'{"native_refusal": "launch_value_malformed", "subject": "' + NATIVE_REFUSAL_SUBJECT.encode("ascii") + b'"}\n'
)
NATIVE_NOISE_LINE: Final = b"the host noted a value its profile does not admit\n"
NATIVE_UNREADABLE_LINE: Final = b"not the host's line: S3CRET-VALUE-IN-PLAIN-TEXT\n"
CHATTY_BYTES: Final = 1024 * 1024
"""Far more than a pipe holds, so an unread standard error would block the writer."""


def _exit_as_the_native_host(mode: str) -> None:
    """Write what the native host writes for this mode and exit with its status, without reading anything."""
    stream = sys.stderr.buffer
    if mode == "native_refusal":
        stream.write(NATIVE_NOISE_LINE + NATIVE_REFUSAL_LINE)
    elif mode == "native_unreadable":
        stream.write(NATIVE_NOISE_LINE + NATIVE_UNREADABLE_LINE)
    else:
        stream.write(NATIVE_REFUSAL_LINE)
    stream.flush()
    # os._exit: the host's status, with no Python finalization to alter it.
    os._exit(125 if mode in {"native_refusal", "native_unreadable"} else 1)


def main() -> None:
    """Run one mode against the record directory named on the command line."""
    mode, record = sys.argv[1], Path(sys.argv[2])
    if mode.startswith("native_"):
        _exit_as_the_native_host(mode)
    frame = sys.stdin.buffer.readline()
    document = json.loads(frame) if frame.strip() else {}
    providers = sorted(document.get("credentials", {}))
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
                "bearer_sha256": (
                    hashlib.sha256(document["gateway_bearer"].encode()).hexdigest()
                    if "gateway_bearer" in document
                    else None
                ),
                "environment": dict(os.environ),
                "arguments": sys.argv,
                "grandchild": None if grandchild is None else grandchild.pid,
            }
        ),
        encoding="utf-8",
    )
    if mode == "chatty":
        sys.stderr.buffer.write(b"x" * CHATTY_BYTES)
        sys.stderr.buffer.flush()
    if mode == "diagnostics":
        # The hosted root arrives as an argument: this stand-in also runs by path, outside the package.
        logs = Path(sys.argv[3]) / "home" / "runtime"
        logs.mkdir(parents=True, exist_ok=True)
        diagnostic = {
            "schema": "cadrumo-agent.log/1",
            "pid": os.getpid(),
            "seq": 1,
            "timestamp": "2026-10-14T12:30:15.123+00:00",
            "level": "DEBUG",
            "service": "gateway",
            "name": "cadrumo_agent.gateway",
            "message": "gateway live probe",
        }
        line = json.dumps(diagnostic) + "\n"
        sys.stderr.write(line)
        sys.stderr.flush()
        (logs / "gateway.log").write_text(line, encoding="utf-8")
        worker_program = """
import json, os, sys
from pathlib import Path
entry = {"schema": "cadrumo-agent.log/1", "pid": os.getpid(), "seq": 1,
         "timestamp": "2026-10-14T12:30:15.124+00:00", "level": "ERROR",
         "service": "worker", "name": "cadrumo_agent.worker", "message": "worker relayed probe"}
line = json.dumps(entry) + "\\n"
root = Path(sys.argv[1])
(root / "worker.log").write_text(line, encoding="utf-8")
(root / "worker-autospawn-54321.stderr.log").write_text(line, encoding="utf-8")
sys.stdout.write(line)
"""
        relayed = subprocess.run(  # noqa: S603 -- fixed diagnostic fixture under the real contained interpreter
            [sys.executable, "-c", worker_program, str(logs)], check=True, capture_output=True
        ).stdout
        # The agent relays its worker's records on its own standard error; the files are only copies.
        sys.stderr.buffer.write(relayed)
        sys.stderr.flush()
    if mode in {"ready", "chatty", "diagnostics"}:
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
