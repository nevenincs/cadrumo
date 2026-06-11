#!/usr/bin/env python
"""Signal-only type-check harness wrapping ty and pyright.

Runs the two project type checkers (``ty`` across ``src`` and ``pyright``
across the strict ``domain`` + ``application`` subset), then reports only
actionable signal:

* On success (zero diagnostics): silent, exit 0. Green is not reported.
* On failure: a compact summary grouped by rule and by file — never the
  raw multi-thousand-line dump — plus a pointer to the full-detail
  command, exit 1.

Pass ``--full`` to print every diagnostic verbatim (advisory mode, exit 0)
for the ``audit-types`` recipe.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass

_CWD = os.getcwd().replace("\\", "/")

TY_TARGET = "src"
PYRIGHT_TARGETS = ("src/aeat/domain", "src/aeat/application")
_TOP_RULES = 12
_TOP_FILES = 12


@dataclass(frozen=True)
class Diagnostic:
    """One normalised type-checker finding."""

    checker: str
    rule: str
    path: str
    line: int
    message: str


def _norm(path: str) -> str:
    """Normalise a checker path to a forward-slash project-relative form."""
    forward = path.replace("\\", "/")
    lowered = forward.lower()
    prefix = _CWD.lower() + "/"
    if lowered.startswith(prefix):
        return forward[len(prefix) :]
    return forward


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a checker, capturing stdout/stderr without raising."""
    return subprocess.run(
        ["uv", "run", "--no-sync", *cmd],
        capture_output=True,
        text=True,
        check=False,
    )


def collect_ty() -> list[Diagnostic]:
    """Run ty and parse its GitLab-JSON diagnostics."""
    result = _run(["ty", "check", TY_TARGET, "--output-format", "gitlab", "--color", "never"])
    payload = result.stdout.strip()
    if not payload:
        return []
    try:
        rows = json.loads(payload)
    except json.JSONDecodeError:
        # Parsing failed — surface the raw stream so the failure is not silent.
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise
    diagnostics: list[Diagnostic] = []
    for row in rows:
        location = row.get("location", {})
        begin = location.get("positions", {}).get("begin", {})
        diagnostics.append(
            Diagnostic(
                checker="ty",
                rule=row.get("check_name", "unknown"),
                path=_norm(location.get("path", "?")),
                line=int(begin.get("line", 0)),
                message=str(row.get("description", "")),
            ),
        )
    return diagnostics


def collect_pyright() -> list[Diagnostic]:
    """Run pyright and parse its JSON error-level diagnostics."""
    result = _run(["pyright", "--outputjson", *PYRIGHT_TARGETS])
    payload = result.stdout.strip()
    if not payload:
        return []
    try:
        report = json.loads(payload)
    except json.JSONDecodeError:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise
    diagnostics: list[Diagnostic] = []
    for row in report.get("generalDiagnostics", []):
        if row.get("severity") != "error":
            continue
        start = row.get("range", {}).get("start", {})
        diagnostics.append(
            Diagnostic(
                checker="pyright",
                rule=str(row.get("rule", "error")),
                path=_norm(row.get("file", "?")),
                line=int(start.get("line", 0)) + 1,
                message=str(row.get("message", "")).splitlines()[0] if row.get("message") else "",
            ),
        )
    return diagnostics


def _print_group(diagnostics: list[Diagnostic], checker: str) -> None:
    """Print the grouped rule/file breakdown for one checker."""
    subset = [d for d in diagnostics if d.checker == checker]
    if not subset:
        return
    print(f"\n{checker} ({len(subset)} diagnostics)")
    by_rule = Counter(d.rule for d in subset)
    print("  by rule:")
    for rule, count in by_rule.most_common(_TOP_RULES):
        print(f"    {count:>6}  {rule}")
    if len(by_rule) > _TOP_RULES:
        print(f"    {'':>6}  ... {len(by_rule) - _TOP_RULES} more rules")
    by_file = Counter(d.path for d in subset)
    print("  worst files:")
    for path, count in by_file.most_common(_TOP_FILES):
        print(f"    {count:>6}  {path}")
    if len(by_file) > _TOP_FILES:
        print(f"    {'':>6}  ... {len(by_file) - _TOP_FILES} more files")


def _print_full(diagnostics: list[Diagnostic]) -> None:
    """Print every diagnostic, one actionable line each."""
    for d in sorted(diagnostics, key=lambda x: (x.checker, x.path, x.line)):
        print(f"{d.path}:{d.line}: {d.checker}[{d.rule}] {d.message}")


def main() -> int:
    """Run both type checkers and emit signal-only output."""
    parser = argparse.ArgumentParser(description="Signal-only ty + pyright harness.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print every diagnostic verbatim and exit 0 (advisory audit mode).",
    )
    args = parser.parse_args()

    diagnostics = collect_ty() + collect_pyright()

    if args.full:
        if diagnostics:
            _print_full(diagnostics)
            print(f"\n{len(diagnostics)} type diagnostics (advisory).")
        else:
            print("no type diagnostics.")
        return 0

    if not diagnostics:
        return 0

    ty_count = sum(1 for d in diagnostics if d.checker == "ty")
    pyright_count = sum(1 for d in diagnostics if d.checker == "pyright")
    print(f"check-types: {len(diagnostics)} diagnostics ({ty_count} ty, {pyright_count} pyright)")
    _print_group(diagnostics, "ty")
    _print_group(diagnostics, "pyright")
    print("\nFull detail: just audit-types")
    return 1


if __name__ == "__main__":
    sys.exit(main())
