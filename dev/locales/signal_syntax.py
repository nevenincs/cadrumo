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
    r"`[^`]*`|--[A-Za-z][A-Za-z0-9-]*|\b[A-Z][A-Z0-9_]+(?:=[^][,;\s]+)?|"
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
    r"(?<![\w])--[A-Za-z][A-Za-z0-9-]*(?:=[^\s,;:()[\]{}]+)?|"
    r"(?<![\w])-[A-Za-z](?=\s|$|[,;:.)\]}])"
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
    r"(?P<title>\b(?:[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ]*\s+){1,3})"
    r"(?P<identifier>[A-Z]{0,5}/?\d{1,4}/\d{4})\b"
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
