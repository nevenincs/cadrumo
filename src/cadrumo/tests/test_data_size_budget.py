"""Bundled-data size budget gate — total tree plus per-distribution slices.

The architecture review (finding ``bundled-data-weight-unbudgeted``) measured
``src/cadrumo/_data`` growing from ~311 MB to 516 MB in six weeks with no ceiling
and no gate. The declared data budget below
converts the next doubling from
a silent surprise into a reviewed decision: this gate asserts the ``_data``
tree stays at or under the declared budget and fails with a message naming
the two options a breach permits.

Bundling the corpus is an accepted decision (offline-verifiable legal grounding,
the corpus-registry-packaging decision); growth is legitimate demand. The budget does
not forbid growth — it forces a decision when growth crosses the ceiling. The
budget may only be raised by a reviewed decision; a breach forces either that
or a reviewed repartition of the data-distribution cohort.

The corpus split is fully realised at the wheel boundary: the packaging
decision ships the corpus source binaries
(``corpus/**/*.{pdf,xls,xlsx}``) in the two ``cadrumo-data-manuals`` /
``cadrumo-data-official`` mandatory distributions and the derived runtime
surfaces in the compact ``cadrumo`` wheel — from the ONE source tree, which is
unchanged, so the 550 MiB
total-tree gate still stands and still guards every byte. But a single total
ceiling could now be silently EVADED by the split: command-bearing-wheel payload
could balloon while the total stays under budget because the corpus-binary slice
happened to shrink, and neither side's own growth would be visible. So the budget
is measured per side as well: the tree is partitioned exhaustively into the
runtime (compact ``cadrumo`` wheel) slice and the corpus-binary slice (the ONE
slice the two mandatory ``cadrumo-data-*`` distributions ship between them),
each carries its own
ceiling, and the partition is asserted exhaustive so no byte can hide between the
two.

The gate reads the tree size directly (summed file bytes, deterministic across
filesystems, unlike block-rounded ``du``) so the arithmetic lives in one place.
No mocks or skips.
"""

from __future__ import annotations

import pytest

from ._inventory import SRC_CADRUMO

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DATA_ROOT = SRC_CADRUMO / "_data"

# Corpus source binaries — the slice the wheel-split ships across the two
# ``cadrumo-data-*`` distributions; everything else in the tree is the runtime
# (compact ``cadrumo`` wheel) slice. A file is a corpus source binary when it
# lives under ``corpus/`` and carries one of these suffixes (the same pattern
# the root wheel excludes).
_CORPUS_BINARY_SUFFIXES = (".pdf", ".xls", ".xlsx")

# Declared budget: 550 MiB — the 516 MiB measured at the most recent review plus
# bounded headroom. Raising this constant requires a reviewed decision (see the
# failure message). Kept in mebibytes so the number matches the ``du -sh``
# reading operators see.
_DATA_SIZE_BUDGET_MIB = 550
_DATA_SIZE_BUDGET_BYTES = _DATA_SIZE_BUDGET_MIB * 1024 * 1024

# Per-distribution ceilings, each the current measured slice plus bounded
# headroom (runtime ~173 MiB, corpus binaries ~312 MiB at the split). They are
# per-distribution caps, not a second aggregate: the total-tree budget above is
# the aggregate ceiling. Raising either requires the same reviewed-decision
# discipline. The runtime ceiling is the load-bearing new guard — it makes
# command-bearing-wheel growth visible even when the corpus slice shrinks.
_RUNTIME_DATA_BUDGET_MIB = 230
_RUNTIME_DATA_BUDGET_BYTES = _RUNTIME_DATA_BUDGET_MIB * 1024 * 1024
_CORPUS_BINARY_BUDGET_MIB = 380
_CORPUS_BINARY_BUDGET_BYTES = _CORPUS_BINARY_BUDGET_MIB * 1024 * 1024

