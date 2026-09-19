#!/usr/bin/env python
"""Signal-only type-check harness wrapping ty, pyrefly, and BasedPyright.

Runs the three project type checkers (``ty`` across ``src`` and ``pyrefly`` /
``basedpyright`` across the strict ``domain`` + ``application`` subset) against
every platform the product supports, then reports only actionable signal:

* On success (zero diagnostics): silent, exit 0. Green is not reported.
* On failure: a compact summary grouped by rule and by file — never the
  raw multi-thousand-line dump — plus a pointer to the full-detail
  command, exit 1.
* With ``--count``: print only the aggregate finding count and exit 0 after a
  successful measurement, so the integer remains the sole machine signal.

Pass ``--full`` to print every diagnostic verbatim (advisory mode, exit 0)
for the ``audit-types`` recipe.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tomllib
from collections import Counter
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_CWD = os.getcwd().replace("\\", "/")

# ty receives no path arguments on purpose. Its project discovery is the same
# boundary contributors exercise with a standalone ``ty check``. A curated
# target list here made the aggregate look healthier than that real check by
# omitting valid ty findings before they could be counted.
# pyrefly takes NO path arguments on purpose. Its checked subset and its test
# exclusion are declared in `[tool.pyrefly]`, and `project_excludes` filters
# only `project_includes` — a path passed here would bypass the exclusion and
# silently re-admit the whole test tree.
_TOP_RULES = 12
_TOP_FILES = 12


@dataclass(frozen=True)
class TargetPlatform:
    """One analysis target: the ``sys.platform`` value the checkers assume."""

    key: str
    basedpyright: str


# The target platform is the single most consequential analysis axis, and no
# checker infers it correctly for a cross-platform project: left unset, all
# three assume the HOST, so this gate's verdict was a function of the runner --
# green on Windows, 49 ty diagnostics on Linux and macOS, from the same tree.
# Pinning one platform would make the verdict deterministic by leaving the
# other platforms' branches unchecked, which is the wrong half of the problem:
# `sys.platform` narrowing means a Windows-only body is ONLY ever analysed by a
# Windows-targeted run. So every supported platform is swept, and a diagnostic
# is a failure wherever it appears. `[tool.ty.environment]`, `[tool.pyrefly]`
# and `[tool.basedpyright]` carry the same pin for a bare, unharnessed
# invocation; the flags below override it per run.
_PLATFORMS: tuple[TargetPlatform, ...] = (
    TargetPlatform(key="linux", basedpyright="Linux"),
    TargetPlatform(key="win32", basedpyright="Windows"),
    TargetPlatform(key="darwin", basedpyright="Darwin"),
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class _PlatformPin:
    """One checker's declared target platform in ``pyproject.toml``."""

    table: tuple[str, ...]
    key: str
    # Which spelling of the platform this checker takes: ty, pyrefly and mypy
    # use the `sys.platform` value, basedpyright its own capitalised names.
    spelling: str


# Every checker that resolves `sys.platform` declares the SAME platform. mypy is
# included although CI does not run it: `[tool.mypy]` exists so an external
# auditor's invocation matches ty's stance, and a stance that disagrees about
# the platform is not a mirror.
_PLATFORM_PINS: tuple[_PlatformPin, ...] = (
    _PlatformPin(table=("tool", "ty", "environment"), key="python-platform", spelling="key"),
    _PlatformPin(table=("tool", "pyrefly"), key="python_platform", spelling="key"),
    _PlatformPin(table=("tool", "mypy"), key="platform", spelling="key"),
    _PlatformPin(table=("tool", "basedpyright"), key="pythonPlatform", spelling="basedpyright"),
)


def _table(document: Mapping[str, Any], path: tuple[str, ...]) -> Mapping[str, Any] | None:
    """Return a nested TOML table, or ``None`` when any segment is absent."""
    current: Any = document
    for segment in path:
        if not isinstance(current, Mapping) or segment not in current:
            return None
        current = current[segment]
    return current if isinstance(current, Mapping) else None


def platform_pin_failures(document: Mapping[str, Any]) -> list[str]:
    """Return why the declared target platforms cannot be trusted, empty when they can.

    The pin is load-bearing: it is the whole of what stands between a bare
    ``ty check`` and a verdict that depends on the contributor's operating
    system. It also fails silently. ty ACCEPTS ``python-platform =
    "not-a-platform"`` without complaint and analyses as though the target were
    not Windows, so a typo does not raise -- it quietly produces a
    plausible-looking answer for a platform nobody chose, and a green one at
    that. The checkers do not validate this, so the validation is here.
    """
    valid = {pin.spelling: {getattr(platform, pin.spelling) for platform in _PLATFORMS} for pin in _PLATFORM_PINS}
    failures: list[str] = []
    declared: dict[str, str] = {}
    for pin in _PLATFORM_PINS:
        location = f"[{'.'.join(pin.table)}] {pin.key}"
        table = _table(document, pin.table)
        value = None if table is None else table.get(pin.key)
        if not isinstance(value, str):
            failures.append(f"{location} is not declared; the checker would inherit the host platform")
            continue
        if value not in valid[pin.spelling]:
            failures.append(
                f"{location} = {value!r} is not a platform this project sweeps "
                f"({', '.join(sorted(valid[pin.spelling]))})"
            )
            continue
        declared[location] = next(platform.key for platform in _PLATFORMS if getattr(platform, pin.spelling) == value)
    if len(set(declared.values())) > 1:
        disagreement = ", ".join(f"{location} -> {key}" for location, key in sorted(declared.items()))
        failures.append(f"the checkers declare different target platforms: {disagreement}")
    return failures


