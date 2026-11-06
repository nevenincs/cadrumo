"""Report the identity canary over this working tree, value-free.

Two sections, because the gate is deliberately narrower than the measurement.
The blocking section is what fails a build; the advisory section is the
population the blocking scope leaves out, printed so the narrowing stays
visible and arguable rather than silent.

A third section holds tests and fixtures to the catalogue convention (see
:mod:`dev.identity.catalogue_gate`) and blocks as well.

Run with ``python -m dev.identity``. Exits non-zero when the blocking scope or
the convention gate has any finding.
"""

from __future__ import annotations

import sys
from collections import Counter

from dev._paths import REPO_ROOT

from ._tree_scan import (
    EXCLUDED_PATH_FRAGMENTS,
    SCANNED_SUFFIXES,
    advisory_findings,
    repository_files,
    scan_tree,
)
from .catalogue_gate import GATE_SUFFIXES, scan_convention

_REPO_ROOT = REPO_ROOT


def _bucket(relative_path: str) -> str:
    """The coarsest location label for a path, for a countable summary."""
    parts = relative_path.split("/")
    if len(parts) == 1:
        return "<repository root>"
    return "/".join(parts[:2]) if parts[0] in {"src", "dev", "docs"} else parts[0]


def main() -> int:
    """Print both sections and return the process exit status."""
    # One enumeration feeds both sections. Walking the working tree twice for a
    # report that describes a single moment also lets the two halves disagree
    # about which files existed.
    files = repository_files(_REPO_ROOT, suffixes=SCANNED_SUFFIXES)

    scan = scan_tree(_REPO_ROOT, files=files)
    print(f"blocking scope: {scan.files_scanned} data files scanned, {len(scan.findings)} findings in tracked content")
    for finding in scan.findings:
        print(f"  {finding.rendered()}")

    print(
        f"\noperator tier, untracked and ignored content: {len(scan.operator_findings)} occurrences. "
        "These do not fail a build. A credential file is EXPECTED to carry the operator's own "
        "identity, and gitignoring it is the correct handling; this section exists so the same "
        "identity can be seen not to have reached tracked content."
    )
    for finding in scan.operator_findings:
        print(f"  {finding.rendered()}")

    if scan.unreadable:
        print(f"\nenumerated but could not be opened: {len(scan.unreadable)}")
        for relative in scan.unreadable:
            print(f"  {relative}")

    print("\nsuppressed by path exclusion (occurrences, values never shown):")
    for fragment, reason in EXCLUDED_PATH_FRAGMENTS.items():
        count = scan.suppressed_by_fragment.get(fragment, 0)
        print(f"  {fragment:28s} {count:6d}   {reason}")

    advisory = advisory_findings(_REPO_ROOT, files=files)
    print(f"\nadvisory, outside the blocking scope: {len(advisory)} occurrences")
    for bucket, count in sorted(Counter(_bucket(finding.path) for finding in advisory).items()):
        print(f"  {bucket:34s} {count:6d}")

    convention = scan_convention(_REPO_ROOT, files=repository_files(_REPO_ROOT, suffixes=GATE_SUFFIXES))
    counts = convention.by_violation()
    print(
        f"\ncatalogue convention, tests and fixtures: {convention.files_scanned} files scanned, "
        f"{len(convention.findings)} findings in {convention.files_with_findings()} files "
        f"({', '.join(f'{kind.value} {count}' for kind, count in sorted(counts.items())) or 'none'})"
    )
    for finding in convention.findings:
        print(f"  {finding.rendered()}")
    if convention.unreadable:
        print(f"convention gate could not open: {len(convention.unreadable)}")
        for relative in convention.unreadable:
            print(f"  {relative}")

    return 1 if scan.findings or convention.findings or convention.unreadable else 0


if __name__ == "__main__":
    sys.exit(main())
