"""Canonical derivation of generated export fields from official design content and reviewed profiles."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final, Literal

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import (
    ExportValuePolicy,
    export_value_policy_wire_length,
)
from cadrumo.domain.calculations.registry.fixed_width_codec import (
    ExportEncoding,
    ExportJustification,
    ExportPadding,
    ExportSignPosition,
)

from .export_field_schema import _is_required, _require_numeric_extent, _schema_field
from .export_fragment_provenance import (
    ExportFieldDerivation,
    ExportFieldDerivationCode,
)
from .joined_record_design import JoinedRecordDesignField
from .note_literals import NoteLiteralDeclaration, note_literal_for
from .render_profile_model import RenderProfile
from .render_profile_model_base import RenderProfileAnchor
from .render_profile_rules import SignedMonetaryCompositeRule, SingletonNumericRule, Width17MembershipRule
from .source_defects import (
    NoteGovernedAmountDeclaration,
    SourceDefectDeclaration,
    adjudicated_literal_for,
    note_governed_amount_for,
)

# A bare trailing full stop is SENTENCE PUNCTUATION on the official content, not
# an annotation, so each value grammar tolerates its own terminator rather than
# the note peel removing it. Two reasons this is the right home. The peel is
# named and contracted for one job -- it returns the stem plus the note numbers
# it removed -- and a period carries no note number, so stripping it there would
# mutate the stem while reporting nothing, making the peel's own accounting
# untestable. And this file already settled the question the other way for the
# constant and boolean-enumeration patterns, which carry their own optional
# `\.?`; leaving three of four numeric grammars tolerant and one strict is what
# let a design writing `15 enteros y 2 decimales.` refuse.
#
# The terminator is deliberately alternation rather than a stacked optional: the
# "menor o igual que N." clause already ends in a period, so appending another
# optional one would quietly admit a doubled `..` that no design writes.
#
# AEAT abbreviates the same clause as `15 ent. y 2 dec.` on some designs and
# spells it out as `15 enteros y 2 decimales` on others. Modelo 303 only ever
# spells it out, so the abbreviated form -- which is the DOMINANT form on Modelo
# 210, covering 24 of its numeric anchors -- refused as ambiguous content. Both
# spellings are the one grammar and are admitted as alternations rather than as
# a second pattern, so the two cannot drift apart.
#
# `decmales` is not a third spelling of the word -- it is AEAT's typo, which
# Modelo 151 ships once per design edition beside eighteen correctly spelled
# siblings in the same 5-position shape. It is admitted by naming that exact
# misspelling rather than by loosening the word to a fuzzy match: a tolerant
# pattern would go on to accept spellings AEAT has never written, and the reading
# is proved anyway, because the declared 3 + 2 digits must equal the slot's own
# 5 positions before the derivation is accepted.
#: The cardinals AEAT actually SPELLS OUT in a numeric shape clause. Modelo 308
#: writes `[quince enteros + dos decimales]` where 200, 322 and 151 write the
#: same clause with digits. Named exactly, in the spirit of the `decmales` typo
#: above: a general Spanish numeral parser would accept words no design writes,
#: and the point is to read what AEAT wrote, not to be clever.
#:
#: A mis-read is caught immediately and cannot ship: the declared whole plus
#: decimals is checked against the slot's own width by `_require_numeric_extent`
#: at both use sites, so mapping a word to the wrong number refuses there.
_SPANISH_CARDINALS: Final[dict[str, int]] = {
    "dos": 2,
    "tres": 3,
    "quince": 15,
}


def _numeric_word_or_digits(value: str) -> int | None:
    """Return the integer a shape clause names, whether written in digits or words."""
    if value.isdigit():
        return int(value)
    return _SPANISH_CARDINALS.get(value.casefold())


_DECIMAL_CONTENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<whole>\d+|[^\W\d_]+)\s*(?:enteros?|ent\.?)\s*(?:y|\+)?\s*(?P<decimals>\d+|[^\W\d_]+)\s*(?:decimales?|decmales|dec\.?)"
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


_DATE_FORMAT_BY_POLICY: Final[Mapping[ExportValuePolicy, str]] = {
    ExportValuePolicy.YYYYMMDD: "aaaammdd",
    ExportValuePolicy.DDMMYYYY: "ddmmaaaa",
}


#: The derivation code for each date policy, spelled out in full rather than
#: built with an f-string from ``_DATE_FORMAT_BY_POLICY`` so the value stays a
#: literal member of ``ExportFieldDerivationCode`` rather than an unbounded str.
_DATE_DERIVATION_CODE_BY_POLICY: Final[Mapping[ExportValuePolicy, ExportFieldDerivationCode]] = {
    ExportValuePolicy.YYYYMMDD: "numeric-date-aaaammdd-v1",
    ExportValuePolicy.DDMMYYYY: "numeric-date-ddmmaaaa-v1",
}


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


_QUOTED_DATE_PATTERN_LETTERS: Final[Mapping[str, str]] = {"d": "d", "M": "m", "y": "a"}


_SINGLETON_POLICY_SHAPES: Final[
    Mapping[ExportValuePolicy, Literal["integer", "decimal", "date", "digit_identity", "text"]]
] = {
    ExportValuePolicy.SELECTED_1_UNSELECTED_0: "integer",
    ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS: "integer",
    ExportValuePolicy.UNSIGNED_INTEGER: "integer",
    ExportValuePolicy.IMPLIED_DECIMAL: "decimal",
    ExportValuePolicy.YYYYMMDD: "date",
    ExportValuePolicy.DDMMYYYY: "date",
    ExportValuePolicy.ENUMERATED_DIGITS: "integer",
    ExportValuePolicy.DIGIT_STRING: "digit_identity",
    ExportValuePolicy.IDENTIFIER_DIGITS: "digit_identity",
    ExportValuePolicy.FOUR_DIGIT_YEAR: "integer",
    ExportValuePolicy.TWO_DIGIT_MONTH: "integer",
    ExportValuePolicy.TWO_DIGIT_DAY: "integer",
    ExportValuePolicy.MISTYPED_ALPHANUMERIC_TEXT: "text",
    ExportValuePolicy.INTEGER_PART: "integer",
    ExportValuePolicy.FRACTIONAL_DIGITS: "integer",
}


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


#: The quotation marks AEAT wraps a constant in. A workbook prints straight
#: quotes; a PDF design prints guillemets, and typographic pairs appear in both
#: -- "Constante «D»." is Modelo 347's, and it read as an ambiguous
#: constant because the pattern below only knew ' and ". Folded to a straight
#: quote before matching, so one pattern reads every form AEAT ships.
_OFFICIAL_QUOTE_FOLD: Final[dict[int, str]] = str.maketrans(
    {"«": '"', "»": '"', "“": '"', "”": '"', "‘": "'", "’": "'"},
)


_OFFICIAL_BLANK_LITERAL_CONTENT: Final[str] = "En blanco"


def _fold_quoted_date_pattern(content: str) -> str | None:
    """Fold a quoted separator-bearing date pattern to its Spanish format token.

    Returns ``None`` for anything that is not one, so an unrecognised content
    form still reaches the ambiguity refusal rather than being read as a date.
    """
    match = _QUOTED_DATE_PATTERN_RE.match(content)
    if match is None:
        return None
    folded = "".join(
        _QUOTED_DATE_PATTERN_LETTERS[character]
        for character in match.group("pattern")
        if character in _QUOTED_DATE_PATTERN_LETTERS
    )
    # A pattern naming only part of a date, or repeating a component, is not a
    # calendar date this grammar can encode. The membership test below then
    # refuses it as ambiguous content, which is the honest answer.
    return folded if len(folded) == 8 else None


def _split_official_note_references(content: str) -> tuple[str, tuple[int, ...]]:
    """Peel every trailing ``Nota N`` reference off official content.

    Returns the value-bearing stem and the referenced note numbers in source
    order. A stem that empties out is content consisting only of note
    references, which the numeric derivation treats as its own form.
    """
    stem = content
    notes: list[int] = []
    while (match := _TRAILING_NOTE_REFERENCE_RE.search(stem)) is not None:
        reference = match.group(0)
        number = _NOTE_NUMBER_RE.search(reference)
        if number is None:
            raise RegistryValidationError(
                f"official content {content!r} matched a trailing note reference {reference!r} carrying no note number",
            )
        notes.append(int(number.group("note")))
        stem = stem[: match.start()]
    return stem.strip(), tuple(reversed(notes))


def _note_governed_period_zero_boolean(raw_values: tuple[str, ...], note_references: tuple[int, ...]) -> bool:
    """Recognise the source form whose adjacent notes extend ``1``/``2`` with ``0``.

    An ordinary note leaves the printed enumeration closed.  The paired Nota 8
    and Nota 9 form is different: the official note table adds the reserved
    period value ``0`` before the printed Yes/No values apply.  The field's
    typed producer supplies that period decision, while the generated schema
    retains all three official wire tokens as its closed codec domain.
    """
    return (
        tuple(str(int(value)) for value in raw_values) == ("1", "2") and 8 in note_references and 9 in note_references
    )


def _literal_derivation(
    joined_field: JoinedRecordDesignField,
    *,
    encoding: ExportEncoding,
    render_profile: RenderProfile,
    export_record_id: str,
    source_defects: tuple[SourceDefectDeclaration, ...] = (),
    literal_notes: tuple[NoteLiteralDeclaration, ...] = (),
) -> ExportFieldDerivation:
    literal, published_content = _literal_source_values(joined_field)
    official_content, note_literal = _resolve_literal_note_content(joined_field, published_content, literal_notes)
    official_literal, blank_source_marker = _parse_official_literal(joined_field, official_content)
    official_literal = _adjudicated_official_literal(joined_field, official_literal, source_defects)
    _validate_literal_bytes(joined_field, literal, official_literal, encoding, blank_source_marker)
    decimals = _literal_numeric_decimals(joined_field, literal, render_profile)
    return _schema_field(
        joined_field,
        data_type="text",
        required=True,
        padding=ExportPadding.NONE,
        justification=ExportJustification.NONE,
        signed=False,
        decimals=decimals,
        export_record_id=export_record_id,
        derivation_code="literal-note-exact-v1" if note_literal is not None else "literal-exact-v1",
    )


def _literal_source_values(joined_field: JoinedRecordDesignField) -> tuple[str, str]:
    """Require the mapped literal and the parser's exact official content."""
    literal = joined_field.semantic_entry.literal
    if literal is None:
        raise RegistryValidationError(f"literal field {joined_field.semantic_entry.export_field_id!r} has no literal")
    official_content = joined_field.parser_field.content
    if official_content is None:
        raise RegistryValidationError(
            f"literal field {joined_field.semantic_entry.export_field_id!r} has no exact official constant content",
        )
    return literal, official_content


