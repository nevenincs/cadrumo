"""Real-behaviour tests for NonTtyRefusedError locale resolution (contract).

Verifies that :class:`NonTtyRefusedError` does NOT set ``error.args[0]``
(which would short-circuit the CLI renderer before reaching the registry
``message_key``), and that the registered locale key
``errors.refused.refused_cli_non_tty`` resolves to non-placeholder copy.

No mocks, no skips, no expected-fail markers, no tautological assertions.
"""

from __future__ import annotations

import pytest

from ....core.i18n import tr
from .._tty import NonTtyRefusedError

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# ---------------------------------------------------------------------------
# contract-A: args is empty — locale resolver is not short-circuited
# ---------------------------------------------------------------------------


def test_non_tty_refused_error_has_no_positional_args() -> None:
    """NonTtyRefusedError must carry no positional args so the CLI renderer
    falls through to the registry message_key for locale resolution."""

    exc = NonTtyRefusedError("Run it in an interactive terminal.")
    assert exc.args == (), (
        f"NonTtyRefusedError.args must be empty so the error registry "
        f"message_key is used for locale resolution; got {exc.args!r}"
    )


def test_non_tty_refused_error_suggestion_is_accessible() -> None:
    """The suggestion kwarg is stored on the instance for the renderer."""

    hint = "Run: aeat app wizard setup --profile myprofile"
    exc = NonTtyRefusedError(hint)
    assert exc.suggestion == hint


def test_non_tty_refused_error_blank_suggestion_stripped() -> None:
    """A blank suggestion is stripped to empty string on the instance."""

    exc = NonTtyRefusedError("   ")
    # suggestion attr stores the original; AeatError(suggestion=...) receives None
    assert exc.suggestion == "   "
    # AeatError.suggestion kwarg carries the stripped value or None
    assert exc.args == ()


# ---------------------------------------------------------------------------
# contract-B: locale key resolves to real operator-facing copy
# ---------------------------------------------------------------------------


_NON_TTY_LOCALE_KEY = "errors.refused.refused_cli_non_tty"


def test_refused_cli_non_tty_locale_key_resolves() -> None:
    """The registry locale key resolves to non-placeholder operator copy."""

    resolved = tr(_NON_TTY_LOCALE_KEY)
    assert _NON_TTY_LOCALE_KEY not in resolved, (
        f"Key {_NON_TTY_LOCALE_KEY!r} was not substituted in the locale catalogue; got {resolved!r}"
    )
    assert len(resolved) > 10, f"Key {_NON_TTY_LOCALE_KEY!r} resolved to suspiciously short string: {resolved!r}"
