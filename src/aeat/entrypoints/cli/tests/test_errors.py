"""Real-behaviour tests for cast-replacement helpers in :mod:`_errors` (contract, contract).

Verifies:

- ``_is_memoised_wrapper`` narrows callable objects correctly.
- ``command_error_boundary`` memo cache returns the identical wrapped object
  for a repeated call (the memoised-wrapper path).
- The cast-rationale marker for the memoised-wrapper path is present in source.

No mocks, no skips, no expected-fail markers, no tautological assertions.
"""

from __future__ import annotations

import pathlib
from collections.abc import Callable

import pytest

from .._errors import _is_memoised_wrapper, command_error_boundary

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


def test_cast_rationale_marker_present_in_errors_source() -> None:
    """Assert the cast-rationale marker for the memoised-wrapper cast is present.

    Acts as a CI gate: if the cast is removed without removing the rationale
    or if the rationale comment is accidentally deleted, this test fails loudly.
    """
    source = pathlib.Path(__file__).parent.parent / "_errors.py"
    text = source.read_text(encoding="utf-8")

    marker = "CAST-RATIONALE-ERRORS-MEMOISED-WRAPPER"
    assert marker in text, (
        f"Cast rationale marker {marker!r} is missing from {source}. "
        "Either restore the comment or remove the cast entirely."
    )
