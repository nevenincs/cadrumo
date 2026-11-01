"""Tokens for the authoritative locale audit."""

from __future__ import annotations

import re

from cadrumo.application.review.filter import LedgerReviewFilterKey
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import extract_placeholders
from cadrumo.core.period import accepted_filing_period_codes
from cadrumo.domain.calculations.registry.censo_modelos import CensoModeloEventKind
from cadrumo.domain.modelos.calculation_revision_amendment import M303RectificativaMotive

from .signal_command_paths import command_path_pattern, filter_detail_row_examples, registered_operation_id_pattern
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
# A context field labelled with its own interpolation name is runtime syntax,
# not a translated word. Mismatched labels remain visible to spelling checks.
_PARAMETER_ASSIGNMENT_RE = re.compile(
    r"(?<!\w)(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{(?P<parameter>[A-Za-z_][A-Za-z0-9_]*)\}(?!\w)"
)
# A period filter is a typed CLI clause. Admit only the real filter key and
# filing codes, so a misspelled key or invalid code is not hidden as syntax.
_LEDGER_PERIOD_FILTER_RE = re.compile(
    r"(?<![\w-])"
    + re.escape(LedgerReviewFilterKey.PERIOD.value)
    + r"=(?:"
    + "|".join(re.escape(code) for code in sorted(accepted_filing_period_codes(), key=len, reverse=True))
    + r")(?![\w-])"
)
# These names are the actual review-filter keys, shown together in CLI help.
# Match the complete ordered list and leave both explanatory glosses visible;
# an incomplete or misspelled list is not treated as an established contract.
_REVIEW_FILTER_LIST_RE = re.compile(
    r"(?<![\w-])"
    + rf"(?P<status>{re.escape(LedgerReviewFilterKey.STATUS.value)}),[ \t]*"
    + rf"(?P<period>{re.escape(LedgerReviewFilterKey.PERIOD.value)})[ \t]*\([^()\r\n]*\)[ \t]*"
    + r"(?:junto con|és|plus)[ \t]+"
    + rf"(?P<year>{re.escape(LedgerReviewFilterKey.YEAR.value)})[ \t]*\([^()\r\n]*\),[ \t]*"
    + rf"(?P<issue>{re.escape(LedgerReviewFilterKey.ISSUE.value)}),[ \t]*"
    + rf"(?P<import>{re.escape(LedgerReviewFilterKey.IMPORT.value)}),[ \t]*"
    + rf"(?P<classification>{re.escape(LedgerReviewFilterKey.CLASSIFICATION.value)}),[ \t]*"
    + rf"(?P<text>{re.escape(LedgerReviewFilterKey.TEXT.value)}),[ \t]*"
    + rf"(?P<direction>{re.escape(LedgerReviewFilterKey.DIRECTION.value)})"
    + r"(?:,[ \t]*or|[ \t]+o|[ \t]+vagy)[ \t]+"
    + rf"(?P<account>{re.escape(LedgerReviewFilterKey.ACCOUNT.value)})(?![\w-])"
)
# Area labels in the asset basis forms carry the SI unit, not a prose word.
# Match only the complete, case-sensitive symbol; adjacent letters or another
# exponent remain visible to spelling checks.
_AREA_UNIT_RE = re.compile(r"(?<!\w)m²(?!\w)")
# The IRNR guidance cites legislative decrees with this exact abbreviation.
# Require the complete number/year reference; the bare word is not vocabulary.
_LEGISLATIVE_DECREE_REFERENCE_RE = re.compile(r"(?<!\w)RDLeg[ \t]+\d{1,4}/\d{4}(?!\w)")
# Dotted suffixes in workbook/statement prompts are file-format notation.
# Keep the list closed to these attested formats; bare words remain prose.
_SPREADSHEET_SUFFIX_RE = re.compile(r"(?<![\w.])\.(?:xlsx|xlsm|xls|csv|tsv)(?!\w)")
# The observation spreadsheet reader names these exact two columns. Keep
# misspelled headers and all surrounding prose visible to the dictionary.
_OBSERVATION_HEADER_RE = re.compile(r"(?<![\w])casilla_code,[ \t]*value(?![\w])")
# These are complete CLI argument/value pairs in the documented root output
# option and the guided profile example. Bare words and changed values remain
# prose. The example's residence is checked against the actual profile schema.
_ROOT_JSON_OPTION_RE = re.compile(r"(?<![\w-])--format(?:[ \t]+|=)json(?![\w-])")
_PROFILE_RESIDENCE_EXAMPLE_RE = re.compile(r"(?<![\w-])--tax-residence-ccaa[ \t]+madrid(?![\w-])")
# The two copyable CCAA examples name values admitted by CCAA.from_label;
# require the whole ordered pair so a bare or misspelled region is still checked.
_RESIDENCE_EXAMPLE_PAIR_RE = re.compile(r"(?<![\w-])cataluna,[ \t]+comunidad-valenciana(?![\w-])")
# The bulk classifier requires both of these CSV headers. Optional columns
# and malformed alternatives remain visible to the spelling signal.
_CLASSIFICATION_HEADER_RE = re.compile(r"(?<!\w)transaction_id,[ \t]*classification(?![\w-])")
_M303_MOTIVES_RE = re.compile(
    r"(?<![\w-])(?P<first>"
    + re.escape(M303RectificativaMotive.RECTIFICACIONES.value)
    + r")[ \t]+(?:or|o|vagy)[ \t]+(?P<second>"
    + re.escape(M303RectificativaMotive.DISCREPANCIA_CRITERIO_ADMINISTRATIVO.value)
    + r")(?![\w-])"
)
# Match the complete three-choice list but remove only its exact wire tokens;
# every translated explanation between them remains dictionary input.
_PRORRATA_INPUT_CHOICES_RE = re.compile(
    r"(?<![\w-])(?P<deductible>exclusively_deductible)[^;\r\n]*;[ \t]*"
    r"(?P<nondeductible>exclusively_non_deductible)[^;\r\n]*;[ \t]*(?P<common>common)(?![\w-])"
)
_RICH_STYLE_SPAN_RE = re.compile(r"\[(?P<style>[A-Za-z][A-Za-z0-9 _-]*)\](?P<body>[^\[\]\r\n]*)\[/\]")
# A keyboard modifier is syntax; leave the key or the localized mouse action
# visible. Escape is admitted only alongside its actual interpolated back label.
_CONTROL_MODIFIER_RE = re.compile(r"(?<![\w-])Ctrl\+(?=⏎|[^\W\d_])")
_ESCAPE_BACK_LABEL_RE = re.compile(r"(?<![\w-])Esc[ \t]+\{back\}(?![\w])")
# Legal notes quote the formula engine's binary percent operator with numeric
# operands. Only the complete call is structural: names, arity, and operands
# outside this observed syntax remain prose for the spelling audit.
# See domain/calculations/registry/_formula_operator_contracts.py (percent).
_PERCENT_FORMULA_CALL_RE = re.compile(r"(?<![\w.])percent\([ \t]*\d+[ \t]*,[ \t]*\d+[ \t]*\)(?![\w])")
# The minute symbol is structural only after a number or its documented
# minutes placeholder; retain the value for the ordinary placeholder/number
# handling and leave bare or misspelled words visible.
# https://www.nist.gov/pml/special-publication-330/sp-330-section-4
_MINUTE_QUANTITY_RE = re.compile(r"(?<![\w.])(?P<value>\{minutes\}|\d+(?:[.,]\d+)?)[ \t]+min(?![\w])")
# Exact boolean choice notation documented by parse_descendiente_flag; an
# unknown field or changed option remains visible to the spelling signal.
_DESCENDANT_BOOL_CHOICES_RE = re.compile(
    r"(?<![\w])(?:CONVIVENCIA|DEPENDENCIA|CUSTODIA|DECLARACION_PROPIA|PRORRATA)=true\|false(?![\w|])"
)
# A complete, copyable list of the governed RELACION wire values. A missing,
# extra, reordered or misspelled choice stays visible for review. The
# authority-backed test verifies this exact list against the live catalogue.
DESCENDANT_RELATION_CHOICES = (
    "descendiente",
    "adoptado",
    "acogimiento_preadoptivo_o_permanente",
    "acogimiento_temporal",
    "tutela",
    "guarda_y_custodia_judicial",
)
DESCENDANT_RELATION_CHOICES_RE = re.compile(
    r"(?<![\w])RELACION=" + r"\|".join(map(re.escape, DESCENDANT_RELATION_CHOICES)) + r"(?![\w|])"
)
# These exact Latin suffixes identify statutory articles, rather than prose in
# the surrounding locale. They are attested by Ley 37/1992's article headings:
# https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740
# Keep both the numeric context and the closed spelling list: a bare suffix,
# misspelling or arbitrary Latin-looking word must still reach its dictionary.
_ARTICLE_ORDINAL = (
    r"(?:bis|quater|nonies|noniesdecies|octiesdecies|quatervicies|quinquies|quinvicies|sexies|unvicies|terdecies|"
    r"quaterdecies|undecies|decies|duodecies|quinquiesdecies|duovicies|sexvicies|tervicies|vicies|octovicies)(?![\w-])"
)
_NUMBERED_ARTICLE_REFERENCE_RE = re.compile(
    rf"(?<![\w.])\d+[ \t]+{_ARTICLE_ORDINAL}(?:[ \t]+(?:a|to)[ \t]+{_ARTICLE_ORDINAL})?"
)
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


