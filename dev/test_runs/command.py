"""Run a development command with a live, command-identified transcript."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT, UTF_8
from .paths import allocate_run_directory

_UTF_8: Final[str] = UTF_8


def run(command: tuple[str, ...], *, repository: Path, family: str, label: str) -> int:
    """Stream ``command`` while retaining its full transcript and metadata."""
    if not command:
        raise ValueError("a command is required")
    started = datetime.now(tz=UTC)
    run_dir = allocate_run_directory(repository, family=family, label=label, now=started)
    artifacts = run_dir / "artifacts"
    cache = run_dir / "cache"
    scratch = run_dir / "scratch"
    artifacts.mkdir(parents=True)
    cache.mkdir()
    scratch.mkdir()
    log_path = run_dir / "run.log"
    print(f"{label} run log: {log_path}", flush=True)

    environment = os.environ.copy()
    environment["CADRUMO_DEV_RUN_ROOT"] = str(run_dir)
    environment["CADRUMO_DEV_ARTIFACTS_DIR"] = str(artifacts)
    environment["CADRUMO_DEV_CACHE_DIR"] = str(cache)
    environment["CADRUMO_DEV_SCRATCH_DIR"] = str(scratch)
    environment["XDG_CACHE_HOME"] = str(cache)
    environment["TEMP"] = str(scratch)
    environment["TMP"] = str(scratch)
    environment["TMPDIR"] = str(scratch)
    with log_path.open("x", encoding=_UTF_8, newline="\n") as transcript:
        transcript.write(f"START {started.isoformat()} pid={os.getpid()}\n")
        transcript.write(f"COMMAND {' '.join(command)}\n")
        transcript.flush()
        process = subprocess.Popen(  # noqa: S603 - argv is the explicit operator command; shell=False.
            command,
            cwd=repository,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding=_UTF_8,
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            transcript.write(line)
            transcript.flush()
        exit_status = process.wait()
        finished = datetime.now(tz=UTC)
        transcript.write(f"FINISH {finished.isoformat()} exit={exit_status}\n")

    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "artifacts": str(artifacts),
                "cache": str(cache),
                "command": list(command),
                "exit_status": exit_status,
                "finished_at": finished.isoformat(),
                "label": label,
                "log": str(log_path),
                "run_id": run_dir.name,
                "scratch": str(scratch),
                "started_at": started.isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    print(f"{label} run log: {log_path} (exit={exit_status}, metadata={run_dir / 'run.json'})", flush=True)
    return exit_status


def main() -> int:
    """Parse the evidence family/label and execute the remaining argv."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = tuple(args.command)
    if command[:1] == ("--",):
        command = command[1:]
    return run(command, repository=REPO_ROOT, family=args.family, label=args.label)


if __name__ == "__main__":
    sys.exit(main())
