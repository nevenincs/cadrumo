"""Tokens for the authoritative locale audit."""

from __future__ import annotations

import re

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import extract_placeholders
from cadrumo.domain.calculations.registry.censo_modelos import CensoModeloEventKind

from .signal_command_paths import command_path_pattern
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
    TRANSLATION_PASCAL_IDENTIFIER_RE,
    TRANSLATION_PATH_RE,
    TRANSLATION_PLACEHOLDER_RE,
    TRANSLATION_ROLE_MARKER_RE,
    TRANSLATION_RST_LINK_RE,
    TRANSLATION_RST_ROLE_RE,
    TRANSLATION_URL_RE,
)

# These are complete command-contract choice lists, not vocabulary exceptions.
# Exact lower-case tokens come from the same types used by command admission.
# The spelling of the surrounding explanation and each gloss stays visible.
_OUTPUT_LANGUAGE_CHOICES_RE = re.compile(
    r"\(" + r"\s*,\s*".join(re.escape(language.value) for language in OutputLanguage) + r"\)"
)
# Area labels in the asset basis forms carry the SI unit, not a prose word.
# Match only the complete, case-sensitive symbol; adjacent letters or another
# exponent remain visible to spelling checks.
_AREA_UNIT_RE = re.compile(r"(?<!\w)m²(?!\w)")
_CENSO_GLOSSED_CHOICES_RE = re.compile(
    rf"(?<!\w)(?P<alta>{re.escape(CensoModeloEventKind.ALTA.value)})(?P<alta_gloss>\s*\([^()\r\n]+\))"
    rf",\s*(?P<modificacion>{re.escape(CensoModeloEventKind.MODIFICACION.value)})"
    rf"(?P<modificacion_gloss>\s*\([^()\r\n]+\)),\s*(?:or\s+)?"
    rf"(?P<baja>{re.escape(CensoModeloEventKind.BAJA.value)})(?P<baja_gloss>\s*\([^()\r\n]+\))"
)


def _visible_choice_glosses(match: re.Match[str]) -> str:
    """Remove only the three exact event tokens, preserving every gloss character."""
    text = list(match.group())
    for name in ("alta", "modificacion", "baja"):
        start, end = match.span(name)
        text[start - match.start() : end - match.start()] = [" "] * (end - start)
    return "".join(text)


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
    return filtered_translation_text(value)[0].casefold()


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
        (_OUTPUT_LANGUAGE_CHOICES_RE, " "),
        (_CENSO_GLOSSED_CHOICES_RE, _visible_choice_glosses),
        (TRANSLATION_URL_RE, " "),
        (TRANSLATION_PATH_RE, " "),
        (command_path_pattern(), " "),
        (TRANSLATION_OPTION_RE, " "),
        (TRANSLATION_FORMULA_RE, " "),
        (_AREA_UNIT_RE, " "),
        (TRANSLATION_NUMERIC_RE, " "),
        (TRANSLATION_IDENTIFIER_RE, " "),
        (TRANSLATION_PASCAL_IDENTIFIER_RE, " "),
        (TRANSLATION_CODE_RE, " "),
        (TRANSLATION_ROLE_MARKER_RE, " "),
    ):
        text, matches = pattern.subn(replacement, text)
        excluded += matches
    text = re.sub(r"[,;]+", " ", text)
    return " ".join(text.split()), excluded


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


def translation_words(
    value: str, *, preserve_apostrophes: bool = False, preserve_periods: bool = False
) -> tuple[str, ...]:
    """Return alphabetic prose words for locale-quality signals."""
    joiners = "·'’" if preserve_apostrophes else "·"
    ending = r"\.?" if preserve_periods else ""
    return tuple(
        match.group(0) for match in re.finditer(rf"[^\W\d_]+(?:[{joiners}][^\W\d_]+)*{ending}", value, flags=re.UNICODE)
    )