def _resolve_literal_note_content(
    joined_field: JoinedRecordDesignField,
    published_content: str,
    literal_notes: tuple[NoteLiteralDeclaration, ...],
) -> tuple[str, str | None]:
    """Replace a note-only pointer only when its exact reviewed reading exists."""
    parser_field = joined_field.parser_field
    official_content, note_references = _split_official_note_references(" ".join(published_content.split()))
    note_literal = None
    if not official_content and note_references:
        note_literal = note_literal_for(
            literal_notes,
            sheet=parser_field.sheet,
            source_cell=parser_field.source_cell,
            published_pointer=published_content,
            note_references=note_references,
        )
        if note_literal is not None:
            official_content = f'Constante "{note_literal}"'
    return official_content, note_literal


def _parse_official_literal(joined_field: JoinedRecordDesignField, official_content: str) -> tuple[str, bool]:
    """Read one unambiguous literal spelling or retain the exact refusal."""
    if official_content == _OFFICIAL_BLANK_LITERAL_CONTENT:
        return "", True
    folded_content = official_content.translate(_OFFICIAL_QUOTE_FOLD)
    match = _OFFICIAL_LITERAL_RE.fullmatch(folded_content)
    if match is not None:
        return str(match.group("literal")), False
    if _OFFICIAL_BARE_RECORD_TAG_RE.fullmatch(folded_content) is not None:
        return folded_content, False
    unquoted = _OFFICIAL_UNQUOTED_LITERAL_RE.fullmatch(folded_content)
    if unquoted is not None:
        return str(unquoted.group("literal")), False
    parser_field = joined_field.parser_field
    if parser_field.content_in_contenido_column and _OFFICIAL_BARE_CELL_LITERAL_RE.fullmatch(folded_content):
        return folded_content, False
    if _OFFICIAL_ALTERNATIVE_LITERALS_RE.fullmatch(folded_content) is not None:
        raise RegistryValidationError(
            f"literal field {joined_field.semantic_entry.export_field_id!r} has ambiguous official constant "
            f"content {official_content!r}: it states two alternative constants and not which one applies",
        )
    labelled = _OFFICIAL_LABELLED_LITERAL_RE.fullmatch(folded_content)
    if labelled is not None:
        return str(labelled.group("literal")), False
    raise RegistryValidationError(
        f"literal field {joined_field.semantic_entry.export_field_id!r} has ambiguous official constant "
        f"content {official_content!r}",
    )


