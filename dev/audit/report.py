#!/usr/bin/env python
"""Monthly code-health report: shadowing, duplication, layering, complexity.

Composes the four EXISTING scanners already shipped under ``dev/`` into one
red/amber/green dashboard, so a contributor gets a single command and a single
verdict instead of four unrelated tool invocations with no shared severity
model:

* **Shadowing** (D1) -- reuses ``dev.import_hygiene_scan.find_multi_sourced_symbols``
  against the checked-in ``dev/import_hygiene_baseline.json`` Family-3 pinned
  set (the same authority ``src/cadrumo/tests/test_import_hygiene_gate.py``
  enforces). A genuine multi-facade duplicate symbol not in the pinned set is
  RED; the pinned/tolerated set is AMBER debt; zero unpinned hits is GREEN.
* **Duplication** (D2) -- shells out to the same ``jscpd`` invocation
  ``just audit-duplication`` runs and reduces its console report through the
  existing ``dev.audit.duplication`` filter. Any clone cluster is advisory
  debt (AMBER); zero clones is GREEN. jscpd has no meaningful "graph broken"
  failure mode, so this dimension never reports RED on its own -- it is
  advisory by design (mirrors ``dev/audit/duplication.py``'s own "duplication
  is advisory debt, not a gate" contract).
* **Layering** -- reuses the ``.importlinter`` contracts already declared at
  the repo root (the restructure EPIC's ``domain/adapters/application/
  entrypoints/core`` layout) via the ``lint-imports`` console script. A
  BROKEN contract is RED; all contracts KEPT is GREEN. This dimension has no
  AMBER state: a layering contract is either satisfied or it is not.
* **Complexity** -- reuses ``dev.audit.complexity``'s baseline-ratchet
  verdict (cyclomatic, maintainability, cognitive). A NEW or REGRESSED hotspot
  is RED; baselined (grandfathered) debt is AMBER; a clean run against an
  empty baseline is GREEN.

This module does not re-implement any scanner; it shells out to / imports the
existing tools and applies one shared severity vocabulary on top. See
``no-dormant-source-resolvers`` / ``composition-service-no-parallel-write-path``
for why composition-over-reimplementation is the mandated shape here.

Usage::

    python -m dev.audit.report [--json] [--full]

Exit code is 1 if any dimension is RED, 0 otherwise (AMBER does not fail the
run -- it is a debt signal a contributor reads on the monthly cadence, not a
release blocker). This mirrors the ``dev/audit/complexity.py`` ratchet
convention: RED is "new/regressed", AMBER is "grandfathered debt", GREEN is
"clean".

See Also:
    :func:`~dev.import_hygiene_scan.find_multi_sourced_symbols`
        Symbol-shadowing scanner reused for the D1 dimension.
    :mod:`~dev.audit.duplication`
        Console-output reducer whose jscpd parsing primitives are reused for
        duplication classification.
    :mod:`~dev.audit.complexity`
        Baseline-ratchet complexity scanner reused for the complexity
        dimension.
    :class:`DimensionReport`
        Per-dimension red/amber/green result type.
    :class:`HealthReport`
        Aggregate report returned by :func:`build_report`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final

from dev.audit.complexity import (
    _BASELINE_PATH as _COMPLEXITY_BASELINE_PATH,
)
from dev.audit.complexity import (
    Baseline as ComplexityBaseline,
)
from dev.audit.complexity import (
    _classify_cc,
    _classify_cog,
    _classify_mi,
    collect_cc,
    collect_cog,
    collect_mi,
)
from dev.audit.complexity import (
    load_baseline as load_complexity_baseline,
)
from dev.audit.duplication import _ANSI, _CLONE_CAP, _FOUND, _TABLE_PCT
from dev.import_hygiene_scan import (
    PKG_ROOT,
    discover_facades,
    find_multi_sourced_symbols,
    walk_module_imports,
)

_UTF_8: Final[str] = "utf-8"
_IMPORT_HYGIENE_BASELINE_PATH: Final[Path] = Path(__file__).resolve().parents[1] / "import_hygiene_baseline.json"
_PRODUCT_SOURCE_ROOT: Final[Path] = Path("src/cadrumo")
_PRODUCTION_EXCLUDE: Final[str] = (
    "src/cadrumo/test_*.py,src/cadrumo/**/test_*.py,src/cadrumo/**/_test_*.py,src/cadrumo/tests/*,src/cadrumo/_data/*"
)


class Status(StrEnum):
    """Traffic-light verdict for one report dimension."""

    RED = "red"
    AMBER = "amber"
    GREEN = "green"


@dataclass(frozen=True)
class DimensionReport:
    """One dimension's classified status, headline, and detail lines."""

    name: str
    status: Status
    headline: str
    details: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# D1: shadowing (multi-sourced / duplicate-facade symbols)
