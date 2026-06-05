"""Smoke-test that the ``questionary`` prompt backend is importable."""

from __future__ import annotations

from importlib.metadata import version

import pytest
from packaging.version import Version

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_questionary_imports() -> None:
    """The wizard runtime requires ``questionary>=2.1.1`` at import time."""

    import questionary

    assert hasattr(questionary, "text")
    assert hasattr(questionary, "select")
    assert hasattr(questionary, "confirm")
    assert hasattr(questionary, "checkbox")
    assert hasattr(questionary, "path")
    assert hasattr(questionary, "password")


def test_questionary_version_satisfies_floor() -> None:
    """Installed ``questionary`` distribution must be at the supported floor."""

    installed = Version(version("questionary"))
    assert installed >= Version("2.1.1")
