"""Census gate for the pages the cli-sequence engine never opens.

:data:`~dev.docs.sequences.checks._SKIPPED_DOC_DIRS` bounds
:func:`~dev.docs.sequences.checks._page_files`, and every consumer of the
committed sequence corpus reads through it: the goldens gate, the Sphinx build
gate, the refresh CLI, and the enrolment floor in
``test_committed_enrolment.py``. One predicate therefore bounds both the work -
which documented CLI sequences are executed and compared against the real
command tree - and every measurement of whether that work happened. A filter in
that position cannot be falsified by anything downstream, because each
downstream population arrived through it.

Measured against the committed tree rather than argued: adding ``explanation``
to the skip set removes seven committed pages from discovery and four enrolled
sequences from the corpus, and none of the 122 collected sequence instruments
report anything. The two-dimensional enrolment floor does not help - it is 190
sequences over 24 pages against a live 277 over 34, so 87 sequences and ten
whole pages can leave discovery with every gate green. That is the failure the
floor's own docstring anticipates for one subtree, arriving through the filter
the floor's population came from.

This module measures the filter from outside it. The candidate set comes from
the repository's own file enumeration over ``docs/`` - tracked plus untracked,
minus ``.gitignore`` - so a local Sphinx build under the gitignored
``docs/_build`` cannot fabricate or suppress a finding - and is narrowed only
by file suffix, never by directory. The residue after subtracting the engine's
own page set is what the directory filter removed, and it must equal a
declared set. Today that set is empty: the four declared skip directories
carry no committed markdown at all, so the filter currently removes nothing.
That is worth pinning precisely because it is easy to lose - the declaration
reads as though it were load-bearing, and the day it becomes so is the day a
page stops being verified with nothing to say so.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from cadrumo.core.directory_scan import scan_directory

from ...._paths import REPO_ROOT
from ....source_tree import repository_files
from ..checks import _SKIPPED_DOC_DIRS, _page_files, default_docs_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_DOCS: Final[Path] = default_docs_root()

#: Committed pages the directory filter is permitted to remove from discovery.
#:
#: Empty, and that is the claim. Every declared skip directory holds build
#: output, private sequence contracts, or Sphinx assets - no page a reader ever
#: sees - so the filter removes nothing today. An entry may be added here only
#: with a stated reason why the page in it is genuinely not a narrative page;
#: a page silently landing in the residue is a page the sequence engine has
#: stopped opening while every instrument that could report it reads a
#: population the same filter produced.
_DECLARED_SKIPPED_PAGES: Final[frozenset[str]] = frozenset[str]()


def _committed_markdown_pages() -> frozenset[str]:
    """Return every committed ``docs/`` markdown page, as docs-relative POSIX paths.

    Enumerated from the repository's own membership rule (tracked files plus
    untracked files the ``.gitignore`` tree does not exclude) rather than a raw
    filesystem walk. ``docs/_build`` is itself gitignored, so a contributor's
    last Sphinx run cannot let a build artefact enter or leave this population
    and move the verdict.
    """
    prefix = "docs/"
    return frozenset(
        path[len(prefix) :] for path in repository_files(REPO_ROOT, under=("docs",)) if path.endswith(".md")
    )


def _residue(candidates: frozenset[str], docs_root: Path) -> frozenset[str]:
    """Return the candidate pages the engine's directory filter removed.

    Shared by the live gate and its detector-teeth case so the teeth exercise
    the same subtraction the gate depends on rather than a look-alike written
    beside it. ``candidates`` is injected because the live population comes from
    the git index while the teeth run over an isolated tree that has none.
    """
    opened = frozenset(path.relative_to(docs_root).as_posix() for path in _page_files(docs_root))
    assert opened <= candidates, (
        f"the sequence engine opened {sorted(opened - candidates)[:5]}, which the candidate "
        "enumeration does not contain; this gate no longer models the filter it audits"
    )
    return candidates - opened


def test_the_committed_page_census_is_not_empty() -> None:
    """Neither side may be silently empty, or the subtraction below is vacuous."""
    candidates = _committed_markdown_pages()
    assert len(candidates) > 40, (
        f"only {len(candidates)} committed markdown page(s) enumerated under docs/; "
        "the index walk has stopped matching and every assertion here would compare empty sets"
    )
    assert _page_files(_DOCS), f"the sequence engine opened no pages under {_DOCS}; this gate measures nothing"


def test_no_committed_page_is_removed_from_sequence_discovery() -> None:
    """A page the directory filter drops is a page no sequence gate can see."""
    removed = sorted(_residue(_committed_markdown_pages(), _DOCS))
    undeclared = [page for page in removed if page not in _DECLARED_SKIPPED_PAGES]

    assert not undeclared, (
        f"{len(undeclared)} committed page(s) are excluded from cli-sequence discovery without being "
        f"declared: {undeclared[:10]}. Any sequence on such a page is never executed and never reported "
        "as unexecuted - the enrolment floor counts only the pages that survived this same filter. "
        "Confirm the page carries no verifiable command prose and declare it, or narrow the skip set."
    )
    stale = sorted(_DECLARED_SKIPPED_PAGES - frozenset(removed))
    assert not stale, (
        f"declared skipped page(s) {stale} are no longer excluded; remove the stale declaration "
        "so it cannot read as a reviewed decision it no longer is"
    )


def test_every_declared_skip_directory_still_holds_no_page() -> None:
    """Each skip entry must still name a tree that carries no narrative page.

    The residue assertion above proves the filter removes nothing in aggregate.
    This proves the same thing entry by entry, so a declaration that has quietly
    become load-bearing is named as itself rather than as an anonymous path in a
    list.
    """
    committed = _committed_markdown_pages()
    populated = {
        directory: pages
        for directory in sorted(_SKIPPED_DOC_DIRS)
        if (pages := sorted(page for page in committed if page.startswith(f"{directory}/")))
    }

    assert not populated, (
        f"skip directories {sorted(populated)} now carry committed markdown pages that discovery "
        f"will never open: {populated}. The filter has stopped being inert; each page needs a "
        "declaration in this module or the skip entry needs narrowing."
    )


def test_a_skipped_subtree_is_named(tmp_path: Path) -> None:
    """Detector teeth: a page leaving discovery must appear in the residue.

    Runs the gate's own subtraction over an isolated documentation root - never
    the contributor's tree - carrying one page inside a declared skip directory.
    The residue must name it, so the live assertions above are proven capable of
    failing rather than merely observed passing.
    """
    docs_root = tmp_path / "docs"
    skipped_dir = sorted(_SKIPPED_DOC_DIRS)[0]
    (docs_root / "how-to").mkdir(parents=True)
    (docs_root / skipped_dir).mkdir()
    (docs_root / "how-to" / "visible.md").write_text("# Visible page\n", encoding="utf-8")
    (docs_root / skipped_dir / "hidden.md").write_text("# Hidden page\n", encoding="utf-8")

    candidates = frozenset(
        path.relative_to(docs_root).as_posix() for path in scan_directory(docs_root, pattern="*.md", recursive=True)
    )
    assert candidates == {"how-to/visible.md", f"{skipped_dir}/hidden.md"}, (
        f"the fixture tree is not the two pages this case reasons about: {sorted(candidates)}"
    )

    assert sorted(_residue(candidates, docs_root)) == [f"{skipped_dir}/hidden.md"], (
        "the residue computation no longer reports a page removed by the directory filter; "
        "the live gate above would pass over the same defect"
    )
