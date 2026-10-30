"""Syntax for the authoritative locale audit."""

from __future__ import annotations

import re
from typing import Final

DOTTED_KEY_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_-]+)+\Z")


TRANSLATION_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(
    r"%\{[^{}\r\n]*\}|%\([A-Za-z_][A-Za-z0-9_.]*\)[#0\- +]?"
    r"(?:\d+|\*)?(?:\.\d+|\.\*)?(?:[hlL])?[diouxXeEfFgGcrsa%]|"
    r"\$\{[^{}\r\n]*\}|\{[^{}\r\n]*\}"
)


TRANSLATION_CODE_RE: Final[re.Pattern[str]] = re.compile(
    r"`[^`]*`|--[A-Za-z][A-Za-z0-9-]*|\b[A-Z][A-Z0-9_]+(?![\w])(?:=[^][,;\s]+)?|"
    r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b|\[\d{1,4}\]"
)


TRANSLATION_MARKDOWN_LINK_RE: Final[re.Pattern[str]] = re.compile(
    r"\[(?P<label>[^\]\r\n]+)\]\(\s*(?:<[^>\r\n]*>|[^)\r\n]*)\)"
)


TRANSLATION_RST_LINK_RE: Final[re.Pattern[str]] = re.compile(
    r"`(?P<label>[^`\r\n<>]*?)\s*<(?P<target>[^>\r\n]+)>\s*`_?"
)


TRANSLATION_RST_ROLE_RE: Final[re.Pattern[str]] = re.compile(r":[A-Za-z][A-Za-z0-9_-]*:`(?P<target>[^`\r\n]+)`")


TRANSLATION_MYST_ROLE_RE: Final[re.Pattern[str]] = re.compile(r"\{[A-Za-z][A-Za-z0-9_-]*\}`(?P<target>[^`\r\n]+)`")


TRANSLATION_LITERAL_RE: Final[re.Pattern[str]] = re.compile(r"```[\s\S]*?```|``[^`\r\n]*``|`[^`\r\n]*`")


TRANSLATION_BRACKET_REFERENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"\[(?:\d+|(?=[^\]\r\n]*[=+\-*/])[A-Za-z0-9_.+*/=-]+)\]"
)


TRANSLATION_URL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)(?<![\w])(?:https?|ftp|file|mailto):[^\s<>()\[\]{}]+|"
    r"(?<![\w])www\.[^\s<>()\[\]{}]+"
)


TRANSLATION_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])(?:[A-Za-z]:[\\/]|\\\\|\.{1,2}[\\/])[^\s<>()\[\]{}]+|"
    r"(?<![\w])(?:[\w.-]+[\\/])+[\w./-]+|"
    r"(?<![\w])[\w-]+(?:\.[\w-]+)+(?=[\s,;:!?)]|$)"
)


TRANSLATION_FORMULA_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])(?:[A-Za-z_][A-Za-z0-9_]*|\d+(?:[.,]\d+)?)(?:\s*(?:=|[+\-*/×÷<>≤≥])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*|\d+(?:[.,]\d+)?))+(?![\w])"
)


TRANSLATION_NUMERIC_RE: Final[re.Pattern[str]] = re.compile(r"(?<![\w])\d+(?:[.,]\d+)*(?:%)?(?![\w])")


TRANSLATION_OPTION_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])--[^\W\d_][\w-]*(?:=[^\s,;:()[\]{}]+)?|"
    r"(?<![\w])-[^\W\d_](?=\s|$|[,;:.)\]}])"
)


# The snake_case arm states its "contains an underscore with something after
# it" condition as a lookahead and then consumes the word once, so no input can
# be split two ways. The earlier spelling repeated `(?:_[A-Za-z0-9_]+)+` after a
# `[A-Za-z0-9_]*` that could claim the same underscores; a long `A_0_0_0…` run
# ending in a non-ASCII letter -- ordinary Spanish, Catalan and Galician prose --
# then had to try every split before failing, doubling in cost per segment.
TRANSLATION_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(
    # The snake_case arm says "an underscore with at least one character after
    # it", not "one or more underscore-prefixed runs". Both accept exactly the
    # same tokens, but the repeated form lets one token be split many ways, so a
    # long `a_0_0_0...` that ends up not matching costs exponential backtracking
    # to refuse.
    r"(?<![\w])(?:[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]+|"
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+|"
    r"[A-Za-z_]*\d[A-Za-z0-9_]*|"
    r"[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+){2,})(?![\w])"
)


TRANSLATION_ROLE_MARKER_RE: Final[re.Pattern[str]] = re.compile(r":[A-Za-z][A-Za-z0-9_-]*:|\{[A-Za-z][A-Za-z0-9_-]*\}")


TRANSLATION_HTML_TAG_RE: Final[re.Pattern[str]] = re.compile(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s+[^<>]*?)?/?>")