def read_pyproject() -> Mapping[str, Any]:
    """Load the project's ``pyproject.toml`` from the repository, not the caller's directory."""
    with (_REPOSITORY_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


@dataclass(frozen=True)
class Diagnostic:
    """One normalised type-checker finding."""

    checker: str
    rule: str
    path: str
    line: int
    message: str
    platform: str


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
# no in-source escape (an ignore comment, ``cast``, ``Any``) and no local stub
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
        encoding="utf-8",
        check=False,
    )


def require_report(payload: str, result: subprocess.CompletedProcess[str], checker: str) -> None:
    """Refuse an empty checker stream instead of reading it as zero diagnostics.

    A clean run is not silent. Every checker here prints a report even when it
    finds nothing - ty prints an empty JSON array, pyrefly an object with an
    empty errors list - so an empty stream means the checker never produced a
    report at all.

    Two of the three collectors already refused it; ty returned an empty
    diagnostic list, which is the answer a genuinely clean tree gives. A ty
    that failed to start, crashed, or wrote nothing therefore reported green
    over a run that never happened, and the gate exited 0. The rule lives here
    once so the three cannot drift apart again.
    """
    if payload:
        return
    sys.stderr.write(result.stderr)
    raise RuntimeError(f"{checker} produced no report; see the captured stderr above")


def collect_ty(platform: TargetPlatform) -> list[Diagnostic]:
    """Run ty against one target platform and parse its GitLab-JSON diagnostics."""
    result = _run(["ty", "check", "--python-platform", platform.key, "--output-format", "gitlab", "--color", "never"])
    payload = result.stdout.strip()
    require_report(payload, result, f"ty[{platform.key}]")
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
                platform=platform.key,
            ),
        )
    return diagnostics


def collect_pyrefly(platform: TargetPlatform) -> list[Diagnostic]:
    """Run pyrefly against one target platform and parse its JSON error-level diagnostics."""
    result = _run(["pyrefly", "check", "--python-platform", platform.key, "--output-format", "json"])
    payload = result.stdout.strip()
    require_report(payload, result, f"pyrefly[{platform.key}]")
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
                platform=platform.key,
            ),
        )
    return diagnostics


def collect_basedpyright(platform: TargetPlatform) -> list[Diagnostic]:
    """Run BasedPyright against one target platform and parse its JSON diagnostics."""
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
            "--pythonplatform",
            platform.basedpyright,
            "--threads",
            "8",
            "--outputjson",
        ]
    )
    payload = result.stdout.strip()
    require_report(payload, result, f"basedpyright[{platform.key}]")
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
                platform=platform.key,
            )
        )
    return diagnostics


def collect_all() -> list[Diagnostic]:
    """Run every checker against every supported platform and return the union.

    The nine runs are independent subprocesses and overlap. Checked rather than
    assumed: three concurrent basedpyright processes over a frozen snapshot
    worktree answered identically to three sequential ones, twice, so they do
    not contend for the analysis cache. `fold_platforms` sorts the union
    afterwards, so the report order does not depend on who finished first.

    A sweep of a tree being edited underneath it will disagree with itself --
    that is the tree moving, not this gate being unstable, and it is why the
    contention question was settled on a snapshot instead of on `src`.
    """
    collectors = (collect_ty, collect_pyrefly, collect_basedpyright)
    with ThreadPoolExecutor(max_workers=len(_PLATFORMS)) as pool:
        futures = [pool.submit(collect, platform) for platform in _PLATFORMS for collect in collectors]
        return [diagnostic for future in futures for diagnostic in future.result()]


def fold_platforms(diagnostics: list[Diagnostic]) -> list[tuple[Diagnostic, tuple[str, ...]]]:
    """Collapse the per-platform runs into one entry per distinct finding.

    A finding every platform reports is one defect, not three, so the counts
    this gate prints stay comparable with a single-platform run. The platforms
    that DID report it ride along, because "only on Windows" is the most
    actionable thing a cross-platform type gate can say.
    """
    order = {platform.key: index for index, platform in enumerate(_PLATFORMS)}
    folded: dict[tuple[str, str, str, int, str], list[str]] = {}
    for diagnostic in diagnostics:
        key = (diagnostic.checker, diagnostic.rule, diagnostic.path, diagnostic.line, diagnostic.message)
        folded.setdefault(key, []).append(diagnostic.platform)
    entries = [
        (
            Diagnostic(
                checker=checker,
                rule=rule,
                path=path,
                line=line,
                message=message,
                platform=min(platforms, key=order.__getitem__),
            ),
            tuple(sorted(set(platforms), key=order.__getitem__)),
        )
        for (checker, rule, path, line, message), platforms in folded.items()
    ]
    return sorted(entries, key=lambda entry: (entry[0].checker, entry[0].path, entry[0].line, entry[0].rule))


