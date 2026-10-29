"""The navigation register as searchable data: which views exist and how a link to one is spelled.

The register is neutral, versioned data shipped with the client contracts. This
module answers three questions about it and nothing else: which views match a
text, what one view id names, and whether one ``cadrumo://view`` link is valid.
Every row names the view's id, parent, surfaces, link parameters with their
value grammar, keywords, label key and the label in the profile's language,
plus the link that opens it. Retired ids are never answered as views.

A view link only shows, selects or focuses; it grants nothing and carries no
profile. The answers here are orientation, not authority.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Final

from cadrumo.core.i18n.render import lookup_translation
from cadrumo_client.contracts.navigation import (
    PREFER_KEY,
    NavigationElement,
    NavigationRegister,
    ViewLink,
    ViewLinkRefused,
    ViewOpened,
    load_navigation_register,
    parse_view_link,
    resolve_view,
    view_link,
)

VIEW_PAGE_DEFAULT: Final = 10
"""How many views a search answers when the call names no limit."""

VIEW_PAGE_MAX: Final = 50
"""The most views one search answers."""

_WORD: Final = re.compile(r"[a-z0-9]+")
_PREFIX_MIN: Final = 3

# What a query word scores where it matches: an id segment names the view most
# exactly, then its label, then its search keywords; a prefix of any of them least.
_ID_SCORE: Final = 4
_LABEL_SCORE: Final = 3
_KEYWORD_SCORE: Final = 2
_PREFIX_SCORE: Final = 1


def _words(text: str) -> tuple[str, ...]:
    """Lowercase, accent-free words, so ``sincronización`` matches ``sincronizacion``."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    bare = "".join(char for char in folded if not unicodedata.combining(char))
    return tuple(match.group() for match in _WORD.finditer(bare))


def _label(element: NavigationElement, language: str) -> str:
    """The element's label in ``language``, else in English, else its key."""
    return (
        lookup_translation(element.label, locale=language)
        or lookup_translation(element.label, locale="en")
        or (element.label)
    )


def _row(register: NavigationRegister, element: NavigationElement, language: str) -> dict[str, Any]:
    """One view as the agent reads it."""
    params = {
        name: {
            "kind": kind,
            "alphabet": register.value_kind(kind).alphabet,
            "length": register.value_kind(kind).length,
        }
        for name, kind in sorted(element.params.items())
    }
    return {
        "id": element.id,
        "parent": element.parent,
        "surfaces": [surface.value for surface in element.surfaces],
        "params": params,
        "keywords": list(element.keywords.split()),
        "label": _label(element, language),
        "label_key": element.label,
        "link": view_link(element.id, register=register),
    }


def _score(element: NavigationElement, label: str, query: tuple[str, ...]) -> int:
    """How well every query word matches the view's id, label and keywords; zero when one word matches nothing."""
    segments = set(_words(element.id.replace("/", " ")))
    label_words = set(_words(label))
    keywords = set(_words(element.keywords))
    everything = segments | label_words | keywords
    total = 0
    for word in query:
        score = (
            _ID_SCORE * (word in segments) + _LABEL_SCORE * (word in label_words) + _KEYWORD_SCORE * (word in keywords)
        )
        if not score and len(word) >= _PREFIX_MIN and any(candidate.startswith(word) for candidate in everything):
            score = _PREFIX_SCORE
        if not score:
            return 0
        total += score
    return total


def _opens(register: NavigationRegister, request: ViewLink) -> dict[str, Any] | None:
    """Where a valid link opens by the surfaces the register declares, or ``None`` when none does.

    This is the register's answer, not a running surface's: a surface that
    implements less than it declares can open the link elsewhere, with a notice.
    """
    outcome = resolve_view(request, register=register)
    if not isinstance(outcome, ViewOpened):
        return None
    return {
        "surface": outcome.surface.value,
        "view": outcome.opened,
        "fallback": outcome.fallback,
        "params_kept": outcome.params == request.params,
        "notice_due": outcome.notice_due,
    }


def view_register_query(args: dict[str, Any], language: str) -> dict[str, Any]:
    """Answer one ``views`` call: an exact id, a link to check, a text to search, or the whole register.

    ``language`` is the profile's output language; each label is resolved in
    it and the reply names it.
    """
    if sum(args.get(name) is not None for name in ("id", "link", "query")) > 1:
        raise ValueError("a views call names at most one of id, link and query")
    register = load_navigation_register()
    if (view_id := args.get("id")) is not None:
        element = register.element(view_id)
        if element is None:
            return {"outcome": "not_found", "id": view_id, "language": language}
        return {"outcome": "found", "language": language, "views": [_row(register, element, language)]}
    if (text := args.get("link")) is not None:
        return _view_link_query(register, text, language)
    return _search_views(register, args, language)


def _view_link_query(register: NavigationRegister, text: str, language: str) -> dict[str, Any]:
    """Validate a view link and report its declared navigation destination."""
    parsed = parse_view_link(text, register=register)
    if isinstance(parsed, ViewLinkRefused):
        return {"outcome": "invalid", "reason": parsed.reason.value}
    # The parser admits only a registered element, so its lineage starts with it.
    element = register.lineage(parsed.view_id)[0]
    return {
        "outcome": "valid",
        "language": language,
        "link": view_link(parsed.view_id, dict(parsed.params), parsed.prefer, register=register),
        "view": _row(register, element, language),
        "params": dict(parsed.params),
        PREFER_KEY: None if parsed.prefer is None else parsed.prefer.value,
        "opens": _opens(register, parsed),
    }


def _search_views(register: NavigationRegister, args: dict[str, Any], language: str) -> dict[str, Any]:
    """Page the complete view register or its stable lexical relevance ranking."""
    limit = args.get("limit", VIEW_PAGE_DEFAULT)
    query = _words(args.get("query") or "")
    if not query:
        rows = [_row(register, element, language) for element in register.elements]
        return {"outcome": "found", "language": language, "views": rows[:limit], "total": len(rows)}
    ranked = sorted(
        (
            (score, index, element)
            for index, element in enumerate(register.elements)
            if (score := _score(element, _label(element, language), query))
        ),
        key=lambda match: (-match[0], match[1]),
    )
    return {
        "outcome": "found",
        "language": language,
        "views": [_row(register, element, language) for _score_value, _index, element in ranked[:limit]],
        "total": len(ranked),
    }
