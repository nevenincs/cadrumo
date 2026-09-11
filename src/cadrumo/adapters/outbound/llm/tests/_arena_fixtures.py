from collections.abc import Iterator

import pytest

from .. import client


def reset_client_process_state() -> None:
    """Clear test-owned process state between client cases."""
    client._PROVIDER_PACING.clear()
    with client._ON_HOST_ARENA_LOCK:
        if client._on_host_arena is not None and client._on_host_arena.held:
            raise RuntimeError("cannot reset the on-host inference arena while a slot is held")
        client._on_host_arena = None


@pytest.fixture(autouse=True)
def _fresh_arena() -> Iterator[None]:
    reset_client_process_state()
    yield
    reset_client_process_state()
