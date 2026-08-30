from collections.abc import Iterator

import pytest

from ..client import reset_on_host_inference_arena


@pytest.fixture(autouse=True)
def _fresh_arena() -> Iterator[None]:
    reset_on_host_inference_arena()
    yield
    reset_on_host_inference_arena()
