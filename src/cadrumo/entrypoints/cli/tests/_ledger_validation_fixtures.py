"""Canonical active-bucket fixture for ledger validation CLI tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ._ledger_validation_support import open_bucket_session


@pytest.fixture(autouse=True)
def _open_bucket_session(tmp_path: Path) -> Iterator[None]:
    with open_bucket_session(tmp_path):
        yield


__all__ = ["_open_bucket_session"]
