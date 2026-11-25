"""Runtime host tests start real runtime processes for test-owned roots."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo_client.transport.tests.account_transport import release_hosted_runtime_endpoints


@pytest.fixture(autouse=True)
def hosted_runtime_endpoints_are_released(tmp_path: Path) -> Iterator[None]:
    """Clear the account transport entries that the test's runtime processes left for its roots."""
    yield
    release_hosted_runtime_endpoints(tmp_path)
