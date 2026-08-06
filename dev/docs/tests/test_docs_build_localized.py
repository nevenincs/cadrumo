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

from pathlib import Path

import pytest

from dev.docs.i18n import TARGET_LANGUAGES
from dev.docs.tests._sphinx_build_harness import (
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
