"""Canonical active-bucket fixture for ledger validation CLI tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ._ledger_validation_support import open_bucket_session


@pytest.fixture
def bucket(tmp_path: Path) -> Iterator[None]:
    with open_bucket_session(tmp_path):
        yield


@pytest.fixture(autouse=True)
def _open_bucket_session(bucket: None) -> None:
    return bucket


__all__ = ["_open_bucket_session", "bucket"]
