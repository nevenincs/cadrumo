"""Tests for the census source universe.

`dev.quality.module_test_reach` listed `dev/quality/repository_sources.py` as
unreached. It is the DENOMINATOR for three identity censuses and an identifier
namespace gate, and it had nothing establishing that the universe it hands them
is the whole one.

The risk here is entirely one-sided. A universe that is too small makes every
consumer report a smaller, cleaner number, and no consumer can tell: a census
that never saw a file cannot say the file was missing. The reads are done
through ``git archive``, which honours ``export-ignore``, so a single attribute
added anywhere in the tree would shrink all four surfaces at once and be visible
nowhere. That path is unused today, which is exactly when to pin it.

Every case resolves HEAD to a concrete commit first. This worktree is edited
concurrently and HEAD moves during a run; comparing two reads taken at different
revisions would fail for a reason that has nothing to do with the module.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from ..repository_sources import SOURCE_ROOT, production_sources, repository_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SUFFIXES = {".py", ".toml", ".json", ".md"}


@pytest.fixture(scope="module")
def revision() -> str:
    """Resolve HEAD once, so every read in this module sees the same tree."""
    return subprocess.run(
        ("git", "rev-parse", "HEAD"),  # noqa: S607  # repository tool is fixed
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()


@pytest.fixture(scope="module")
def tracked(revision: str) -> frozenset[str]:
    """Return every tracked source path under the source root at that revision."""
    listed = subprocess.run(  # noqa: S603  # fixed read-only argument list
        ("git", "ls-tree", "-r", "--name-only", revision, SOURCE_ROOT),  # noqa: S607  # fixed tool
        capture_output=True,
        check=True,
        text=True,
    ).stdout.split()
    return frozenset(path for path in listed if pathlib.PurePosixPath(path).suffix in _SUFFIXES)


def test_the_universe_is_every_tracked_source_file_and_no_fewer(
    revision: str,
    tracked: frozenset[str],
) -> None:
    """The one property four consumers depend on and none of them can check.

    ``git archive`` omits anything marked ``export-ignore``, and a census cannot
    report a file it never received. A single attribute would quietly shrink
    three censuses and a namespace gate together, each of them reporting a
    healthier number than the tree deserves.
    """
    universe = {path for path, _ in repository_sources(revision)}

    assert universe == tracked


def test_the_universe_is_not_empty(revision: str) -> None:
    """A denominator of zero makes every consumer trivially clean.

    A PARTIAL collapse does the same thing more quietly. `> 0` caught only the
    total case, so a narrowed root or a tightened filter could drop this
    universe from tens of thousands to a handful and every consumer would
    still read clean. A floor, not a pinned count: live it holds 27,717
    sources at HEAD.
    """
    universe = repository_sources(revision)

    assert len(universe) > 20000, (
        f"the repository source universe holds only {len(universe)} entries, so every "
        "consumer reading it is close to trivially clean"
    )


def test_every_source_is_returned_as_decoded_text(revision: str) -> None:
    """Undecodable files are skipped silently, so the skip must stay at zero.

    The previous case is what makes this one meaningful: a dropped file changes
    the count, and the equality above is what would catch it. This states the
    type contract the consumers parse against.
    """
    assert all(isinstance(source, str) for _, source in repository_sources(revision))


def test_the_pairs_are_sorted_so_two_reads_agree(revision: str) -> None:
    """Consumers diff their output; an unstable order would be noise in every diff."""
    paths = [path for path, _ in repository_sources(revision)]

    assert paths == sorted(paths)


def test_the_production_universe_excludes_test_modules(revision: str) -> None:
    """A census counting its own fixtures reports findings nobody can act on."""
    paths = [path for path, _ in production_sources(revision)]

    assert paths, "the production universe is empty"
    assert not [path for path in paths if "/tests/" in path]
    assert not [path for path in paths if pathlib.PurePosixPath(path).name.startswith("test_")]


def test_the_production_universe_is_python_only(revision: str) -> None:
    """The consumers parse every member as a module, so a stray document would raise."""
    assert all(path.endswith(".py") for path, _ in production_sources(revision))


def test_the_production_universe_is_a_subset_of_the_source_universe(revision: str) -> None:
    """It is a filter, not a second read, and must not reach files the read missed."""
    universe = {path for path, _ in repository_sources(revision)}
    production = {path for path, _ in production_sources(revision)}

    # The premise first: a subset claim is VACUOUSLY TRUE over an empty left
    # side, so an emptied filter satisfied the containment below before this
    # guard was reached.
    assert production, "the filter removed everything"
    assert production <= universe, f"the filter reached files the read missed: {sorted(production - universe)}"


def test_an_unknown_revision_fails_closed(revision: str) -> None:
    """A typo'd revision must not read as a repository containing nothing.

    Returning an empty universe would make every consumer report zero findings,
    which is the same answer a clean tree gives.
    """
    with pytest.raises(subprocess.CalledProcessError):
        repository_sources("no-such-revision-anywhere")
