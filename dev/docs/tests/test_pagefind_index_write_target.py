"""The index pass writes ONE index, and only into the site it was given.

``PagefindIndex.__aexit__`` writes the index on a clean exit. For as long as
:func:`build_search_index` ALSO called ``write_files`` explicitly, every build
performed two writes: the intended one, and a second with no path, which
Pagefind resolves against the process working directory. A docs build run from
the repository root deposited a full second copy of the index there -- roughly
ten thousand files -- on every run.

Gitignoring that path hid the symptom rather than fixing it, and the rule
barring a committed search index exists because such a tree was once committed
from exactly that location. So the property pinned here is not "the site index
is correct" (a second stray copy leaves it correct); it is that the working
directory is UNTOUCHED. The test therefore runs the build from a scratch CWD it
owns and asserts nothing appeared there -- the observable a correct build and
the defective one differ on.
"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

import pytest

from cadrumo.core import scan_directory

from ..._paths import REPO_ROOT
from ..pagefind_index import build_search_index

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

# dev/docs/tests -> parents[3] is the repo root.
_REPO_ROOT = REPO_ROOT
_BUILT_HTML = _REPO_ROOT / "docs" / "_build" / "html"
_PAGEFIND_YML = _REPO_ROOT / "docs" / "pagefind.yml"


def _site(tmp_path: Path) -> Path:
    """Assemble a small real page corpus to index."""
    pages = scan_directory(_BUILT_HTML, pattern="*.html")[:2] if _BUILT_HTML.is_dir() else ()
    if len(pages) < 2:
        pytest.fail(
            f"need built documentation HTML under {_BUILT_HTML} to index; "
            "this test drives the real Pagefind pass, so it needs a real build.",
        )
    site = tmp_path / "site"
    site.mkdir(parents=True)
    for source in pages:
        (site / source.name).write_bytes(source.read_bytes())
    shutil.copy(_PAGEFIND_YML, site / "pagefind.yml")
    return site


def test_the_index_pass_writes_nothing_into_the_working_directory(tmp_path: Path) -> None:
    """A build leaves the process working directory exactly as it found it.

    The scratch CWD is owned by this test and starts empty apart from the site,
    so any ``pagefind`` tree appearing beside it came from the unpathed second
    write. Asserting on the whole directory listing rather than on one expected
    name keeps the check honest if the stray output is ever named differently.
    """
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    site = _site(workdir)
    before = {entry.name for entry in scan_directory(workdir)}

    with contextlib.chdir(workdir):
        build_search_index(site, inject=None)

    after = {entry.name for entry in scan_directory(workdir)}
    assert after == before, f"the index pass created {sorted(after - before)} in the working directory"


def test_the_index_still_lands_in_the_site(tmp_path: Path) -> None:
    """The other half: aiming the write did not stop it happening.

    Without this, the assertion above would be satisfied by a build that wrote
    no index at all -- a passing result indistinguishable from a broken pass.
    """
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    site = _site(workdir)

    with contextlib.chdir(workdir):
        build_search_index(site, inject=None)

    fragments = scan_directory(site / "pagefind" / "fragment", pattern="*.pf_fragment", recursive=True)
    assert (site / "pagefind" / "pagefind-entry.json").is_file(), "the site carries no built index entry"
    assert fragments, "the site index carries no fragments; the write was aimed away rather than aimed correctly"
