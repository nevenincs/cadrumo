"""User-scope nitpicky docs build gate: the operator surface, no autodoc.

One real ``-b dummy -n -W`` build of the operator-facing surface under
``CADRUMO_DOCS_SCOPE=user``. Split into its own module so pytest-xdist's
per-file distribution runs it concurrently with the full-scope and localized
builds (see :mod:`dev.docs.tests._sphinx_build_harness` for the shared
machinery, the hook-dedupe rationale, and the timeout rationale).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.docs.tests._sphinx_build_harness import (
    copy_docs_source,
    gate_build_env,
    run_nitpicky_dummy_build,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs, pytest.mark.timeout(1800)]


def test_user_scope_build_is_nitpicky_clean_and_excludes_api(tmp_path: Path) -> None:
    """A real user-scope ``-n -W`` build succeeds, excludes docs/api, keeps user pages.

    The operator-facing surface builds clean under nitpicky warnings-as-errors
    with ``CADRUMO_DOCS_SCOPE=user``: the API autodoc tree is excluded from the
    read set (so the application is never imported to render it) and the scoped
    API-reference suppression resolves the handful of user->api links, while every
    other reference class still reds the gate. The enrolled user pages (and their
    executed cli-sequence directives) build. Full scope is covered by
    ``test_docs_build_full_scope.test_sphinx_nitpicky_build_is_clean``.

    Args:
        tmp_path: Pytest-provided isolated output directory.
    """
    docs_source = copy_docs_source(tmp_path)
    result = run_nitpicky_dummy_build(
        docs_source,
        tmp_path / "out",
        gate_build_env(tmp_path, CADRUMO_DOCS_SCOPE="user"),
    )
    assert result.returncode == 0, (
        "nitpicky user-scope build reported warnings or errors:\n"
        + (result.stdout or "")[-6000:]
        + (result.stderr or "")[-6000:]
    )
    combined = result.stdout + result.stderr
    # An enrolled user page built; the excluded API tree was never read (no api
    # docname in the read set) and no residual api reference survived the scoped
    # suppression to reach the warning stream.
    assert "how-to/quickstart" in combined
    assert "api/cadrumo" not in combined
