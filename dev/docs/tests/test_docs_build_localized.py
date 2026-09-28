"""The localized docs-build matrix: its coverage gate and its build recipes.

The per-language matrix the docs CI grows: each Spanish, Catalan, and Hungarian
target builds the operator surface under ``-n -W`` with
``CADRUMO_DOCS_LANGUAGE`` set, reading the committed ``docs/locales/<lang>``
catalogues. Each of those builds lives in its own
``test_docs_build_localized_<lang>`` module, because pytest-xdist distributes by
file and three multi-minute builds in one module serialise on one worker while
the rest of the lane idles (see :mod:`dev.docs.tests._sphinx_build_harness` for
the shared machinery, the hook-dedupe rationale, and the timeout rationale, and
:mod:`dev.docs.tests._localized_build_support` for the one shared runner).

Splitting by file is the one thing that could drop a language silently, because a
module set is a hand-authored list where the parametrized matrix was derived. So
this module keeps the join: the gate below asserts the per-language modules on
disk are exactly :data:`~dev.docs.i18n.TARGET_LANGUAGES`, which stays the single
language authority.
"""

from __future__ import annotations

import itertools
import re
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import iter_directory
from dev._paths import REPO_ROOT

from ..i18n import TARGET_LANGUAGES
from ._localized_build_support import LOCALIZED_MODULE_STEM

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_every_translation_target_has_its_own_build_module() -> None:
    """The per-language gate modules are exactly the declared translation targets.

    The build matrix is one module per language so xdist runs it concurrently,
    which makes the module set a hand-authored list. A new translation target
    would then be published, searched, and built by nobody, while the three
    modules that do exist go on passing -- exactly the shortfall the derived
    parametrization could not have.

    Independent roots: the modules are files in this directory, the target set is
    derived from the ``OutputLanguage`` closed set in
    :data:`~dev.docs.i18n.TARGET_LANGUAGES`.
    """
    here = Path(__file__).resolve().parent
    present = {
        path.stem.removeprefix(LOCALIZED_MODULE_STEM)
        for path in iter_directory(here, pattern=f"{LOCALIZED_MODULE_STEM}*.py")
    }

    missing = sorted(set(TARGET_LANGUAGES) - present)
    assert not missing, (
        f"these translation targets have no {LOCALIZED_MODULE_STEM}<lang>.py build gate: {missing}; "
        "the language is published and translated but its nitpicky build is run by nobody"
    )

    extra = sorted(present - set(TARGET_LANGUAGES))
    assert not extra, (
        f"these build gates name languages the product does not translate: {extra}; "
        f"the declared targets are {TARGET_LANGUAGES}"
    )


#: The repository root, three levels up from ``dev/docs/tests``.
_REPO_ROOT = REPO_ROOT

#: One delegation from the aggregate to the canonical single-language recipe.
_LOCALIZED_BUILD_LINE_RE = re.compile(r"^\s*just\s+docs-lang\s+(?P<language>[a-z-]+)\s*$", re.MULTILINE)


def _justfile_recipe(name: str) -> str:
    """Return one recipe's body from the repository justfile."""
    lines = (_REPO_ROOT / "justfile").read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(f"{name}:"):
            continue
        body = list(itertools.takewhile(lambda following: following.startswith((" ", "\t")), lines[index + 1 :]))
        return "\n".join(body)
    pytest.fail(f"the justfile declares no {name!r} recipe")


def test_the_localized_build_recipe_covers_every_translation_target_in_its_own_root() -> None:
    """``docs-langs`` builds exactly the translation set, each into its own site root.

    Two failures this pins, both of which have already cost this project real
    time. A hand-listed language set silently falls short of the catalogue set
    when a translation target is added, so a root nobody built looks merely
    absent. And ``--language`` alone only selects the catalogue: without a
    matching ``--out-dir`` the localized pages render into the canonical
    English root, which produced a tree carrying no language root at all while
    the recipe appeared to build three.

    English is deliberately absent: it is the msgid source with no catalogue to
    select, and the deploy's own command builder documents that passing the
    flag for it would force the user scope and drop the API tree.
    """
    matched = list(_LOCALIZED_BUILD_LINE_RE.finditer(_justfile_recipe("docs-langs")))

    assert [match["language"] for match in matched] == list(TARGET_LANGUAGES), (
        "docs-langs does not build exactly the translation targets "
        f"{TARGET_LANGUAGES}: it builds {[match['language'] for match in matched]}"
    )


def test_the_single_language_build_recipe_renders_into_that_language_root() -> None:
    """``docs-lang LANG`` puts its build in ``LANG``'s own root, not the English one."""
    body = _justfile_recipe("docs-lang LANG")

    assert "--language {{LANG}}" in body, f"docs-lang no longer selects a catalogue: {body}"
    assert "--out-dir docs/_build/html/{{LANG}}" in body, (
        f"docs-lang renders into the canonical English root instead of its own language root: {body}"
    )
