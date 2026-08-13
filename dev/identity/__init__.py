"""Working-tree identity canary.

Public API for the scan that answers "did a real Spanish taxpayer identity reach
this repository". Detection itself belongs to :mod:`dev.sanitizer` and is reached
through that package's facade; this package owns the surface (a working tree) and
the scope decision. See :mod:`dev.identity._tree_scan` for both arguments in
full, including why there is no value allowlist.

Resolution is lazy. The other probes in this package -- the hex-64 and identifier
censuses -- are declaration readers with no PDF dependency, and eagerly importing
the sanitiser here would drag ``pikepdf`` into every one of them for nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._tree_scan import (
        BLOCKING_KINDS,
        DATA_SUFFIXES,
        EXCLUDED_PATH_FRAGMENTS,
        NARRATIVE_SUFFIXES,
        SCANNED_SUFFIXES,
        TreeFinding,
        TreeScan,
        advisory_findings,
        exclusion_reason,
        matching_fragments,
        repository_files,
        scan_tree,
    )

__all__ = [
    "BLOCKING_KINDS",
    "DATA_SUFFIXES",
    "EXCLUDED_PATH_FRAGMENTS",
    "NARRATIVE_SUFFIXES",
    "SCANNED_SUFFIXES",
    "TreeFinding",
    "TreeScan",
    "advisory_findings",
    "exclusion_reason",
    "matching_fragments",
    "repository_files",
    "scan_tree",
]


def __getattr__(name: str) -> Any:
    """Resolve a public name from the private scan module on first access."""
    if name in __all__:
        from . import _tree_scan

        return getattr(_tree_scan, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
