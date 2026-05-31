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

from aeat.core.errors import AeatError, CoreError, CoreValidationError

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


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


def test_core_error_does_not_catch_non_core_aeat_error() -> None:
    """CoreError does not catch AeatError subclasses from other hierarchies.

    Confirms the catch surface is narrowed: a non-CoreError AeatError
    (McpLaunchError inherits AeatError directly, not CoreError) raised
    inside a try block is NOT caught by a CoreError handler.
    """
    from aeat.core.errors import McpLaunchError  # noqa: PLC0415

    with pytest.raises(McpLaunchError):
        try:
            raise McpLaunchError("not a core error")
        except CoreError:
            pytest.fail("CoreError should not catch a non-CoreError AeatError subclass")