def _scope(platforms: tuple[str, ...]) -> str:
    """Render the platform scope of a finding, silent when it is every platform."""
    if len(platforms) == len(_PLATFORMS):
        return ""
    return f"  [{', '.join(platforms)}]"


def _print_platform_summary(entries: list[tuple[Diagnostic, tuple[str, ...]]]) -> None:
    """Print how many findings each target platform contributes."""
    print("  by platform:")
    for platform in _PLATFORMS:
        count = sum(1 for _, platforms in entries if platform.key in platforms)
        print(f"    {count:>6}  {platform.key}")


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


def _print_full(entries: list[tuple[Diagnostic, tuple[str, ...]]]) -> None:
    """Print every diagnostic, one actionable line each."""
    for d, platforms in entries:
        print(f"{d.path}:{d.line}: {d.checker}[{d.rule}] {d.message}{_scope(platforms)}")


def _make_output_host_independent() -> None:
    """Stop a console encoding from deciding whether the report can be printed.

    A basedpyright message can carry a character outside the console's legacy
    code page -- ``U+FFFF`` appears in its unknown-type messages -- and on a
    Windows console defaulting to cp1252 that raised ``UnicodeEncodeError`` mid
    report, so the gate died instead of reporting. Same defect class as an
    unpinned target platform: the output depended on the host rather than the
    tree. The replacement character loses one glyph of a message that already
    names its file and line.
    """
    for stream in (sys.stdout, sys.stderr):
        # Narrowed on the type rather than on hasattr: `reconfigure` belongs to
        # TextIOWrapper, and a redirected stream need not be one.
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    """Run all type checkers and emit signal-only output."""
    _make_output_host_independent()
    pin_failures = platform_pin_failures(read_pyproject())
    if pin_failures:
        # Refused rather than measured: a run whose target platform is unknown
        # cannot be reported as a verdict about the tree.
        for failure in pin_failures:
            sys.stderr.write(f"check-types: {failure}\n")
        return 1
    parser = argparse.ArgumentParser(description="Signal-only ty + pyrefly + basedpyright harness.")
    output_mode = parser.add_mutually_exclusive_group()
    output_mode.add_argument(
        "--full",
        action="store_true",
        help="Print every diagnostic verbatim and exit 0 (advisory audit mode).",
    )
    output_mode.add_argument(
        "--count",
        action="store_true",
        help="Print only the aggregate diagnostic count and exit 0 after measuring.",
    )
    args = parser.parse_args()

    collected = fold_platforms(collect_all())
    suppressed = [entry for entry in collected if _is_irreducible_external_gap(entry[0])]
    entries = [entry for entry in collected if not _is_irreducible_external_gap(entry[0])]
    diagnostics = [entry[0] for entry in entries]

    if args.count:
        print(len(entries))
        return 0

    if args.full:
        if entries:
            _print_full(entries)
            print(f"\n{len(entries)} type diagnostics (advisory).")
        else:
            print("no type diagnostics.")
        if suppressed:
            print(f"\n{len(suppressed)} documented irreducible external-import gap(s) suppressed:")
            for d, platforms in sorted(suppressed, key=lambda entry: (entry[0].path, entry[0].checker)):
                print(f"  {d.path}:{d.line}: {d.checker}[{d.rule}] {d.message}{_scope(platforms)}")
        return 0

    # Never a silent cap: disclose the documented suppressions even on green.
    if suppressed:
        print(
            f"note: {len(suppressed)} documented irreducible external-import gap(s) suppressed "
            "(optional deps / third-party stubs) - see _IRREDUCIBLE_EXTERNAL_GAPS in dev/quality/types.py",
        )

    if not entries:
        return 0

    ty_count = sum(1 for d in diagnostics if d.checker == "ty")
    pyrefly_count = sum(1 for d in diagnostics if d.checker == "pyrefly")
    basedpyright_count = sum(1 for d in diagnostics if d.checker == "basedpyright")
    print(
        "check-types: "
        f"{len(entries)} diagnostics "
        f"({ty_count} ty, {pyrefly_count} pyrefly, {basedpyright_count} basedpyright)"
    )
    _print_platform_summary(entries)
    _print_group(diagnostics, "ty")
    _print_group(diagnostics, "pyrefly")
    _print_group(diagnostics, "basedpyright")
    print("\nFull detail: just audit-types")
    return 1


if __name__ == "__main__":
    sys.exit(main())
