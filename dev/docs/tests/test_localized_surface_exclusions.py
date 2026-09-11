"""Census gate for the pages the localized surface silently drops.

:func:`dev.docs.i18n.user_scope_source_pages` is the single definition of the
localized documentation surface: extraction, the catalogue-drift gate, and the
completeness gate all consume it. Its own docstring states the consequence of
membership plainly - "a page excluded here is one nobody translates AND one
nobody reports as untranslated". That symmetry is what makes an exclusion
invisible: the page leaves the work set and the audit set in the same move, so
no existing gate can report it missing. The vacuity floors downstream do not
help, because a floor over a census that drops members is satisfied by the
survivors; ``_MINIMUM_READ_CATALOGUES`` is 38 against 57 live pages, so
nineteen pages could leave the surface with every gate still green.

The last filter in that chain is a content sniff: a page whose opening bytes
contain the :data:`~dev.docs.i18n._GENERATED_MARKER` banner is treated as
generator-owned and English-only. Reading the artefact rather than a list of
page names is the right design - it is why there is no second registry to fall
out of step - but the predicate is a substring test, so it cannot distinguish a
generator's banner from a hand-authored page that discusses generated files in
its opening paragraph. The bounded read narrows that window; it does not close
it, and :func:`test_a_prose_mention_in_the_opening_bytes_leaves_the_surface`
below demonstrates the false positive is reachable rather than theoretical.

This module makes the drop loud instead. It recomputes the candidate set from
the production constants - never a restatement of them, so the gate cannot
drift from the filter it audits - subtracts the published surface, and requires
the residue to equal a declared set. A page that newly disappears is then named
by a failing assertion instead of quietly ceasing to be translated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from dev._paths import REPO_ROOT

from ..i18n import (
    _DOC_SUFFIXES,
    _EXCLUDED_FILES,
    _EXCLUDED_TOP_DIRS,
    _GENERATED_MARKER,
    _GENERATED_MARKER_SCAN_BYTES,
    user_scope_source_pages,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_DOCS: Final[Path] = REPO_ROOT / "docs"

#: The pages the generated-marker sniff removes from the localized surface.
#:
#: Every entry must be a real generator-owned artefact, and the gate below
#: proves each one still carries the banner. That second claim is deliberate:
#: the sibling ``_EXCLUDED_FILES`` registry rotted exactly once by naming a file
#: that had been retired, excluding nothing while still reading as a reviewed
#: decision. A declaration nobody re-checks is the failure this module exists to
#: prevent, so it must not reproduce it.
_DECLARED_GENERATED_PAGES: Final[frozenset[str]] = frozenset({"reference/environment-overrides.md"})


def _candidate_pages(docs_root: Path) -> frozenset[str]:
    """Return the page set before the generated-marker sniff runs.

    Applies the suffix, top-directory, and filename filters by reading the
    production constants, so the only difference between this set and
    :func:`~dev.docs.i18n.user_scope_source_pages` is the content sniff whose
    effect this module measures.
    """
    candidates: set[str] = set()
    for source in scan_directory(docs_root, recursive=True, select=DirectoryEntryKind.FILES):
        if source.suffix not in _DOC_SUFFIXES:
            continue
        relative = source.relative_to(docs_root)
        if relative.parts[0] in _EXCLUDED_TOP_DIRS:
            continue
        if relative.name in _EXCLUDED_FILES or relative.name.startswith(("test_", "_test_")):
            continue
        candidates.add(relative.as_posix())
    return frozenset(candidates)


def _marker_excluded_pages(docs_root: Path) -> frozenset[str]:
    """Return the pages the generated-marker sniff removed under ``docs_root``.

    Shared by the live-tree gate and its detector-teeth case, so the teeth
    exercise the same set arithmetic the gate depends on rather than a
    look-alike written beside it.
    """
    candidates = _candidate_pages(docs_root)
    assert candidates, f"no candidate documentation pages found under {docs_root}; this gate scanned nothing"
    published = frozenset(user_scope_source_pages(docs_root))
    assert published <= candidates, (
        "user_scope_source_pages published a page the candidate filters reject; "
        "this gate no longer models the filter chain it audits"
    )
    return candidates - published


def test_the_marker_excluded_pages_are_exactly_the_declared_set() -> None:
    """Only declared generator-owned pages may leave the localized surface."""
    excluded = _marker_excluded_pages(_DOCS)
    undeclared = sorted(excluded - _DECLARED_GENERATED_PAGES)
    assert not undeclared, (
        f"{len(undeclared)} page(s) left the localized surface without being declared: {undeclared}. "
        "A page dropped here is never translated AND never reported as untranslated, so no other gate "
        "can see it. Confirm each is genuinely generator-owned and declare it, or narrow the sniff."
    )
    vanished = sorted(_DECLARED_GENERATED_PAGES - excluded)
    assert not vanished, (
        f"declared generator-owned page(s) {vanished} are no longer excluded; "
        "remove the stale declaration so it cannot read as a reviewed decision it no longer is"
    )


def test_every_declared_exclusion_still_carries_the_banner() -> None:
    """A declared exclusion must still be an artefact the generator stamps."""
    for page in sorted(_DECLARED_GENERATED_PAGES):
        source = _DOCS / page
        assert source.is_file(), f"declared generator-owned page {page} does not exist under {_DOCS}"
        head = source.read_bytes()[:_GENERATED_MARKER_SCAN_BYTES]
        assert _GENERATED_MARKER.encode() in head, (
            f"{page} no longer carries the generated banner within the first "
            f"{_GENERATED_MARKER_SCAN_BYTES} bytes; it is being excluded for a reason nobody declared"
        )


def test_a_prose_mention_in_the_opening_bytes_leaves_the_surface(tmp_path: Path) -> None:
    """Pin the reachable false positive in the generated-marker sniff.

    This asserts the CURRENT behaviour of a substring test, not that the
    behaviour is correct. A hand-authored page that names the banner phrase in
    its opening paragraph is dropped from the localized surface with no
    diagnostic anywhere, which is the failure direction the module docstring
    describes. Retire this case when the sniff is narrowed - to a first-line
    anchor, a comment-syntax match, or a generator-written sidecar - and the
    page below starts surviving.
    """
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    plain = docs_root / "plain.md"
    plain.write_text("# Plain page\n\nOrdinary authored prose.\n", encoding="utf-8")
    discusses = docs_root / "discusses.md"
    discusses.write_text(
        f"# Editing the reference\n\nA page whose banner reads {_GENERATED_MARKER} is regenerated,\n"
        "so edit the generator instead of the page.\n",
        encoding="utf-8",
    )
    assert _GENERATED_MARKER.encode() in discusses.read_bytes()[:_GENERATED_MARKER_SCAN_BYTES], (
        "fixture no longer places the phrase inside the bounded read window"
    )

    published = frozenset(user_scope_source_pages(docs_root))
    assert "plain.md" in published, "the control page must survive; the fixture root is misconfigured"
    assert "discusses.md" not in published, (
        "the authored page discussing generated files now survives the sniff; "
        "if the predicate was narrowed on purpose, delete this case"
    )


def test_an_undeclared_drop_is_detected(tmp_path: Path) -> None:
    """Detector teeth: a page leaving the surface undeclared must be named.

    Runs the gate's own residue computation over an isolated documentation root
    - never the contributor's tree - carrying one page the sniff drops. The
    residue must name it, so the live assertion above is proven capable of
    failing rather than merely observed passing.
    """
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    (docs_root / "index.md").write_text("# Index\n\nAuthored prose.\n", encoding="utf-8")
    smuggled = docs_root / "smuggled.md"
    smuggled.write_text(f"# Notes\n\nThe banner {_GENERATED_MARKER} appears here.\n", encoding="utf-8")

    excluded = _marker_excluded_pages(docs_root)
    assert sorted(excluded - _DECLARED_GENERATED_PAGES) == ["smuggled.md"], (
        "the residue computation no longer reports an undeclared silent drop; "
        "the live gate above would pass over the same defect"
    )
