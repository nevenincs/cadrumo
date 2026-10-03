"""Tokens for the authoritative locale audit."""

from __future__ import annotations

import re

from cadrumo.core.i18n.render import extract_placeholders

from .signal_syntax import (
    TRANSLATION_BRACKET_REFERENCE_RE,
    TRANSLATION_CODE_RE,
    TRANSLATION_FORMULA_RE,
    TRANSLATION_HTML_TAG_RE,
    TRANSLATION_IDENTIFIER_RE,
    TRANSLATION_LITERAL_RE,
    TRANSLATION_MARKDOWN_LINK_RE,
    TRANSLATION_MYST_ROLE_RE,
    TRANSLATION_NUMERIC_RE,
    TRANSLATION_OPTION_RE,
    TRANSLATION_PATH_RE,
    TRANSLATION_PLACEHOLDER_RE,
    TRANSLATION_ROLE_MARKER_RE,
    TRANSLATION_RST_LINK_RE,
    TRANSLATION_RST_ROLE_RE,
    TRANSLATION_URL_RE,
)


def translation_tokens(value: str) -> tuple[frozenset[str], frozenset[str]]:
    """Return expansion placeholders and bracketed casilla references."""
    bracketed = tuple(match.group(1) for match in re.finditer(r"\[([^\[\]\r\n]+)\]", value))
    references = frozenset[str](token for token in bracketed if is_bracket_reference(token))
    return extract_placeholders(value), references


def is_bracket_reference(token: str) -> bool:
    """Whether a bracketed token is a casilla number or compact formula expression."""
    return token.isdecimal() or bool(
        not any(character.isspace() for character in token)
        and any(operator in token for operator in "=+-*/")
        and re.fullmatch(r"[A-Za-z0-9_.+*/=-]+", token)
    )


def human_translation_text(value: str) -> str:
    """Return prose after removing interpolation and transport syntax.

    Similarity and spelling signals are intended to review copied prose, not
    the stable syntax embedded in a message.  Links preserve their visible
    labels while their targets, code/literal spans, paths, options, structured
    identifiers, formulas, and interpolation placeholders are excluded before
    either signal inspects the text.  The original value remains untouched for
    placeholder parity and rendering checks.
    """
    return filtered_translation_text(value)[0]


def filtered_translation_text(value: str) -> tuple[str, int]:
    """Return prose and the number of syntax spans excluded from spelling.

    This is intentionally syntax-only: no locale vocabulary or product-term
    allowlist is consulted.  Link and role callbacks retain explicit visible
    labels, while targets remain outside the dictionary surface.
    """
    text = value
    excluded = 0
    for pattern, replacement in (
        (TRANSLATION_HTML_TAG_RE, " "),
        (TRANSLATION_MARKDOWN_LINK_RE, visible_link_label),
        (TRANSLATION_RST_LINK_RE, visible_link_label),
        (TRANSLATION_RST_ROLE_RE, visible_role_label),
        (TRANSLATION_MYST_ROLE_RE, visible_role_label),
        (TRANSLATION_LITERAL_RE, " "),
        (TRANSLATION_BRACKET_REFERENCE_RE, " "),
        (TRANSLATION_PLACEHOLDER_RE, " "),
        (TRANSLATION_URL_RE, " "),
        (TRANSLATION_PATH_RE, " "),
        (TRANSLATION_OPTION_RE, " "),
        (TRANSLATION_FORMULA_RE, " "),
        (TRANSLATION_NUMERIC_RE, " "),
        (TRANSLATION_IDENTIFIER_RE, " "),
        (TRANSLATION_CODE_RE, " "),
        (TRANSLATION_ROLE_MARKER_RE, " "),
    ):
        text, matches = pattern.subn(replacement, text)
        excluded += matches
    text = re.sub(r"[,;]+", " ", text)
    return " ".join(text.casefold().split()), excluded


def visible_link_label(match: re.Match[str]) -> str:
    """Keep a rendered link label while excluding its target syntax."""
    label = match.group("label").strip()
    return f" {label} " if label else " "


def visible_role_label(match: re.Match[str]) -> str:
    """Keep an explicit role label while excluding its target."""
    target = match.group("target").strip()
    if "<" not in target or not target.endswith(">"):
        return " "
    label = target.rsplit("<", 1)[0].strip()
    return f" {label} " if label else " "


def translation_words(value: str) -> tuple[str, ...]:
    """Return alphabetic prose words for locale-quality signals."""
    return tuple(match.group(0) for match in re.finditer(r"[^\W\d_]+", value, flags=re.UNICODE))
