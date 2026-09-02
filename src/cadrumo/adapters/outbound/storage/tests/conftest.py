from pathlib import Path

import pytest

from ..local import LocalFileSystemProvider


@pytest.fixture
def provider(tmp_path: Path) -> LocalFileSystemProvider:
    return LocalFileSystemProvider(tmp_path / "vault")
