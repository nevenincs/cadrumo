"""Absence gate: no access-gate refusal carries an authored sentence.

The two refusals this package raises must reach the operator through a
registered locale key, never through English pinned at the raise site.
Asserting the key and the context alone cannot hold that line: message
resolution prefers the key, so a sentence passed alongside it stays hidden
from such an assertion while ``str(exc)`` still prefers the positional
argument and carries the English into tracebacks, logs, and every boundary
rendering the exception directly, in every locale.

The live-read refusal declares a ``translated_message`` and is asserted for the
*absence* of any authored sentence: ``str(exc)`` must equal exactly that key.

The permanent live-write refusal is asserted for its terminal disposition and
for the raise site passing no arguments, but NOT yet for that absence — see the
note on its test.

Real ``Settings`` through the real override seam; no doubles.
"""

from __future__ import annotations

import pytest

from ...config import load_settings, override_settings
from ...errors.error_codes import get_registered_error_code, resolve_error_message
from ..errors import AeatLiveReadNotEnabledError, LiveSubmitForbiddenError
from ..gate import AeatAccessGate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_LIVE_READ_KEY = "errors.refused.refused_access_gate_live_read_not_enabled"
_LIVE_SUBMIT_KEY = "errors.locked.locked_access_gate_live_submit_forbidden"


def test_live_read_refusal_renders_as_its_key_only() -> None:
    """The pytest live-read refusal carries the key and machine facts, no prose."""
    with override_settings(cadrumo_live_tests_enabled="0"), pytest.raises(AeatLiveReadNotEnabledError) as excinfo:
        AeatAccessGate(settings=load_settings()).require_live_read()

    error = excinfo.value
    assert error.translated_message == _LIVE_READ_KEY
    assert str(error) == error.translated_message, f"the raise site carries an authored sentence: {str(error)!r}"
    assert str(error) == _LIVE_READ_KEY
    assert error.context == {
        "env_var": "CADRUMO_LIVE_TESTS_ENABLED",
        "required_value": "1",
        "current_value": "0",
        "live_reads_enabled": False,
    }
    assert get_registered_error_code(error).code == "REFUSED_ACCESS_GATE_LIVE_READ_NOT_ENABLED"
    resolved = resolve_error_message(error)
    assert resolved and resolved != _LIVE_READ_KEY


def test_live_write_refusal_is_terminal_and_argument_free_at_the_raise_site() -> None:
    """The permanent write refusal is terminal and passes nothing at the raise site.

    Live AEAT submission has no recovery: no action an operator can take
    unlocks it, so the refusal binds no continuation and advertises no retry.
    The gate raises it with no constructor arguments at all.

    This asserts the raise site and the terminal disposition only. It
    deliberately does NOT assert that ``str(exc)`` equals the registered key,
    because today it does not: the class defaults an authored English sentence
    into its first positional parameter, so every call site in the tree looks
    argument-free while the prose still reaches ``args``. Adding the absence
    assertion is the job of whoever removes that default; asserting the
    present behaviour instead would pin the defect as the contract.
    """
    with override_settings(cadrumo_live_tests_enabled="1"), pytest.raises(LiveSubmitForbiddenError) as excinfo:
        AeatAccessGate(settings=load_settings()).require_live_write()

    error = excinfo.value
    assert error.context is None
    code = get_registered_error_code(error)
    assert code.code == "LOCKED_ACCESS_GATE_LIVE_SUBMIT_FORBIDDEN"
    assert code.message_key == _LIVE_SUBMIT_KEY
    assert not code.retryable, "a permanently forbidden write must never advertise a retry"
    resolved = resolve_error_message(error)
    assert resolved and resolved != _LIVE_SUBMIT_KEY
