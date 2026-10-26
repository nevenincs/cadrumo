from collections.abc import Iterator

import pytest

from .. import client


def reset_client_process_state() -> None:
    """Clear test-owned process state between client cases."""
    client._PROVIDER_PACING.clear()


@pytest.fixture(autouse=True)
def _fresh_client_process_state() -> Iterator[None]:
    reset_client_process_state()
    yield
    reset_client_process_state()
