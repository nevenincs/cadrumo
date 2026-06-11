"""Coverage gate: every walker-indexable _data file is in the index.

The build-time RAG sweep trusts the index to reflect every extraction
sidecar. The service watcher can miss bulk-written files (the documented
staleness hole), so this gate asserts that no file the walker WOULD index
under ``src/aeat/_data`` is absent from the index metadata. It is
deterministic and offline: it reads the on-disk ``code_index_meta.json`` and
reuses the installed walker's own ``scan_files`` to compute the expected set,
so the same gitignore / ``.vaultragignore`` / extension / size / binary
filters apply - a raw surface excluded in favour of its extraction sidecar is
legitimately absent, not a gap.

The gate is ``integration``-marked because it reads index state produced by
the resident service (the reindex-before-sweep step must have run); it does
no live search and spawns no service of its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._reindex import (
    expected_data_files,
    load_index_meta,
    missing_data_files,
)

# integration-only (NOT docs): this gate reads live index state produced by
# the resident service, so it runs when the reindex-before-sweep step has made
# the index current (the W03.P09 sweep entry, or a deliberate manual run) - not
# in the docs build lane, where a mid-flight reindex would red it spuriously.
pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

# dev/docs/preprocess/tests/test_index_coverage.py -> parents[4] is repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]


def test_index_metadata_exists() -> None:
    """The code index metadata is present (the reindex step has run)."""
    meta = load_index_meta(_REPO_ROOT)
    assert meta, "code_index_meta.json is empty or absent; run the reindex step"


def test_extraction_sidecars_are_in_the_expected_set() -> None:
    """Every committed extraction sidecar is walker-indexable.

    Confirms the sidecar convention holds end to end: the 429 ``*.extracted.md``
    sidecars produced by the corpus preprocessors carry a walker-supported
    extension and survive the gitignore / ``.vaultragignore`` filters, so they
    are in the set the coverage gate expects to find indexed.
    """
    expected = expected_data_files(_REPO_ROOT)
    sidecars = {p for p in expected if p.endswith(".extracted.md")}
    # The four preprocessors emitted 429 text sidecars (219 HTML + 102
    # workbook + 72 PDF + 36 text-tail); they must all be walker-indexable.
    assert len(sidecars) >= 429


def test_no_supported_data_file_is_unindexed() -> None:
    """ZERO walker-indexable ``_data`` files are absent from the index.

    This is the staleness-hole gate: it fails loudly if any extraction
    sidecar (or any natively-supported ``_data`` file) was written but never
    indexed. A non-empty miss set means the reindex-before-sweep step did not
    run or did not complete; the sweep must not proceed until this is green.
    """
    missing = missing_data_files(_REPO_ROOT)
    # Report a bounded sample so a failure names the offending files.
    sample = sorted(missing)[:20]
    assert not missing, (
        f"{len(missing)} walker-indexable _data files are not in the index "
        f"(run the reindex-before-sweep step). Sample: {sample}"
    )
