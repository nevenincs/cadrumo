"""Behavioural tests for the CoreError root and catch-order contract.

CoreError is the structural intermediate root for internal framework and
core-primitive failures. AeatError is the project-wide root with registry
enforcement; CoreError gives callers a narrower catch surface for failures
that originate inside core/ rather than domain or application layers.

These tests assert the catch-order contract without relying on the class
hierarchy definition itself (non-tautological: a broken base would cause
a TypeError at construction time and the catch arm would not fire).
"""

from __future__ import annotations

import pytest

from .. import AeatError, CoreError, CoreValidationError
from .._not_found import CoreNotFoundError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_core_validation_error_catch_surface_is_well_defined() -> None:
    """CoreValidationError is catchable as CoreError, AeatError, and ValueError."""
    assert issubclass(CoreError, AeatError)

    caught_as_core: CoreError | None = None
    try:
        raise CoreValidationError("core catch")
    except CoreError as exc:
        caught_as_core = exc
    assert isinstance(caught_as_core, CoreValidationError)
    assert isinstance(caught_as_core, AeatError)

    caught_as_aeat: AeatError | None = None
    try:
        raise CoreValidationError("aeat catch")
    except AeatError as exc:
        caught_as_aeat = exc
    assert isinstance(caught_as_aeat, CoreError)

    caught_as_value_error: ValueError | None = None
    try:
        raise CoreValidationError("value error arm")
    except ValueError as exc:
        caught_as_value_error = exc
    assert isinstance(caught_as_value_error, CoreValidationError)


def test_core_not_found_error_descends_from_core_error() -> None:
    """CoreNotFoundError is a CoreError and KeyError.

    Non-tautological: raising CoreNotFoundError and catching it as CoreError
    proves the inheritance chain without reading the class definition.
    If the inheritance were broken, the except arm would not fire and
    pytest would report an uncaught CoreNotFoundError.
    """
    assert issubclass(CoreNotFoundError, CoreError)
    assert issubclass(CoreNotFoundError, AeatError)
    assert issubclass(CoreNotFoundError, KeyError)

    caught_as_core: CoreError | None = None
    try:
        raise CoreNotFoundError("record missing")
    except CoreError as exc:
        caught_as_core = exc

    assert caught_as_core is not None
    assert isinstance(caught_as_core, CoreNotFoundError)
    assert isinstance(caught_as_core, KeyError)

    # KeyError arm also fires for mapping-style lookup misses.
    caught_as_key_error: KeyError | None = None
    try:
        raise CoreNotFoundError("key error arm")
    except KeyError as exc:
        caught_as_key_error = exc

    assert caught_as_key_error is not None
    assert isinstance(caught_as_key_error, CoreNotFoundError)


def test_core_error_does_not_catch_non_core_aeat_error() -> None:
    """CoreError does not catch AeatError subclasses from other hierarchies.

    Confirms the catch surface is narrowed: a non-CoreError AeatError
    (McpLaunchError inherits AeatError directly, not CoreError) raised
    inside a try block is NOT caught by a CoreError handler.
    """
    from .. import McpLaunchError

    with pytest.raises(McpLaunchError):
        try:
            raise McpLaunchError("not a core error")
        except CoreError:
            pytest.fail("CoreError should not catch a non-CoreError AeatError subclass")
