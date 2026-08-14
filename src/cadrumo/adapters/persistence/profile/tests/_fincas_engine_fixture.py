"""Canonical real-SQL engine fixture for the fincas repository tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from .....tests.secure_sql import isolated_runtime_profile
from ...storage.sql.engine import get_engine


@pytest.fixture(autouse=True)
def engine(tmp_path: Path) -> Iterator[Engine]:
    """Provide a real encrypted SQL engine through the profile runtime."""

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield get_engine(profile.settings)


__all__ = ["engine"]
