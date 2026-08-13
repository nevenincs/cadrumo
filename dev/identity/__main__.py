"""Report the identity canary over this working tree, value-free.

Two sections, because the gate is deliberately narrower than the measurement.
The blocking section is what fails a build; the advisory section is the
population the blocking scope leaves out, printed so the narrowing stays
visible and arguable rather than silent.

Run with ``python -m dev.identity``. Exits non-zero when the blocking scope has
any finding.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from ._tree_scan import EXCLUDED_PATH_FRAGMENTS, advisory_findings, scan_tree

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _bucket(relative_path: str) -> str:
    """The coarsest location label for a path, for a countable summary."""
    parts = relative_path.split("/")
    if len(parts) == 1:
        return "<repository root>"
    return "/".join(parts[:2]) if parts[0] in {"src", "dev", "docs"} else parts[0]


def main() -> int:
    """Print both sections and return the process exit status."""
    scan = scan_tree(_REPO_ROOT)
    print(f"blocking scope: {scan.files_scanned} data files scanned, {len(scan.findings)} findings")
    for finding in scan.findings:
        print(f"  {finding.rendered()}")

    print("\nsuppressed by path exclusion (occurrences, values never shown):")
    for fragment, reason in EXCLUDED_PATH_FRAGMENTS.items():
        count = scan.suppressed_by_fragment.get(fragment, 0)
        print(f"  {fragment:28s} {count:6d}   {reason}")

    advisory = advisory_findings(_REPO_ROOT)
    print(f"\nadvisory, outside the blocking scope: {len(advisory)} occurrences")
    for bucket, count in sorted(Counter(_bucket(finding.path) for finding in advisory).items()):
        print(f"  {bucket:34s} {count:6d}")

    return 1 if scan.findings else 0


if __name__ == "__main__":
    sys.exit(main())
