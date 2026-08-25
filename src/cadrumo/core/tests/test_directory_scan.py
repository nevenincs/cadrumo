"""Behavioural contracts for the canonical ``os.scandir`` directory primitive.

The load-bearing tests here are differential: they assert that
:func:`scan_directory` returns exactly what the :class:`~pathlib.Path` call it
replaces returns, on a real temporary tree, for every call shape the codebase
uses. A migration that swaps hundreds of ``sorted(root.glob(...))`` sites onto
this primitive is only safe if that equality holds, so it is asserted directly
rather than inferred from the implementation.

Each differential test also pins the fixture tree it relies on -- that a
directory really does match the pattern, that mixed-case names really are
present -- so the comparison cannot pass vacuously against an empty result on
a tree that lost the interesting entries.
"""

from __future__ import annotations

import importlib
import inspect
import os
import shutil
from pathlib import Path

import pytest

from ..directory_scan import DirectoryEntryKind, iter_directory, scan_directory
from ..errors import CoreValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A temporary tree carrying every shape the call-site survey found.

    Mixed case, a leading-dot name, a DIRECTORY whose name matches the
    ``*.toml`` pattern, nested depth, prefix-plus-infix names, and a
    directory a caller would want pruned.
    """
    (tmp_path / "a.TOML").write_text("a", encoding="utf-8")
    (tmp_path / "b.toml").write_text("b", encoding="utf-8")
    (tmp_path / ".hidden.toml").write_text("h", encoding="utf-8")
    (tmp_path / "modelo-100.json").write_text("m", encoding="utf-8")
    (tmp_path / "modelo-200.json").write_text("m", encoding="utf-8")
    (tmp_path / "index-redacciones.html").write_text("r", encoding="utf-8")
    (tmp_path / "test_beta.py").write_text("t", encoding="utf-8")
    (tmp_path / "notes.md").write_text("n", encoding="utf-8")

    (tmp_path / "dir.toml").mkdir()
    (tmp_path / "dir.toml" / "nested.toml").write_text("n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.toml").write_text("c", encoding="utf-8")
    (tmp_path / "sub" / "test_alpha.py").write_text("t", encoding="utf-8")
    (tmp_path / "sub" / "deep").mkdir()
    (tmp_path / "sub" / "deep" / "d.toml").write_text("d", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "junk.toml").write_text("j", encoding="utf-8")
    return tmp_path


# ── Differential equivalence against the pathlib calls being replaced ──────


def test_scan_directory_reproduces_iterdir(tree: Path) -> None:
    """The no-argument shape is ``sorted(root.iterdir())``, directories included."""
    expected = sorted(tree.iterdir())

    assert any(path.is_dir() for path in expected), "fixture lost its directories"
    assert scan_directory(tree) == tuple(expected)


def test_scan_directory_reproduces_glob(tree: Path) -> None:
    """A pattern with no ``recursive`` is ``sorted(root.glob(pattern))``."""
    expected = sorted(tree.glob("*.toml"))

    assert (tree / "dir.toml") in expected, "fixture lost the pattern-matching DIRECTORY"
    assert (tree / ".hidden.toml") in expected, "fixture lost the leading-dot name"
    assert scan_directory(tree, pattern="*.toml") == tuple(expected)


def test_scan_directory_reproduces_rglob(tree: Path) -> None:
    """``recursive=True`` with a pattern is ``sorted(root.rglob(pattern))``."""
    expected = sorted(tree.rglob("*.toml"))

    assert (tree / "sub" / "deep" / "d.toml") in expected, "fixture lost its depth"
    assert scan_directory(tree, pattern="*.toml", recursive=True) == tuple(expected)


def test_scan_directory_reproduces_rglob_without_a_pattern(tree: Path) -> None:
    """``recursive=True`` alone is ``sorted(root.rglob("*"))`` -- every descendant."""
    expected = sorted(tree.rglob("*"))

    assert scan_directory(tree, recursive=True) == tuple(expected)


@pytest.mark.parametrize("pattern", ["test_*.py", "modelo-*.json", "*-redacciones.html", "*", "*.md"])
def test_scan_directory_reproduces_glob_for_prefix_and_infix_patterns(tree: Path, pattern: str) -> None:
    """Prefix and infix globs match as ``Path.glob`` does, not as ``endswith`` would."""
    expected = tuple(sorted(tree.glob(pattern)))

    assert expected, f"fixture matches nothing for {pattern!r}; the comparison would be vacuous"
    assert scan_directory(tree, pattern=pattern) == expected


def test_pattern_case_folding_follows_the_platform_exactly_as_glob_does(tree: Path) -> None:
    """``a.TOML`` is found by ``*.toml`` wherever ``Path.glob`` finds it, and nowhere else.

    Asserting equality with ``glob`` rather than asserting a fixed outcome:
    the contract is platform parity, and the platforms genuinely differ --
    Windows folds case here, POSIX does not.
    """
    scanned = scan_directory(tree, pattern="*.toml")

    assert scanned == tuple(sorted(tree.glob("*.toml")))
    assert ((tree / "a.TOML") in scanned) is (os.path.normcase("A") == os.path.normcase("a"))


# ── Ordering ──────────────────────────────────────────────────────────────


def test_scan_directory_orders_by_path_comparison_not_string_comparison(tmp_path: Path) -> None:
    """Ordering is ``sorted()`` over ``Path``, which case-normalises on Windows.

    ``sorted()`` over the string forms would put every uppercase name first
    on every platform, reordering mixed-case trees against what the call
    sites saw through ``sorted(root.glob(...))``.
    """
    for name in ("B.toml", "a.toml", "C.toml", "d.toml"):
        (tmp_path / name).write_text("x", encoding="utf-8")

    scanned = scan_directory(tmp_path, pattern="*.toml")

    assert scanned == tuple(sorted(tmp_path.glob("*.toml")))
    assert scanned == tuple(sorted(scanned, key=lambda path: os.path.normcase(str(path))))


def test_iter_directory_yields_a_deterministic_preorder_stream(tree: Path) -> None:
    """The lazy stream is stable across runs, and is pre-order, not globally sorted."""
    first = tuple(iter_directory(tree, recursive=True))
    second = tuple(iter_directory(tree, recursive=True))

    assert first == second
    assert set(first) == set(scan_directory(tree, recursive=True))
    assert first.index(tree / "sub") < first.index(tree / "sub" / "deep")


# ── Missing and unreadable roots ──────────────────────────────────────────


def test_missing_directory_yields_nothing_by_default(tmp_path: Path) -> None:
    """A missing root is silently empty, as ``Path.glob`` and ``Path.rglob`` are."""
    missing = tmp_path / "absent"

    assert list(missing.glob("*")) == []
    assert scan_directory(missing) == ()
    assert scan_directory(missing, pattern="*.toml", recursive=True) == ()
    assert list(iter_directory(missing)) == []


def test_a_file_as_root_yields_nothing_by_default(tree: Path) -> None:
    """A root that is a file is silently empty, matching ``Path.glob``."""
    a_file = tree / "b.toml"

    assert list(a_file.glob("*")) == []
    assert scan_directory(a_file) == ()


def test_require_root_raises_on_a_missing_directory(tmp_path: Path) -> None:
    """The raising behaviour is opt-in and surfaces the real OS error."""
    with pytest.raises(FileNotFoundError):
        scan_directory(tmp_path / "absent", require_root=True)


def test_require_root_raises_eagerly_from_the_lazy_shape(tmp_path: Path) -> None:
    """``iter_directory`` raises at the call, not at the first ``next()``."""
    with pytest.raises(FileNotFoundError):
        iter_directory(tmp_path / "absent", require_root=True)


def test_require_root_raises_when_the_root_is_a_file(tree: Path) -> None:
    """A file root is an OS error too, not an empty listing, once opted in."""
    with pytest.raises(OSError):
        scan_directory(tree / "b.toml", require_root=True)


def test_an_unreadable_subdirectory_never_fails_the_walk(tree: Path) -> None:
    """Failures BELOW the root always skip that subtree, as pathlib's walk does.

    Proven by removing a subdirectory between the moment it is listed and
    the moment it would be entered, which is the race a long walk over a
    live tree really hits.
    """
    entries = iter_directory(tree, recursive=True, select=DirectoryEntryKind.DIRECTORIES)
    first = next(entries)
    shutil.rmtree(tree / "sub")

    remaining = list(entries)

    assert first is not None
    assert (tree / "sub" / "deep") not in remaining


# ── Files, directories, and the both-of-them default ──────────────────────


def test_select_narrows_to_files_or_directories(tree: Path) -> None:
    """The three kinds partition what the default shape yields."""
    everything = scan_directory(tree, recursive=True, select=DirectoryEntryKind.ALL)
    files = scan_directory(tree, recursive=True, select=DirectoryEntryKind.FILES)
    directories = scan_directory(tree, recursive=True, select=DirectoryEntryKind.DIRECTORIES)

    assert files and directories
    assert set(files) | set(directories) == set(everything)
    assert not set(files) & set(directories)
    assert all(path.is_file() for path in files)
    assert all(path.is_dir() for path in directories)


def test_the_default_selection_keeps_directories_that_match_the_pattern(tree: Path) -> None:
    """``*.toml`` yields the ``dir.toml`` DIRECTORY, exactly as ``Path.glob`` does.

    The trap this pins: defaulting to files-only would have silently
    dropped this entry at every migrated ``glob`` site.
    """
    assert (tree / "dir.toml") in scan_directory(tree, pattern="*.toml")
    assert (tree / "dir.toml") not in scan_directory(tree, pattern="*.toml", select=DirectoryEntryKind.FILES)


# ── Pruning ───────────────────────────────────────────────────────────────


def test_prune_directories_excludes_the_directory_and_its_subtree(tree: Path) -> None:
    """A pruned name is neither yielded nor entered."""
    pruned = scan_directory(tree, pattern="*.toml", recursive=True, prune_directories=("__pycache__", "dir.toml"))

    assert (tree / "__pycache__" / "junk.toml") not in pruned
    assert (tree / "dir.toml") not in pruned
    assert (tree / "dir.toml" / "nested.toml") not in pruned
    assert (tree / "sub" / "deep" / "d.toml") in pruned


def test_nothing_is_pruned_unless_the_caller_names_it(tree: Path) -> None:
    """The default prunes nothing, so a scan stays pathlib-identical."""
    assert (tree / "__pycache__" / "junk.toml") in scan_directory(tree, pattern="*.toml", recursive=True)


# ── Symlinks ──────────────────────────────────────────────────────────────


def test_a_symlinked_directory_is_not_entered_and_is_not_a_directory(tmp_path: Path) -> None:
    """Symlinks are judged with ``follow_symlinks=False``, in both roles.

    Creating the symlink is allowed to fail loudly rather than skip: a test
    that cannot establish its precondition must say so. On POSIX this always
    works; on Windows it needs developer mode or elevation.
    """
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "inside.toml").write_text("x", encoding="utf-8")
    os.symlink(tmp_path / "real", tmp_path / "link", target_is_directory=True)

    directories = scan_directory(tmp_path, recursive=True, select=DirectoryEntryKind.DIRECTORIES)
    files = scan_directory(tmp_path, recursive=True, select=DirectoryEntryKind.FILES)
    everything = scan_directory(tmp_path, recursive=True)

    assert (tmp_path / "real") in directories
    assert (tmp_path / "link") not in directories
    assert (tmp_path / "link") in files
    assert (tmp_path / "link" / "inside.toml") not in everything


def test_a_symlink_loop_cannot_hang_the_walk(tmp_path: Path) -> None:
    """A directory linking to its own ancestor terminates rather than recursing."""
    (tmp_path / "branch").mkdir()
    (tmp_path / "branch" / "leaf.toml").write_text("x", encoding="utf-8")
    os.symlink(tmp_path, tmp_path / "branch" / "loop", target_is_directory=True)

    scanned = scan_directory(tmp_path, recursive=True)

    assert (tmp_path / "branch" / "leaf.toml") in scanned
    assert (tmp_path / "branch" / "loop") in scanned
    assert not any("loop" in path.parts[:-1] for path in scanned)


# ── Laziness ──────────────────────────────────────────────────────────────


def test_iter_directory_walks_lazily(tree: Path) -> None:
    """A subdirectory is read when it is reached, not when the call is made.

    Proven without instrumentation: a file created after iteration starts,
    inside a directory not yet visited, still appears in the stream. The
    eager shape could not see it.
    """
    entries = iter_directory(tree, pattern="*.toml", recursive=True)
    first = next(entries)
    (tree / "sub" / "deep" / "created-midwalk.toml").write_text("x", encoding="utf-8")

    remaining = list(entries)

    assert first
    assert (tree / "sub" / "deep" / "created-midwalk.toml") in remaining


def test_iter_directory_releases_each_directory_handle_before_yielding(tree: Path) -> None:
    """A directory can be deleted while its own entries are being consumed.

    Windows raises a sharing violation on a directory with an open handle,
    so this is the observable proof that the listing is materialised and the
    ``os.scandir`` handle closed before the consumer sees an entry.
    """
    entries = iter_directory(tree / "sub", recursive=True)
    next(entries)

    shutil.rmtree(tree / "sub" / "deep")

    assert not (tree / "sub" / "deep").exists()


# ── Refused patterns ──────────────────────────────────────────────────────


@pytest.mark.parametrize("pattern", ["*/*.toml", "sub/*.toml", "a\\b.toml"])
def test_a_multi_segment_pattern_is_refused(tree: Path, pattern: str) -> None:
    """Multi-segment globs refuse loudly instead of matching nothing quietly."""
    with pytest.raises(CoreValidationError, match="spans path segments"):
        scan_directory(tree, pattern=pattern)


def test_a_double_star_pattern_is_refused(tree: Path) -> None:
    """``**`` is refused; recursion is spelled by the ``recursive`` argument."""
    with pytest.raises(CoreValidationError, match="recursive=True"):
        scan_directory(tree, pattern="**")


def test_an_empty_pattern_is_refused(tree: Path) -> None:
    """An empty pattern is a caller error, matching ``Path.glob("")``."""
    with pytest.raises(CoreValidationError, match="must not be empty"):
        scan_directory(tree, pattern="")

    with pytest.raises(ValueError, match="pattern"):
        list(tree.glob(""))


def test_the_lazy_shape_validates_its_pattern_before_returning(tree: Path) -> None:
    """A refused pattern raises from the call itself, not from the first ``next()``."""
    with pytest.raises(CoreValidationError):
        iter_directory(tree, pattern="*/*.toml")


# ── Facade ────────────────────────────────────────────────────────────────


def test_the_root_is_always_an_argument_and_never_a_repo_anchor() -> None:
    """Neither entry point may grow a default root, and the module holds no anchor.

    The development tooling tree imports this primitive and scans the repo root,
    ``docs/``, build outputs and temp directories. A convenience default
    pointing at the package tree -- the shape
    ``cadrumo/tests/_inventory.py`` legitimately uses, because it is test
    scaffolding that may know the repo layout -- would make this production
    module know a layout it has no business knowing.
    """
    for entry_point in (scan_directory, iter_directory):
        root_parameter = inspect.signature(entry_point).parameters["root"]
        assert root_parameter.default is inspect.Parameter.empty, f"{entry_point.__name__} grew a default root"

    module = inspect.getmodule(scan_directory)
    assert module is not None
    anchors = {name: value for name, value in vars(module).items() if isinstance(value, Path)}
    assert not anchors, f"module-level Path anchors would bind the primitive to a layout: {anchors}"


def test_a_relative_root_is_scanned_and_kept_relative(tree: Path) -> None:
    """A relative root works and its results stay relative, exactly as pathlib's do.

    Some callers routinely pass a relative path segment rather than an absolute
    path. Resolving the root here would hand those callers absolute results
    where ``Path.glob`` gave them relative ones.
    """
    origin = Path.cwd()
    os.chdir(tree)
    try:
        scanned = scan_directory(Path("sub"), pattern="*.toml")

        assert scanned == tuple(sorted(Path("sub").glob("*.toml")))
        assert scanned == (Path("sub/c.toml"),)
        assert not scanned[0].is_absolute()
    finally:
        os.chdir(origin)


def test_the_primitive_is_owned_by_its_public_defining_module() -> None:
    """The inert core namespace cannot become a second scan authority."""
    core = importlib.import_module("cadrumo.core")

    assert inspect.getmodule(scan_directory).__name__ == "cadrumo.core.directory_scan"
    assert inspect.getmodule(iter_directory).__name__ == "cadrumo.core.directory_scan"
    assert DirectoryEntryKind.__module__ == "cadrumo.core.directory_scan"
    assert not {"scan_directory", "iter_directory", "DirectoryEntryKind"} & set(core.__all__)
    for name in ("scan_directory", "iter_directory", "DirectoryEntryKind"):
        assert not hasattr(core, name)
