"""Opt-in session-owned live CLI runner; real custody/client, no test overrides.

Uses the isolated synthetic profile handed off by Session 02. Its password stays
in DPAPI and the approved anonymous descriptor channel. Never run under pytest.
"""

from __future__ import annotations

import asyncio
import json
import os
import runpy
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout, suppress
from pathlib import Path


def main() -> None:
    if sys.platform != "win32":
        raise RuntimeError("this live runner requires the Windows desktop")
    print(json.dumps({"stage": "starting", "terminal": sys.stdin.isatty()}), flush=True)
    workspace = Path(__file__).resolve().parents[6]
    root = workspace / "var/storage/session02-google-live"
    private = root / "session01-driver"
    private.mkdir(exist_ok=True)
    os.environ.update(
        {
            "CADRUMO_AUTHORITY_ROOT": str(workspace / ".authority"),
            "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
            "CADRUMO_SECRET_STORE_DIR": str(root / "secrets"),
            "CADRUMO_OUTPUT_LANGUAGE": "en",
            "CADRUMO_LOG_DIR": str(root / "logs"),
        }
    )
    os.environ.pop("CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE", None)
    import win32api
    import win32crypt
    import win32job

    from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
    from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
    from cadrumo.application.runtime.contracts import RuntimeClientHello
    from cadrumo.domain.calculations.registry.authority import published_authority_generation
    from cadrumo.entrypoints.cli.bootstrap import main as cli_main

    mode = sys.argv[1]
    commands = {
        "status": ["config", "google", "status"],
        "oauth": ["config", "google", "login"],
        "probe": ["config", "google", "probe", "--read-only"],
        "probe-write": ["config", "google", "probe"],
        "folder": ["config", "google", "folder", "view"],
        "archive-dry": [
            "config",
            "profile",
            "archive",
            "push",
            "--namespace",
            "cadrumo.google.drive.config",
            "--dry-run",
        ],
        "archive": ["config", "profile", "archive", "push", "--namespace", "cadrumo.google.drive.config"],
    }
    if mode not in {*commands, "resume", "reconcile", "organize", "review"}:
        raise ValueError("unsupported live acceptance mode")
    if mode in {"oauth", "resume"} and not sys.stdin.isatty():
        raise RuntimeError("OAuth requires the real controlling terminal")
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    job = win32job.CreateJobObject(None, "")
    limits = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
    limits["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)
    with (private / "runtime.log").open("ab") as log:
        log_offset = log.tell()
        process = subprocess.Popen(  # noqa: S603 -- exact supported runtime path and fixed arguments; no shell.
            [
                str(workspace / ".venv/Scripts/cadrumo-runtime.exe"),
                "--storage-root",
                str(root),
                "--storage-identity",
                endpoint.storage_identity,
                "--expected-version",
                "0.5.1",
                "--supervised",
            ],
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=log,
            creationflags=0x08000000,  # Windows CREATE_NO_WINDOW; runtime is supervised through pipes.
        )
        try:
            process_handle = win32api.OpenProcess(0x0101, False, process.pid)
            try:
                win32job.AssignProcessToJobObject(job, process_handle)
            finally:
                process_handle.Close()
            ready = False
            readiness_deadline = time.monotonic() + 600
            while time.monotonic() < readiness_deadline:
                if process.poll() is not None:
                    break
                try:
                    connection = asyncio.run(
                        RuntimeLaunchDoor(
                            endpoint,
                            expected=RuntimeClientHello(
                                product_version="0.5.1",
                                storage_identity=endpoint.storage_identity,
                                authority_generation=published_authority_generation(),
                            ),
                        ).open(timeout=2)
                    )
                except Exception:
                    time.sleep(0.5)
                else:
                    observed_boot = str(connection.hello.boot_id)
                    connection.close()
                    # Another developer may own this storage endpoint. A valid
                    # handshake alone does not make that runtime ours to use.
                    with (private / "runtime.log").open("rb") as owned_log:
                        owned_log.seek(log_offset)
                        records = owned_log.read().decode("utf-8").splitlines()
                    owned_boots = set()
                    for line in records:
                        try:
                            record = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(record, dict) and record.get("type") == "ready":
                            owned_boots.add(record.get("boot_id"))
                    if observed_boot not in owned_boots:
                        time.sleep(0.5)
                        continue
                    ready = True
                    break
            print(json.dumps({"stage": "runtime", "ready": ready, "terminal": sys.stdin.isatty()}), flush=True)
            if not ready:
                raise RuntimeError("runtime readiness failed")
            if mode in {"resume", "reconcile", "organize", "review"}:
                script = (
                    private / "review_google.py"
                    if mode == "review"
                    else private / "organize_google.py"
                    if mode == "organize"
                    else private / "resume_google.py"
                    if mode == "resume"
                    else root / "session02-driver/reconcile_operations.py"
                )
                runpy.run_path(str(script), run_name="__main__")
                return
            secret = win32crypt.CryptUnprotectData(
                (root / "session02-driver/synthetic-profile-input.dpapi").read_bytes(), None, None, None, 0
            )[1].decode()
            read_fd, write_fd = os.pipe()
            os.write(write_fd, json.dumps({"profile_passphrase": secret}).encode())
            os.close(write_fd)
            del secret
            sys.argv = [
                "aeat",
                "--format",
                "json",
                "--profile",
                "Session02 Google Review",
                "--profile-secrets-fd",
                str(read_fd),
                *commands[mode],
            ]
            print(json.dumps({"stage": "cli", "action": mode}), flush=True)
            exit_code = 0
            with (
                (private / f"{mode}.json").open("w", encoding="utf-8") as out,
                (private / f"{mode}.stderr").open("w", encoding="utf-8") as err,
            ):
                try:
                    with redirect_stdout(out), redirect_stderr(err):
                        cli_main()
                except SystemExit as error:
                    exit_code = error.code
                finally:
                    with suppress(OSError):
                        os.close(read_fd)
            print(json.dumps({"stage": "settled", "exit_code": exit_code}), flush=True)
        finally:
            endpoint.close()
            if process.poll() is None:
                control = process.stdin
                if control is None:
                    raise RuntimeError("owned runtime lost its supervisor input")
                control.write(b'{"type":"stop"}\n')
                control.flush()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    win32job.TerminateJobObject(job, 1)
                    process.wait(timeout=10)
            job.Close()
            print(json.dumps({"stage": "runtime_stopped", "exit_code": process.returncode}), flush=True)


if __name__ == "__main__":
    main()
