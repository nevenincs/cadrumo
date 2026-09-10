"""Tests for the census source universe.

It is the DENOMINATOR for a hand-respelling census, and what it filters is
the whole of what that census sees: a suffix or a test-module rule read wrong
here makes every consumer report a smaller, cleaner number, and no consumer
can tell -- a census that never saw a file cannot say the file was missing.

Enumeration itself -- which files exist, which a ``.gitignore`` rule
excludes -- is :mod:`dev.source_tree`'s contract and is proven there; these
cases plant a small scratch tree and pin what THIS module does with what
enumeration hands it: the suffix filter, the production-module filter, decode
behaviour, and sort order.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..repository_sources import SOURCE_ROOT, production_sources, repository_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A scratch tree with a source module, a test module, and a non-source file."""
    _write(tmp_path, f"{SOURCE_ROOT}/domain/thing.py", "VALUE = 1\n")
    _write(tmp_path, f"{SOURCE_ROOT}/domain/tests/test_thing.py", "VALUE = 2\n")
    _write(tmp_path, f"{SOURCE_ROOT}/domain/notes.txt", "not a source suffix\n")
    _write(tmp_path, "dev/outside_source_root.py", "VALUE = 3\n")
    return tmp_path


def test_the_universe_is_scoped_to_source_root(tree: Path) -> None:
    """A file outside ``SOURCE_ROOT`` is not this census's business."""
    paths = {path for path, _ in repository_sources(tree)}

    assert paths == {
        f"{SOURCE_ROOT}/domain/thing.py",
        f"{SOURCE_ROOT}/domain/tests/test_thing.py",
    }


def test_a_non_matching_suffix_is_excluded(tree: Path) -> None:
    """The consumers parse each member as a module or a document, never free text."""
    paths = {path for path, _ in repository_sources(tree)}

    assert f"{SOURCE_ROOT}/domain/notes.txt" not in paths


def test_every_source_is_returned_as_decoded_text(tree: Path) -> None:
    """An undecodable file is skipped rather than raising, so the type contract holds."""
    assert all(isinstance(source, str) for _, source in repository_sources(tree))


def test_an_undecodable_file_is_skipped_not_raised(tmp_path: Path) -> None:
    """A binary file under the source root must not crash the census."""
    binary = tmp_path / SOURCE_ROOT / "domain"
    binary.mkdir(parents=True)
    (binary / "blob.py").write_bytes(b"\xff\xfe\x00\x01")

    assert repository_sources(tmp_path) == ()


def test_the_pairs_are_sorted_so_two_reads_agree(tree: Path) -> None:
    """Consumers diff their output; an unstable order would be noise in every diff."""
    paths = [path for path, _ in repository_sources(tree)]

    assert paths == sorted(paths)


def test_the_production_universe_excludes_test_modules(tree: Path) -> None:
    """A census counting its own fixtures reports findings nobody can act on."""
    paths = [path for path, _ in production_sources(tree)]

    assert paths == [f"{SOURCE_ROOT}/domain/thing.py"]
    assert not [path for path in paths if "/tests/" in path]
    assert not [path for path in paths if Path(path).name.startswith("test_")]


def test_the_production_universe_is_python_only(tree: Path) -> None:
    """The consumers parse every member as a module, so a stray document would raise."""
    assert all(path.endswith(".py") for path, _ in production_sources(tree))


def test_the_production_universe_is_a_subset_of_the_source_universe(tree: Path) -> None:
    """It is a filter, not a second read, and must not reach files the read missed."""
    universe = {path for path, _ in repository_sources(tree)}
    production = {path for path, _ in production_sources(tree)}

    # The premise first: a subset claim is VACUOUSLY TRUE over an empty left
    # side, so an emptied filter satisfied the containment below before this
    # guard was reached.
    assert production, "the filter removed everything"
    assert production <= universe, f"the filter reached files the read missed: {sorted(production - universe)}"


def test_an_ignored_file_under_source_root_is_excluded(tmp_path: Path) -> None:
    """The repository's own ignore rules apply here as everywhere else in the tree."""
    _write(tmp_path, f"{SOURCE_ROOT}/.gitignore", "generated/\n")
    _write(tmp_path, f"{SOURCE_ROOT}/generated/emitted.py", "VALUE = 4\n")
    _write(tmp_path, f"{SOURCE_ROOT}/kept.py", "VALUE = 5\n")

    paths = {path for path, _ in repository_sources(tmp_path)}

    assert f"{SOURCE_ROOT}/generated/emitted.py" not in paths
    assert f"{SOURCE_ROOT}/kept.py" in paths


def test_an_empty_tree_is_the_honest_empty_universe(tmp_path: Path) -> None:
    """No source root, no files: the honest empty case, not a silent failure."""
    assert repository_sources(tmp_path) == ()
    assert production_sources(tmp_path) == ()
