from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.config import override_settings
from .runtime_profile_backend import runtime_cli_profile


@pytest.fixture(name="_active_cli_profile")
def active_cli_profile_fixture(tmp_path: Path) -> Iterator[None]:
    with override_settings(cadrumo_output_language="en"), runtime_cli_profile(tmp_path=tmp_path):
        yield
