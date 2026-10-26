"""Architecture contract for the application-owned login-session port."""

from __future__ import annotations

from typing import cast

import pytest

from ..login_session_port import ProfileLoginSessionPort, bind_profile_login_session_port, profile_login_session_port

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_nested_composition_resolves_the_exact_bound_port() -> None:
    outward_port = cast("ProfileLoginSessionPort", object())

    with bind_profile_login_session_port(outward_port):
        assert profile_login_session_port() is outward_port
