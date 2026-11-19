"""Every process that reads one published authority derives the same per-sequence verdict keys.

A recorded clean verdict is reusable only by a later process, so a key that
depended on anything drawn per process would make the cache record verdicts it
can never serve.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Final

import pytest

from dev.packaging.command_execution import run_command
from dev.paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_PRINT_KEYS: Final = (
    "import json\n"
    "from dev.docs.sequences.checks import default_docs_root, discover_sequences\n"
    "from dev.docs.sequences.verdict_cache import published_sequence_verdicts\n"
    "docs_root = default_docs_root()\n"
    "verdicts = published_sequence_verdicts(docs_root=docs_root, goldens_root=None)\n"
    "discovered, problems = discover_sequences(docs_root=docs_root)\n"
    "assert not problems, problems\n"
    "keys = {f'{item.page}/{item.sequence_id}': verdicts.key(item) for item in discovered}\n"
    "print(json.dumps({'corpus': verdicts.corpus_key, 'keys': keys}))\n"
)


def _keys_in_a_fresh_process() -> dict[str, object]:
    result = run_command(
        [sys.executable, "-c", _PRINT_KEYS],
        cwd=REPO_ROOT,
        environment=dict(os.environ),
    )
    assert result.returncode == 0, result.stderr
    document = json.loads(result.stdout.strip().splitlines()[-1])
    assert isinstance(document, dict)
    return {str(name): value for name, value in document.items()}


def test_two_processes_reading_one_authority_derive_the_same_corpus_and_sequence_keys() -> None:
    first = _keys_in_a_fresh_process()
    corpus = first["corpus"]
    keys = first["keys"]
    assert isinstance(corpus, str) and len(corpus) == 64
    assert isinstance(keys, dict) and keys, "the committed corpus must enrol sequences"
    assert len(set(keys.values())) == len(keys), "every sequence carries its own key"
    assert all(corpus != key for key in keys.values())
    assert _keys_in_a_fresh_process() == first