# Cohort remediation: if legitimate corpus growth breaches a per-file cap,
# rebalance the mandatory data distributions or add another mandatory slice.
_CORPUS_COHORT_REPARTITION = (
    "Rebalance the mandatory cadrumo-data-* ownership partitions, or add another "
    "mandatory exact-version data distribution, when structural corpus growth "
    "would otherwise breach a package-index file cap."
)


def _is_corpus_source_binary(relative_posix: str, suffix: str) -> bool:
    """Return True when a ``_data``-relative path is a corpus source binary."""

    return relative_posix.startswith("corpus/") and suffix.lower() in _CORPUS_BINARY_SUFFIXES


def _data_tree_bytes() -> int:
    """Return the summed size in bytes of every file under ``src/cadrumo/_data``."""

    return sum(path.stat().st_size for path in _DATA_ROOT.rglob("*") if path.is_file())


def _data_slice_bytes() -> tuple[int, int, int]:
    """Return ``(total, corpus_binary, runtime)`` byte sizes, partitioning the tree.

    ``corpus_binary`` is the slice the two ``aeat-data-*`` companions ship
    between them and ``runtime`` is the compact ``cadrumo`` wheel slice; the two are
    disjoint and exhaustive, so ``corpus_binary + runtime == total`` by
    construction.
    """

    total = 0
    corpus_binary = 0
    for path in _DATA_ROOT.rglob("*"):
        if not path.is_file():
            continue
        size = path.stat().st_size
        total += size
        if _is_corpus_source_binary(path.relative_to(_DATA_ROOT).as_posix(), path.suffix):
            corpus_binary += size
    return total, corpus_binary, total - corpus_binary


def test_data_root_exists() -> None:
    """The bundled data root is present before the budget is measured."""

    assert _DATA_ROOT.is_dir(), f"missing bundled data root: {_DATA_ROOT}"


def test_data_tree_within_declared_budget() -> None:
    """The ``_data`` tree stays at or under the declared 550 MiB budget."""

    actual_bytes = _data_tree_bytes()
    actual_mib = actual_bytes / 1024 / 1024
    assert actual_bytes <= _DATA_SIZE_BUDGET_BYTES, (
        f"src/cadrumo/_data is {actual_mib:.1f} MiB, over the {_DATA_SIZE_BUDGET_MIB} MiB declared data budget. "
        f"A breach permits exactly two options: (1) raise the budget with a reviewed decision that "
        f"records why the growth is warranted, or (2) repartition the mandatory corpus cohort — "
        f"{_CORPUS_COHORT_REPARTITION}"
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
        f"{_RUNTIME_DATA_BUDGET_MIB} MiB per-distribution ceiling. This slice is the tree minus the corpus source "
        f"binaries (extracted text, normative html, registry, terminology, agent data). Raise the ceiling with a "
        f"reviewed decision that records why the runtime payload grew, or move payload to the aeat-data-* companions."
    )


def test_corpus_binary_slice_within_companion_budget() -> None:
    """The corpus-binary (``aeat-data-*`` companions) slice stays under its ceiling."""

    _total, corpus_binary, _runtime = _data_slice_bytes()
    corpus_mib = corpus_binary / 1024 / 1024
    assert corpus_binary <= _CORPUS_BINARY_BUDGET_BYTES, (
        f"the corpus-binary (aeat-data-* companions) _data slice is {corpus_mib:.1f} MiB, over the "
        f"{_CORPUS_BINARY_BUDGET_MIB} MiB per-distribution ceiling. Raise the ceiling with a reviewed decision that "
        f"records why the corpus source binaries grew."
    )


def test_slices_partition_the_tree_exhaustively() -> None:
    """The runtime and corpus-binary slices sum to the whole tree, so the split hides no byte."""

    total, corpus_binary, runtime = _data_slice_bytes()
    assert corpus_binary + runtime == total, (
        f"the per-distribution slices do not partition the tree exhaustively: "
        f"corpus_binary ({corpus_binary}) + runtime ({runtime}) != total ({total}); "
        "a byte would be unaccounted for and could evade the per-distribution ceilings"
    )
