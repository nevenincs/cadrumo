"""The registry test host composes the outward ports its services resolve.

The worked-example modules in this tree drive real application services, and
those services resolve outward ports from the host that composed them. The
composition fixture is session-scoped and AUTOUSE, so it reaches only the tree
whose conftest binds it -- which made "is this tree composed?" a property that
was only ever observed indirectly, as an ``InternalInvariantError`` surfacing
from whichever aggregation happened to read a profile record first.

Asserting it here states the host's obligation directly, and names the missing
binding when it is gone instead of blaming the calculation that tripped over
it.
"""

from __future__ import annotations

import pytest

from cadrumo.application.user_profile.custody_ports import profile_custody_port
from cadrumo.application.user_profile.login_session_port import profile_login_session_port

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_login_session_port_is_composed_for_this_tree() -> None:
    """``profile_login_session_port()`` resolves rather than refusing."""
    assert profile_login_session_port() is not None


def test_the_custody_port_is_composed_for_this_tree() -> None:
    """Its paired custody port comes from the same composition."""
    assert profile_custody_port() is not None
