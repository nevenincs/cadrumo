"""Localized user-scope nitpicky docs build gates: one build per translation target.

The per-language matrix the docs CI grows: each Spanish, Catalan, and Hungarian
target builds the operator surface under ``-n -W`` with
``CADRUMO_DOCS_LANGUAGE`` set, reading the committed ``docs/locales/<lang>``
catalogues. The language set derives from
:data:`~dev.docs.i18n.TARGET_LANGUAGES` (never a second hand-listed set). Split
into its own module so pytest-xdist's per-file distribution runs the matrix
concurrently with the full-scope and English user-scope builds (see
:mod:`dev.docs.tests._sphinx_build_harness` for the shared machinery, the
hook-dedupe rationale, and the timeout rationale).
"""

from __future__ import annotations

import itertools
import re
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..i18n import TARGET_LANGUAGES
from ._sphinx_build_harness import (
    copy_docs_source,
    gate_build_env,
    run_nitpicky_dummy_build,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs, pytest.mark.timeout(1800)]


@pytest.mark.parametrize("language", TARGET_LANGUAGES)
def test_localized_user_scope_build_is_nitpicky_clean(tmp_path: Path, language: str) -> None:
    """A per-language user-scope ``-n -W`` build succeeds for every translation target.

    An untranslated or fuzzy segment falls back to English at render time -
    that fallback is refused by the separate completeness gate, not here - so
    the structural build must be as clean in every language as it is in
    English (``test_docs_build_user_scope`` covers the English source). The
    full autodoc build stays English-only.

    Args:
        tmp_path: Pytest-provided isolated output directory.
        language: The BCP-47 translation target to build.
    """
    docs_source = copy_docs_source(tmp_path)
    result = run_nitpicky_dummy_build(
        docs_source,
        tmp_path / "out",
        gate_build_env(tmp_path, CADRUMO_DOCS_SCOPE="user", CADRUMO_DOCS_LANGUAGE=language),
    )
    assert result.returncode == 0, (
        f"nitpicky {language} user-scope build reported warnings or errors:\n"
        + (result.stdout or "")[-6000:]
        + (result.stderr or "")[-6000:]
    )


#: The repository root, three levels up from ``dev/docs/tests``.
_REPO_ROOT = REPO_ROOT

#: One localized build line in the ``docs-langs`` recipe: the catalogue it
#: selects and the root it renders into, captured separately so the gate below
#: can require them to name the SAME language.
_LOCALIZED_BUILD_LINE_RE = re.compile(
    r"--scope\s+user\s+--language\s+(?P<language>[a-z-]+)\s+--out-dir\s+docs/_build/html/(?P<root>[a-z-]+)",
)


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
    mismatched = [match["language"] for match in matched if match["root"] != match["language"]]
    assert not mismatched, f"docs-langs renders {mismatched} into a root that is not its own language"


def test_the_single_language_build_recipe_renders_into_that_language_root() -> None:
    """``docs-lang LANG`` puts its build in ``LANG``'s own root, not the English one."""
    body = _justfile_recipe("docs-lang LANG")

    assert "--language {{LANG}}" in body, f"docs-lang no longer selects a catalogue: {body}"
    assert "--out-dir docs/_build/html/{{LANG}}" in body, (
        f"docs-lang renders into the canonical English root instead of its own language root: {body}"
    )