# ---------------------------------------------------------------------------


def _load_import_hygiene_baseline() -> dict[str, object]:
    """Load the checked-in Family-3 pinned-symbol baseline, or an empty shell."""
    if not _IMPORT_HYGIENE_BASELINE_PATH.is_file():
        return {"family3_pinned_duplicate_symbols": {"tolerated_multi_sourced_symbols": []}}
    return json.loads(_IMPORT_HYGIENE_BASELINE_PATH.read_text(encoding=_UTF_8))


def audit_shadowing() -> DimensionReport:
    """Classify D1 (symbol shadowing / multi-facade duplicates).

    RED: a "high"-confidence symbol declared in more than one owning
    package's ``__all__`` that is NOT in the pinned-tolerated set (a new,
    undocumented structural duplicate). AMBER: the pinned/tolerated set is
    non-empty (grandfathered debt). GREEN: no multi-facade duplicates at all.
    """
    baseline = _load_import_hygiene_baseline()
    tolerated_entries = baseline.get("family3_pinned_duplicate_symbols", {}).get("tolerated_multi_sourced_symbols", [])
    tolerated = {entry["symbol"] for entry in tolerated_entries}

    py_files = sorted(p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts)
    facades = discover_facades()
    all_sites = [site for path in py_files for site in walk_module_imports(path)]
    multi_sourced = find_multi_sourced_symbols(facades, all_sites)

    case_a_high = [m for m in multi_sourced if m.confidence == "high" and len(m.facades) > 1]
    untolerated = sorted(f"{m.symbol} (facades={m.facades})" for m in case_a_high if m.symbol not in tolerated)
    pinned = sorted(m.symbol for m in case_a_high if m.symbol in tolerated)

    if untolerated:
        return DimensionReport(
            name="shadowing",
            status=Status.RED,
            headline=f"{len(untolerated)} undocumented multi-facade duplicate symbol(s)",
            details=untolerated,
        )
    if pinned:
        return DimensionReport(
            name="shadowing",
            status=Status.AMBER,
            headline=f"{len(pinned)} pinned/tolerated multi-facade symbol(s) (grandfathered debt)",
            details=pinned,
        )
    return DimensionReport(name="shadowing", status=Status.GREEN, headline="no multi-facade duplicate symbols")


# ---------------------------------------------------------------------------
# D2: duplication (jscpd copy-paste clones)
# ---------------------------------------------------------------------------


def _jscpd_command() -> list[str] | None:
    """Resolve the ``npx`` shim (``.cmd`` on Windows) for the jscpd invocation.

    Mirrors the resolution idiom in ``dev/docs/build.py``/``dev/packaging/smoke_core.py``:
    ``subprocess`` on Windows cannot ``CreateProcess`` a bare ``npx`` name because
    the real executable is a ``.cmd`` shim, so the PATH lookup must be done by
    ``shutil.which`` rather than left to the OS loader.
    """
    npx = shutil.which("npx")
    if npx is None:
        return None
    return [
        npx,
        "--yes",
        "jscpd@4.2.0",
        str(_PRODUCT_SOURCE_ROOT),
        "--format",
        "python",
        "--min-lines",
        "6",
        "--min-tokens",
        "80",
        "--max-size",
        "250kb",
        "--ignore",
        "**/test_*.py,**/_test_*.py,**/tests/**,**/_data/**",
        "--gitignore",
        "--reporters",
        "console",
        "--noTips",
    ]


