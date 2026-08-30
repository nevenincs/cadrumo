"""Real-behavior tests for MasterKeyReentrantError envelope round-trip (contract).

Asserts that:
- `MasterKeyReentrantError` is raised on re-entrant context-manager use.
- The exception is a registered `CadrumoError` subclass with a bound `ErrorCode`.
- `build_error_envelope` round-trips the exception to a well-formed `ErrorEnvelope`.
"""

from __future__ import annotations

import secrets

import pytest

from ......core.config import override_settings
from ......core.errors.error_codes import ERROR_REGISTRY, build_error_envelope, render_error_text
from ......core.i18n import clear_output_language_cache
from ......tests.master_key import EphemeralMasterKeyProvider
from ...bucket import BucketLockedError
from ..errors import MasterKeyReentrantError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_ephemeral_provider_raises_reentrant_error_on_second_enter() -> None:
    """EphemeralMasterKeyProvider.__enter__ raises MasterKeyReentrantError on re-entry."""

    key = secrets.token_bytes(32)
    provider = EphemeralMasterKeyProvider(key=key)

    with provider, pytest.raises(MasterKeyReentrantError) as exc_info:
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

    assert envelope.code == "INTERNAL_MASTER_KEY_REENTRANT"
    assert envelope.category == "INTERNAL"
    assert envelope.message != ""
    assert envelope.retryable is False
    assert envelope.message  # non-empty translated message


def test_master_key_reentrant_error_carries_provider_name_in_context() -> None:
    """MasterKeyReentrantError surfaces provider_name in its context dict."""

    err = MasterKeyReentrantError("EphemeralMasterKeyProvider")

    assert err.context is not None
    assert err.context["provider_name"] == "EphemeralMasterKeyProvider"


def test_a_locked_runtime_state_renders_the_locked_operator_category() -> None:
    """A locked runtime state is a LOCKED category, not an auth rejection.

    Re-founded on the bucket-session lock after the keychain-locked error was
    deleted with the shared-master key store it reported on. The property is
    the storage layer's, not that one class's: a lock the operator can clear
    must reach them as LOCKED, so the envelope steers them to unlocking rather
    than to re-entering a credential. Keeping the property and moving its
    subject is the point -- deleting the case with the class would have retired
    the assertion along with the thing it was merely using to make it.
    """
    err = BucketLockedError(bucket_id="2f9a4c61-7b30-4e58-9d12-6a05c8e3b7f4")
    envelope = build_error_envelope(err)

    assert envelope.code == "LOCKED_STORAGE_BUCKET_SESSION"
    assert envelope.category == "LOCKED"
    # The rendered prefix is localised and the catalogue default is Spanish, so
    # the operator category is asserted against a pinned language.
    with override_settings(cadrumo_output_language="en"):
        clear_output_language_cache()
        try:
            assert render_error_text(err).startswith("Locked. ")
        finally:
            clear_output_language_cache()
