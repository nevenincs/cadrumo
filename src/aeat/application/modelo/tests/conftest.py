"""Pytest fixtures for modelo application tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from ._file_flow_support import _Repos, _repos


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    yield from _repos(tmp_path)