def _reduce_jscpd_output(raw_stdout: str) -> tuple[int, str]:
    """Reduce jscpd's raw stdout to a clone count and the duplicated-lines pct.

    Mirrors ``dev.audit.duplication.main``'s parsing exactly (that module
    reads from stdin as a CLI filter; this reuses its regexes directly rather
    than shelling out to a second subprocess).
    """
    raw = _ANSI.sub("", raw_stdout)
    total = 0
    duplicated_pct = ""
    for line in raw.splitlines():
        found = _FOUND.search(line)
        if found:
            total = int(found.group(1))
        if "Duplicated lines" not in line and "%" in line and not duplicated_pct:
            pct = _TABLE_PCT.search(line)
            if pct:
                duplicated_pct = pct.group(1)
    return total, duplicated_pct


def audit_duplication(repo_root: Path) -> DimensionReport:
    """Classify D2 (copy-paste duplication) by shelling out to jscpd.

    AMBER: one or more clone clusters found (advisory debt; jscpd has no
    "broken" state so this dimension never reports RED). GREEN: no clones.
    """
    command = _jscpd_command()
    if command is None:
        return DimensionReport(
            name="duplication",
            status=Status.AMBER,
            headline="npx not found on PATH; duplication signal unavailable this cycle",
        )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="replace",
            check=False,
            cwd=repo_root,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DimensionReport(
            name="duplication",
            status=Status.AMBER,
            headline=f"jscpd could not run ({exc}); duplication signal unavailable this cycle",
        )

    total, pct = _reduce_jscpd_output(result.stdout)
    if total <= 0:
        return DimensionReport(name="duplication", status=Status.GREEN, headline="no clones found")

    pct_clause = f", {pct}% duplicated lines" if pct else ""
    return DimensionReport(
        name="duplication",
        status=Status.AMBER,
        headline=f"{total} clone cluster(s){pct_clause} (advisory debt)",
        details=[f"see `just audit-duplication` for the full clone report ({_CLONE_CAP}-line cap)"],
    )


# ---------------------------------------------------------------------------
# Layering (.importlinter contracts)
# ---------------------------------------------------------------------------


