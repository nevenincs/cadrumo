"""Canonical regular-expression grammars for official export field content."""

from __future__ import annotations

import re
from typing import Final

_DECIMAL_CONTENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<whole>\d+|[^\W\d_]+)\s*(?:enteros?|ent\.?)\s*(?:y|\+|,)?\s*(?P<decimals>\d+|[^\W\d_]+)\s*(?:decimales?|decmales|dec\.?)"
    r"(?:,\s*menor\s+o\s+igual\s+que\s+\d+\.|\.)?$",
    re.IGNORECASE,
)


_INTEGER_CONTENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<whole>\d+)\s*(?:enteros?|ent\.?)\.?$",
    re.IGNORECASE,
)


_POSITIONED_INTEGER_CONTENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^entero (?P<whole>\d+) posiciones$",
    re.IGNORECASE,
)


_QUOTED_NUMERIC_ENUMERATION_RE: Final[re.Pattern[str]] = re.compile(
    r'^"\d+"(?:,\s*"\d+")*$',
)


# The same closed set written BARE, without quotes and without labels, which is
# how Modelo 151 states every one of its single-position code slots: `1,2,3`,
# `0,1,2`, `1,2,3,4`. Anchored whole and requiring at least two members, so it
# cannot swallow a lone number -- a bare `1` states a constant, not a choice --
# and the slot-width check below still refuses any value that does not fit.
_BARE_NUMERIC_ENUMERATION_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d+(?:\s*,\s*\d+)+\.?$",
)


# Some designs close a comma-separated numeric list with a Spanish connective.
# The whole cell must be only that list; a condition after it stays ambiguous.
_BARE_NUMERIC_ENUMERATION_FINAL_OR_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d+(?:\s*,\s*\d+)*\s+(?:o|ó)\s+\d+\.?$",
    re.IGNORECASE,
)


# A trailing `Nota N` reference annotates official content without altering the
# wire fact it states: the AEAT note tables govern which value applies in which
# filing period (Nota 8, Nota 9), whether a slot may be filled at all (Nota 10),
# or an optional foral value (Nota 7). Every one of those axes is carried by the
# anchor's canonical typed owner -- casilla 154's transitional-rate parameter
# encodes Nota 8's two windows exactly -- so the reference is peeled before the
# value grammar runs rather than tolerated ad hoc inside each pattern.
#
# AEAT writes the reference three ways: bare (`Nota 3`), parenthesised
# (`(Nota 1)`) and parenthesised with a verb (`(ver Nota 5)`), the last often on
# its own line after the value clause. All three annotate; none states a wire
# fact, so the peel admits the optional bracket and verb rather than leaving a
# design refusing as ambiguous because AEAT added two words.
_TRAILING_NOTE_REFERENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"[.,;\s]*\(?\s*(?:ver\s+)?\bNota\s+\d+\s*\.?\s*\)?\s*$",
    re.IGNORECASE,
)


_NOTE_NUMBER_RE: Final[re.Pattern[str]] = re.compile(r"Nota\s+(?P<note>\d+)", re.IGNORECASE)


_QUOTED_NUMERIC_BOOLEAN_ENUMERATION_RE: Final[re.Pattern[str]] = re.compile(
    r'^"\d+"\s+(?:SI|NO)(?:\s+\([^)]*\))?(?:,\s*"\d+"\s+(?:SI|NO)(?:\s+\([^)]*\))?)*\.?$',
)


_QUOTED_NUMERIC_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r'"(?P<value>\d+)"')


# AEAT writes the SAME closed value set two ways: quoted ("1", "2") on some
# designs and dash-labelled with its meaning inline on others ("1 - 12 meses
# dentro del año natural  2 - 12 meses (365 días)  3 - inferior a 12 meses").
# Both are one enumeration and are derived through the one enumeration path, so
# a design that changes only its spelling cannot change the emitted contract.
#
# The label may follow the dash with no space at all ("1 -Sí, 2 -No"), so the
# separator admits none. What it does NOT admit is a digit after the dash: that
# is a numeric RANGE ("01-12"), which states an interval rather than a closed
# set, and reading it as an enumeration would emit two members where the design
# means twelve.
_DASH_NUMERIC_ENUMERATION_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\s)(?P<value>\d+)\s*-\s*(?=\D)")


