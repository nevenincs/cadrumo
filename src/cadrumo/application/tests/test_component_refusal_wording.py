"""Refusals for a component that is not set up read plainly in every language.

Each refusal names the component the way Setup names it and, when setup can
repair it, says to set it up. The text comes from the real locale catalogues;
a sentence must never carry a command, an exception name or an internal term.
"""

from __future__ import annotations

import re

import pytest

from ...core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ...core.i18n.render import lookup_translation
from ..dependency_registry import BROWSER_DECLARATION, LOCAL_AI_DECLARATION
from ..dependency_wording import dependency_name_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INTERNAL = re.compile(r"(?i)\b(runtime|provision\w*|playwright|headless|digest|ollama|chromium|api|aeat)\b|_|`")

_BROWSER_SET_UP = "adapters.browser.errors.not_provisioned"
_BROWSER_NOT_USABLE = "adapters.browser.errors.not_usable"
_READER_LOCAL_AI = "errors.refused.refused_ledger_evidence_local_ai_not_ready"
_READER_UNAVAILABLE = "errors.refused.refused_ledger_evidence_reader_unavailable"
_IMPORT_LOCAL_AI = "application.provisioning.refusal.column_names_local_ai_not_ready"
_IMPORT_UNSERVABLE = "application.provisioning.refusal.column_names_local_ai_unavailable"
_LABEL_LOCAL_AI = "application.ledger.evidence.label_reading.local_ai_not_ready"
_LABEL_UNAVAILABLE = "application.ledger.evidence.label_reading.reader_unavailable"

#: Each sentence and the component it names, or ``None`` when the reader may be any.
_SENTENCES = {
    _BROWSER_SET_UP: BROWSER_DECLARATION,
    _BROWSER_NOT_USABLE: BROWSER_DECLARATION,
    _READER_LOCAL_AI: LOCAL_AI_DECLARATION,
    _READER_UNAVAILABLE: None,
    _IMPORT_LOCAL_AI: LOCAL_AI_DECLARATION,
    _IMPORT_UNSERVABLE: LOCAL_AI_DECLARATION,
    _LABEL_LOCAL_AI: LOCAL_AI_DECLARATION,
    _LABEL_UNAVAILABLE: None,
}
#: The sentences whose refusal setup repairs, so they say to set the component up.
_OFFERS_SETUP = frozenset({_BROWSER_SET_UP, _READER_LOCAL_AI, _IMPORT_LOCAL_AI, _LABEL_LOCAL_AI})
_LABEL_PLACEHOLDERS = ("%{count}", "%{fields}")


def _text(key: str, locale: str) -> str:
    text = lookup_translation(key, locale=locale)
    assert text is not None and text.strip(), f"{key} has no {locale} text"
    assert text != key
    return text


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_every_refusal_is_authored_plainly_in_every_language(locale: str) -> None:
    for key in _SENTENCES:
        text = _text(key, locale)
        bare = re.sub(r"%\{\w+\}", "", text)
        assert not _INTERNAL.search(bare), f"{key} in {locale} uses an internal term: {text!r}"
    for key in (_LABEL_LOCAL_AI, _LABEL_UNAVAILABLE):
        text = _text(key, locale)
        assert all(placeholder in text for placeholder in _LABEL_PLACEHOLDERS), f"{key} in {locale}: {text!r}"


@pytest.mark.parametrize("locale", tuple(locale for locale in SUPPORTED_OUTPUT_LANGUAGES if locale != "en"))
def test_every_refusal_is_translated(locale: str) -> None:
    for key in _SENTENCES:
        assert _text(key, locale) != _text(key, "en"), f"{key} is untranslated in {locale}"


def test_a_refusal_setup_repairs_says_so_and_one_it_cannot_does_not() -> None:
    for key in _SENTENCES:
        text = _text(key, "en")
        assert ("Set it up" in text) is (key in _OFFERS_SETUP), f"{key}: {text!r}"


def test_each_refusal_names_its_component_as_setup_names_it() -> None:
    for key, declaration in _SENTENCES.items():
        if declaration is None:
            continue
        name = _text(dependency_name_key(declaration), "en")
        assert name.lower() in _text(key, "en").lower(), f"{key} does not name {name!r}"
