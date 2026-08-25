#!/usr/bin/env python
"""Monthly code-health report: shadowing, duplication, layering, complexity.

Composes the four EXISTING scanners already shipped under ``dev/`` into one
red/amber/green dashboard, so a contributor gets a single command and a single
verdict instead of four unrelated tool invocations with no shared severity
model:

* **Shadowing** (D1) -- reuses ``dev.quality.import_hygiene_scan.find_multi_sourced_symbols``
  against the checked-in ``dev/import_hygiene_baseline.json`` Family-3 pinned
  set (the same authority ``src/cadrumo/tests/test_import_hygiene_gate.py``
  enforces). A genuine multi-facade duplicate symbol not in the pinned set is
  RED; the pinned/tolerated set is AMBER debt; zero unpinned hits is GREEN.
* **Duplication** (D2) -- delegates the entire measurement to
  ``dev.audit.duplication.run_duplication_scan``, the one runner
  ``just audit-duplication`` also calls. Any clone cluster is advisory debt
  (AMBER, carrying the measured count); a scan that demonstrably inspected the
  tree and found nothing is GREEN; a scan that could not run or produced no
  parseable evidence is AMBER-unavailable, never GREEN. jscpd has no meaningful
  "graph broken" failure mode, so this dimension never reports RED on its own --
  it is advisory by design (mirrors ``dev/audit/duplication.py``'s own
  "duplication is advisory debt, not a gate" contract).
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
``aeat-calculation-aggregation`` / ``aeat-architecture-boundaries``
for why composition-over-reimplementation is the mandated shape here.

Usage::

    python -m dev.audit.report [--json] [--full]

Exit code is 1 if any dimension is RED, 0 otherwise (AMBER does not fail the
run -- it is a debt signal a contributor reads on the monthly cadence, not a
release blocker). This mirrors the ``dev/audit/complexity.py`` ratchet
convention: RED is "new/regressed", AMBER is "grandfathered debt", GREEN is
"clean".

See Also:
    :func:`~dev.quality.import_hygiene_scan.find_multi_sourced_symbols`
        Symbol-shadowing scanner reused for the D1 dimension.
    :func:`~dev.audit.duplication.run_duplication_scan`
        The single duplication runner consumed for the D2 dimension.
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

from cadrumo.core import scan_directory

from .._paths import REPO_ROOT, UTF_8
from ..quality.import_hygiene_scan import (
    PKG_ROOT,
    discover_facades,
    find_multi_sourced_symbols,
    walk_module_imports,
)
from .complexity import (
    _BASELINE_PATH as _COMPLEXITY_BASELINE_PATH,
)
from .complexity import (
    Baseline as ComplexityBaseline,
)
from .complexity import (
    _classify_cc,
    _classify_cog,
    _classify_mi,
    collect_cc,
    collect_cog,
    collect_mi,
)
from .complexity import (
    load_baseline as load_complexity_baseline,
)
from .complexity_allowlist import load_allowlist as load_complexity_allowlist
from .duplication import DuplicationOutcome, run_duplication_scan

_UTF_8: Final[str] = UTF_8
_IMPORT_HYGIENE_BASELINE_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1] / "quality" / "import_hygiene_baseline.json"
)
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

    py_files = list(scan_directory(PKG_ROOT, pattern="*.py", recursive=True, prune_directories=("__pycache__",)))
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


def audit_duplication(repo_root: Path) -> DimensionReport:
    """Classify D2 (copy-paste duplication) from the one duplication runner.

    Delegates the whole measurement to :func:`~dev.audit.duplication.run_duplication_scan`
    and only maps its typed outcome onto this module's severity vocabulary; there
    is no second jscpd invocation or parser here.

    GREEN exclusively on ``observed_zero`` -- a scan that demonstrably inspected
    the production tree and found nothing. Clones are AMBER carrying the measured
    count (advisory debt: the count is not a gate). An unavailable scan is
    AMBER naming the reason, never green -- "we could not measure" and "there is
    nothing to find" are different facts.
    """
    result = run_duplication_scan(repo_root)

    if result.outcome is DuplicationOutcome.UNAVAILABLE:
        return DimensionReport(
            name="duplication",
            status=Status.AMBER,
            headline=result.headline(),
            details=["no duplication evidence was produced this cycle; this is not a clean-tree signal"],
        )
    if result.outcome is DuplicationOutcome.OBSERVED_ZERO:
        return DimensionReport(name="duplication", status=Status.GREEN, headline=result.headline())

    return DimensionReport(
        name="duplication",
        status=Status.AMBER,
        headline=result.headline(),
        details=["see `just audit-duplication` for the full clone report"],
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

    # A run that ABORTED is not a run that found violations, and the two must
    # not share a report. import-linter aborts before evaluating anything when
    # an ignore_imports entry matches nothing, so a single stale entry disables
    # the whole contract family; it exits non-zero and prints NO contract
    # results at all. Classified only by exit code that reads as "contracts
    # broken", and classified only by `broken` being empty it would read as
    # GREEN. Both are wrong in the same dangerous direction: the gate did not
    # run. Compare what was EVALUATED against what is DECLARED.
    declared = _declared_contract_count(repo_root)
    evaluated = len(kept) + len(broken)
    if declared and evaluated != declared:
        return DimensionReport(
            name="layering",
            status=Status.RED,
            headline=(
                f"import-linter evaluated {evaluated} of {declared} declared contract(s); "
                "the run aborted rather than reporting a breach"
            ),
            details=[
                "A stale `ignore_imports` entry matching nothing aborts the whole run before any "
                "contract is checked, so this is a rotted gate configuration, not a layering "
                "violation. Run `just check-imports` and read the error naming the unmatched entry.",
                *broken,
            ],
        )

    if broken:
        return DimensionReport(
            name="layering",
            status=Status.RED,
            headline=f"{len(broken)} of {evaluated} import-linter contract(s) broken",
            details=[*broken, "run `just check-imports` locally for the full violating-edge report"],
        )

    if result.returncode != 0:
        return DimensionReport(
            name="layering",
            status=Status.RED,
            headline=(
                f"import-linter exited {result.returncode} while reporting all {evaluated} "
                "contract(s) kept; the signal is self-contradictory"
            ),
            details=["run `just check-imports` locally and read the full output"],
        )

    return DimensionReport(
        name="layering",
        status=Status.GREEN,
        headline=f"all {evaluated} of {declared} import-linter contract(s) kept",
    )


def _declared_contract_count(repo_root: Path) -> int:
    """Return how many contracts ``.importlinter`` declares, or 0 if unreadable.

    The floor for the layering dimension. Without it a run that evaluated
    nothing is indistinguishable from a run that evaluated everything cleanly,
    which is the precise failure that left five contracts unchecked for an
    extended period while the dimension read as unremarkable.
    """
    config = repo_root / ".importlinter"
    try:
        text = config.read_text(encoding=_UTF_8, errors="replace")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.strip().startswith("[importlinter:contract:"))


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
    # Reviewed acceptances must be merged HERE too, not only in the complexity
    # CLI. This dimension is what `just audit-health-report` reports, so an
    # allowlist consulted by the tool but not by the report would leave the
    # signal anyone actually watches unchanged -- the acceptance would look
    # applied while the number it exists to move stayed put.
    allowlist = load_complexity_allowlist(is_test_run=False)
    cc_verdict = _classify_cc(cc, {**baseline.cyclomatic, **allowlist.ceilings("cyclomatic")})
    mi_verdict = _classify_mi(mi, {**baseline.maintainability, **allowlist.ceilings("maintainability")})
    cog_verdict = _classify_cog(cog, {**baseline.cognitive, **allowlist.ceilings("cognitive")})

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

    repo_root = REPO_ROOT
    report = build_report(repo_root)

    if args.json:
        print(json.dumps(report.to_json(), indent=2, ensure_ascii=False))
    else:
        _print_text_report(report, args.full)

    return 1 if report.overall is Status.RED else 0


if __name__ == "__main__":
    sys.exit(main())
