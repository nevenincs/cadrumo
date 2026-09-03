#!/usr/bin/env python
"""Signal-only type-check harness wrapping ty, pyrefly, and BasedPyright.

Runs the three project type checkers (``ty`` across ``src`` and ``pyrefly`` /
``basedpyright`` across the strict ``domain`` + ``application`` subset), then
reports only actionable signal:

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
# pyrefly takes NO path arguments on purpose. Its checked subset and its test
# exclusion are declared in `[tool.pyrefly]`, and `project_excludes` filters
# only `project_includes` — a path passed here would bypass the exclusion and
# silently re-admit the whole test tree.
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


@dataclass(frozen=True)
class _ExternalGap:
    """One documented, irreducible external-import diagnostic to suppress."""

    path_suffix: str
    checker: str
    rule: str
    needle: str
    reason: str


# Documented, reviewed suppression for genuinely-irreducible external
# dependency / third-party-stub IMPORT gaps — deliberately NOT a tech-debt
# baseline. Each entry would be a proven optional-dep / missing-stub import that
# no in-source escape (``# type: ignore`` / ``cast`` / ``Any``) and no local stub
# can resolve within the two checkers' constraints. The match is intentionally
# tight — (path suffix, checker, rule, message substring) — so a NEW diagnostic
# under any other rule or naming ANY other symbol is still a hard failure.
#
# The set is EMPTY and every import gap is currently a hard failure. The one
# entry it carried suppressed the ``model2vec`` unresolved-import in the
# corpus-search model loader; that loader was deleted with the runtime embedding
# stack, so the suppression it needed no longer has a subject. Reviewed
# 2026-08-01.
_IRREDUCIBLE_EXTERNAL_GAPS: tuple[_ExternalGap, ...] = ()


def _is_irreducible_external_gap(diagnostic: Diagnostic) -> bool:
    """Return True when a diagnostic matches a documented irreducible external-import gap."""
    return any(
        diagnostic.checker == gap.checker
        and diagnostic.rule == gap.rule
        and diagnostic.path.endswith(gap.path_suffix)
        and gap.needle in diagnostic.message
        for gap in _IRREDUCIBLE_EXTERNAL_GAPS
    )


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


def collect_pyrefly() -> list[Diagnostic]:
    """Run pyrefly and parse its JSON error-level diagnostics."""
    result = _run(["pyrefly", "check", "--output-format", "json"])
    payload = result.stdout.strip()
    if not payload:
        # An empty stream is not "clean" — a clean run still prints
        # `{"errors": []}`. Nothing at all means the checker never produced a
        # report, so fail loudly instead of reporting a green that was never
        # measured.
        sys.stderr.write(result.stderr)
        raise RuntimeError("pyrefly produced no report; see the captured stderr above")
    try:
        report = json.loads(payload)
    except json.JSONDecodeError:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise
    diagnostics: list[Diagnostic] = []
    for row in report.get("errors", []):
        if row.get("severity") != "error":
            continue
        diagnostics.append(
            Diagnostic(
                checker="pyrefly",
                rule=str(row.get("name", "error")),
                path=_norm(str(row.get("path", "?"))),
                # pyrefly reports 1-based lines already; pyright's were 0-based.
                line=int(row.get("line", 0)),
                message=str(row.get("concise_description") or row.get("description") or "").splitlines()[0],
            ),
        )
    return diagnostics


def collect_basedpyright() -> list[Diagnostic]:
    """Run BasedPyright and parse its JSON diagnostics."""
    # Name the strict production-only configuration explicitly.  ``pyproject``
    # is the sole basedpyright authority — a root ``pyrightconfig.json`` used to
    # sit beside it declaring a wider, laxer surface (all of ``src/cadrumo`` at
    # ``standard``) and won discovery, so the gate and the contributor's editor
    # reported different things; it was deleted rather than kept in sync.  The
    # flag is retained so the boundary this gate measures stays legible at the
    # call site and cannot silently move if another config file reappears.
    # ``--pythonpath`` names the interpreter whose environment resolves imports.
    # Without it basedpyright auto-detects a ``.venv`` beside the working
    # directory, so the gate silently reports 25k phantom ``reportMissingImports``
    # cascades whenever it runs against a tree that has no ``.venv`` of its own --
    # a source snapshot, for instance. Naming the running interpreter makes the
    # gate report the same thing wherever it is invoked from.
    result = _run(
        [
            "basedpyright",
            "--project",
            "pyproject.toml",
            "--pythonpath",
            sys.executable,
            "--threads",
            "8",
            "--outputjson",
        ]
    )
    payload = result.stdout.strip()
    if not payload:
        sys.stderr.write(result.stderr)
        raise RuntimeError("basedpyright produced no report; see the captured stderr above")
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
                checker="basedpyright",
                rule=str(row.get("rule") or "error"),
                path=_norm(str(row.get("file") or "?")),
                line=int(start.get("line", -1)) + 1,
                message=str(row.get("message") or "").splitlines()[0],
            )
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
    """Run all type checkers and emit signal-only output."""
    parser = argparse.ArgumentParser(description="Signal-only ty + pyrefly + basedpyright harness.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print every diagnostic verbatim and exit 0 (advisory audit mode).",
    )
    args = parser.parse_args()

    collected = collect_ty() + collect_pyrefly() + collect_basedpyright()
    suppressed = [d for d in collected if _is_irreducible_external_gap(d)]
    diagnostics = [d for d in collected if not _is_irreducible_external_gap(d)]

    if args.full:
        if diagnostics:
            _print_full(diagnostics)
            print(f"\n{len(diagnostics)} type diagnostics (advisory).")
        else:
            print("no type diagnostics.")
        if suppressed:
            print(f"\n{len(suppressed)} documented irreducible external-import gap(s) suppressed:")
            for d in sorted(suppressed, key=lambda x: (x.path, x.checker)):
                print(f"  {d.path}:{d.line}: {d.checker}[{d.rule}] {d.message}")
        return 0

    # Never a silent cap: disclose the documented suppressions even on green.
    if suppressed:
        print(
            f"note: {len(suppressed)} documented irreducible external-import gap(s) suppressed "
            "(optional deps / third-party stubs) - see _IRREDUCIBLE_EXTERNAL_GAPS in dev/quality/types.py",
        )

    if not diagnostics:
        return 0

    ty_count = sum(1 for d in diagnostics if d.checker == "ty")
    pyrefly_count = sum(1 for d in diagnostics if d.checker == "pyrefly")
    basedpyright_count = sum(1 for d in diagnostics if d.checker == "basedpyright")
    print(
        "check-types: "
        f"{len(diagnostics)} diagnostics "
        f"({ty_count} ty, {pyrefly_count} pyrefly, {basedpyright_count} basedpyright)"
    )
    _print_group(diagnostics, "ty")
    _print_group(diagnostics, "pyrefly")
    _print_group(diagnostics, "basedpyright")
    print("\nFull detail: just audit-types")
    return 1


if __name__ == "__main__":
    sys.exit(main())
