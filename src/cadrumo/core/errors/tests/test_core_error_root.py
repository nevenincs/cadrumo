"""Behavioural tests for the CoreError root and catch-order contract.

CoreError is the structural intermediate root for internal framework and
core-primitive failures. CadrumoError is the project-wide root with registry
enforcement; CoreError gives callers a narrower catch surface for failures
that originate inside core/ rather than domain or application layers.

These tests assert the catch-order contract without relying on the class
hierarchy definition itself (non-tautological: a broken base would cause
a TypeError at construction time and the catch arm would not fire).
"""

from __future__ import annotations

import pytest

from ..hierarchy import CadrumoError, CoreError, CoreValidationError
from ..not_found import CoreNotFoundError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_core_validation_error_catch_surface_is_well_defined() -> None:
    """CoreValidationError is canonical and does not impersonate ValueError."""
    assert issubclass(CoreError, CadrumoError)

    caught_as_core: CoreError | None = None
    try:
        raise CoreValidationError("core catch")
    except CoreError as exc:
        caught_as_core = exc
    assert isinstance(caught_as_core, CoreValidationError)
    assert isinstance(caught_as_core, CadrumoError)

    caught_as_cadrumo: CadrumoError | None = None
    try:
        raise CoreValidationError("cadrumo catch")
    except CadrumoError as exc:
        caught_as_cadrumo = exc
    assert isinstance(caught_as_cadrumo, CoreError)

    assert not issubclass(CoreValidationError, ValueError)


def test_core_not_found_error_descends_from_core_error() -> None:
    """CoreNotFoundError is a canonical CoreError, not a KeyError alias.

    Non-tautological: raising CoreNotFoundError and catching it as CoreError
    proves the inheritance chain without reading the class definition.
    If the inheritance were broken, the except arm would not fire and
    pytest would report an uncaught CoreNotFoundError.
    """
    assert issubclass(CoreNotFoundError, CoreError)
    assert issubclass(CoreNotFoundError, CadrumoError)
    assert not issubclass(CoreNotFoundError, KeyError)

    caught_as_core: CoreError | None = None
    try:
        raise CoreNotFoundError("record missing")
    except CoreError as exc:
        caught_as_core = exc

    assert caught_as_core is not None
    assert isinstance(caught_as_core, CoreNotFoundError)


def test_core_error_does_not_catch_non_core_cadrumo_error() -> None:
    """CoreError does not catch CadrumoError subclasses from other hierarchies.

    Confirms the catch surface is narrowed: a non-CoreError CadrumoError
    (NoActiveProfileError inherits CadrumoError directly, not CoreError)
    raised inside a try block is NOT caught by a CoreError handler.
    """
    from ..hierarchy import NoActiveProfileError

    with pytest.raises(NoActiveProfileError):
        try:
            raise NoActiveProfileError("not a core error")
        except CoreError:
            pytest.fail("CoreError should not catch a non-CoreError CadrumoError subclass")
