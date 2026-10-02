"""The corpus root is configured, never guessed, and its absence fails a run.

These cases need no corpus, so they run in the ordinary lane: they prove that a
corpus-reading run on a machine without the corpus refuses with the remedy,
rather than skipping or reading whatever sits at a path baked into the source.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from .._key import INGEST_CORPUS_ROOT_ENV, CorpusKeyError, CorpusRootError, corpus_root, load_corpus_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_an_unconfigured_root_is_refused_with_the_variable_and_the_recipe(
    configured: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if configured is None:
        monkeypatch.delenv(INGEST_CORPUS_ROOT_ENV, raising=False)
    else:
        monkeypatch.setenv(INGEST_CORPUS_ROOT_ENV, configured)

    with pytest.raises(CorpusRootError, match=rf"{INGEST_CORPUS_ROOT_ENV} is not set.*just test-ingest-corpus"):
        corpus_root()
    with pytest.raises(CorpusRootError):
        load_corpus_key()


def test_a_root_that_does_not_exist_is_refused_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    absent = tmp_path / "no-corpus-here"
    monkeypatch.setenv(INGEST_CORPUS_ROOT_ENV, str(absent))

    with pytest.raises(CorpusRootError, match=re.escape(str(absent))):
        corpus_root()


def test_a_directory_without_the_key_is_not_a_corpus_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(INGEST_CORPUS_ROOT_ENV, str(tmp_path))

    with pytest.raises(CorpusRootError, match=re.escape("holds no GROUND_TRUTH.json")):
        corpus_root()


def test_a_configured_root_carrying_another_key_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "GROUND_TRUTH.json").write_text('{"schema_version": "1.0", "documents": []}', encoding="utf-8")
    monkeypatch.setenv(INGEST_CORPUS_ROOT_ENV, str(tmp_path))

    assert corpus_root() == tmp_path
    with pytest.raises(CorpusKeyError, match=f"not the pinned v5 key.*{INGEST_CORPUS_ROOT_ENV}"):
        load_corpus_key()