#: A third spelling of the same closed set, label FIRST: Modelo 322 writes
#: "Si=1, No=2". The label must START WITH A LETTER, which is what keeps a
#: COMPARISON out: Modelo 202 writes tranches as `"1" (>= 10 M y < 20 M €)`, and
#: a rule that accepted any non-digit before the `=` read `>= 10` as the value
#: 10 -- three two-character "values" for a one-character slot, which the width
#: check then refused. A formula (`[65]=[66]`) is excluded for the same reason.
_EQUALS_NUMERIC_ENUMERATION_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[\s,;])[^\W\d_][^\s,;=]*\s*=\s*(?P<value>\d+)",
)


#: The quoted spelling with a FREE-TEXT label after each value, which is the same
#: closed set as the SI/NO form above with a longer label: Modelo 202 writes
#: `"0" No consta, "1" Cooperativa, "2" Otras entidades`. Only the values are
#: quoted, so the label cannot contribute a value however many numbers it names.
_QUOTED_NUMERIC_LABELLED_ENUMERATION_RE: Final[re.Pattern[str]] = re.compile(
    r'^"\d+"[^"]*(?:"\d+"[^"]*)+$',
)


#: The PARENTHESISED quoted spelling, which modelo 200 alone uses: `("0", "1")`,
#: with a whitespace variant `( "0", "1")`. It is the same closed set the forms
#: above express -- AEAT names every admissible value and no other -- so it is
#: derived through the identical enumeration path rather than a second shape.
#: The leading parenthesis is why the quoted-labelled rule above cannot see it:
#: that one anchors on a value at position zero.
_PARENTHESISED_QUOTED_NUMERIC_ENUMERATION_RE: Final[re.Pattern[str]] = re.compile(
    r'^\(\s*"\d+"(?:\s*,\s*"\d+")+\s*\)$',
)


#: AEAT also states a date slot as a QUOTED separator-bearing pattern in the
#: programmer's vocabulary rather than the Spanish token: Modelo 151 writes
#: `Formato: "dd/MM/yyyy"` for its fecha de nacimiento. The separators are
#: presentation only -- the design's own Lon column gives that slot 8 positions,
#: which the printed pattern does not fit -- so the pattern is folded to the same
#: Spanish token the policy table already keys on rather than given a second
#: table that could disagree with it. Case-sensitive on purpose: `MM` is the
#: month and `mm` the minute in this vocabulary, and a slot spelling minutes is
#: not a date this grammar should silently accept.
_QUOTED_DATE_PATTERN_RE: Final[re.Pattern[str]] = re.compile(
    r'^formato\s*:?\s*"(?P<pattern>[dMy][dMy/.\-]*[dMy])"$',
    re.IGNORECASE,
)


