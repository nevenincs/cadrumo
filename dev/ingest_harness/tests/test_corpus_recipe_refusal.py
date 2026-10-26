"""The dedicated corpus recipe fails, never skips, on a host with no configured corpus.

Driven through a real child pytest with the recipe's own marker selection, since
what is under test is the verdict an operator sees rather than one function's
refusal.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from dev._paths import REPO_ROOT

from .._key import INGEST_CORPUS_ROOT_ENV

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_the_corpus_recipe_fails_rather_than_skips_without_a_corpus() -> None:
    """Drive the dedicated recipe's own selection on a host with no configured corpus.

    Blank rather than removed: the root conftest fills an absent variable from
    ``env/.env``, and an operator's real corpus there would turn this into a
    passing run that proves nothing.
    """
    environment = os.environ.copy()
    environment.pop("CADRUMO_TEST_RUN_ROOT", None)
    environment[INGEST_CORPUS_ROOT_ENV] = ""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-v",
            "-n0",
            "-m",
            "private_ingest_corpus",
            "dev/ingest_harness/tests/test_corpus_anchors.py",
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == pytest.ExitCode.TESTS_FAILED, output
    assert f"{INGEST_CORPUS_ROOT_ENV} is not set" in output
    summary = next(line for line in reversed(result.stdout.splitlines()) if line.startswith("=") and " in " in line)
    assert "skipped" not in summary, summary
    assert "passed" not in summary, summary
