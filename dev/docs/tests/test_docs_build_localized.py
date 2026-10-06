"""The localized docs-build recipes the justfile declares.

Each translated site root used to be one nitpicky build of its own, and this
module kept the join between the module set and the language authority. The
documentation is now compiled once for every language
(``test_docs_build_localized_compile``), so what remains here is the pair of
justfile recipes a contributor builds a localized root with, and the two
failures they have already cost this project: a hand-listed language set that
silently falls short of the catalogue set, and ``--language`` without a matching
``--out-dir``, which renders the localized pages into the canonical English
root.
"""

from __future__ import annotations

import itertools
import re

import pytest

from dev._paths import REPO_ROOT

from ..i18n import TARGET_LANGUAGES

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


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
    assert '--out-dir "{{CADRUMO_DOCS_BUILD_ROOT}}/html/{{LANG}}"' in body, (
        f"docs-lang renders into the canonical English root instead of its own language root: {body}"
    )