_OFFICIAL_LITERAL_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*constante(?:\s+n[uú]mero)?\s+(?P<quote>['\"])(?P<literal>[^'\"]*)(?P=quote)\.?\s*$",
    re.IGNORECASE,
)


#: The same quoted constant FOLLOWED BY an explanatory clause. Modelo 296 writes
#: `Constante "F" ANEXO "VALORES NEGOCIABLES..."` and then several lines saying
#: when that sheet type is used, so the constant is stated exactly but the cell
#: does not end there. Two checks below make reading past the literal safe: the
#: extracted value must equal the map's declared literal byte for byte, and its
#: encoded length must equal the official slot width. A mis-read prefix fails
#: both, so this widens what can be PARSED without widening what is ACCEPTED.
#: TWO quoted constants joined by an alternation connector, which states a CHOICE
#: rather than one constant with a label. `Constante "<T" o "ZZ"` names two
#: possible byte strings and the design does not say which applies, so the
#: renderer cannot know what to write.
#:
#: This is checked BEFORE the labelled form below, which would otherwise read the
#: first alternative as the constant and the rest as its label -- silently
#: choosing `<T` and discarding `o "ZZ"`. Wrong constant bytes on the wire is the
#: worst outcome available here, and it would be invisible: the emitted record is
#: well formed and the wrong literal is the right width.
#:
#: An explanatory clause may itself quote an ordinary field enumeration. Modelo
#: 296's ``Constante «F» ... "1" ó "2"`` is the worked case: the trailing
#: ``"1" ó "2"`` describes another field's permitted values, not alternative
#: bytes for the already-declared ``F``. The indirect branch therefore requires
#: prose immediately before the connector to end in a non-quote. Direct
#: ``Constante "E" o "S"`` alternatives remain rejected by the first branch,
#: and a later ``... rentas. o "S"`` remains rejected by the second.
_OFFICIAL_ALTERNATIVE_LITERALS_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*constante(?:\s+n[uú]mero)?\s+(?P<quote>['\"])[^'\"]*(?P=quote)"
    r"(?:\s*\.?\s*\b(?:o|ó|or|u)\s*(?P=quote)[^'\"]*(?P=quote).*?"
    r"|(?:\.\s+|\s+).*?[^\s'\"]\s+\b(?:o|ó|or|u)\s*(?P=quote)[^'\"]*(?P=quote).*?)$",
    re.IGNORECASE | re.DOTALL,
)


_OFFICIAL_LABELLED_LITERAL_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*constante(?:\s+n[uú]mero)?\s+(?P<quote>['\"])(?P<literal>[^'\"]*)(?P=quote)(?:\.\s+|\s+)\S.*$",
    re.IGNORECASE | re.DOTALL,
)


#: A record's own identifier is the one constant some designs print BARE. Modelo
#: 353 writes `</T35301000>` in the Contenido cell with neither the `Constante`
#: label nor quotes, where its own opening tag on the same sheet carries both;
#: Modelo 322 prints BOTH ends bare, `<T32201000>` and `</T32201000>`. The shape
#: is what makes it unambiguous, so this pattern matches the tag itself rather
#: than relaxing the labelled-constant pattern, which would turn every unlabelled
#: cell on every design into a mandated literal.
_OFFICIAL_BARE_RECORD_TAG_RE: Final[re.Pattern[str]] = re.compile(r"</?T[0-9A-Z]+>")


#: A LABELLED constant whose value AEAT left unquoted. Modelo 200 writes
#: `Constante 0A` for its periodo and `Constante </T20003000>` for two record
#: closers, where the same design quotes every other constant. The `Constante`
#: label is kept as the requirement -- that is what separates this from the
#: unlabelled cell the pattern above deliberately refuses to treat as a literal;
#: only the quotes are optional. Measured across all thirteen committed generated
#: trees, this matches ZERO fields that the quoted and bare-tag patterns did not
#: already match, so it widens what an author may declare without moving any
#: published tree.
_OFFICIAL_UNQUOTED_LITERAL_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*constante\s+(?P<literal>[^\s'\"]+?)\.?\s*$",
    re.IGNORECASE,
)


#: A single bare token that IS the whole of a printed Contenido cell. Modelo 360
#: writes its design version ``000100`` in that cell with neither the
#: ``Constante`` label nor quotes. The cell is the design's statement of the
#: field's content, so a lone token filling it states the constant as surely as
#: the label does. Admitted ONLY when the reader located the text in that column
#: (``content_in_contenido_column``): the same token arriving as text the line
#: parser merely attributed to a field could be the tail of a description, and
#: stays refused. One token, so a cell listing alternatives ("0" "1") or carrying
#: prose never matches.
_OFFICIAL_BARE_CELL_LITERAL_RE: Final[re.Pattern[str]] = re.compile(r"[^\s'\"]+")


#: What SEPARATES two quoted values in a labelled enumeration AEAT actually
#: writes. `_QUOTED_NUMERIC_LABELLED_ENUMERATION_RE` allows any non-quote text
#: between values, so an ordinary SENTENCE containing two quoted numbers -- `"0000"
#: only if the taxpayer elects "0050"` -- parsed as a closed value set and the
#: renderer went on to constrain the slot to it. Prose is not a value set.
#:
#: Derived from the corpus rather than guessed: across the 103 bundled designs
#: that load, the labelled form matches 221 cells in 28 distinct shapes, and
#: every one of them separates its values with a delimiter -- a comma, a
#: newline, a dash, or a Spanish connective. Two are RANGE forms (`"01".."12"`
#: and `"01" a "52"`), which is why `..` and ` a ` are admitted. All 28 stay
#: admitted under this rule and the prose above does not.
_LABELLED_ENUMERATION_VALUE_DELIMITER_RE: Final[re.Pattern[str]] = re.compile(
    r"[,;\n]|\s(?:o|\u00f3|u|y|e|a)\s|\s[-\u2013\u2014.]\s|\s\.-\s|\.\.",
    re.IGNORECASE,
)


_QUOTED_NUMERIC_VALUE_RE: Final[re.Pattern[str]] = re.compile(r'"\d+"')
