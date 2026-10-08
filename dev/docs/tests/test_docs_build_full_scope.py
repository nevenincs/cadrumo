"""Full-scope nitpicky docs build gate: the whole handbook, autodoc included.

One real ``-b dummy -n -W`` Sphinx build over the full documentation set — the
~1,200 ``automodule`` stubs that import the entire application plus every
narrative page. This is the single most expensive build in the docs lane, so it
lives alone in this module: pytest-xdist distributes by file, and the compile
of every language with its witness build
(``test_docs_build_localized_compile``) runs concurrently instead of queueing
behind it.
Shared machinery and the hook-dedupe rationale live in
:mod:`dev.docs.tests._sphinx_build_harness`.

"""

from __future__ import annotations

from pathlib import Path

import pytest

from ._sphinx_build_harness import (
    copy_docs_source,
    gate_build_env,
    run_nitpicky_dummy_build,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_sphinx_nitpicky_build_is_clean(tmp_path: Path) -> None:
    """The nitpicky, warnings-as-errors full-scope build must succeed.

    Uses the ``dummy`` builder, not ``html``: the gate only asserts that the
    full parse and cross-reference resolution (where ``-n`` nitpicky warnings
    fire) raise no warnings under ``-W``; it does not need rendered HTML, so
    rendered-page emission is skipped.

    Args:
        tmp_path: Pytest-provided isolated output directory.
    """
    docs_source = copy_docs_source(tmp_path)
    result = run_nitpicky_dummy_build(
        docs_source,
        tmp_path / "out",
        gate_build_env(tmp_path),
    )
    assert result.returncode == 0, (
        "nitpicky sphinx build reported warnings or errors:\n"
        + (result.stdout or "")[-6000:]
        + (result.stderr or "")[-6000:]
    )
