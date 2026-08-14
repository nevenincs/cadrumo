"""Canonical isolated storage fixture for documentation sequence builds."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.tests.env_scope import scoped_env_var


@pytest.fixture
def _isolated_sequence_storage(tmp_path: Path) -> Iterator[None]:
    root = tmp_path / "cadrumo-store"
    root.mkdir()
    with (
        scoped_env_var("CADRUMO_LOCAL_STORAGE_ROOT", str(root)),
        scoped_env_var("CADRUMO_OUTPUT_LANGUAGE", "en"),
    ):
        yield


__all__ = ["_isolated_sequence_storage"]
