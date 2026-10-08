"""Every process that reads one published authority derives one verdict key.

A recorded clean verdict is reusable only by a later process, so a key that
depended on anything drawn per process would make the cache record verdicts it
can never serve.
"""

from __future__ import annotations

import os
import sys
from typing import Final

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_PRINT_KEY: Final = (
    "from dev.docs.sequences.checks import default_docs_root\n"
    "from dev.docs.sequences.verdict_cache import published_verdict_key\n"
    "print(published_verdict_key(docs_root=default_docs_root(), goldens_root=None))\n"
)


def _key_in_a_fresh_process() -> str:
    result = run_command(
        [sys.executable, "-c", _PRINT_KEY],
        cwd=REPO_ROOT,
        environment=dict(os.environ),
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_two_processes_reading_one_authority_derive_the_same_key() -> None:
    first = _key_in_a_fresh_process()
    assert len(first) == 64
    assert _key_in_a_fresh_process() == first
