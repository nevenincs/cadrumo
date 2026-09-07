"""Refuse tracked content that records paths inside a transient working tree.

A gate that walks the filesystem sees whatever happens to be on disk. An
interrupted CLI benchmark run leaves a complete, gitignored copy of the source
tree behind, and any scan that reaches it counts thousands of files no reviewer
can act on and no other checkout can reproduce.

Two censuses shipped that way before this gate existed. One recorded 44 per
cent of its consumer entries from the mirror; the other put 4,478 phantom paths
into a committed, human-reviewed artifact. Neither went red, because a census
that absorbs phantom files still emits a plausible number -- which is why the
property is asserted here rather than left to each scanner's own care.

The check is on tracked content, so it holds regardless of which scanner
leaked: a producer that starts walking an untracked tree tomorrow reds this
gate the moment its artifact is committed.
"""

from __future__ import annotations

import subprocess
from typing import Final

import pytest

from .._paths import REPO_ROOT, UTF_8

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Directory names that exist only while a tool is running, or only on the
#: machine that ran it. A tracked file naming one is recording a path that
#: does not exist for anybody else.
TRANSIENT_TREE_SEGMENTS: Final[tuple[str, ...]] = (".baseline-source-snapshot",)

#: Files permitted to name a transient tree, each because naming it is the
#: point: they exist to create it, prune it, or prove it stays out.
#: Keyed by path so a file that stops needing the exemption fails this gate
#: rather than keeping a silent licence.
DECLARED_NAMING_SITES: Final[dict[str, str]] = {
    "dev/quality/fixture_census.py": "prunes the snapshot from its walk, with a stated reason",
    "dev/quality/tests/test_no_dunder_init_module_imports.py": "excludes the snapshot from its import scan",
    "src/cadrumo/application/modelo/tests/test_workspace_producers.py": (
        "asserts the snapshot stays out of its producer walk"
    ),
    "src/cadrumo/domain/calculations/registry/tests/test_public_api_boundaries.py": (
        "excludes the snapshot from its boundary scan"
    ),
    "dev/registry/analysis/regulatory_prose_parser_channel.py": "prunes the snapshot from its module walk",
    "dev/tests/test_tracked_content_excludes_transient_trees.py": "declares the segments and this allowlist",
}

_TEXT_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyi", ".json", ".md", ".rst", ".toml", ".txt"})

#: The vault is removable development scaffolding whose audits and execution
#: records describe this hazard by name -- naming it is their whole job, and a
#: growing corpus of them must not each need an allowlist entry. It carries no
#: generated path artefacts, so excluding it costs the gate nothing.
_PROSE_ROOT: Final[str] = ".vault/"


def _tracked_text_files() -> tuple[str, ...]:
    listed = subprocess.run(  # fixed read-only git subcommand assembled only by this module
        ("git", "ls-files", "-z"),  # noqa: S607  # repository tool is fixed
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return tuple(
        entry for entry in listed.split(chr(0)) if entry and any(entry.endswith(suffix) for suffix in _TEXT_SUFFIXES)
    )


def _offending_files() -> tuple[dict[str, str], tuple[str, ...]]:
    """Return the offending files, and the tracked files that would not read.

    The population floor below counts what the walk LISTED, not what it
    read, so a file that fails to open still counts toward it while
    contributing nothing to the scan. The floor is blind to this by
    construction -- it measures the wrong stage -- and an unread file is
    exactly where a recorded transient path would sit unnoticed."""
    offenders: dict[str, str] = {}
    unread: list[str] = []
    for entry in _tracked_text_files():
        if entry in DECLARED_NAMING_SITES or entry.startswith(_PROSE_ROOT):
            continue
        try:
            raw = (REPO_ROOT / entry).read_bytes()
        except OSError:
            unread.append(entry)
            continue
        # Decoded lossily on purpose. The segments searched for are ASCII, and
        # a replacement character cannot forge or hide one, so a lossy decode
        # answers this scan’s question exactly. Refusing the file instead
        # would drop a tracked corpus document that is simply not UTF-8 -- one
        # such BOE text is tracked today -- and that is the file the scan was
        # silently skipping before.
        content = raw.decode(UTF_8, errors="replace")
        for segment in TRANSIENT_TREE_SEGMENTS:
            if segment in content:
                offenders[entry] = segment
                break
    return offenders, tuple(unread)


def test_no_tracked_file_records_a_transient_tree_path() -> None:
    offenders, unread = _offending_files()

    assert offenders == {}
    assert not unread, (
        "these tracked files would not read, so a transient tree path recorded "
        f"in one of them was never scanned for: {list(unread)}"
    )


def test_every_declared_naming_site_still_names_a_transient_tree() -> None:
    """A stale exemption must fail rather than sit unnoticed."""
    stale = {
        entry
        for entry in DECLARED_NAMING_SITES
        if not any(segment in (REPO_ROOT / entry).read_text(encoding=UTF_8) for segment in TRANSIENT_TREE_SEGMENTS)
    }
    assert stale == set()


def test_the_scan_reaches_real_tracked_content() -> None:
    """An empty or tiny scan would pass the refusal vacuously."""
    scanned = _tracked_text_files()
    assert len(scanned) > 1000
    assert any(entry.endswith(".json") for entry in scanned)
    assert any(entry.startswith("src/cadrumo/") for entry in scanned)
