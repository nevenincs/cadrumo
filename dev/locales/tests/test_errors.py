"""Canonical ownership tests for locale-tool errors."""

from __future__ import annotations

from importlib import import_module

import pytest

from .. import errors
from ..errors import LocaleError, LocaleWriteConflictError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

locales_package = import_module("..", __package__)


def test_errors_live_in_public_defining_module_without_facade_reexports() -> None:
    """The public module owns both classes and the package stays structural for them."""
    assert errors.__name__ == "dev.locales.errors"
    assert LocaleError.__module__ == errors.__name__
    assert LocaleWriteConflictError.__module__ == errors.__name__
    assert "LocaleError" not in locales_package.__all__
    assert "LocaleWriteConflictError" not in locales_package.__all__
    assert not hasattr(locales_package, "LocaleError")
    assert not hasattr(locales_package, "LocaleWriteConflictError")
