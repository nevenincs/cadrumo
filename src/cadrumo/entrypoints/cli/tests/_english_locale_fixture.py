"""Canonical English-output fixture for CLI contract tests."""

from collections.abc import Iterator

import pytest

from ....core.config import override_settings
from ....core.i18n.render import clear_output_language_cache


@pytest.fixture(name="_english_locale", autouse=True)
def english_locale_fixture() -> Iterator[None]:
    """Pin rendered CLI assertions to English and clear the locale cache either side."""

    with override_settings(cadrumo_output_language="en"):
        clear_output_language_cache()
        yield
    clear_output_language_cache()


__all__ = ["english_locale_fixture"]
