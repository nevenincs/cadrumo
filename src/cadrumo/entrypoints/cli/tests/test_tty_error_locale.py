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

    exc = NonTtyRefusedError()
    assert exc.args == (), (
        f"NonTtyRefusedError.args must be empty so the error registry "
        f"message_key is used for locale resolution; got {exc.args!r}"
    )


def test_non_tty_refused_error_has_no_recovery_transport_attribute() -> None:
    """The renderer receives a typed verdict, never a copied command string."""

    exc = NonTtyRefusedError()
    assert not hasattr(exc, "suggestion")


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


# ---------------------------------------------------------------------------
# contract-C: secure-input refusal keys resolve to real operator-facing copy
# ---------------------------------------------------------------------------


_SECURE_INPUT_REFUSAL_KEYS = (
    "cli.config.custody.errors.non_interactive_secret_required",
    "cli.config.custody.errors.secrets_channel_conflict",
    "cli.config.custody.errors.secrets_fd_invalid_json",
    "cli.config.custody.errors.secrets_fd_missing_fields",
    "cli.config.custody.errors.secrets_fd_reserved_stream",
    "cli.config.custody.errors.secrets_fd_too_large",
    "cli.config.custody.errors.secrets_fd_unreadable",
    "cli.config.custody.errors.secrets_stdin_invalid_json",
    "cli.config.custody.errors.secrets_stdin_missing_fields",
    "cli.config.custody.errors.secrets_stdin_too_large",
)


@pytest.mark.parametrize("key", _SECURE_INPUT_REFUSAL_KEYS)
def test_secure_input_refusal_keys_resolve(key: str) -> None:
    """Every custody secure-input refusal key resolves to non-placeholder copy.

    These are the localized TTY / bounded-stdin refusals the custody verbs
    raise through :class:`CliRefusedBoundaryError`; a missing key would ship a
    raw catalogue path to the operator at the exact moment they are locked out.
    """

    resolved = tr(key)
    assert key not in resolved, f"Key {key!r} was not substituted in the locale catalogue; got {resolved!r}"
    assert len(resolved) > 10, f"Key {key!r} resolved to suspiciously short string: {resolved!r}"
