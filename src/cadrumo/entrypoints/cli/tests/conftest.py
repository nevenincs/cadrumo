"""Directory-scoped fixtures for the CLI behavior tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ._overview_native_support import registered_overview_profile
from .runtime_profile_cli_fixture import NativeCliProfileFixture


@pytest.fixture
def native_overview_profile(tmp_path: Path) -> Iterator[NativeCliProfileFixture]:
    """Register a readiness-complete synthetic profile before worker login."""
    with registered_overview_profile(tmp_path) as fixture:
        yield fixture
