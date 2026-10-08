"""Preflight must never promote a terminal or missing native login to authority."""

import pytest

from ..linux_manager_probe import require_graphical

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_graphical_native_identity_required() -> None:
    evidence: dict[str, object] = {
        "uids": [1000] * 4,
        "effective_capabilities": 0,
        "owner_uid": 1000,
        "session": "c1",
        "type": "wayland",
        "class": "user",
        "state": "active",
        "active": True,
        "remote": False,
    }
    require_graphical(evidence, 1000)
    for field, value in (
        ("type", "tty"),
        ("session", ""),
        ("owner_uid", 1001),
        ("uids", [1000, 0, 0, 0]),
        ("effective_capabilities", 1),
        ("active", False),
        ("state", "closing"),
        ("class", "manager"),
        ("remote", True),
        ("native_identity_error", "No data available"),
    ):
        with pytest.raises(RuntimeError, match="graphical logind"):
            require_graphical({**evidence, field: value}, 1000)
    with pytest.raises(RuntimeError, match="graphical logind"):
        require_graphical(evidence, 0)