def _visible_assignment_label(match: re.Match[str]) -> str:
    """Keep a mismatched label visible after its placeholder is removed."""
    name = match.group("name")
    return " " if name == match.group("parameter") else f" {name} "


def _filter_rich_styles(value: str) -> tuple[str, int]:
    """Keep visible Rich span text and count only styles that Rich admits."""
    from rich.errors import StyleSyntaxError
    from rich.style import Style

    excluded = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal excluded
        try:
            Style.parse(match.group("style"))
        except StyleSyntaxError:
            return match.group()
        excluded += 1
        body = match.group("body")
        if not isinstance(body, str):
            raise TypeError("Rich span body must be text")
        return body

    return _RICH_STYLE_SPAN_RE.sub(replace, value), excluded


def _visible_review_filter_glosses(match: re.Match[str]) -> str:
    """Retain punctuation and both user-facing glosses around actual keys."""
    text = list(match.group())
    for name in match.re.groupindex:
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
    text, excluded = filter_detail_row_examples(value)
    text, rich_excluded = _filter_rich_styles(text)
    excluded += rich_excluded
    for pattern, replacement in (
        (TRANSLATION_HTML_TAG_RE, " "),
        (TRANSLATION_MARKDOWN_LINK_RE, visible_link_label),
        (TRANSLATION_RST_LINK_RE, visible_link_label),
        (TRANSLATION_RST_ROLE_RE, visible_role_label),
        (TRANSLATION_MYST_ROLE_RE, visible_role_label),
        (TRANSLATION_LITERAL_RE, " "),
        (TRANSLATION_BRACKET_REFERENCE_RE, " "),
        (_PARAMETER_ASSIGNMENT_RE, _visible_assignment_label),
        (_MINUTE_QUANTITY_RE, r"\g<value>"),
        (_OBSERVATION_HEADER_RE, " "),
        (_CLASSIFICATION_HEADER_RE, " "),
        (_ROOT_JSON_OPTION_RE, " "),
        (_PROFILE_RESIDENCE_EXAMPLE_RE, " "),
        (_RESIDENCE_EXAMPLE_PAIR_RE, " "),
        (_CONTROL_MODIFIER_RE, " "),
        (_ESCAPE_BACK_LABEL_RE, " "),
        (_M303_MOTIVES_RE, _visible_review_filter_glosses),
        (_PRORRATA_INPUT_CHOICES_RE, _visible_review_filter_glosses),
        (registered_operation_id_pattern(), " "),
        (TRANSLATION_PLACEHOLDER_RE, " "),
        (_OUTPUT_LANGUAGE_CHOICES_RE, " "),
        (_CENSO_GLOSSED_CHOICES_RE, _visible_choice_glosses),
        (_DESCENDANT_BOOL_CHOICES_RE, " "),
        (DESCENDANT_RELATION_CHOICES_RE, " "),
        (_REVIEW_FILTER_LIST_RE, _visible_review_filter_glosses),
        (_LEGISLATIVE_DECREE_REFERENCE_RE, " "),
        (_SPREADSHEET_SUFFIX_RE, " "),
        (TRANSLATION_URL_RE, " "),
        (TRANSLATION_PATH_RE, " "),
        (command_path_pattern(), " "),
        (TRANSLATION_OPTION_RE, " "),
        (_LEDGER_PERIOD_FILTER_RE, " "),
        (_PERCENT_FORMULA_CALL_RE, " "),
        (TRANSLATION_FORMULA_RE, " "),
        (_AREA_UNIT_RE, " "),
        (_NUMBERED_ARTICLE_REFERENCE_RE, " "),
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
