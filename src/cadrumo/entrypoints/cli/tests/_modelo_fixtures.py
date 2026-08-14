from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.config import override_settings
from ....tests.secure_sql import isolated_cli_runtime_profile


@pytest.fixture(name="_active_cli_profile")
def active_cli_profile_fixture(tmp_path: Path) -> Iterator[None]:
    with override_settings(cadrumo_output_language="en"), isolated_cli_runtime_profile(tmp_path=tmp_path):
        yield