TRANSLATION_HTML_LANGUAGE_RE: Final[re.Pattern[str]] = re.compile(
    r"<(?P<tag>[A-Za-z][A-Za-z0-9:-]*)\b"
    r"(?=[^<>]*?\blang\s*=\s*[\"'](?P<locale>[A-Za-z]{2})(?:-[^\"']*)?[\"'])"
    r"[^<>]*>(?P<body>.*?)</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)


TRANSLATION_MARKDOWN_LINK_CONTEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"\[(?P<label>[^\]\r\n]+)\]\(\s*(?:<(?P<angle_target>[^>\r\n]*)>|(?P<target>[^)\r\n]*))\)"
)


TRANSLATION_LEGAL_TITLE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<title>\b(?:Ley(?:\s+Orgánica)?|Real\s+Decreto(?:-ley|\s+Legislativo)?|"
    r"Decreto(?:-ley|\s+Legislativo)?|Orden|Resolución)\s+)"
    r"(?P<identifier>[A-Z]{0,5}/?\d{1,4}/\d{4})\b"
)


TRANSLATION_SPANISH_AUTHORITY_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:Agencia (?:Estatal de Administración )?Tributaria|Boletín Oficial del Estado)\b"
)


# The terminology handbook keeps these Spanish tax nouns in foreign prose.
# Match complete terms, including only their ordinary singular/plural forms;
# the Spanish dictionary still checks every matched word. Multiword terms
# must stay whole so their prepositions do not become global exceptions.
# Owners: _data/terminology/concepts and the bienes de inversión register.
TRANSLATION_SPANISH_TAX_TERM_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w'’-])(?:bienes de inversión|recargo de equivalencia|"
    r"regla de prorrata|prorrata especial|datos censales|"
    r"declaración (?:tributaria|censal|de la renta)|"
    r"justificante de presentación|retenciones (?:del trabajo|de alquiler)|"
    r"atribución de rentas|impuesto sobre sociedades|"
    r"operaciones (?:vinculadas|intracomunitarias|con terceros)|"
    r"sede electrónica|cuenta corriente tributaria|domiciliación bancaria|"
    r"autoliquidación conjunta|referencia catastral|situación catastral|"
    r"diseño de registros|consulta de declaraciones presentadas|fichero BOE|"
    r"cotejo por CSV|CSV cotejo|"
    r"casillas?|modelos?|borrador(?:es)?|censos?|"
    r"expedientes?|justificantes?|prorratas?|prorrateo|renta)(?![\w'’])",
    re.IGNORECASE,
)


# These are AEAT's exact service names, not separate vocabulary exceptions
# for the fragments that punctuation would otherwise split apart.
TRANSLATION_CLAVE_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w'’])Cl@ve(?: Móvil| PIN| Permanente)?(?![\w'’])"
)


TRANSLATION_HUNGARIAN_DATE_RE: Final[re.Pattern[str]] = re.compile(r"(?<![\w])ÉÉÉÉ-HH-NN(?:TÓÓ:PP:MMZ)?(?![\w-])")


# Hungarian attaches case suffixes to foreign words, abbreviations, and numbers
# with a hyphen. Strip only suffix spellings attested as Hunspell fragments in
# the locale corpus, retaining the stem for normal spelling validation.
TRANSLATION_HUNGARIAN_HYPHENATED_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w-])(?P<stem>(?:[^\W\d_][\w.-]*|\d+))-"
    r"(?P<suffix>ból|ből|tól|től|nál|nél|ról|ről|os|ös|es)(?![\w-])"
)


# Hungarian attaches grammatical endings to percentages with a hyphen. Keep
# only these endings structural, since the numeric filter removes the number
# and percent sign later; unrelated endings remain spelling input.
TRANSLATION_HUNGARIAN_PERCENT_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w-])(?P<stem>\d+\s*%)-(?P<suffix>os|ot|ban|ig|tól)(?![\w-])"
)


MODELO_FORM_RE: Final[re.Pattern[str]] = re.compile(r"(?i)\b(?:modelo|form)\s+\d{1,4}\b")


PLATFORM_FORMAT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:\b[A-Z][A-Z0-9]{1,}\b|(?<![\w])\.[A-Za-z0-9]{1,8}(?![\w]))"
)


VERSION_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])v?(?:\d+|[xXyYzZ])(?:[._-](?:\d+|[xXyYzZ])){1,3}(?![\w])"
)


PLATFORM_LABEL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])(?P<label>[A-Za-z][A-Za-z0-9]*)\s*\((?P<details>[^()\r\n]*)\)"
)


ARCHITECTURE_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])(?:[A-Za-z]{1,4}[-_]?\d{1,3}(?:[-_][A-Za-z0-9]{1,4})*|\d{1,3}[-_x]\d{1,3})(?![\w])"
)
