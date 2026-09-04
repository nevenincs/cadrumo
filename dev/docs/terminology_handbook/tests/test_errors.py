"""Canonical ownership tests for the Terminology Handbook errors."""

from __future__ import annotations

from importlib import import_module

import pytest

from .. import errors
from ..errors import TerminologyError, TerminologyLoadError, TerminologyValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

handbook_package = import_module("..", __package__)


def test_errors_live_in_public_defining_module_without_facade_reexports() -> None:
    """The public module owns the hierarchy and the package forwards nothing.

    The assertion used to scan the package's ``__all__`` for names matching
    ``Terminology*Error``, which assumed an ``__all__`` existed to scan - true
    only while the initialiser forwarded forty-nine other names. The property it
    was after survives and is stated directly: the initialiser exports nothing,
    so no name can be absent from a list that no longer exists.
    """
    error_types = (TerminologyError, TerminologyLoadError, TerminologyValidationError)
    assert errors.__name__ == "dev.docs.terminology_handbook.errors"
    assert {error_type.__module__ for error_type in error_types} == {errors.__name__}
    assert not hasattr(handbook_package, "__all__"), "an inert initialiser declares no exports"
    assert not hasattr(handbook_package, "TerminologyError")
    assert not hasattr(handbook_package, "TerminologyValidationError")
    # Nothing but submodules, which is what importing a package leaves behind
    # and the only thing an inert initialiser may carry.
    public = [name for name in vars(handbook_package) if not name.startswith("_")]
    assert all(
        getattr(handbook_package, name).__name__.startswith("dev.docs.terminology_handbook.") for name in public
    ), f"the initialiser still forwards non-module names: {public}"