def audit_layering(repo_root: Path) -> DimensionReport:
    """Classify the layering dimension via the ``.importlinter`` contracts.

    RED: at least one contract is BROKEN. GREEN: every declared contract is
    KEPT. There is no AMBER state -- a layering contract is a hard boundary,
    not a ratcheted debt ceiling (see ``.importlinter``'s own per-contract
    ``ignore_imports`` for how sanctioned exceptions are recorded instead).
    """
    lint_imports = shutil.which("lint-imports")
    if lint_imports is None:
        return DimensionReport(
            name="layering",
            status=Status.AMBER,
            headline="lint-imports not found on PATH; layering signal unavailable this cycle",
        )
    try:
        result = subprocess.run(
            [lint_imports],
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="replace",
            check=False,
            cwd=repo_root,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DimensionReport(
            name="layering",
            status=Status.AMBER,
            headline=f"lint-imports could not run ({exc}); layering signal unavailable this cycle",
        )

    output = result.stdout + result.stderr
    broken = [line.strip() for line in output.splitlines() if line.strip().endswith("BROKEN")]
    kept = [line.strip() for line in output.splitlines() if line.strip().endswith("KEPT")]

    if result.returncode != 0 or broken:
        return DimensionReport(
            name="layering",
            status=Status.RED,
            headline=f"{len(broken)} import-linter contract(s) broken",
            details=[*broken, "run `just check-imports` locally for the full violating-edge report"],
        )
    return DimensionReport(
        name="layering",
        status=Status.GREEN,
        headline=f"all {len(kept)} import-linter contract(s) kept",
    )


# ---------------------------------------------------------------------------
# Complexity (cyclomatic / maintainability / cognitive, baseline ratchet)
# ---------------------------------------------------------------------------


def audit_complexity() -> DimensionReport:
    """Classify complexity by reusing ``dev.audit.complexity``'s own ratchet.

    RED: a new or regressed hotspot vs. the checked-in baseline. AMBER: the
    baseline carries grandfathered debt this run stays within. GREEN: no
    findings and an empty baseline.
    """
    cc = collect_cc(_PRODUCTION_EXCLUDE)
    mi = collect_mi(_PRODUCTION_EXCLUDE)
    cog = collect_cog(_PRODUCT_SOURCE_ROOT, is_test_run=False, threshold=20)

    baseline: ComplexityBaseline = load_complexity_baseline(is_test_run=False, path=_COMPLEXITY_BASELINE_PATH)
    cc_verdict = _classify_cc(cc, baseline.cyclomatic)
    mi_verdict = _classify_mi(mi, baseline.maintainability)
    cog_verdict = _classify_cog(cog, baseline.cognitive)

    failing = [*cc_verdict.failing, *mi_verdict.failing, *cog_verdict.failing]
    allowed = len(cc_verdict.allowed) + len(mi_verdict.allowed) + len(cog_verdict.allowed)

    if failing:
        return DimensionReport(
            name="complexity",
            status=Status.RED,
            headline=f"{len(failing)} new/regressed complexity hotspot(s)",
            details=failing,
        )
    if allowed:
        return DimensionReport(
            name="complexity",
            status=Status.AMBER,
            headline=f"{allowed} baselined complexity hotspot(s) (grandfathered debt)",
        )
    return DimensionReport(name="complexity", status=Status.GREEN, headline="no complexity hotspots")


# ---------------------------------------------------------------------------
# Report aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HealthReport:
    """The full monthly code-health report: one status per dimension."""

    dimensions: tuple[DimensionReport, ...]

    @property
    def overall(self) -> Status:
        """Worst status across all dimensions (RED > AMBER > GREEN)."""
        statuses = {d.status for d in self.dimensions}
        if Status.RED in statuses:
            return Status.RED
        if Status.AMBER in statuses:
            return Status.AMBER
        return Status.GREEN

    def to_json(self) -> dict[str, object]:
        """Serialise the report as a JSON-ready mapping."""
        return {
            "overall": self.overall.value,
            "dimensions": [
                {
                    "name": d.name,
                    "status": d.status.value,
                    "headline": d.headline,
                    "details": d.details,
                }
                for d in self.dimensions
            ],
        }


def build_report(repo_root: Path) -> HealthReport:
    """Run every dimension audit and assemble the composed report."""
    return HealthReport(
        dimensions=(
            audit_shadowing(),
            audit_duplication(repo_root),
            audit_layering(repo_root),
            audit_complexity(),
        ),
    )


_STATUS_GLYPH: Final[dict[Status, str]] = {
    Status.RED: "RED",
    Status.AMBER: "AMBER",
    Status.GREEN: "GREEN",
}


def _print_text_report(report: HealthReport, full: bool) -> None:
    """Print the human-readable dashboard."""
    print(f"code-health report: overall {_STATUS_GLYPH[report.overall]}")
    print()
    for dimension in report.dimensions:
        print(f"[{_STATUS_GLYPH[dimension.status]:>5}] {dimension.name}: {dimension.headline}")
        if dimension.details:
            shown = dimension.details if full else dimension.details[:10]
            for line in shown:
                print(f"         {line}")
            if len(dimension.details) > len(shown):
                print(f"         ... {len(dimension.details) - len(shown)} more")
    print()
    if report.overall is Status.RED:
        print("code-health report: FAIL - one or more dimensions RED.")
    else:
        print("code-health report: PASS (AMBER dimensions are advisory debt, not a gate).")


def main() -> int:
    """Run the composed monthly code-health report and print the verdict."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON instead of text.")
    parser.add_argument("--full", action="store_true", help="List every detail line (uncapped) in text mode.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    report = build_report(repo_root)

    if args.json:
        print(json.dumps(report.to_json(), indent=2, ensure_ascii=False))
    else:
        _print_text_report(report, args.full)

    return 1 if report.overall is Status.RED else 0


if __name__ == "__main__":
    sys.exit(main())
