"""Canonical ownership tests for locale-tool errors."""

from __future__ import annotations

from importlib import import_module

import pytest

from .. import errors
from ..errors import LocaleError, LocaleWriteConflictError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

locales_package = import_module("..", __package__)


def test_errors_live_in_public_defining_module_without_facade_reexports() -> None:
    """The public module owns both classes and the package forwards nothing.

    The assertion used to read the package's ``__all__`` and check the two error
    names were absent from it. That spelling assumed the initialiser still had an
    ``__all__`` to read, which was true while it forwarded forty-three other
    names and stopped being true when it was reduced to an inert namespace
    marker. The property it was after survives and is now stated directly and
    more strongly: the initialiser exports nothing at all, so no name can be
    absent from a list that no longer exists.
    """
    assert errors.__name__ == "dev.locales.errors"
    assert LocaleError.__module__ == errors.__name__
    assert LocaleWriteConflictError.__module__ == errors.__name__
    assert not hasattr(locales_package, "__all__"), "an inert initialiser declares no exports"
    assert not hasattr(locales_package, "LocaleError")
    assert not hasattr(locales_package, "LocaleWriteConflictError")
    # Nothing but submodules and dunders, which is what importing a package
    # leaves behind and is the only thing an inert initialiser may carry.
    public = [name for name in vars(locales_package) if not name.startswith("_")]
    assert all(getattr(locales_package, name).__name__.startswith("dev.locales.") for name in public), (
        f"the initialiser still forwards non-module names: {public}"
    )
