"""Gate the shipped-data source tree's composition against the distribution split.

This measures every file under ``src/cadrumo/_data`` except test subtrees, using
summed file bytes rather than filesystem blocks, and partitions that universe
into the corpus source binaries shipped by the mandatory ``cadrumo-data-*``
companions and the runtime complement shipped by the command-bearing ``cadrumo``
wheel. The partition is what keeps the physical wheel split from hiding logical
product growth: every byte belongs to exactly one slice, so no byte can sit
outside both.

The published registry authority is not part of this universe. It is generated
output kept outside the package source tree, and a distribution receives it from
the packaging boundary rather than from here; the packaging gates assert what the
archives actually carry. ``test_data_tree_carries_no_authority_payload`` holds
that boundary closed from this side, so the composition checks cannot silently
begin measuring regenerated binary payload again.

There is deliberately no *budget* ceiling here — no reviewed figure tracking what
the tree currently weighs. Such a number is raised by whoever it blocks, which
makes it a record of past growth rather than a control on future growth, and a
check whose expected value is edited to match the observed one asserts nothing.
Real-wheel ownership and the compressed package-index caps are proved where they
are enforceable, by the packaging gates against built artifacts.

What remains is a hard cap: an outer bound far above any plausible legitimate
tree, which fires only when something has gone structurally wrong — a hydration
loop writing the same corpus repeatedly, generated output landing in the source
tree, a binary dump committed by accident. It is not a budget and must not be
raised to accommodate growth; if the tree genuinely approaches it, the answer is
that the data no longer belongs in the package. No mocks or skips.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ..core.directory_scan import DirectoryEntryKind, scan_directory
from .inventory import SRC_CADRUMO

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DATA_ROOT = SRC_CADRUMO / "_data"
_AUTHORITY_ROOT = _DATA_ROOT / "registry" / "authority"

# Corpus source binaries — the slice the wheel-split ships across the two
# ``cadrumo-data-*`` distributions; everything else in the tree is the runtime
# (compact ``cadrumo`` wheel) slice. A file is a corpus source binary when it
# lives under ``corpus/`` and carries one of these suffixes (the same pattern
# the root wheel excludes).
_CORPUS_BINARY_SUFFIXES = (".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip")


# A structural-failure stop, not a budget. Set far above any legitimate tree so
# that ordinary growth never reaches it and nobody has cause to edit it; it
# fires when something is writing bytes that should not be here at all.
# Mebibytes keep source-tree units distinct from the companions' decimal 100 MB
# compressed-artifact cap.
_DATA_HARD_CAP_MIB = 1536
_DATA_HARD_CAP_BYTES = _DATA_HARD_CAP_MIB * 1024 * 1024


def _is_corpus_source_binary(relative_posix: str, suffix: str) -> bool:
    """Return True when a ``_data``-relative path is a corpus source binary."""

    return relative_posix.startswith("corpus/") and suffix.lower() in _CORPUS_BINARY_SUFFIXES


def _authority_payload_files() -> list[Path]:
    """Return any published-authority payload still sitting under the data tree."""

    if not _AUTHORITY_ROOT.is_dir():
        return []
    return [
        path
        for path in scan_directory(_AUTHORITY_ROOT, recursive=True, select=DirectoryEntryKind.FILES)
        if path.suffix == ".sqlite3" or path.name == "authority.current.json"
    ]


def _iter_budget_data_files() -> Iterator[Path]:
    """Yield shipped-data files, excluding test subtrees."""

    for path in scan_directory(_DATA_ROOT, recursive=True, select=DirectoryEntryKind.FILES):
        if "tests" in path.relative_to(_DATA_ROOT).parts:
            continue
        yield path


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
    """The bundled data root is present before the tree is measured."""

    assert _DATA_ROOT.is_dir(), f"missing bundled data root: {_DATA_ROOT}"


def test_data_tree_carries_no_authority_payload() -> None:
    """No published-authority payload sits under the shipped-data source tree.

    Two failures ride on this. The composition measured below would quietly
    include roughly eighty mebibytes of regenerated bytes, so the runtime slice
    would stop describing what the command-bearing wheel carries. Worse, the
    build hook resolves this location as its embedded-sdist layout: bytes left
    here after the authority moves out are still buildable, so a half-finished
    move produces an artifact that looks entirely correct while carrying an
    authority nobody publishes any more. A build that succeeds from an
    abandoned directory is more dangerous than one that fails.
    """

    offenders = sorted(path.name for path in _authority_payload_files())
    assert not offenders, (
        f"published authority payload is present under {_AUTHORITY_ROOT}: {offenders!r}. "
        "After the authority moved out of the package source tree these bytes are a stale leftover, not a "
        "source: delete the directory rather than leaving it in place. The authority is resolved through "
        "CADRUMO_AUTHORITY_ROOT and staged into distributions at build time; the packaging gates measure "
        "what the archives actually carry."
    )


def test_data_tree_within_hard_cap() -> None:
    """The shipped-data tree stays inside its structural-failure stop."""

    total, _corpus_binary, _runtime = _data_slice_bytes()
    total_mib = total / 1024 / 1024
    assert total <= _DATA_HARD_CAP_BYTES, (
        f"src/cadrumo/_data is {total_mib:.1f} MiB, past the {_DATA_HARD_CAP_MIB} MiB hard cap. "
        "This cap is an outer bound on structural failure, not a budget: find what is writing bytes into the "
        "package source tree — duplicated corpus hydration, generated output landing here, an accidental binary — "
        "rather than raising it."
    )


def test_slices_partition_the_tree_exhaustively() -> None:
    """The runtime and corpus-binary slices sum to the whole tree, so the split hides no byte."""

    total, corpus_binary, runtime = _data_slice_bytes()
    assert total > 0, "the shipped-data tree measured as empty; every slice check below would pass vacuously"
    assert corpus_binary + runtime == total, (
        f"the source-tree slices do not partition the tree exhaustively: "
        f"corpus_binary ({corpus_binary}) + runtime ({runtime}) != total ({total}); "
        "a byte would be unaccounted for and could evade slice ownership"
    )
