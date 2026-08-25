"""Coverage gate: every walker-indexable _data file is in the index.

The build-time RAG sweep trusts the index to reflect every indexable
``_data`` surface. The service watcher can miss bulk-written files (the documented
staleness hole), so this gate asserts that no file the walker WOULD index
under ``src/cadrumo/_data`` is absent from the index metadata. It is
deterministic and offline: it reads the on-disk ``code_index_meta.json`` and
reuses the installed walker's own ``scan_files`` to compute the expected set,
so the same gitignore / ``.vaultragignore`` / extension / size / binary
filters apply - the extraction sidecars excluded in favour of their
hook-preprocessed sources are legitimately absent, not a gap.

The gate is ``integration``-marked because it reads index state produced by
the resident service (the reindex-before-sweep step must have run); it does
no live search and spawns no service of its own.
"""

from __future__ import annotations

import pytest

from ...._paths import REPO_ROOT
from .._reindex import (
    expected_data_files,
    load_index_meta,
    missing_data_files,
)

# integration-only (NOT docs): this gate reads live index state produced by
# the resident service, so it runs when a reindex-before-sweep pass has made
# the index current (whether via the sweep entry point or a deliberate manual
# run) - not in the docs build lane, where a mid-flight reindex would red it
# spuriously.
pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

# dev/docs/preprocess/tests/test_index_coverage.py -> parents[4] is repo root.
_REPO_ROOT = REPO_ROOT


def test_index_metadata_exists() -> None:
    """The code index metadata is present (the reindex step has run)."""
    meta = load_index_meta(_REPO_ROOT)
    assert meta, "code_index_meta.json is empty or absent; run the reindex step"


def test_extraction_sidecars_are_excluded_from_the_expected_set() -> None:
    """No committed extraction sidecar is walker-indexable any more.

    Post-cutover the sidecars are the
    PRODUCT corpus payload and are ``.vaultragignore``-excluded from the dev
    index; the walker reads the same text from the SOURCE files through the
    ``.vaultragpreprocess.toml`` hook rules. A sidecar re-entering the
    expected set means the exclusion rotted and every corpus document would
    be double-indexed.
    """
    expected = expected_data_files(_REPO_ROOT)
    assert expected, "the walker produced no expected data files; an empty set trivially contains no sidecars"
    sidecars = {p for p in expected if ".extracted." in p}
    assert not sidecars, f"sidecars re-entered the walker expected set: {sorted(sidecars)[:5]}"


def test_only_zero_byte_sources_are_dropped_from_the_expected_set() -> None:
    """The expected set drops zero-byte sources, and nothing else.

    A zero-byte source is rejected by the indexer's admission policy
    (``SOURCE_EMPTY``) and can never appear in the index metadata, so keeping
    it in the expected set would red the coverage gate permanently. That
    carve-out has to stay exactly that narrow: this asserts every path the
    walker scanned but the expected set omits is genuinely zero bytes, so the
    exclusion cannot be widened into an allowlist that hides a real staleness
    miss.
    """
    from vaultspec_rag.indexer._codebase_indexer import CodebaseIndexer

    indexer = CodebaseIndexer(
        root_dir=_REPO_ROOT,
        model=None,  # ty: ignore[invalid-argument-type]  # reason: scan_files() is model-free per its docstring
        store=None,  # ty: ignore[invalid-argument-type]  # reason: scan_files() is store-free per its docstring
    )
    data_prefix = "src/cadrumo/_data/"
    scanned = {
        rel
        for rel in (path.resolve().relative_to(_REPO_ROOT.resolve()).as_posix() for path in indexer.scan_files())
        if rel.startswith(data_prefix)
    }
    dropped = scanned - expected_data_files(_REPO_ROOT)
    non_empty = sorted(rel for rel in dropped if (_REPO_ROOT / rel).stat().st_size > 0)
    assert not non_empty, f"expected set dropped file(s) that carry content: {non_empty}"


def test_no_supported_data_file_is_unindexed() -> None:
    """ZERO walker-indexable ``_data`` files are absent from the index.

    This is the staleness-hole gate: it fails loudly if any walker-indexable
    ``_data`` file was written but never indexed. A non-empty miss set means
    the reindex-before-sweep step did not run or did not complete; the sweep
    must not proceed until this is green.
    """
    missing = missing_data_files(_REPO_ROOT)
    # Report a bounded sample so a failure names the offending files.
    sample = sorted(missing)[:20]
    assert not missing, (
        f"{len(missing)} walker-indexable _data files are not in the index "
        f"(run the reindex-before-sweep step). Sample: {sample}"
    )
