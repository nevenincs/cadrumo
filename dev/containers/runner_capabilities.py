"""Verify a self-hosted runner carries every capability the workflows assume.

The Linux X64 runners are containers, so their capabilities are pinned by the
``runner`` stage of the repository-root ``Dockerfile`` and proven by
``just runner-image-test``. The macOS and Windows runners are HOST installs
with no image and, until this probe, no equivalent check at all — half the
fleet was unmodelled.

What "assumed" means here is measured, not guessed. Parsing the ``run:`` blocks
of every workflow shows ``uv``, ``just`` and ``node`` are each installed by a
pinned setup action, while ``gh`` is invoked by four workflows and installed by
none: ``packaging-campaign-trigger``, ``packaging-homebrew``,
``packaging-scoop`` and ``release-please``. Three of the four run on this
fleet, and its absence surfaces mid-lane as a command-not-found inside a step
that never names the missing tool.

The Homebrew acquisition matrix additionally pins an EXACT brew path per leg
(``/opt/homebrew/bin/brew`` on macOS arm64, ``/home/linuxbrew/.linuxbrew/bin/brew``
on both Linux legs) and fails its first step on ``test -x "$BREW_PATH"``. This
probe checks the same path the matrix declares, and additionally checks that it
resolves with no symlink indirection — a brew reached through a relocated prefix
passes ``test -x`` and ``--version`` and then fails ``brew link`` at the very end
of a real install, after building every resource.

Deliberately NOT checked: ``scoop``. ``packaging-scoop`` requests the
``windows-scoop`` label, which no runner on the fleet carries, so that lane never
schedules. Probing for it would report a failure that cannot affect any run.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Homebrew prefixes exactly as `packaging-homebrew.yml`'s matrix declares them.
_BREW_PATHS = {
    ("Darwin", "arm64"): Path("/opt/homebrew/bin/brew"),
    ("Linux", "x86_64"): Path("/home/linuxbrew/.linuxbrew/bin/brew"),
    ("Linux", "aarch64"): Path("/home/linuxbrew/.linuxbrew/bin/brew"),
}


@dataclass(frozen=True)
class Finding:
    """One capability result."""

    name: str
    ok: bool
    detail: str


def _machine() -> str:
    """Return the architecture token the workflow matrix compares against."""
    machine = platform.machine()
    # Windows reports AMD64; the matrix legs that pin arch are Darwin/Linux only.
    return {"AMD64": "x86_64", "arm64": "arm64", "aarch64": "aarch64"}.get(machine, machine)


def version_probe(executable: str) -> tuple[bool, str]:
    """Return whether an executable is usable, and a one-line description.

    Presence is not capability. This returned a DETAIL string for every
    outcome, including a binary that resolved but whose --version failed, and
    the caller marked the finding ok regardless - so a gh that could not run
    at all was reported as a carried capability, printed under an ok marker,
    and the probe exited 0. On a fleet where a job lands on whichever runner
    is free, that is the coin-flip failure this module exists to remove.
    """
    resolved = shutil.which(executable)
    if resolved is None:
        return False, "not on PATH"
    completed = subprocess.run(  # noqa: S603 - `shutil.which`-resolved executable, fixed argv
        [resolved, "--version"], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        return False, f"present at {resolved} but --version failed: {completed.stderr.strip()[:120]}"
    first = completed.stdout.strip().splitlines()
    return True, first[0] if first else resolved


def _check_gh() -> Finding:
    """`gh` is the one tool no workflow installs and four workflows invoke."""
    usable, detail = version_probe("gh")
    if not usable:
        return Finding(
            "gh",
            ok=False,
            detail=(
                f"{detail}. Four workflows invoke it and none install it; "
                "three of them run on this fleet, so their gh steps fail with "
                "a command-not-found that never names the missing tool."
            ),
        )
    return Finding("gh", ok=True, detail=detail)


def _check_brew() -> Finding | None:
    """Check the exact brew path this platform's matrix leg declares."""
    key = (platform.system(), _machine())
    expected = _BREW_PATHS.get(key)
    if expected is None:
        return None  # No Homebrew acquisition leg targets this platform.

    if not os.access(expected, os.X_OK):
        return Finding(
            "brew",
            ok=False,
            detail=(
                f"{expected} is not executable. packaging-homebrew's {key[0]}/{key[1]} leg "
                'fails its first step, "Verify declared Homebrew release row", on test -x.'
            ),
        )

    resolved = Path(expected).resolve()
    prefix_root = expected.parents[1]  # /opt/homebrew or /home/linuxbrew/.linuxbrew
    if prefix_root not in resolved.parents:
        return Finding(
            "brew",
            ok=False,
            detail=(
                f"{expected} resolves to {resolved}, outside {prefix_root}. Homebrew computes "
                "relative link traversals against the RESOLVED path, so a relocated prefix "
                "passes test -x and --version and then fails `brew link` at the very end of "
                "an install with 'Permission denied @ dir_s_mkdir'."
            ),
        )
    return Finding("brew", ok=True, detail=f"{expected} -> {resolved}")


def _check_docker_for_nested_smoke() -> Finding | None:
    """Linux runners drive nested smoke containers through the host socket."""
    if platform.system() != "Linux":
        return None
    resolved = shutil.which("docker")
    if resolved is None:
        return Finding("docker", ok=False, detail="not on PATH; packaging-smoke's container lane cannot run")
    completed = subprocess.run(  # noqa: S603 - `shutil.which`-resolved executable, fixed argv
        [resolved, "version", "--format", "{{.Server.Version}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return Finding(
            "docker",
            ok=False,
            detail="client present but the daemon does not answer; the nested clean-Linux proof cannot start",
        )
    return Finding("docker", ok=True, detail=f"daemon {completed.stdout.strip()}")


def main(argv: list[str] | None = None) -> int:
    """Report every capability finding, exiting non-zero on any failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="Report findings without failing the job (for an inventory pass).",
    )
    args = parser.parse_args(argv)

    print(f"runner: {platform.system()} {_machine()} ({platform.platform()})")
    print(f"python: {sys.version.split()[0]}\n")

    findings = [f for f in (_check_gh(), _check_brew(), _check_docker_for_nested_smoke()) if f is not None]

    for finding in findings:
        marker = "ok  " if finding.ok else "FAIL"
        print(f"{marker} {finding.name:<8} {finding.detail}")

    failures = [f for f in findings if not f.ok]
    if not failures:
        print("\nrunner carries every capability the workflows assume.")
        return 0

    print(f"\n{len(failures)} capability gap(s). Each is a coin-flip failure: a job lands on")
    print("whichever labelled runner is free, so a tool missing on one runner reproduces")
    print("only half the time.")
    return 0 if args.warn_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
