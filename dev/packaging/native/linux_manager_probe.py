"""Collect placement evidence on a disposable graphical Linux login.

Run this file with system Python: ``--check`` only reads current identity;
``--disposable-runner`` also creates three short-lived probe processes. This is
an architectural experiment, never installer or runtime acceptance evidence.
No login is registered and no application or user preferences are modified.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import select
import subprocess
import sys
import uuid
from pathlib import Path


def _text(library: ctypes.CDLL, name: str, argument: object) -> str:
    function = getattr(library, name)
    function.argtypes = [
        ctypes.c_int if isinstance(argument, int) else ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    function.restype = ctypes.c_int
    pointer = ctypes.c_void_p()
    result = function(argument, ctypes.byref(pointer))
    if result < 0:
        raise OSError(-result, f"{name}: {os.strerror(-result)}")
    if not pointer.value:
        raise RuntimeError(f"{name} returned an empty value")
    try:
        return ctypes.string_at(pointer).decode("utf-8", errors="strict")
    finally:
        libc = ctypes.CDLL(None)
        libc.free.argtypes = [ctypes.c_void_p]
        libc.free(pointer)


def observe(pid: int, pidfd: int) -> dict[str, object]:
    """Bracket native observations with liveness of the held process identity."""
    if select.select([pidfd], [], [], 0)[0]:
        raise RuntimeError("Observed process already exited")
    library = ctypes.CDLL("libsystemd.so.0")
    stat = Path(f"/proc/{pid}/stat").read_text()
    start = int(stat[stat.rindex(")") + 2 :].split()[19])
    status = Path(f"/proc/{pid}/status").read_text()
    fields = dict(line.split(":", 1) for line in status.splitlines())
    evidence: dict[str, object] = {
        "pid": pid,
        "start_ticks": start,
        "uids": [int(value) for value in fields["Uid"].split()],
        "effective_capabilities": int(fields["CapEff"].strip(), 16),
        "executable": os.readlink(f"/proc/{pid}/exe"),
        "cgroup": Path(f"/proc/{pid}/cgroup").read_text().splitlines(),
    }
    try:
        session = _text(library, "sd_pidfd_get_session", pidfd)
        evidence["session"] = session
        owner = ctypes.c_uint()
        function = library.sd_pidfd_get_owner_uid
        function.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint)]
        function.restype = ctypes.c_int
        result = function(pidfd, ctypes.byref(owner))
        if result < 0:
            raise OSError(-result, os.strerror(-result))
        evidence["owner_uid"] = owner.value
        for field in ("type", "class", "state"):
            evidence[field] = _text(library, f"sd_session_get_{field}", session.encode())
        for field in ("active", "remote"):
            function = getattr(library, f"sd_session_is_{field}")
            function.argtypes = [ctypes.c_char_p]
            function.restype = ctypes.c_int
            result = function(session.encode())
            if result < 0:
                raise OSError(-result, os.strerror(-result))
            evidence[field] = bool(result)
        if _text(library, "sd_pidfd_get_session", pidfd) != session:
            raise RuntimeError("Native session changed during observation")
    except OSError as error:
        # Missing session after placement is a result, never a fallback authority.
        evidence["native_identity_error"] = str(error)
    if select.select([pidfd], [], [], 0)[0]:
        raise RuntimeError("Observed process exited during observation")
    return evidence


def require_graphical(evidence: dict[str, object], uid: int) -> None:
    """Refuse absent, elevated, terminal, remote, or inactive native identity."""
    if (
        uid == 0
        or evidence.get("uids") != [uid] * 4
        or evidence.get("effective_capabilities") != 0
        or evidence.get("owner_uid") != uid
        or not isinstance(evidence.get("session"), str)
        or not evidence.get("session")
        or evidence.get("type") not in ("x11", "wayland")
        or evidence.get("class") != "user"
        or evidence.get("state") != "active"
        or evidence.get("active") is not True
        or evidence.get("remote") is not False
        or "native_identity_error" in evidence
    ):
        raise RuntimeError("A local, active, unelevated graphical logind session is required")


def _placement(mode: str) -> dict[str, object]:
    if sys.platform != "linux":
        raise RuntimeError("Linux is required")
    unit = f"cadrumo-placement-probe-{uuid.uuid4().hex}"
    child = [sys.executable, "-I", str(Path(__file__).resolve()), "--child"]
    command = child
    if mode != "direct":
        command = [
            "/usr/bin/systemd-run",
            "--user",
            "--quiet",
            "--no-ask-password",
            "--expand-environment=no",
            f"--unit={unit}",
        ]
        if mode == "scope":
            command += ["--scope", "--property=TimeoutStopUSec=4s"]
        else:
            command += [
                "--pipe",
                "--wait",
                "--service-type=exec",
                "--property=Restart=no",
                "--property=TimeoutStopSec=4s",
            ]
        command += ["--", *child]
    result: dict[str, object] = {"mode": mode, "command": command}
    # A live stdin handshake is necessary to observe the actual child while a
    # pidfd remains held. A collect-after-exit subprocess helper cannot do that.
    with subprocess.Popen(  # noqa: S603 - fixed native tools and this exact probe, no shell or user command.
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    ) as process:
        result["wrapper_pid"] = process.pid
        try:
            if process.stdout is None or process.stdin is None:
                raise RuntimeError("Probe pipes unavailable")
            if not select.select([process.stdout], [], [], 10)[0]:
                raise RuntimeError("Probe child announcement timed out")
            announcement = os.read(process.stdout.fileno(), 128)
            if not announcement.endswith(b"\n") or not announcement.strip().isdigit():
                raise RuntimeError("Probe child announcement is invalid")
            pid = int(announcement)
            with os.fdopen(os.pidfd_open(pid), "rb", buffering=0) as handle:
                result["child"] = observe(pid, handle.fileno())
                process.stdin.write(b"release\n")
                process.stdin.flush()
                result["wrapper_exit"] = process.wait(timeout=10)
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            result["error"] = str(error)
        finally:
            if mode != "direct":
                # Only the uniquely named transient unit created by this probe.
                try:
                    subprocess.run(  # noqa: S603 - fixed systemctl and locally generated unique unit.
                        [
                            "/usr/bin/systemctl",
                            "--user",
                            "--no-ask-password",
                            "stop",
                            unit + (".scope" if mode == "scope" else ".service"),
                        ],
                        timeout=8,
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except (OSError, subprocess.TimeoutExpired) as error:
                    result["cleanup_error"] = str(error)
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
    return result


def main() -> int:
    """Print refusal or bounded experiment observations as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only graphical-session preflight")
    parser.add_argument("--disposable-runner", action="store_true", help="Acknowledge disposable interactive runner")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.child:
        print(os.getpid(), flush=True)
        if select.select([sys.stdin], [], [], 15)[0]:
            os.read(sys.stdin.fileno(), 64)
        return 0
    report: dict[str, object] = {
        "acceptance": False,
        "purpose": "native placement identity experiment",
        "placements": [],
    }
    try:
        if sys.platform != "linux":
            raise RuntimeError("Linux is required")
        with os.fdopen(os.pidfd_open(os.getpid()), "rb", buffering=0) as handle:
            parent = observe(os.getpid(), handle.fileno())
        report["parent"] = parent
        require_graphical(parent, os.getuid())
        if not options.check:
            if not options.disposable_runner:
                raise RuntimeError("Explicit --disposable-runner is required for process placement")
            report["placements"] = [_placement(mode) for mode in ("direct", "scope", "pipe")]
        report["preflight"] = "passed"
    except (OSError, RuntimeError, AttributeError) as error:
        report["refusal"] = str(error)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if "refusal" in report else 0


if __name__ == "__main__":
    raise SystemExit(main())
