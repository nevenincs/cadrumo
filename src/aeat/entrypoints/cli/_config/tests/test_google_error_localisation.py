"""Locale coverage for the `aeat config google ...` error refusal helper.

`_google_refusal` is the single chokepoint every `aeat config google`
command routes adapter failures through. Before it existed the commands
re-raised `CliRefusedBoundaryError(str(exc))` — a literal-positional
refusal that rendered the adapter's English message verbatim in every
locale. These tests lock the contract that the helper dispatches on the
concrete exception type to a localised `cli.config.google.errors.*`
frame instead.
"""

from __future__ import annotations

import pytest

from .....adapters.outbound.google import (
    GoogleAuthClientNotRegisteredError,
    GoogleAuthError,
    GoogleAuthExpiredError,
    GoogleAuthValidationError,
)
from .....adapters.outbound.storage import OutboundStorageError
from .....core.errors import resolve_error_message
from .....core.i18n import tr
from .._google import _google_refusal

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _refusal_message(exc: GoogleAuthError | OutboundStorageError) -> str:
    """Return the operator-facing string the helper would surface."""

    return resolve_error_message(_google_refusal(exc))


def test_each_error_type_routes_to_its_own_localised_key() -> None:
    """Each concrete adapter exception renders its own translation key.

    The assertion compares against `tr(key, ...)` to prove routing, then
    guards against the tautology where `tr` echoes a missing key back:
    the rendered message must differ from both the bare key and the raw
    `str(exc)` the old code leaked.
    """

    expected: dict[GoogleAuthError | OutboundStorageError, str] = {
        GoogleAuthValidationError("raw adapter detail"): "cli.config.google.errors.validation",
        GoogleAuthClientNotRegisteredError("raw adapter detail"): "cli.config.google.errors.client_not_registered",
        GoogleAuthExpiredError("raw adapter detail"): "cli.config.google.errors.token_expired",
        OutboundStorageError("raw adapter detail"): "cli.config.google.errors.storage",
    }

    rendered: set[str] = set()
    for exc, key in expected.items():
        message = _refusal_message(exc)
        assert message == tr(key, detail=str(exc)), (type(exc).__name__, message)
        assert message != key, f"{key} rendered as the bare key — missing locale entry"
        assert message != str(exc), f"{type(exc).__name__} leaked the raw adapter string"
        rendered.add(message)

    assert len(rendered) == len(expected), "distinct error types collapsed to the same frame"


def test_detail_interpolating_key_carries_the_adapter_specifics() -> None:
    """Keys that interpolate `{detail}` keep the adapter's own text."""

    message = _refusal_message(GoogleAuthValidationError("missing installed wrapper"))
    assert "missing installed wrapper" in message


def test_unknown_google_error_falls_back_to_the_generic_frame() -> None:
    """A bare `GoogleAuthError` with no dedicated key uses `auth_failed`."""

    message = _refusal_message(GoogleAuthError("unclassified failure"))
    assert message == tr("cli.config.google.errors.auth_failed", detail="unclassified failure")
    assert "unclassified failure" in message
