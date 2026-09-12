"""Private error-code helper contracts owned by the core errors package."""

from __future__ import annotations

import ast
import inspect

import pytest

from ...i18n.render import UnmatchedPlaceholderError
from ..error_codes import (
    _DEFERRED_BIND,
    _category_text_prefix,
    _flush_deferred_binds,
    get_registered_error_code,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_category_prefix_resolution_has_no_in_code_translation_default() -> None:
    """Category presentation must resolve through the locale catalogue alone."""
    tree = ast.parse(inspect.getsource(_category_text_prefix))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    translation_calls = [node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "tr"]

    assert translation_calls
    assert all(keyword.arg != "default" for call in translation_calls for keyword in call.keywords)


def test_deferred_bind_flushes_on_get_registered_error_code() -> None:
    """bind_error_code defers silently when _DECLARED_CODE_BY_QUALNAME is unavailable.

    Simulates the circular-import window by manually placing a registered
    class into _DEFERRED_BIND, clearing its .code attribute, then verifying
    that get_registered_error_code rebinds it correctly.  This is the path
    that prevents the ValueError crash seen by Inés / Diego when parallel
    agent __pycache__ writes produced a stale pyc for registry/_core.py.
    """

    # UnmatchedPlaceholderError is registered in registry/_core.py.
    # Confirm it is already correctly bound in normal operation.
    code_before = get_registered_error_code(UnmatchedPlaceholderError)
    assert code_before.code == "INTERNAL_I18N_UNMATCHED_PLACEHOLDER"

    # Simulate the deferred state: remove from _CLASS_CODE_REGISTRY and
    # add to _DEFERRED_BIND (as if __init_subclass__ fired mid-init).
    from ..error_codes import _CLASS_CODE_REGISTRY

    saved_code = _CLASS_CODE_REGISTRY.pop(UnmatchedPlaceholderError, None)
    _DEFERRED_BIND.add(UnmatchedPlaceholderError)

    try:
        # _flush_deferred_binds should rebind the class without raising.
        _flush_deferred_binds()
        assert UnmatchedPlaceholderError not in _DEFERRED_BIND, "class should have been flushed out of _DEFERRED_BIND"
        assert UnmatchedPlaceholderError in _CLASS_CODE_REGISTRY, "class should have been added to _CLASS_CODE_REGISTRY"
        rebound = get_registered_error_code(UnmatchedPlaceholderError)
        assert rebound.code == "INTERNAL_I18N_UNMATCHED_PLACEHOLDER"
    finally:
        # Restore invariant regardless of assertion outcome.
        if saved_code is not None:
            _CLASS_CODE_REGISTRY[UnmatchedPlaceholderError] = saved_code
        _DEFERRED_BIND.discard(UnmatchedPlaceholderError)
