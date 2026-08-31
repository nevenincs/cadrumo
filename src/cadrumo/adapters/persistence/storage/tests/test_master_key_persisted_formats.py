"""Master-key persisted-format contracts."""

import pytest

from .._storage_path_definitions import LOGIN_THROTTLE_FILENAME
from ..master_key import login_throttle

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_login_throttle_sidecar_name_is_declared_once() -> None:
    assert login_throttle.LOGIN_THROTTLE_FILENAME == LOGIN_THROTTLE_FILENAME
