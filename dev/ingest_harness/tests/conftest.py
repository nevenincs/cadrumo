"""Shared fixtures for the ingestion harness tests."""

import pytest

from .._key import CorpusKey, load_corpus_key


@pytest.fixture(scope="module")
def key() -> CorpusKey:
    """Load the real pinned corpus key once per test module."""
    return load_corpus_key()
