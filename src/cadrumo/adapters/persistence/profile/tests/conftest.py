"""Fixtures for profile persistence integration tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests._file_flow_support import _file_flow_runtime, _FileFlowRuntime, _Repos, _repos


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    yield from _repos(tmp_path)


@pytest.fixture
def file_flow_runtime(tmp_path: Path) -> Iterator[_FileFlowRuntime]:
    """Yield the file-flow repository bundle alongside its live engine."""
    yield from _file_flow_runtime(tmp_path)
