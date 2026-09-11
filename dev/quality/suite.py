#!/usr/bin/env python
"""Consolidated blocking code-quality dashboard for the build harness.

Runs every fast static quality gate to completion (not fail-fast), then
reports signal only:

* On full success: silent, exit 0. Green gates are not reported.
* On any failure: a compact dashboard naming each failing gate, replaying
  its actionable output, and listing the gates that passed by name only,
  then exit 1.

Each gate invokes its underlying tool directly (no ``just`` re-entry, no
nested ``uv run``): this process is already started via ``uv run --no-sync
python -m dev.quality.suite``, so the active venv's console scripts
(``ruff`` and ``deptry``) resolve by bare name; the import-quality row calls
the authoritative Python driver, which resolves Import Linter itself, and
``sys.executable`` names the venv interpreter for the Python-module gates.
This script aggregates pass/fail and surfaces the failing detail.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Final

from dev._paths import UTF_8

_UTF_8: Final[str] = UTF_8

# Each gate's underlying command, kept byte-identical to the tool invocation
# the matching `just check-*` recipe wraps (see justfile). Direct invocation
# here is deliberately independent of the recipe wrapper (`dev.quality.quiet`
# for the bare-tool gates): that wrapper's job — stay silent on success,
# replay on failure — is already `main()`'s job for the dashboard, so
# duplicating it here would be redundant, not protective.
GATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("check-style", ("ruff", "check", ".")),
    ("check-format", ("ruff", "format", "--check", ".")),
    ("check-types", (sys.executable, "-m", "dev.quality.types")),
    ("check-import-boundaries", (sys.executable, "-m", "dev.quality.import_gate")),
    (
        "check-dependency-declarations",
        (
            "deptry",
            "src/cadrumo",
            # The harness package ships its own console script and is where the
            # MCP and anyio dependencies are actually imported. Leaving it out
            # reported both as declared-but-unused: a scan-scope artefact, not
            # a real unused dependency.
            "src/cadrumo_harness",
            "dev/registry",
            "--known-first-party",
            "cadrumo",
            "--known-first-party",
            "cadrumo_harness",
            "--known-first-party",
            "dev",
            "--non-dev-dependency-groups",
            "registry",
            "--extend-exclude",
            ".*test_.*[.]py",
            "--extend-exclude",
            ".*_test_.*[.]py",
            "--extend-exclude",
            r".*[\\/]tests[\\/].*",
        ),
    ),
    (
        "check-module-reachability",
        (sys.executable, "-m", "dev.quality.unreachable_module_coverage"),
    ),
    (
        "check-symbol-usage",
        (sys.executable, "-m", "dev.quality.unused_symbol_coverage"),
    ),
    (
        "check-export-consumption",
        (sys.executable, "-m", "dev.quality.unconsumed_export_coverage"),
    ),
    (
        "check-secure-store-write-paths",
        (sys.executable, "-m", "dev.quality.secure_store_write_path"),
    ),
    (
        "check-persistence-write-paths",
        (sys.executable, "-m", "dev.quality.write_path_coverage"),
    ),
    ("check-docstring-references", (sys.executable, "-m", "dev.quality.docstring_reference_targets")),
)


@dataclass(frozen=True)
class GateResult:
    """Outcome of one gate run."""

    name: str
    returncode: int
    output: str


def run_gate(name: str, command: tuple[str, ...]) -> GateResult:
    """Run a single gate's underlying tool command, capturing combined output."""
    # Decode explicitly: `text=True` alone uses the locale preferred encoding,
    # which on a Windows console is cp1252. The wrapped gates emit UTF-8, so the
    # reader thread died on the first non-cp1252 byte and the dashboard lost the
    # whole run rather than reporting the gate's verdict.
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="replace",
        check=False,
    )
    return GateResult(
        name=name,
        returncode=result.returncode,
        output=((result.stdout or "") + (result.stderr or "")).strip(),
    )


def main() -> int:
    """Run every gate and emit the consolidated dashboard.

    Every gate runs even after one fails, because an aggregate is asked for a
    complete picture and fail-fast costs a CI round-trip per defect. The status
    returned is the FIRST non-zero one: the earliest failure is the one that may
    explain the rest, and its actual value distinguishes a gate that found
    something (1) from a gate that could not run at all (127). See
    ``dev/EXIT-CODES.md``.
    """
    results = [run_gate(name, command) for name, command in GATES]
    failed = [r for r in results if r.returncode != 0]
    passed = [r for r in results if r.returncode == 0]

    if not failed:
        return 0

    _emit(f"check-code: {len(failed)} of {len(results)} gates failed\n")
    for result in failed:
        _emit(f"FAIL  {result.name}")
        if result.output:
            _emit(result.output)
        _emit("")
    if passed:
        _emit("passed: " + ", ".join(r.name for r in passed))
    return failed[0].returncode


def _emit(line: str) -> None:
    """Print a dashboard line without tripping a narrow console encoding.

    The replay carries the wrapped tools' UTF-8, which a cp1252 console
    cannot encode, so printing the dashboard raised instead of reporting
    which gate failed.
    """
    encoding = sys.stdout.encoding or ""
    if encoding.lower().replace("-", "") != "utf8":
        sys.stdout.buffer.write(f"{line}\n".encode(errors="replace"))
        sys.stdout.flush()
        return
    print(line)


if __name__ == "__main__":
    sys.exit(main())
