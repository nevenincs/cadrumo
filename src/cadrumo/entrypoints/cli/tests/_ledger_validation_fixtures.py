"""Tax ledger validation fixture declarations through an injected world port."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from .cli_fixture_worlds import CliWorldProvider


@pytest.fixture
def bucket(tmp_path: Path, cli_world_provider: CliWorldProvider) -> Iterator[None]:
    with cli_world_provider.backend("validation", tmp_path):
        yield


@pytest.fixture(autouse=True)
def _open_bucket_session(bucket: None) -> None:
    return bucket


__all__ = ["_open_bucket_session", "bucket"]