def _adjudicated_official_literal(
    joined_field: JoinedRecordDesignField,
    official_literal: str,
    source_defects: tuple[SourceDefectDeclaration, ...],
) -> str:
    """Apply only an exact published-cell defect decision, if one exists."""
    parser_field = joined_field.parser_field
    adjudicated = adjudicated_literal_for(
        source_defects,
        sheet=parser_field.sheet,
        source_cell=parser_field.source_cell,
        published_content=parser_field.content or "",
    )
    return official_literal if adjudicated is None else adjudicated


def _validate_literal_bytes(
    joined_field: JoinedRecordDesignField,
    literal: str,
    official_literal: str,
    encoding: ExportEncoding,
    blank_source_marker: bool,
) -> None:
    """Keep byte agreement and official slot width after source adjudication."""
    try:
        literal_bytes = literal.encode(encoding)
        official_literal_bytes = official_literal.encode(encoding)
    except UnicodeEncodeError as exc:
        raise RegistryValidationError(
            f"literal field {joined_field.semantic_entry.export_field_id!r} cannot encode as {encoding!r}",
        ) from exc
    if literal_bytes != official_literal_bytes:
        raise RegistryValidationError(
            f"literal field {joined_field.semantic_entry.export_field_id!r} value does not agree byte-for-byte "
            "with the exact official constant content",
        )
    literal_length = len(literal_bytes)
    if not blank_source_marker and literal_length != joined_field.parser_field.length:
        raise RegistryValidationError(
            f"literal field {joined_field.semantic_entry.export_field_id!r} has {literal_length} encoded bytes, "
            f"but the official slot is {joined_field.parser_field.length} bytes",
        )


