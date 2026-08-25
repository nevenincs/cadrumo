"""Translation contracts for certificate-authentication failures."""

from __future__ import annotations

import pytest

from ......core.errors import AeatLoginAssertionError
from ......core.i18n import tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_AUTHENTICATOR_LOCALE_KEYS = [
    "adapters.auth.authenticator.errors.already_active",
    "adapters.auth.authenticator.errors.assertion_failed",
    "adapters.auth.authenticator.errors.resume_failed",
    "adapters.auth.authenticator.errors.metadata_parse_failed",
]


@pytest.mark.parametrize(
    ("message", "key"),
    [
        (
            "persisted AEAT session resume did not produce a usable context",
            "adapters.auth.authenticator.errors.resume_failed",
        ),
        (
            "persisted metadata did not produce a parsed model",
            "adapters.auth.authenticator.errors.metadata_parse_failed",
        ),
    ],
)
def test_defensive_failure_carries_translation_key(message: str, key: str) -> None:
    """Defensive certificate-auth failures retain their catalogue key."""
    error = AeatLoginAssertionError(message, translated_message=key)
    assert error.translated_message == key
    assert str(error) == message


@pytest.mark.parametrize("key", _AUTHENTICATOR_LOCALE_KEYS)
def test_authenticator_locale_key_resolves_to_real_copy(key: str) -> None:
    """Every certificate-auth failure key resolves to non-placeholder copy."""
    resolved = tr(key)
    assert key not in resolved
    assert len(resolved) > 10
