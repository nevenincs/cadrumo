"""Gate the shipped-data source tree and its distribution slices by byte size.

The accepted data-budget decision keeps the offline-verifiable corpus cohort
complete while making growth visible. This gate measures every file under
``src/cadrumo/_data`` except test subtrees, using summed file bytes rather than
filesystem blocks. It partitions that budget universe into the corpus source
binaries shipped by the mandatory ``cadrumo-data-*`` companions and the runtime
complement shipped by the command-bearing ``cadrumo`` wheel.

Whole-tree, runtime, and aggregate corpus-binary ceilings are independent. Their
exact partition prevents the physical wheel split from hiding logical product
growth. Real-wheel ownership and compressed package-index caps are proved by the
packaging gates. Raising any source ceiling requires reviewed governance authority.
No mocks or skips.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ..core.directory_scan import DirectoryEntryKind, scan_directory
from ._inventory import SRC_CADRUMO

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DATA_ROOT = SRC_CADRUMO / "_data"

# Corpus source binaries — the slice the wheel-split ships across the two
# ``cadrumo-data-*`` distributions; everything else in the tree is the runtime
# (compact ``cadrumo`` wheel) slice. A file is a corpus source binary when it
# lives under ``corpus/`` and carries one of these suffixes (the same pattern
# the root wheel excludes).
_CORPUS_BINARY_SUFFIXES = (".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip")

# Approved whole-tree ceiling after complete supported-period corpus hydration.
# Raising it requires reviewed governance authority. Mebibytes keep source-slice units
# distinct from the companions' decimal 100 MB compressed-artifact cap.
_DATA_SIZE_BUDGET_MIB = 625
_DATA_SIZE_BUDGET_BYTES = _DATA_SIZE_BUDGET_MIB * 1024 * 1024

# Slice ceilings are aggregate source-tree controls, not per-wheel file caps.
# The runtime guard makes command-bearing payload growth visible even if the
# corpus-binary slice shrinks. Raising either requires reviewed governance authority.
_RUNTIME_DATA_BUDGET_MIB = 270
_RUNTIME_DATA_BUDGET_BYTES = _RUNTIME_DATA_BUDGET_MIB * 1024 * 1024
_CORPUS_BINARY_BUDGET_MIB = 380
_CORPUS_BINARY_BUDGET_BYTES = _CORPUS_BINARY_BUDGET_MIB * 1024 * 1024


def _is_corpus_source_binary(relative_posix: str, suffix: str) -> bool:
    """Return True when a ``_data``-relative path is a corpus source binary."""

    return relative_posix.startswith("corpus/") and suffix.lower() in _CORPUS_BINARY_SUFFIXES


def _iter_budget_data_files() -> Iterator[Path]:
    """Yield shipped-data files, excluding every test-only subtree."""

    for path in scan_directory(_DATA_ROOT, recursive=True, select=DirectoryEntryKind.FILES):
        if "tests" in path.relative_to(_DATA_ROOT).parts:
            continue
        yield path


def _data_tree_bytes() -> int:
    """Return summed bytes for the test-excluded shipped-data source tree."""

    return sum(path.stat().st_size for path in _iter_budget_data_files())


def _data_slice_bytes() -> tuple[int, int, int]:
    """Return ``(total, corpus_binary, runtime)`` byte sizes, partitioning the tree.

    ``corpus_binary`` is the slice the two ``cadrumo-data-*`` companions ship
    between them and ``runtime`` is the compact ``cadrumo`` wheel slice; the two are
    disjoint and exhaustive, so ``corpus_binary + runtime == total`` by
    construction.
    """

    total = 0
    corpus_binary = 0
    for path in _iter_budget_data_files():
        size = path.stat().st_size
        total += size
        if _is_corpus_source_binary(path.relative_to(_DATA_ROOT).as_posix(), path.suffix):
            corpus_binary += size
    return total, corpus_binary, total - corpus_binary


def test_data_root_exists() -> None:
    """The bundled data root is present before the budget is measured."""

    assert _DATA_ROOT.is_dir(), f"missing bundled data root: {_DATA_ROOT}"


def test_data_tree_within_declared_budget() -> None:
    """The shipped-data source tree stays under its reviewed ceiling."""

    actual_bytes = _data_tree_bytes()
    actual_mib = actual_bytes / 1024 / 1024
    assert actual_bytes <= _DATA_SIZE_BUDGET_BYTES, (
        f"src/cadrumo/_data is {actual_mib:.1f} MiB, over the {_DATA_SIZE_BUDGET_MIB} MiB declared data budget. "
        "Remove dead or non-shipped data, or obtain reviewed governance authority for warranted growth. "
        "Repartitioning alone cannot reduce the logical whole-tree total."
    )


def test_runtime_slice_within_command_bearing_wheel_budget() -> None:
    """The runtime (compact ``cadrumo`` wheel) slice stays under its ceiling.

    This is the guard the split makes necessary: derived-surface growth in the
    runtime wheel is now visible even when the corpus-binary slice shrinks and
    the total-tree budget stays satisfied.
    """

    _total, _corpus_binary, runtime = _data_slice_bytes()
    runtime_mib = runtime / 1024 / 1024
    assert runtime <= _RUNTIME_DATA_BUDGET_BYTES, (
        f"the runtime (compact cadrumo wheel) _data slice is {runtime_mib:.1f} MiB, over the "
        f"{_RUNTIME_DATA_BUDGET_MIB} MiB runtime-slice ceiling. This slice is the tree minus the corpus source "
        f"binaries (extracted text, normative html, registry, terminology, agent data). Raise the ceiling with a "
        "reviewed decision that records why the runtime payload grew, or remove dead derived data. Do not move "
        "ownership-incompatible runtime payload into a companion merely to pass this gate."
    )


def test_corpus_binary_slice_within_companion_budget() -> None:
    """The aggregate corpus-binary slice stays under its reviewed ceiling."""

    _total, corpus_binary, _runtime = _data_slice_bytes()
    corpus_mib = corpus_binary / 1024 / 1024
    assert corpus_binary <= _CORPUS_BINARY_BUDGET_BYTES, (
        f"the aggregate corpus-binary (cadrumo-data-* companions) _data slice is {corpus_mib:.1f} MiB, over the "
        f"{_CORPUS_BINARY_BUDGET_MIB} MiB slice ceiling. Remove superseded binaries or obtain reviewed governance authority "
        "for warranted aggregate growth. Repartitioning may restore per-wheel distributability, but it cannot reduce "
        "this aggregate slice."
    )


def test_slices_partition_the_tree_exhaustively() -> None:
    """The runtime and corpus-binary slices sum to the whole tree, so the split hides no byte."""

    total, corpus_binary, runtime = _data_slice_bytes()
    assert corpus_binary + runtime == total, (
        f"the source-tree slices do not partition the tree exhaustively: "
        f"corpus_binary ({corpus_binary}) + runtime ({runtime}) != total ({total}); "
        "a byte would be unaccounted for and could evade the slice ceilings"
    )
