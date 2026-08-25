"""Architecture contract for the application-owned login-session port."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest

from cadrumo.application.user_profile.login_session_port import (
    ProfileLoginSessionPort,
    bind_profile_login_session_port,
    profile_login_session_port,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_login_session_application_modules_have_no_persistence_imports() -> None:
    owner = Path(__file__).parents[1]
    for filename in ("_login_session.py", "_login_session_port.py"):
        tree = ast.parse((owner / filename).read_text(encoding="utf-8"))
        imported = tuple(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))

        assert not any("adapters.persistence.storage" in module for module in imported)


def test_nested_composition_resolves_the_exact_bound_port() -> None:
    outward_port = cast("ProfileLoginSessionPort", object())

    with bind_profile_login_session_port(outward_port):
        assert profile_login_session_port() is outward_port
