"""Shared runner for the per-language nitpicky docs build gates.

Underscore-prefixed so it is never collected as a test module. Holds the one
build the per-language modules each drive once, so the assertion exists in one
place while pytest-xdist still sees one heavy build per file (see
:mod:`dev.docs.tests._sphinx_build_harness` for why that split matters).
"""

from __future__ import annotations

from pathlib import Path

from ..i18n import TARGET_LANGUAGES
from ._sphinx_build_harness import copy_docs_source, gate_build_env, run_nitpicky_dummy_build

#: The filename stem every per-language gate module shares. The coverage gate in
#: ``test_docs_build_localized`` derives the module set from it, so the stem is
#: named once rather than spelled out in each place that matches on it.
LOCALIZED_MODULE_STEM = "test_docs_build_localized_"


def assert_localized_user_scope_build_is_nitpicky_clean(tmp_path: Path, language: str) -> None:
    """Run one language's user-scope ``-n -W`` build and assert it is clean.

    An untranslated or fuzzy segment falls back to English at render time -- that
    fallback is refused by the separate completeness gate, not here -- so the
    structural build must be as clean in every language as it is in English
    (``test_docs_build_user_scope`` covers the English source). The full autodoc
    build stays English-only.

    Args:
        tmp_path: Pytest-provided isolated output directory.
        language: The BCP-47 translation target to build.

    Raises:
        AssertionError: When ``language`` is not a declared translation target,
            or when the build reports warnings or errors.
    """
    assert language in TARGET_LANGUAGES, (
        f"{language!r} is not a declared translation target ({TARGET_LANGUAGES}); a gate module "
        "for a language the catalogue set does not carry builds a root nobody publishes"
    )
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
