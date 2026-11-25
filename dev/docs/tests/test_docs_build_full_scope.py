"""Full-scope nitpicky docs build gate: the whole handbook, autodoc included.

One real ``-b dummy -n -W`` Sphinx build over the full documentation set — the
~1,200 ``automodule`` stubs that import the entire application plus every
narrative page. This is the single most expensive build in the docs lane, so it
lives alone in this module: pytest-xdist distributes by file, and the compile
of every language with its witness build
(``test_docs_build_localized_compile``) runs concurrently instead of queueing
behind it.
Shared machinery and the hook-dedupe rationale live in
:mod:`dev.docs.tests.sphinx_build_harness`.

"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dev.packaging.command_execution import CommandResult
from dev.paths import REPO_ROOT

from ..strict_build_record import STRICT_BUILD_RECORD_ENV, strict_build_record_problems
from .sphinx_build_harness import (
    copy_docs_source,
    gate_build_env,
    persist_sphinx_build_output,
    run_nitpicky_dummy_build,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_sphinx_output_artifacts_preserve_complete_streams(tmp_path: Path) -> None:
    """Diagnostic artifacts keep full subprocess streams, beyond the assertion tail."""
    now = datetime.now(UTC)
    result = CommandResult(
        argv=("sphinx-build", "-n", "-W"),
        cwd=str(tmp_path),
        started_at=now,
        completed_at=now,
        duration_seconds=1.0,
        returncode=1,
        stdout="stdout-start\n" + "s" * 9000,
        stderr="stderr-start\n" + "e" * 9000,
    )

    stdout_path, stderr_path, command_path = persist_sphinx_build_output(
        result,
        artifacts_directory=tmp_path,
        label="focused-smoke",
    )

    assert stdout_path.read_text(encoding="utf-8") == result.stdout
    assert stderr_path.read_text(encoding="utf-8") == result.stderr
    command = json.loads(command_path.read_text(encoding="utf-8"))
    assert command["argv"] == list(result.argv)
    assert command["returncode"] == 1


def test_sphinx_nitpicky_build_is_clean(tmp_path: Path) -> None:
    """The nitpicky, warnings-as-errors full-scope build must succeed.

    Uses the ``dummy`` builder, not ``html``: the gate only asserts that the
    full parse and cross-reference resolution (where ``-n`` nitpicky warnings
    fire) raise no warnings under ``-W``; it does not need rendered HTML, so
    rendered-page emission is skipped.

    A lane that already ran the strict full-scope build names its record in
    ``CADRUMO_DOCS_STRICT_BUILD_RECORD``; the record then stands in for this
    build only while it is clean, was taken under the proving configuration
    and the documentation inputs still have the digest it recorded. Anything
    else fails here rather than building again.

    Args:
        tmp_path: Pytest-provided isolated output directory.
    """
    recorded = os.environ.get(STRICT_BUILD_RECORD_ENV, "").strip()
    if recorded:
        problems = strict_build_record_problems(Path(recorded), repo_root=REPO_ROOT)
        assert problems == (), "the recorded strict full-scope build does not prove this contract:\n" + "\n".join(
            problems
        )
        return
    docs_source = copy_docs_source(tmp_path)
    result = run_nitpicky_dummy_build(
        docs_source,
        tmp_path / "out",
        gate_build_env(tmp_path),
    )
    run_root = Path(os.environ["CADRUMO_TEST_RUN_ROOT"]).resolve(strict=True)
    artifacts_directory = run_root / "artifacts"
    stdout_path, stderr_path, command_path = persist_sphinx_build_output(
        result,
        artifacts_directory=artifacts_directory,
        label="fullscope",
    )
    assert result.returncode == 0, (
        "nitpicky sphinx build reported warnings or errors; complete output is retained at "
        f"{stdout_path}, {stderr_path}, and {command_path}:\n"
        + (result.stdout or "")[-6000:]
        + (result.stderr or "")[-6000:]
    )
