"""A registered message never opens with its own category's prefix.

``render_error_text`` owns the category prefix and writes it before the message,
so a catalogue message that restates it ("Refused. Refused. ...") prints the
word twice. The check runs over every declared code in every supported locale.
"""

from __future__ import annotations

import pytest

from ...external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ...i18n.render import lookup_translation
from ..error_codes import declared_error_codes_by_qualname

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _word(text: str) -> str:
    return text.strip().rstrip(".:").strip().casefold()


def test_no_registered_message_begins_with_its_own_category_prefix() -> None:
    offenders: list[str] = []
    checked = 0
    for error_code in declared_error_codes_by_qualname().values():
        for locale in SUPPORTED_OUTPUT_LANGUAGES:
            message = lookup_translation(error_code.message_key, locale=locale)
            if message is None or message == "":
                continue
            checked += 1
            prefix = _word(
                lookup_translation(f"errors.prefix.{error_code.category.value.lower()}", locale=locale) or ""
            )
            if prefix and message.strip().casefold().startswith(prefix):
                offenders.append(f"{locale} {error_code.message_key}: {message[:50]!r}")
    assert checked
    assert not offenders, offenders
