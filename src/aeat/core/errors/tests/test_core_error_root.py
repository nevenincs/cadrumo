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


def test_core_error_is_subclass_of_aeat_error() -> None:
    """CoreError descends from AeatError so the registry constraint applies."""
    assert issubclass(CoreError, AeatError)


def test_catching_core_error_catches_concrete_subclass_instance() -> None:
    """A concrete CoreError subclass instance is caught by a CoreError handler.

    Non-tautological: the concrete class must genuinely inherit from
    CoreError for the isinstance check inside the except clause to fire.
    If the inheritance were removed the except arm would not be reached
    and the assertion would never execute — pytest would report the test
    as erroring with an uncaught CoreValidationError, not as a pass.
    """
    caught: CoreError | None = None
    try:
        raise CoreValidationError("invariant violated")
    except CoreError as exc:
        caught = exc

    assert caught is not None, "CoreError except arm was not reached"
    assert isinstance(caught, CoreValidationError)
    assert isinstance(caught, CoreError)
    assert isinstance(caught, AeatError)


def test_catching_aeat_error_catches_core_error_subclass() -> None:
    """The AeatError catch surface covers CoreError subclasses.

    Verifies the full MRO: CoreValidationError -> CoreError -> AeatError.
    """
    caught: AeatError | None = None
    try:
        raise CoreValidationError("mro check")
    except AeatError as exc:
        caught = exc

    assert caught is not None
    assert isinstance(caught, CoreError)


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


def test_core_validation_error_catch_order_is_well_defined() -> None:
    """CoreValidationError is catchable as CoreError, AeatError, and ValueError.

    The MRO for CoreValidationError is:
      CoreValidationError -> CoreError -> AeatError -> Exception
                         -> ValueError -> Exception

    A handler that catches the most specific type wins. Assert all three
    catch sites fire correctly so the catch order is unambiguous.
    """
    exc = CoreValidationError("bad input")
    assert isinstance(exc, CoreValidationError)
    assert isinstance(exc, CoreError)
    assert isinstance(exc, AeatError)
    assert isinstance(exc, ValueError)

    # Narrowest catch fires first
    caught_as_validation: CoreValidationError | None = None
    try:
        raise CoreValidationError("narrow catch")
    except CoreValidationError as e:
        caught_as_validation = e
    assert caught_as_validation is not None

    # ValueError arm also works (pydantic field validator compatibility)
    caught_as_value_error: ValueError | None = None
    try:
        raise CoreValidationError("value error arm")
    except ValueError as e:
        caught_as_value_error = e
    assert caught_as_value_error is not None
    assert isinstance(caught_as_value_error, CoreValidationError)


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
