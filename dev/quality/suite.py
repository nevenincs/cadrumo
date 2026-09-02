#!/usr/bin/env python
"""Consolidated static-gate dashboard for the build harness.

Runs every fast static quality gate to completion (not fail-fast), then
reports signal only:

* On full success: silent, exit 0. Green gates are not reported.
* On any failure: a compact dashboard naming each failing gate, replaying
  its actionable output, and listing the gates that passed by name only,
  then exit 1.

Each gate invokes its underlying tool directly (no ``just`` re-entry, no
nested ``uv run``): this process is already started via ``uv run --no-sync
python -m dev.quality.suite``, so the active venv's console scripts
(``ruff``, ``lint-imports``, ``deptry``) resolve by bare name and
``sys.executable`` already names the venv interpreter for the Python-module
gates. This script aggregates pass/fail and surfaces the failing detail.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from typing import Final

from .._paths import UTF_8

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
    ("check-imports", ("lint-imports",)),
    ("check-relative-imports", (sys.executable, "-m", "dev.quality.relative_imports")),
    (
        "check-dependencies",
        (
            "deptry",
            "src/cadrumo",
            "dev/registry",
            "--known-first-party",
            "cadrumo",
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
        "check-architecture",
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-n0",
            "dev/tests/test_import_edge_integrity_gate.py",
            "dev/tests/test_facade_export_gate.py",
        ),
    ),
    (
        "check-unreachable-ratchet",
        (sys.executable, "-m", "dev.quality.unreachable_module_ratchet"),
    ),
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


#: The line ``lint-imports`` prints once it has evaluated the contract set. Its
#: ABSENCE from a failing run is the signal this module annotates.
_CONTRACT_TALLY_MARKER: Final[str] = "Contracts:"

#: What ``lint-imports`` prints instead when an ignore_imports pin matches nothing.
_UNMATCHED_IGNORE_MARKER: Final[str] = "No matches for ignored import"


def _unmatched_pins(output: str) -> list[str]:
    """Rejoin each unmatched-pin report, which the tool wraps across lines.

    ``lint-imports`` wraps this message at the terminal width, and the wrap
    point moves with the pin's length: a long importer can push the whole
    ``a -> b`` pair onto the lines AFTER the marker, leaving the marker line
    carrying no pin at all. Reading only that line therefore quotes the reader
    the word "import" and nothing actionable, which was this annotation's own
    defect until a real dead-gate run showed it -- the fixture happened to wrap
    after the module name, so the tests passed while the live case did not.

    The report ends at the sentence's full stop, so lines are gathered until
    one ends in a period rather than guessing at a line count.
    """
    lines = output.splitlines()
    pins: list[str] = []
    for index, line in enumerate(lines):
        if _UNMATCHED_IGNORE_MARKER not in line:
            continue
        pin = line
        cursor = index
        while not pin.rstrip().endswith(".") and cursor + 1 < len(lines):
            cursor += 1
            # The tool leaves a trailing space where it wrapped at a word break
            # and none where it wrapped mid-token. Honouring that is what keeps
            # a dotted module path copy-pasteable: joining unconditionally with
            # a space splits the identifier and yields a pin nobody can find.
            continuation = lines[cursor].strip()
            pin = pin + continuation if pin.endswith(" ") else pin.rstrip() + continuation
        pins.append(pin.strip())
    return pins


def annotate_unevaluated_contracts(output: str) -> str:
    """Say so when a layering run ended before evaluating any contract.

    ``unmatched_ignore_imports_alerting = error`` is deliberate: it fails a pin
    that overshoots, which is what keeps the narrow per-module exemptions
    honest. The cost is blast radius. One pin matching nothing stops the run
    before a single contract is checked, and the output is then one line about
    an ignore -- which reads like a small complaint rather than "none of the
    ten contracts was evaluated". A dead gate has twice been mistaken for a
    quiet one here.

    A pin goes unmatched precisely when somebody FIXES the violation it
    excused, so whoever caused this has no reason to suspect the layering
    config at all. Naming the situation is the whole point.
    """
    if _CONTRACT_TALLY_MARKER in output or _UNMATCHED_IGNORE_MARKER not in output:
        return output
    stale = _unmatched_pins(output)
    return "\n".join(
        (
            output,
            "",
            "NO CONTRACTS WERE EVALUATED. The run stopped on an ignore_imports pin that",
            "matches nothing, so every layering contract is unchecked -- this is not one",
            "narrow failure. A pin stops matching when its violation is FIXED, so look for",
            "a repaired import rather than a new one, confirm the edge is gone, then",
            "delete the pin from .importlinter:",
            *(f"    {line}" for line in stale),
        )
    )


def main() -> int:
    """Run all gates and emit the consolidated dashboard."""
    results = [run_gate(name, command) for name, command in GATES]
    failed = [r for r in results if r.returncode != 0]
    passed = [r for r in results if r.returncode == 0]

    if not failed:
        return 0

    _emit(f"check-all: {len(failed)} of {len(results)} gates failed\n")
    for result in failed:
        _emit(f"FAIL  {result.name}")
        if result.output:
            _emit(annotate_unevaluated_contracts(result.output))
        _emit("")
    if passed:
        _emit("passed: " + ", ".join(r.name for r in passed))
    return 1


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
