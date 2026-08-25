"""Real-behaviour tests for CLI error-boundary cast narrowing.

These tests pin the memoised wrapper branch in
:func:`~entrypoints.cli.errors.command_error_boundary` and the
:func:`~entrypoints.cli.errors._is_memoised_wrapper` TypeGuard used to recover
the callback's original callable type. The coverage is intentionally
identity- and behaviour-based: wrapping the same callback twice must return the
same object, and the wrapper must still behave like the original callback.

No mocks, skips, expected-fail markers, or tautological assertions are used.

See Also:
    :mod:`~entrypoints.cli.errors`
        Shared CLI error-emission boundary that owns callback wrapping,
        memoisation, and typed stderr emission.
    :class:`~core.errors.CadrumoError`
        Central typed error base forwarded through the command boundary.

Every CLI callback must pass through the central error boundary and its
registry-backed renderer; the CLI backend boundary keeps error handling
centralized, never duplicated per command.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ..errors import _is_memoised_wrapper, command_error_boundary

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# ---------------------------------------------------------------------------
# contract: TypeGuard narrowing for valid / invalid callables
# ---------------------------------------------------------------------------


def test_is_memoised_wrapper_narrows_callable() -> None:
    """``_is_memoised_wrapper`` returns True for any callable object."""

    def plain_func() -> int:
        return 1

    assert _is_memoised_wrapper(plain_func) is True

    class _CallableClass:
        def __call__(self) -> int:
            return 2

    assert _is_memoised_wrapper(_CallableClass()) is True
    assert _is_memoised_wrapper(lambda: None) is True


def test_is_memoised_wrapper_rejects_non_callable() -> None:
    """``_is_memoised_wrapper`` returns False for non-callable objects."""

    assert _is_memoised_wrapper(42) is False
    assert _is_memoised_wrapper("string") is False
    assert _is_memoised_wrapper(None) is False
    assert _is_memoised_wrapper(object()) is False


def test_command_error_boundary_memoised_wrapper_returns_same_object() -> None:
    """Wrapping the same callback twice returns the identical wrapper object.

    This exercises the memoised-wrapper branch at line where the cast
    (CAST-RATIONALE-ERRORS-MEMOISED-WRAPPER) lives. The returned object must
    be the same callable that was stored in the first wrapping call, confirming
    the TypeGuard + cast path is traversed and returns the correct narrowed value.
    """

    def my_callback(x: int) -> str:
        return str(x)

    first_wrapped: Callable[[int], str] = command_error_boundary(my_callback)
    second_wrapped: Callable[[int], str] = command_error_boundary(my_callback)

    # The memoised path must return the same object identity.
    assert first_wrapped is second_wrapped

    # The wrapped callable must behave identically to the original.
    assert first_wrapped(99) == "99"