def _literal_numeric_decimals(
    joined_field: JoinedRecordDesignField,
    literal: str,
    render_profile: RenderProfile,
) -> int | None:
    """Validate a literal's reviewed numeric scale and return that scale."""
    numeric_rule = render_profile.literal_numeric_rule_by_anchor.get(_render_profile_anchor(joined_field))
    if numeric_rule is None:
        return None
    if numeric_rule.literal != literal:
        raise RegistryValidationError("literal numeric rule disagrees with the exact official constant")
    return numeric_rule.decimal_digits


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


def _labelled_enumeration_values_are_delimited(content: str) -> bool:
    """Report whether every gap between quoted values carries a real delimiter."""
    gaps = _QUOTED_NUMERIC_VALUE_RE.split(content)[1:-1]
    return all(_LABELLED_ENUMERATION_VALUE_DELIMITER_RE.search(gap) is not None for gap in gaps)


#: The official type token for a signed amount, as the design's own type note
#: defines it: "N: numerico con signo", against "Num: numerico sin signo".
_SIGNED_AEAT_TYPE: Final[str] = "N"


#: The scale the `money` shape carries in its own type. A signed amount has no
#: other representable shape, so this is also the only scale a signed amount can
#: be emitted at.
_MONEY_SCALE: Final[int] = 2


def _derive_sign_from_official_type(joined_field: JoinedRecordDesignField) -> bool:
    """Return whether the official type column declares this amount signed.

    This derivation used to write ``False`` for every amount without reading the
    column at all, which is how a fifth of the generated surface came to declare
    unsigned the slots the design types as signed.

    The representation is grounded, so the sign can now be emitted rather than
    refused. AEAT's "Disenos de registro" manual states the convention for every
    design: numeric fields are right-aligned and zero-filled SIN SIGNOS, and only
    NEGATIVE amounts are preceded by the character ``N``. So a signed slot reserves
    no byte -- the marker displaces the leading digit when the value is negative,
    which is what the codec now renders and parses.

    Only ``N`` is read as signed. A token outside the design's own vocabulary is
    left unsigned here rather than guessed at, and is answered by the separate
    treatment of the uncontrolled type spellings.
    """
    return joined_field.parser_field.aeat_type == _SIGNED_AEAT_TYPE


