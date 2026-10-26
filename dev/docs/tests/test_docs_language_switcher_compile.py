"""A recorded error page must keep absolute links inside every language root."""

from __future__ import annotations

import re

import pytest

from cadrumo.core.external_constants import OutputLanguage

from ..compile_slots import activate, deactivate
from ..language_switcher import switcher_of_page, unresolved_cross_root_links

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_LANGUAGES = ("en", "es", "ca", "hu")


@pytest.mark.parametrize("site_path", ["", "/handbook"])
@pytest.mark.parametrize("at_apex", [True, False], ids=["desktop", "website"])
@pytest.mark.parametrize("source_language", ["en", "es"])
def test_recorded_error_page_preserves_site_base(site_path: str, at_apex: bool, source_language: str) -> None:
    """Exercise actual multi-language recording and independent href resolution."""
    prefixes = {code: "" if at_apex and code == "en" else f"{code}/" for code in _LANGUAGES}
    slots = activate(_LANGUAGES)
    try:
        mark = switcher_of_page(
            [{"code": code, "label": code.upper()} for code in _LANGUAGES],
            language=OutputLanguage(source_language),
            prefixes=prefixes,
            root_uri=f"{site_path}/{prefixes[source_language]}",
            pagename="404",
            aria_label="Language",
        )
        for index, language in enumerate(_LANGUAGES):
            element = slots.resolved(mark, index)
            links = dict((code, href) for href, code in re.findall(r'href="([^"]+)" lang="([^"]+)"', element))
            assert links == {code: f"{site_path}/{prefixes[code]}404.html" for code in _LANGUAGES if code != language}
            assert (
                unresolved_cross_root_links(
                    element,
                    language=language,
                    page="404.html",
                    prefixes=prefixes,
                    files={code: {"404.html"} for code in _LANGUAGES},
                    site_path=site_path,
                )
                == []
            )
    finally:
        deactivate()
