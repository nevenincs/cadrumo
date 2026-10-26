"""The localized docs-build recipes the justfile declares.

Each translated site root used to be one nitpicky build of its own, and this
module kept the join between the module set and the language authority. The
documentation is now compiled once for every language
(``test_docs_build_localized_compile``), so what remains here is the pair of
justfile recipes a contributor reaches the localized roots through: the one
compile that writes them all, which must not turn back into a build per
language, and the single-language build it is proven against, whose
``--language`` without a matching ``--out-dir`` renders the localized pages into
the canonical English root.
"""

from __future__ import annotations

import itertools

import pytest

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


#: The repository root, three levels up from ``dev/docs/tests``.
_REPO_ROOT = REPO_ROOT


def _justfile_recipe(name: str) -> str:
    """Return one recipe's body from the repository justfile."""
    lines = (_REPO_ROOT / "justfile").read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(f"{name}:"):
            continue
        body = list(itertools.takewhile(lambda following: following.startswith((" ", "\t")), lines[index + 1 :]))
        return "\n".join(body)
    pytest.fail(f"the justfile declares no {name!r} recipe")


def test_the_localized_build_recipe_compiles_once_for_every_language() -> None:
    """``docs-langs`` is one compile under the canonical HTML root, and names no language.

    The recipe used to delegate to ``docs-lang`` once per translation target,
    which was one Sphinx build per language and a hand-listed set that could
    fall short of the catalogue set. One compile carries every language the site
    publishes (``test_docs_build_localized_compile`` reads that set off its
    output), so the recipe has nothing to list, and a line that names a language
    here is the per-language build coming back.
    """
    lines = [line.strip() for line in _justfile_recipe("docs-langs").splitlines() if line.strip()]

    assert len(lines) == 1, f"docs-langs runs more than the one compile: {lines}"
    assert "-m dev.docs.compile_once" in lines[0], f"docs-langs does not run the one compile: {lines[0]}"
    assert '--html-root "{{CADRUMO_DOCS_BUILD_ROOT}}/html"' in lines[0], (
        f"docs-langs writes the language roots somewhere other than under the canonical HTML root: {lines[0]}"
    )
    assert "--language" not in lines[0], f"docs-langs builds a language on its own again: {lines[0]}"
    assert "docs-lang " not in lines[0], f"docs-langs builds a language on its own again: {lines[0]}"


def test_the_single_language_build_recipe_renders_into_that_language_root() -> None:
    """``docs-lang LANG`` puts its build in ``LANG``'s own root, not the English one."""
    body = _justfile_recipe("docs-lang LANG")

    assert "--language {{LANG}}" in body, f"docs-lang no longer selects a catalogue: {body}"
    assert '--out-dir "{{CADRUMO_DOCS_BUILD_ROOT}}/html/{{LANG}}"' in body, (
        f"docs-lang renders into the canonical English root instead of its own language root: {body}"
    )
