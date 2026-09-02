"""Canonical runtime-profile fixtures for CLI suites that need a populated bucket."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from ....tests.secure_sql import isolated_runtime_profile

__all__ = ["_isolated_cli_state"]


@contextmanager
def _runtime_profile_state(tmp_path: Path) -> Generator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path):
        yield


@pytest.fixture(autouse=True)
def _isolated_cli_state(tmp_path: Path) -> Iterator[None]:
    with _runtime_profile_state(tmp_path):
        yield
