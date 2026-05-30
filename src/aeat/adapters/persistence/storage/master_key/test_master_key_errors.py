"""Real-behavior tests for MasterKeyReentrantError envelope round-trip (S245).

Asserts that:
- `MasterKeyReentrantError` is raised on re-entrant context-manager use.
- The exception is a registered `AeatError` subclass with a bound `ErrorCode`.
- `build_error_envelope` round-trips the exception to a well-formed `ErrorEnvelope`.
"""

from __future__ import annotations

import secrets

import pytest

from aeat.core.errors import ERROR_REGISTRY, build_error_envelope
from aeat.adapters.persistence.storage.master_key._errors import MasterKeyReentrantError
from aeat.adapters.persistence.storage.master_key import EphemeralMasterKeyProvider

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


def test_ephemeral_provider_raises_reentrant_error_on_second_enter() -> None:
    """EphemeralMasterKeyProvider.__enter__ raises MasterKeyReentrantError on re-entry."""

    key = secrets.token_bytes(32)
    provider = EphemeralMasterKeyProvider(key=key)

    with provider:
        with pytest.raises(MasterKeyReentrantError) as exc_info:
            provider.__enter__()

    assert exc_info.value.provider_name == "EphemeralMasterKeyProvider"


def test_master_key_reentrant_error_is_registered() -> None:
    """MasterKeyReentrantError must have a bound ErrorCode in ERROR_REGISTRY."""

    err = MasterKeyReentrantError("SomeProvider")
    code = err.code

    assert code.code == "INTERNAL_MASTER_KEY_REENTRANT"
    assert code.code in ERROR_REGISTRY


def test_master_key_reentrant_error_envelope_round_trip() -> None:
    """build_error_envelope produces a well-formed envelope from MasterKeyReentrantError."""

    err = MasterKeyReentrantError("TestProvider")
    envelope = build_error_envelope(err)

    assert envelope.schema_version == "1"
    assert envelope.code == "INTERNAL_MASTER_KEY_REENTRANT"
    assert envelope.category == "INTERNAL"
    assert envelope.retryable is False
    assert envelope.message  # non-empty translated message


def test_master_key_reentrant_error_carries_provider_name_in_context() -> None:
    """MasterKeyReentrantError surfaces provider_name in its context dict."""

    err = MasterKeyReentrantError("FileFallbackMasterKeyProvider")

    assert err.context is not None
    assert err.context["provider_name"] == "FileFallbackMasterKeyProvider"