def _numeric_derivation(
    joined_field: JoinedRecordDesignField,
    *,
    export_record_id: str,
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...] = (),
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    content = parser_field.content
    if content is None:
        raise RegistryValidationError(
            f"official numeric field {joined_field.semantic_entry.export_field_id!r} has no unambiguous content form",
        )
    normalised_content = _normalise_numeric_content(content)
    pointer_content = normalised_content
    normalised_content, note_references = _split_official_note_references(normalised_content)
    if not normalised_content and note_references:
        return _pointer_numeric_derivation(
            joined_field,
            pointer_content=pointer_content,
            note_governed_amounts=note_governed_amounts,
            export_record_id=export_record_id,
        )
    if (derived := _date_numeric_derivation(joined_field, normalised_content, export_record_id)) is not None:
        return derived
    if (derived := _exercise_numeric_derivation(joined_field, normalised_content, export_record_id)) is not None:
        return derived
    if (derived := _decimal_numeric_derivation(joined_field, normalised_content, export_record_id)) is not None:
        return derived
    if (derived := _integer_numeric_derivation(joined_field, normalised_content, export_record_id)) is not None:
        return derived
    if (
        derived := _enumeration_numeric_derivation(
            joined_field,
            normalised_content,
            note_references,
            export_record_id,
        )
    ) is not None:
        return derived
    if (
        derived := _constant_numeric_derivation(
            joined_field,
            normalised_content,
            note_references,
            export_record_id,
        )
    ) is not None:
        return derived
    raise RegistryValidationError(
        f"official numeric field {joined_field.semantic_entry.export_field_id!r} has ambiguous content {content!r}",
    )


def _normalise_numeric_content(content: str) -> str:
    """Fold whitespace and peel only brackets wrapping the complete clause."""
    normalised = " ".join(content.split())
    # Modelo 151 brackets the whole clause -- `[15 enteros + 2 decimales]` --
    # where 202, 303 and 322 write the same clause bare. The brackets set the
    # clause off typographically and state nothing, so peel only a full wrapper;
    # an interior or unmatched bracket must still reach the ambiguity refusal.
    if normalised.startswith("[") and normalised.endswith("]"):
        return normalised[1:-1].strip()
    return normalised


