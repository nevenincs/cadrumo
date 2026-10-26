"""Real CLI coverage for the sessionless ownership of the durable all-profile reset verbs."""

from __future__ import annotations

import pytest

from .._bootstrap_exempt import is_bootstrap_exempt

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_config_reset_group_has_exact_sessionless_bootstrap_ownership() -> None:
    for path in (
        "config reset start",
        "config reset status",
        "config reset resume",
    ):
        assert is_bootstrap_exempt(path)
    assert is_bootstrap_exempt("config auth reset") is False
