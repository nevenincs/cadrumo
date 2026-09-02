"""Locale coverage for the `aeat config google ...` error refusal helper.

The projection delegates message ownership to the central exception registry;
the config package neither repeats a class-name map nor leaks adapter prose.
"""

from __future__ import annotations

import pytest

from .....adapters.outbound.google.errors import (
    GoogleAuthClientNotRegisteredError,
    GoogleAuthError,
    GoogleAuthExpiredError,
    GoogleAuthValidationError,
)
from .....adapters.outbound.storage.errors import OutboundStorageError
from .....core.errors.error_codes import get_registered_error_code, resolve_error_message
from .....core.i18n import tr
from ..google import google_refusal

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _refusal_message(exc: GoogleAuthError | OutboundStorageError) -> str:
    """Return the operator-facing string the helper would surface."""

    return resolve_error_message(google_refusal(exc))


def test_each_error_type_routes_through_the_central_registry() -> None:
    """Each concrete adapter exception uses its registered message authority."""

    errors: tuple[GoogleAuthError | OutboundStorageError, ...] = (
        GoogleAuthValidationError("raw adapter detail"),
        GoogleAuthClientNotRegisteredError("raw adapter detail"),
        GoogleAuthExpiredError("raw adapter detail"),
        OutboundStorageError("raw adapter detail"),
    )

    rendered: set[str] = set()
    for exc in errors:
        key = get_registered_error_code(exc).message_key
        message = _refusal_message(exc)
        assert message == tr(key), (type(exc).__name__, message)
        assert message != key, f"{key} rendered as the bare key — missing locale entry"
        assert message != str(exc), f"{type(exc).__name__} leaked the raw adapter string"
        rendered.add(message)

    assert len(rendered) == len(errors), "distinct registered errors collapsed to the same frame"


def test_base_google_error_uses_its_registered_generic_frame() -> None:
    """The broad adapter base also has one canonical registry entry."""

    exc = GoogleAuthError("unclassified failure")
    assert _refusal_message(exc) == tr(get_registered_error_code(exc).message_key)


def test_google_refusal_keeps_the_adapter_failure_as_factual_detail_only() -> None:
    """The config boundary does not recreate the retired adapter recovery transport."""

    refusal = google_refusal(GoogleAuthValidationError("missing installed wrapper"))

    assert refusal.context is None
    assert not hasattr(refusal, "suggestion")