def _pointer_numeric_derivation(
    joined_field: JoinedRecordDesignField,
    *,
    pointer_content: str,
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...],
    export_record_id: str,
) -> ExportFieldDerivation:
    """Resolve a numeric cell whose only content is one or more note pointers."""
    parser_field = joined_field.parser_field
    adjudicated = note_governed_amount_for(
        note_governed_amounts,
        sheet=parser_field.sheet,
        published_content=pointer_content,
    )
    if adjudicated is None:
        # No reviewed note reading means the historical unscaled shape cannot
        # be silently changed by a rule nobody has adjudicated for this design.
        return _schema_field(
            joined_field,
            data_type="integer",
            required=_is_required(parser_field.validation),
            padding=ExportPadding.LEFT_ZERO,
            justification=ExportJustification.RIGHT,
            signed=False,
            export_record_id=export_record_id,
            derivation_code="numeric-integer-v1",
        )
    # The sign travels with the adjudication and drives data_type, `signed` and
    # `decimals` together. The width check includes the sign position, so an
    # adjudication that does not fill the slot is refused like an unsigned one.
    signed = adjudicated.signed
    _require_numeric_extent(joined_field, expected_length=adjudicated.wire_length)
    return _schema_field(
        joined_field,
        data_type="money" if signed else "decimal",
        required=_is_required(parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=signed,
        export_record_id=export_record_id,
        decimals=None if signed else adjudicated.decimal_digits,
        allowed_values=adjudicated.mandated_values,
        derivation_code="numeric-note-governed-amount-v1",
    )


def _date_numeric_derivation(
    joined_field: JoinedRecordDesignField,
    content: str,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    """Derive either official date order when its content and width agree."""
    parser_field = joined_field.parser_field
    date_token = _fold_quoted_date_pattern(content) or content.casefold()
    for policy, date_format in _DATE_FORMAT_BY_POLICY.items():
        if date_token != date_format:
            continue
        expected_length = export_value_policy_wire_length(policy)
        if parser_field.length != expected_length:
            raise RegistryValidationError(
                f"official date field {joined_field.semantic_entry.export_field_id!r} has "
                f"{parser_field.length} bytes, expected {expected_length}",
            )
        return _schema_field(
            joined_field,
            data_type="date",
            required=_is_required(parser_field.validation),
            padding=ExportPadding.NONE,
            justification=ExportJustification.NONE,
            signed=False,
            export_record_id=export_record_id,
            date_format=date_format,
            derivation_code=_DATE_DERIVATION_CODE_BY_POLICY[policy],
        )
    return None


def _exercise_numeric_derivation(
    joined_field: JoinedRecordDesignField,
    content: str,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    """Derive the closed four-digit ejercicio shape stated as ``AAAA``."""
    if content.casefold() != "aaaa":
        return None
    parser_field = joined_field.parser_field
    expected_length = export_value_policy_wire_length(ExportValuePolicy.FOUR_DIGIT_YEAR)
    if parser_field.length != expected_length:
        raise RegistryValidationError(
            f"official ejercicio field {joined_field.semantic_entry.export_field_id!r} has "
            f"{parser_field.length} bytes, expected {expected_length}",
        )
    return _schema_field(
        joined_field,
        data_type="integer",
        required=_is_required(parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        value_policy=ExportValuePolicy.FOUR_DIGIT_YEAR,
        derivation_code="numeric-ejercicio-aaaa-v1",
    )


def _decimal_numeric_derivation(
    joined_field: JoinedRecordDesignField,
    content: str,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    """Derive a stated whole-plus-decimals shape and its official sign."""
    match = _DECIMAL_CONTENT_RE.fullmatch(content)
    if match is None:
        return None
    whole = _numeric_word_or_digits(match.group("whole"))
    decimals = _numeric_word_or_digits(match.group("decimals"))
    if whole is None or decimals is None:
        return None
    _require_numeric_extent(joined_field, expected_length=whole + decimals)
    signed = _derive_sign_from_official_type(joined_field)
    if signed and decimals != _MONEY_SCALE:
        raise RegistryValidationError(
            f"export field {joined_field.semantic_entry.export_field_id!r} is typed "
            f"'{_SIGNED_AEAT_TYPE}' (numerico con signo) at {decimals} decimals, and a signed "
            f"amount is representable only at the {_MONEY_SCALE}-decimal money scale",
        )
    return _schema_field(
        joined_field,
        # Signed `money` carries its scale in the type; only unsigned `decimal`
        # declares the scale as a separate count.
        data_type="money" if signed else "decimal",
        required=_is_required(joined_field.parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=signed,
        export_record_id=export_record_id,
        decimals=None if signed else decimals,
        derivation_code="numeric-decimal-v1",
    )


def _integer_numeric_derivation(
    joined_field: JoinedRecordDesignField,
    content: str,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    """Derive the official integer-width wording when its extent matches."""
    match = _INTEGER_CONTENT_RE.fullmatch(content) or _POSITIONED_INTEGER_CONTENT_RE.fullmatch(content)
    if match is None:
        return None
    _require_numeric_extent(joined_field, expected_length=int(match.group("whole")))
    return _schema_field(
        joined_field,
        data_type="integer",
        required=_is_required(joined_field.parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        derivation_code="numeric-integer-v1",
    )


def _numeric_enumeration_values(content: str) -> tuple[str, ...] | None:
    """Read a closed numeric enumeration in any accepted official spelling."""
    labelled_values = _labelled_numeric_values(content)
    if labelled_values is not None:
        return labelled_values
    if _is_quoted_numeric_enumeration(content):
        return tuple(str(match.group("value")) for match in _QUOTED_NUMERIC_TOKEN_RE.finditer(content))
    return None


def _labelled_numeric_values(content: str) -> tuple[str, ...] | None:
    """Read dash, equals, or bare comma-separated numeric labels."""
    dash_values = tuple(str(match.group("value")) for match in _DASH_NUMERIC_ENUMERATION_TOKEN_RE.finditer(content))
    equals_values = tuple(str(match.group("value")) for match in _EQUALS_NUMERIC_ENUMERATION_TOKEN_RE.finditer(content))
    labelled_values = dash_values if len(dash_values) > 1 else equals_values
    if not labelled_values and _BARE_NUMERIC_ENUMERATION_RE.fullmatch(content) is not None:
        labelled_values = tuple(value.strip() for value in content.rstrip(".").split(","))
    return labelled_values if len(labelled_values) > 1 else None


def _is_quoted_numeric_enumeration(content: str) -> bool:
    """Report whether an official quoted spelling names a closed value set."""
    return (
        _QUOTED_NUMERIC_ENUMERATION_RE.fullmatch(content) is not None
        or _QUOTED_NUMERIC_BOOLEAN_ENUMERATION_RE.fullmatch(content) is not None
        or (
            _QUOTED_NUMERIC_LABELLED_ENUMERATION_RE.fullmatch(content) is not None
            and _labelled_enumeration_values_are_delimited(content)
        )
        or _PARENTHESISED_QUOTED_NUMERIC_ENUMERATION_RE.fullmatch(content) is not None
    )


def _enumeration_numeric_derivation(
    joined_field: JoinedRecordDesignField,
    content: str,
    note_references: tuple[int, ...],
    export_record_id: str,
) -> ExportFieldDerivation | None:
    """Validate and derive a closed set of numeric wire values."""
    raw_values = _numeric_enumeration_values(content)
    if raw_values is None:
        return None
    parser_field = joined_field.parser_field
    if any(len(value) != parser_field.length for value in raw_values):
        raise RegistryValidationError(
            f"official numeric enumeration {joined_field.semantic_entry.export_field_id!r} has values "
            "outside the declared slot width",
        )
    allowed_values = tuple(str(int(value)) for value in raw_values)
    if len(set(allowed_values)) != len(allowed_values):
        raise RegistryValidationError(
            f"official numeric enumeration {joined_field.semantic_entry.export_field_id!r} has duplicate values",
        )
    if _note_governed_period_zero_boolean(raw_values, note_references):
        # Adjacent Nota 8/9 add period-reserved zero to the printed 1/2 pair;
        # retain a closed codec domain while the typed producer chooses the value.
        allowed_values = ("0", *allowed_values)
    return _schema_field(
        joined_field,
        data_type="integer",
        required=_is_required(parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        value_policy=ExportValuePolicy.ENUMERATED_DIGITS,
        allowed_values=allowed_values,
        derivation_code="numeric-enumeration-v1",
    )


def _constant_numeric_derivation(
    joined_field: JoinedRecordDesignField,
    content: str,
    note_references: tuple[int, ...],
    export_record_id: str,
) -> ExportFieldDerivation | None:
    """Derive a constant as a shape or as its exact closed value domain."""
    match = _OFFICIAL_LITERAL_RE.fullmatch(content)
    if match is None:
        return None
    parser_field = joined_field.parser_field
    constant_literal = match.group("literal")
    if len(constant_literal) != parser_field.length:
        raise RegistryValidationError(
            f"official numeric constant {joined_field.semantic_entry.export_field_id!r} has a value "
            "outside the declared slot width",
        )
    if note_references:
        # A note-bearing constant is not a closed wire fact; a typed owner may
        # vary its value while the source still fixes the integer wire shape.
        return _schema_field(
            joined_field,
            data_type="integer",
            required=_is_required(parser_field.validation),
            padding=ExportPadding.LEFT_ZERO,
            justification=ExportJustification.RIGHT,
            signed=False,
            export_record_id=export_record_id,
            derivation_code="numeric-integer-v1",
        )
    # An unannotated constant is a one-member enumeration. Carrying that value
    # lets the field follow its canonical producer while refusing disagreement
    # with the design's mandated bytes.
    return _schema_field(
        joined_field,
        data_type="integer",
        required=_is_required(parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        value_policy=ExportValuePolicy.ENUMERATED_DIGITS,
        allowed_values=(str(int(constant_literal)),),
        derivation_code="numeric-enumeration-v1",
    )


def _render_profile_numeric_derivation(
    joined_field: JoinedRecordDesignField,
    profile: RenderProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    anchor = _render_profile_anchor(joined_field)
    # Indexed on the profile, not scanned here: a scan compared this anchor
    # against every anchor of every rule, and anchors are pydantic models whose
    # equality is not cheap.
    width_rule = profile.width_17_rule_by_anchor.get(anchor)
    if width_rule is not None:
        return _profile_width_17_derivation(
            joined_field,
            width_rule,
            export_record_id=export_record_id,
        )
    singleton = profile.singleton_rule_by_anchor.get(anchor)
    if singleton is None:
        raise RegistryValidationError(
            f"validated render profile has no exact rule for blank numeric anchor {anchor!r}",
        )
    return _profile_singleton_derivation(
        joined_field,
        singleton,
        export_record_id=export_record_id,
    )


#: The width-17 sign policies this derivation distinguishes. ``signed`` below is a
#: boolean coercion of a two-member set, and it drives ``data_type``, ``signed``
#: and ``decimals`` together -- so a third policy admitted by
#: ``Width17MembershipRule.sign_policy`` without a decision here would not refuse;
#: it would render as an unsigned decimal carrying the rule's scale, wrong in all
#: three at once. The owning test holds this pair exhaustive against that field.
_WIDTH_17_SIGNED_POLICY: Final[str] = "n-prefix-negative-blank-nonnegative"


_WIDTH_17_UNSIGNED_POLICY: Final[str] = "unsigned"


def _profile_width_17_derivation(
    joined_field: JoinedRecordDesignField,
    rule: Width17MembershipRule,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    signed = rule.sign_policy == _WIDTH_17_SIGNED_POLICY
    return _schema_field(
        joined_field,
        data_type="money" if signed else "decimal",
        required=_is_required(joined_field.parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=signed,
        export_record_id=export_record_id,
        # `money` carries its scale in the type; only `decimal` declares one, and
        # the schema refuses a field that declares decimals beside any other
        # data_type. Passing the rule's scale unconditionally would make every
        # signed width-17 amount unrepresentable.
        decimals=None if signed else rule.decimal_digits,
        derivation_code="render-profile-width-17-v1",
    )


def _profile_singleton_derivation(
    joined_field: JoinedRecordDesignField,
    rule: SingletonNumericRule,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    data_type, padding, justification, date_format, decimals, signed = _singleton_numeric_shape(rule)
    allowed_values = rule.allowed_values or None if rule.value_policy is ExportValuePolicy.ENUMERATED_DIGITS else None
    return _schema_field(
        joined_field,
        data_type=data_type,
        required=_is_required(joined_field.parser_field.validation),
        padding=padding,
        justification=justification,
        signed=signed,
        export_record_id=export_record_id,
        derivation_code="render-profile-singleton-v1",
        date_format=date_format,
        decimals=decimals,
        value_policy=None if signed else rule.value_policy,
        allowed_values=allowed_values,
    )


def _singleton_numeric_shape(
    rule: SingletonNumericRule,
) -> tuple[
    Literal["text", "integer", "decimal", "money", "date", "boolean"],
    ExportPadding,
    ExportJustification,
    str | None,
    int | None,
    bool,
]:
    """Resolve a reviewed singleton's closed value policy to its wire shape."""
    data_type: Literal["text", "integer", "decimal", "money", "date", "boolean"]
    date_format: str | None = None
    decimals: int | None = None
    signed = rule.aeat_type == "N"
    policy_shape = _SINGLETON_POLICY_SHAPES.get(rule.value_policy)
    if policy_shape is None:
        raise RegistryValidationError(f"unsupported singleton export value policy {rule.value_policy!r}")
    if policy_shape == "date":
        data_type = "date"
        date_format = _DATE_FORMAT_BY_POLICY.get(rule.value_policy)
        if date_format is None:
            raise RegistryValidationError(f"date singleton export policy lacks a date format {rule.value_policy!r}")
        padding = ExportPadding.NONE
        justification = ExportJustification.NONE
    elif policy_shape == "decimal":
        data_type = "money" if signed else "decimal"
        decimals = None if signed else rule.decimal_digits
        padding = ExportPadding.LEFT_ZERO
        justification = ExportJustification.RIGHT
    elif policy_shape == "digit_identity":
        data_type = "text"
        padding = ExportPadding.NONE
        justification = ExportJustification.NONE
    elif policy_shape == "text":
        data_type = "text"
        padding = ExportPadding.RIGHT_SPACE
        justification = ExportJustification.LEFT
    elif policy_shape == "integer":
        data_type = "integer"
        padding = ExportPadding.LEFT_ZERO
        justification = ExportJustification.RIGHT
    else:
        raise RegistryValidationError(f"unsupported singleton export policy shape {policy_shape!r}")
    return data_type, padding, justification, date_format, decimals, signed


def _profile_signed_composite_derivation(
    joined_field: JoinedRecordDesignField,
    rule: SignedMonetaryCompositeRule,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    return _schema_field(
        joined_field,
        data_type="money",
        required=_is_required(joined_field.parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=True,
        sign_position=ExportSignPosition.BLANK_OR_N,
        export_record_id=export_record_id,
        derivation_code="render-profile-signed-monetary-composite-v1",
    )


def _render_profile_anchor(joined_field: JoinedRecordDesignField) -> RenderProfileAnchor:
    field = joined_field.parser_field
    # DERIVED, not authored: this anchor is built from the parser field, so a
    # missing ordinal is an observed fact about the design rather than a claim,
    # exactly as in ``render_profile._field_anchor``.
    return RenderProfileAnchor(
        sheet=field.sheet,
        source_row=field.source_row,
        source_cell=field.source_cell,
        ordinal=field.ordinal,
        ordinal_absent=field.ordinal is None,
        record_identity=field.record_identity,
    )
