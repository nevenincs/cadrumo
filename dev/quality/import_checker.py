"""Internal coordinator for the subordinate import-form checks."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from dev._paths import REPO_ROOT, UTF_8
from dev.exit_codes import TOOL_BROKEN
from dev.quality.import_authority import read_authority
from dev.quality.import_binding_inventory import check_initializers, read_modules
from dev.quality.import_check_models import Authority, CheckResult, Finding, ImportOccurrence
from dev.quality.import_dynamic_checks import check_dynamic_imports
from dev.quality.import_dynamic_targets import discover_closed_attribute_targets
from dev.quality.import_occurrences import collect_import_occurrences
from dev.quality.import_static_checks import check_static_imports


def _write_component_result(
    args: argparse.Namespace, authority: Authority, authority_findings: tuple[str, ...], result: CheckResult
) -> None:
    """Write component result."""
    if args.report is not None:
        args.report.write_text(
            json.dumps(result.as_dict(authority.repository), indent=2, sort_keys=True) + "\n",
            encoding=UTF_8,
            newline="\n",
        )
    for finding in authority_findings:
        print(finding)
    if result.findings:
        rendered = result.render(authority.repository)
        if rendered:
            print(rendered)
    else:
        print(f"import-checker: scanned {result.files_scanned} governed Python file(s)")


def check_authority(authority: Authority) -> CheckResult:
    """Run one complete syntax/canonical/dynamic traversal."""
    try:
        modules, findings = read_modules(authority)
        if not modules:
            findings.append(Finding("ZERO_FILES", "no governed Python files were scanned", fatal=True))
            return _result(findings, 0, authority.repository)
        check_initializers(authority, modules, findings)
        check_static_imports(authority, modules, findings)
        known = frozenset((*modules, *authority.root_packages))
        closed_attribute_targets = discover_closed_attribute_targets(modules, authority.root_names, known)
        check_dynamic_imports(authority, modules, findings, closed_attribute_targets)
        occurrences = collect_import_occurrences(authority, modules, closed_attribute_targets)
        return _result(findings, len(modules), authority.repository, occurrences)
    except Exception as exc:  # broad: the checker boundary must fail closed
        return CheckResult(
            (Finding("INTERNAL_CHECKER", f"subordinate checker aborted: {exc}", fatal=True),),
            0,
        )


def _result(
    findings: list[Finding],
    files_scanned: int,
    repository: Path,
    occurrences: Sequence[ImportOccurrence] = (),
) -> CheckResult:
    """Sort diagnostics before returning the component result."""
    ordered = sorted(
        findings,
        key=lambda finding: (
            finding.path.relative_to(repository).as_posix() if finding.path is not None else "",
            finding.lineno or 0,
            finding.category,
            finding.message,
        ),
    )
    ordered_occurrences = sorted(
        occurrences,
        key=lambda occurrence: (
            occurrence.fingerprint,
            occurrence.path.as_posix(),
            occurrence.lineno,
        ),
    )
    return CheckResult(tuple(ordered), files_scanned, tuple(ordered_occurrences))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the internal subordinate component for diagnostics and isolation tests."""
    parser = argparse.ArgumentParser(
        description="Internal import-quality component; use just check-import-boundaries for the verdict."
    )
    parser.add_argument("--internal", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--root", type=Path, default=None, help="repository/source root to scan")
    parser.add_argument("--config", type=Path, default=None, help="Import Linter configuration path")
    parser.add_argument("--report", type=Path, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.internal:
        print("[INTERNAL_CHECKER] subordinate checker is internal; use just check-import-boundaries")
        return TOOL_BROKEN
    root = args.root or Path(os.environ.get("CADRUMO_IMPORT_GATE_ROOT", REPO_ROOT))
    try:
        read = read_authority(root, args.config)
    except Exception as exc:  # broad: direct component execution must fail closed
        print(f"[INTERNAL_CHECKER] authority preflight aborted: {exc}")
        return TOOL_BROKEN
    if read.authority is None:
        for finding in read.findings:
            print(finding)
        return TOOL_BROKEN
    result = check_authority(read.authority)
    _write_component_result(args, read.authority, read.findings, result)
    return TOOL_BROKEN if read.broken and result.returncode == 0 else result.returncode


if __name__ == "__main__":
    sys.exit(main())
