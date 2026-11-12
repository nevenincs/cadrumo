"""Every profile access refusal reason is served as plain words in every locale."""

from __future__ import annotations

import pytest

from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.core.i18n.render import tr
from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ..access_errors import ProfileAccessRefusedError
from ..access_refusal_words import access_refusal_message_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("es", "ca", "en", "hu")


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("reason", list(AccessDenialCode), ids=lambda reason: reason.value)
def test_every_reason_resolves_to_words_in_every_locale(reason: AccessDenialCode, locale: str) -> None:
    key = access_refusal_message_key(reason)
    words = tr(key, locale=locale)
    assert words != key
    assert words != reason.value
    assert "%{" not in words
    assert "{" not in words
    assert len(words.split()) >= 4


@pytest.mark.parametrize("reason", list(AccessDenialCode), ids=lambda reason: reason.value)
def test_every_reason_has_its_own_key(reason: AccessDenialCode) -> None:
    keys = {access_refusal_message_key(member) for member in AccessDenialCode}
    assert len(keys) == len(AccessDenialCode)
    assert access_refusal_message_key(reason) in keys


def test_unknown_reason_reads_as_the_generic_operation_refusal() -> None:
    assert access_refusal_message_key("not_a_reason") == access_refusal_message_key(AccessDenialCode.OPERATION_DENIED)


def test_busy_subject_is_explained_not_shown_as_a_token() -> None:
    error = ProfileAccessRefusedError(AccessDenialCode.SUBJECT_BUSY)
    message = resolve_error_message(error, locale="en")
    assert message != AccessDenialCode.SUBJECT_BUSY.value
    assert "subject_busy" not in message
    assert "earlier operation" in message


@pytest.mark.parametrize("locale", _LOCALES)
def test_each_locale_words_differ_between_reasons(locale: str) -> None:
    served = {tr(access_refusal_message_key(member), locale=locale) for member in AccessDenialCode}
    assert len(served) == len(AccessDenialCode)
