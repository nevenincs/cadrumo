"""Tax surface fixture declaration through a runtime-owned setup port."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from .cli_fixture_worlds import CliWorldProvider


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, cli_world_provider: CliWorldProvider) -> Iterator[None]:
    with cli_world_provider.backend("surface", tmp_path):
        cli_world_provider.create_surface_profile()
        yield
