"""Derive numeric export fields from official shapes and reviewed rules."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy, export_value_policy_wire_length
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportJustification, ExportPadding

from .export_field_derivation import (
    BARE_NUMERIC_ENUMERATION_FINAL_OR_RE,
    BARE_NUMERIC_ENUMERATION_RE,
    DASH_NUMERIC_ENUMERATION_TOKEN_RE,
    DECIMAL_CONTENT_RE,
    EQUALS_NUMERIC_ENUMERATION_TOKEN_RE,
    INTEGER_CONTENT_RE,
    LABELLED_ENUMERATION_VALUE_DELIMITER_RE,
    OFFICIAL_LITERAL_RE,
    OFFICIAL_UNQUOTED_LITERAL_RE,
    PARENTHESISED_QUOTED_NUMERIC_ENUMERATION_RE,
    POSITIONED_INTEGER_CONTENT_RE,
    QUOTED_DATE_PATTERN_RE,
    QUOTED_NUMERIC_BOOLEAN_ENUMERATION_RE,
    QUOTED_NUMERIC_ENUMERATION_RE,
    QUOTED_NUMERIC_LABELLED_ENUMERATION_RE,
    QUOTED_NUMERIC_TOKEN_RE,
    QUOTED_NUMERIC_VALUE_RE,
)
from .export_field_note_references import split_official_note_references
from .export_field_schema import is_required, require_numeric_extent, schema_field
from .export_fragment_provenance import ExportFieldDerivation, ExportFieldDerivationCode
from .joined_record_design import JoinedRecordDesignField
from .note_governed_enumerations import NoteGovernedEnumerationDeclaration, note_governed_enumeration_for
from .source_defects import NoteGovernedAmountDeclaration, note_governed_amount_for

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


DATE_FORMAT_BY_POLICY: Final[Mapping[ExportValuePolicy, str]] = {
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


_QUOTED_DATE_PATTERN_LETTERS: Final[Mapping[str, str]] = {"d": "d", "M": "m", "y": "a"}


#: The official type token for a signed amount, as the design's own type note
#: defines it: "N: numerico con signo", against "Num: numerico sin signo".
_SIGNED_AEAT_TYPE: Final[str] = "N"


#: The scale the `money` shape carries in its own type. A signed amount has no
#: other representable shape, so this is also the only scale a signed amount can
#: be emitted at.
_MONEY_SCALE: Final[int] = 2


def _numeric_word_or_digits(value: str) -> int | None:
    """Return the integer a shape clause names, whether written in digits or words."""
    if value.isdigit():
        return int(value)
    return _SPANISH_CARDINALS.get(value.casefold())


def _fold_quoted_date_pattern(content: str) -> str | None:
    """Fold a quoted separator-bearing date pattern to its Spanish format token.

    Returns ``None`` for anything that is not one, so an unrecognised content
    form still reaches the ambiguity refusal rather than being read as a date.
    """
    match = QUOTED_DATE_PATTERN_RE.match(content)
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


def derive_sign_from_official_type(joined_field: JoinedRecordDesignField) -> bool:
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


def _labelled_enumeration_values_are_delimited(content: str) -> bool:
    """Report whether every gap between quoted values carries a real delimiter."""
    gaps = QUOTED_NUMERIC_VALUE_RE.split(content)[1:-1]
    return all(LABELLED_ENUMERATION_VALUE_DELIMITER_RE.search(gap) is not None for gap in gaps)


def numeric_derivation(
    joined_field: JoinedRecordDesignField,
    *,
    export_record_id: str,
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...] = (),
    note_governed_enumerations: tuple[NoteGovernedEnumerationDeclaration, ...] = (),
) -> ExportFieldDerivation:
    """Derive a numeric export field from its official design content."""
    parser_field = joined_field.parser_field
    content = parser_field.content
    if content is None:
        raise RegistryValidationError(
            f"official numeric field {joined_field.semantic_entry.export_field_id!r} has no unambiguous content form",
        )
    normalised_content = _normalise_numeric_content(content)
    pointer_content = normalised_content
    normalised_content, note_references = split_official_note_references(normalised_content)
    if not normalised_content and note_references:
        return _pointer_numeric_derivation(
            joined_field,
            pointer_content=pointer_content,
            note_governed_amounts=note_governed_amounts,
            note_governed_enumerations=note_governed_enumerations,
            export_record_id=export_record_id,
        )
    adjudicated = note_governed_amount_for(
        note_governed_amounts,
        sheet=joined_field.parser_field.sheet,
        published_content=pointer_content,
    )
    if adjudicated is not None:
        return _note_governed_printed_derivation(joined_field, normalised_content, adjudicated, export_record_id)
    derived = _ordered_numeric_shape_derivation(joined_field, normalised_content, note_references, export_record_id)
    if derived is not None:
        return derived
    raise RegistryValidationError(
        f"official numeric field {joined_field.semantic_entry.export_field_id!r} has ambiguous content {content!r}",
    )


def _ordered_numeric_shape_derivation(
    joined_field: JoinedRecordDesignField,
    content: str,
    note_references: tuple[int, ...],
    export_record_id: str,
) -> ExportFieldDerivation | None:
    """Try recognized numeric shapes in the historical refusal order."""
    for derivation in (
        _date_numeric_derivation,
        _exercise_numeric_derivation,
        _decimal_numeric_derivation,
        _integer_numeric_derivation,
        _m369_closed_period_range,
    ):
        result = derivation(joined_field, content, export_record_id)
        if result is not None:
            return result
    for derivation in (_enumeration_numeric_derivation, _constant_numeric_derivation):
        result = derivation(joined_field, content, note_references, export_record_id)
        if result is not None:
            return result
    return None


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
    note_governed_enumerations: tuple[NoteGovernedEnumerationDeclaration, ...],
    export_record_id: str,
) -> ExportFieldDerivation:
    """Resolve a numeric cell whose only content is one or more note pointers."""
    parser_field = joined_field.parser_field
    adjudicated = note_governed_amount_for(
        note_governed_amounts,
        sheet=parser_field.sheet,
        published_content=pointer_content,
    )
    enumeration = note_governed_enumeration_for(
        note_governed_enumerations,
        sheet=parser_field.sheet,
        source_cell=parser_field.source_cell,
        published_pointer=pointer_content,
    )
    if enumeration is not None:
        if adjudicated is not None:
            raise RegistryValidationError(
                f"official numeric field {joined_field.semantic_entry.export_field_id!r} has both an amount "
                "and an enumeration reading of one note pointer",
            )
        return _note_governed_enumeration_derivation(joined_field, enumeration, export_record_id)
    if adjudicated is None:
        # No reviewed note reading means the historical unscaled shape cannot
        # be silently changed by a rule nobody has adjudicated for this design.
        return schema_field(
            joined_field,
            data_type="integer",
            required=is_required(parser_field.validation),
            padding=ExportPadding.LEFT_ZERO,
            justification=ExportJustification.RIGHT,
            signed=False,
            export_record_id=export_record_id,
            derivation_code="numeric-integer-v1",
        )
    return _note_governed_amount_derivation(
        joined_field, adjudicated, export_record_id, allowed_values=adjudicated.mandated_values
    )


def _note_governed_printed_derivation(
    joined_field: JoinedRecordDesignField,
    stem: str,
    adjudicated: NoteGovernedAmountDeclaration,
    export_record_id: str,
) -> ExportFieldDerivation:
    """Scale a printed numeric constant or enumeration the way a reviewed reading states.

    The printed digits fix the slot's wire runs, not their scale: ``00500`` in
    a Tipo % slot is five percent and ``"00000", "00050", "00062"`` closes it to
    0, 0.50 and 0.62 percent, at two implied decimals. Every printed run must
    still fill the slot, so a reading cannot be attached to a cell whose digits
    contradict the declared extent. A printed enumeration is the closed domain
    unless the reading records the runs a note the cell names adds to it, such
    as the ``00000`` a foral-only filer may print; a reading that drops a
    printed run is refused rather than preferred.
    """
    field_id = joined_field.semantic_entry.export_field_id
    printed = _numeric_enumeration_values(stem)
    if printed is None:
        match = OFFICIAL_LITERAL_RE.fullmatch(stem) or OFFICIAL_UNQUOTED_LITERAL_RE.fullmatch(stem)
        constant = None if match is None else match.group("literal")
        if constant is None or not constant.isascii() or not constant.isdecimal():
            raise RegistryValidationError(
                f"note-governed reading of {field_id!r} addresses a cell whose content {stem!r} "
                "is neither a numeric constant nor a numeric enumeration",
            )
        _require_reading_fills_the_printed_runs(field_id, (constant,), adjudicated)
        return _note_governed_amount_derivation(
            joined_field, adjudicated, export_record_id, allowed_values=adjudicated.mandated_values
        )
    _require_reading_fills_the_printed_runs(field_id, printed, adjudicated)
    domain = tuple(str(int(value)) for value in printed)
    if len(set(domain)) != len(domain):
        raise RegistryValidationError(f"official numeric enumeration {field_id!r} has duplicate values")
    if adjudicated.mandated_values is None:
        return _note_governed_amount_derivation(joined_field, adjudicated, export_record_id, allowed_values=domain)
    if not set(domain) <= set(adjudicated.mandated_values):
        raise RegistryValidationError(
            f"note-governed reading of {field_id!r} mandates {adjudicated.mandated_values!r}, which omits runs "
            f"the design prints in {domain!r}",
        )
    return _note_governed_amount_derivation(
        joined_field, adjudicated, export_record_id, allowed_values=adjudicated.mandated_values
    )


def _require_reading_fills_the_printed_runs(
    field_id: str,
    printed: tuple[str, ...],
    adjudicated: NoteGovernedAmountDeclaration,
) -> None:
    if any(len(value) != adjudicated.wire_length for value in printed):
        raise RegistryValidationError(
            f"note-governed reading of {field_id!r} declares {adjudicated.wire_length} positions where the "
            f"design prints {printed!r}",
        )


def _note_governed_amount_derivation(
    joined_field: JoinedRecordDesignField,
    adjudicated: NoteGovernedAmountDeclaration,
    export_record_id: str,
    *,
    allowed_values: tuple[str, ...] | None,
) -> ExportFieldDerivation:
    """Derive the representation a reviewed note reading declares for one slot."""
    parser_field = joined_field.parser_field
    # The sign travels with the adjudication and drives data_type, `signed` and
    # `decimals` together. The width check includes the sign position, so an
    # adjudication that does not fill the slot is refused like an unsigned one.
    signed = adjudicated.signed
    require_numeric_extent(joined_field, expected_length=adjudicated.wire_length)
    return schema_field(
        joined_field,
        data_type="money" if signed else "decimal",
        required=is_required(parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=signed,
        export_record_id=export_record_id,
        decimals=None if signed else adjudicated.decimal_digits,
        allowed_values=allowed_values,
        derivation_code="numeric-note-governed-amount-v1",
    )


def _note_governed_enumeration_derivation(
    joined_field: JoinedRecordDesignField,
    enumeration: NoteGovernedEnumerationDeclaration,
    export_record_id: str,
) -> ExportFieldDerivation:
    """Close a pointer-only slot to the codes its note's value table states."""
    parser_field = joined_field.parser_field
    # The same width rule the printed enumerations obey: a tabulated code that
    # does not fill the slot is not a reading of this design.
    if any(len(value) != parser_field.length for value in enumeration.allowed_values):
        raise RegistryValidationError(
            f"note-governed enumeration {joined_field.semantic_entry.export_field_id!r} has values "
            "outside the declared slot width",
        )
    return schema_field(
        joined_field,
        data_type="integer",
        required=is_required(parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        value_policy=ExportValuePolicy.ENUMERATED_DIGITS,
        allowed_values=enumeration.allowed_values,
        derivation_code="numeric-note-governed-enumeration-v1",
    )


def _date_numeric_derivation(
    joined_field: JoinedRecordDesignField,
    content: str,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    """Derive either official date order when its content and width agree."""
    parser_field = joined_field.parser_field
    date_token = _fold_quoted_date_pattern(content) or content.casefold()
    for policy, date_format in DATE_FORMAT_BY_POLICY.items():
        if date_token != date_format:
            continue
        expected_length = export_value_policy_wire_length(policy)
        if parser_field.length != expected_length:
            raise RegistryValidationError(
                f"official date field {joined_field.semantic_entry.export_field_id!r} has "
                f"{parser_field.length} bytes, expected {expected_length}",
            )
        return schema_field(
            joined_field,
            data_type="date",
            required=is_required(parser_field.validation),
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
    return schema_field(
        joined_field,
        data_type="integer",
        required=is_required(parser_field.validation),
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
    match = DECIMAL_CONTENT_RE.fullmatch(content)
    if match is None:
        return None
    whole = _numeric_word_or_digits(match.group("whole"))
    decimals = _numeric_word_or_digits(match.group("decimals"))
    if whole is None or decimals is None:
        return None
    require_numeric_extent(joined_field, expected_length=whole + decimals)
    signed = derive_sign_from_official_type(joined_field)
    if signed and decimals != _MONEY_SCALE:
        raise RegistryValidationError(
            f"export field {joined_field.semantic_entry.export_field_id!r} is typed "
            f"'{_SIGNED_AEAT_TYPE}' (numerico con signo) at {decimals} decimals, and a signed "
            f"amount is representable only at the {_MONEY_SCALE}-decimal money scale",
        )
    return schema_field(
        joined_field,
        # Signed `money` carries its scale in the type; only unsigned `decimal`
        # declares the scale as a separate count.
        data_type="money" if signed else "decimal",
        required=is_required(joined_field.parser_field.validation),
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
    match = INTEGER_CONTENT_RE.fullmatch(content) or POSITIONED_INTEGER_CONTENT_RE.fullmatch(content)
    if match is None:
        return None
    require_numeric_extent(joined_field, expected_length=int(match.group("whole")))
    return schema_field(
        joined_field,
        data_type="integer",
        required=is_required(joined_field.parser_field.validation),
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
        return tuple(str(match.group("value")) for match in QUOTED_NUMERIC_TOKEN_RE.finditer(content))
    return None


def numbered_line_enumeration_values(content: str | None) -> tuple[str, ...] | None:
    """Read a complete cell listing one numeric code and label on each line.

    M309's situation and taxable-event cells use ``1. Label`` rather than
    quoted or dash-separated codes. Keep the source line boundaries: flattening
    first would make numbers inside a label indistinguishable from codes.
    Introductions, continuation lines and unlabelled numbers remain refused.
    """
    if content is None:
        return None
    lines = tuple(line.strip() for line in content.splitlines() if line.strip())
    if len(lines) < 2:
        return None
    values: list[str] = []
    for line in lines:
        match = re.fullmatch(r"([0-9]+)\.\s+\S.*", line)
        if match is None:
            return None
        value = match.group(1)
        if not isinstance(value, str):
            return None
        values.append(value)
    return tuple(values)


def _m369_closed_period_range(
    joined_field: JoinedRecordDesignField, content: str, export_record_id: str
) -> ExportFieldDerivation | None:
    """Read only the three source-anchored two-digit period ranges of M369."""
    field = joined_field.parser_field
    expected = {
        ("T36901 Ext", 22, "A22", "17", 218, 2): "1 a 4",
        ("T36904 Un", 21, "A21", "16", 203, 2): "1 a 4",
        ("T36910 Imp", 24, "A24", "19", 234, 2): "1 a 12",
    }.get((field.record_identity, field.source_row, field.source_cell, field.ordinal, field.offset, field.length))
    if expected is None or content != expected:
        return None
    upper = 4 if expected == "1 a 4" else 12
    return schema_field(
        joined_field,
        data_type="integer",
        required=is_required(field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        value_policy=ExportValuePolicy.ENUMERATED_DIGITS,
        allowed_values=tuple(str(value) for value in range(1, upper + 1)),
        derivation_code="numeric-enumeration-v1",
    )


def _labelled_numeric_values(content: str) -> tuple[str, ...] | None:
    """Read dash, equals, or bare comma-separated numeric labels."""
    dash_values = tuple(str(match.group("value")) for match in DASH_NUMERIC_ENUMERATION_TOKEN_RE.finditer(content))
    equals_values = tuple(str(match.group("value")) for match in EQUALS_NUMERIC_ENUMERATION_TOKEN_RE.finditer(content))
    labelled_values = dash_values if len(dash_values) > 1 else equals_values
    if len(labelled_values) > 1:
        return labelled_values
    return _bare_labelled_numeric_values(content)


def _bare_labelled_numeric_values(content: str) -> tuple[str, ...] | None:
    if BARE_NUMERIC_ENUMERATION_RE.fullmatch(content) is not None:
        values = tuple(value.strip() for value in content.rstrip(".").split(","))
        return values if len(values) > 1 else None
    if BARE_NUMERIC_ENUMERATION_FINAL_OR_RE.fullmatch(content) is not None:
        values = tuple(str(value) for value in re.findall(r"\d+", content))
        return values if len(values) > 1 else None
    return None


def _is_quoted_numeric_enumeration(content: str) -> bool:
    """Report whether an official quoted spelling names a closed value set."""
    return (
        QUOTED_NUMERIC_ENUMERATION_RE.fullmatch(content) is not None
        or QUOTED_NUMERIC_BOOLEAN_ENUMERATION_RE.fullmatch(content) is not None
        or (
            QUOTED_NUMERIC_LABELLED_ENUMERATION_RE.fullmatch(content) is not None
            and _labelled_enumeration_values_are_delimited(content)
        )
        or PARENTHESISED_QUOTED_NUMERIC_ENUMERATION_RE.fullmatch(content) is not None
    )


def _enumeration_numeric_derivation(
    joined_field: JoinedRecordDesignField,
    content: str,
    note_references: tuple[int, ...],
    export_record_id: str,
) -> ExportFieldDerivation | None:
    """Validate and derive a closed set of numeric wire values."""
    raw_values = numbered_line_enumeration_values(joined_field.parser_field.content)
    if raw_values is None:
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
    return schema_field(
        joined_field,
        data_type="integer",
        required=is_required(parser_field.validation),
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
    match = OFFICIAL_LITERAL_RE.fullmatch(content)
    if match is None:
        match = OFFICIAL_UNQUOTED_LITERAL_RE.fullmatch(content)
    if match is None:
        return None
    parser_field = joined_field.parser_field
    constant_literal = match.group("literal")
    if not constant_literal.isascii() or not constant_literal.isdecimal():
        return None
    if len(constant_literal) != parser_field.length:
        raise RegistryValidationError(
            f"official numeric constant {joined_field.semantic_entry.export_field_id!r} has a value "
            "outside the declared slot width",
        )
    if note_references:
        # A note-bearing constant is not a closed wire fact; a typed owner may
        # vary its value while the source still fixes the integer wire shape.
        return schema_field(
            joined_field,
            data_type="integer",
            required=is_required(parser_field.validation),
            padding=ExportPadding.LEFT_ZERO,
            justification=ExportJustification.RIGHT,
            signed=False,
            export_record_id=export_record_id,
            derivation_code="numeric-integer-v1",
        )
    # An unannotated constant is a one-member enumeration. Carrying that value
    # lets the field follow its canonical producer while refusing disagreement
    # with the design's mandated bytes.
    return schema_field(
        joined_field,
        data_type="integer",
        required=is_required(parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        value_policy=ExportValuePolicy.ENUMERATED_DIGITS,
        allowed_values=(str(int(constant_literal)),),
        derivation_code="numeric-enumeration-v1",
    )
