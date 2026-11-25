"""A KDF refusal's served retry flag and its words in every locale say the same thing."""

from __future__ import annotations

import pytest

from ......core.errors.error_codes import build_error_envelope, resolve_error_message
from ..errors import ProfileCustodyBusyRefusedError, ProfileCustodyRefusal
from ..kdf_refusals import busy_refusal, resource_busy_refusal, resource_refusal, supervision_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_RETRY_WORDS = {
    "en": ("try again", "retry"),
    "es": ("vuelve a intentar", "reintent"),
    "ca": ("torna-ho a provar", "reintent"),
    "hu": ("próbáld újra", "újrapróbál"),
}
"""Each locale's ways of telling the person to repeat the call."""


@pytest.mark.parametrize("locale", sorted(_RETRY_WORDS))
def test_a_child_that_did_not_attest_in_time_is_retryable_and_says_so(locale: str) -> None:
    refusal = busy_refusal()

    envelope = build_error_envelope(refusal)

    assert isinstance(refusal, ProfileCustodyBusyRefusedError)
    assert refusal.refusal is ProfileCustodyRefusal.KDF_SUPERVISION_BUSY
    assert envelope.retryable is True
    assert envelope.code == "REFUSED_STORAGE_PROFILE_CUSTODY_BUSY"
    assert envelope.context is not None and envelope.context["refusal"] == "KDF_SUPERVISION_BUSY"
    message = resolve_error_message(refusal, locale=locale).casefold()
    assert any(words in message for words in _RETRY_WORDS[locale]), message


@pytest.mark.parametrize("locale", sorted(_RETRY_WORDS))
def test_supervision_that_cannot_start_is_not_retryable_and_never_says_retry(locale: str) -> None:
    refusal = supervision_refusal()

    envelope = build_error_envelope(refusal)

    assert not isinstance(refusal, ProfileCustodyBusyRefusedError)
    assert refusal.refusal is ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE
    assert envelope.retryable is False
    assert envelope.code == "REFUSED_STORAGE_PROFILE_CUSTODY"
    assert envelope.context is not None and envelope.context["refusal"] == "KDF_SUPERVISION_UNAVAILABLE"
    message = resolve_error_message(refusal, locale=locale).casefold()
    assert message and not message.startswith("errors.")
    assert not any(words in message for words in _RETRY_WORDS[locale]), message


@pytest.mark.parametrize("locale", sorted(_RETRY_WORDS))
def test_a_permit_lock_or_derivation_that_did_not_finish_in_time_is_retryable_and_says_so(locale: str) -> None:
    refusal = resource_busy_refusal()

    envelope = build_error_envelope(refusal)

    assert isinstance(refusal, ProfileCustodyBusyRefusedError)
    assert refusal.refusal is ProfileCustodyRefusal.KDF_RESOURCE_BUSY
    assert envelope.retryable is True
    assert envelope.code == "REFUSED_STORAGE_PROFILE_CUSTODY_BUSY"
    assert envelope.context is not None and envelope.context["refusal"] == "KDF_RESOURCE_BUSY"
    message = resolve_error_message(refusal, locale=locale).casefold()
    assert message != resolve_error_message(busy_refusal(), locale=locale).casefold()
    assert any(words in message for words in _RETRY_WORDS[locale]), message


@pytest.mark.parametrize("locale", sorted(_RETRY_WORDS))
def test_a_host_that_cannot_supply_the_derivation_is_not_retryable_and_never_says_retry(locale: str) -> None:
    refusal = resource_refusal()

    envelope = build_error_envelope(refusal)

    assert not isinstance(refusal, ProfileCustodyBusyRefusedError)
    assert refusal.refusal is ProfileCustodyRefusal.KDF_RESOURCE_LIMIT
    assert envelope.retryable is False
    assert envelope.code == "REFUSED_STORAGE_PROFILE_CUSTODY"
    assert envelope.context is not None and envelope.context["refusal"] == "KDF_RESOURCE_LIMIT"
    message = resolve_error_message(refusal, locale=locale).casefold()
    assert message and not message.startswith("errors.")
    assert not any(words in message for words in _RETRY_WORDS[locale]), message
