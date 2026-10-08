"""Derive literal export fields from exact official content and reviewed evidence."""

from __future__ import annotations

from typing import Final

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.fixed_width_codec import ExportEncoding, ExportJustification, ExportPadding

from .export_field_derivation import (
    _OFFICIAL_ALTERNATIVE_LITERALS_RE,
    _OFFICIAL_BARE_CELL_LITERAL_RE,
    _OFFICIAL_BARE_RECORD_TAG_RE,
    _OFFICIAL_LABELLED_LITERAL_RE,
    _OFFICIAL_LITERAL_RE,
    _OFFICIAL_UNQUOTED_LITERAL_RE,
)
from .export_field_literal_source_pins import (
    _source_pinned_165_transport_constant,
    _source_pinned_190_transport_constant,
    _source_pinned_194_transport_constant,
    _source_pinned_270_transport_constant,
    _source_pinned_280_transport_without_parsed_content,
    _source_pinned_341_pdf_constant,
    _source_pinned_345_transport_constant,
    _source_pinned_349_constant,
)
from .export_field_note_references import _split_official_note_references
from .export_field_render_profile_derivation import _render_profile_anchor
from .export_field_schema import _schema_field
from .export_fragment_provenance import ExportFieldDerivation
from .joined_record_design import JoinedRecordDesignField
from .note_literals import NoteLiteralDeclaration, note_literal_for
from .render_profile_model import RenderProfile
from .render_profile_rules import TelematicTransportChoiceRule
from .source_defects import SourceDefectDeclaration, adjudicated_literal_for

#: The quotation marks AEAT wraps a constant in. A workbook prints straight
#: quotes; a PDF design prints guillemets, and typographic pairs appear in both
#: -- "Constante «D»." is Modelo 347's, and it read as an ambiguous
#: constant because the pattern below only knew ' and ". Folded to a straight
#: quote before matching, so one pattern reads every form AEAT ships.
_OFFICIAL_QUOTE_FOLD: Final[dict[int, str]] = str.maketrans(
    {"«": '"', "»": '"', "“": '"', "”": '"', "‘": "'", "’": "'"},
)


_OFFICIAL_BLANK_LITERAL_CONTENT: Final[str] = "En blanco"


def _literal_derivation(
    joined_field: JoinedRecordDesignField,
    *,
    encoding: ExportEncoding,
    render_profile: RenderProfile,
    export_record_id: str,
    source_defects: tuple[SourceDefectDeclaration, ...] = (),
    literal_notes: tuple[NoteLiteralDeclaration, ...] = (),
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    if (
        parser_field.source_cell is None
        and parser_field.aeat_type == "Blancos"
        and parser_field.normalized_description == "CEROS."
        and parser_field.content is None
    ):
        # In a PDF a dashed naturaleza is parsed as a reserved run. The
        # complete description CEROS explicitly fixes its bytes to zeros;
        # it neither supplies an amount nor authorizes space padding.
        literal = joined_field.semantic_entry.literal
        expected = "0" * parser_field.length
        if literal is None:
            raise RegistryValidationError("reserved zero run has no mapped literal")
        _validate_literal_bytes(joined_field, literal, expected, encoding, False)
        return _schema_field(
            joined_field,
            data_type="text",
            required=True,
            padding=ExportPadding.NONE,
            justification=ExportJustification.NONE,
            signed=False,
            export_record_id=export_record_id,
            derivation_code="literal-exact-v1",
        )
    missing_content_literal = _source_pinned_280_transport_without_parsed_content(joined_field, render_profile)
    if missing_content_literal is not None:
        _validate_literal_bytes(joined_field, missing_content_literal, missing_content_literal, encoding, False)
        return _schema_field(
            joined_field,
            data_type="text",
            required=True,
            padding=ExportPadding.NONE,
            justification=ExportJustification.NONE,
            signed=False,
            export_record_id=export_record_id,
            derivation_code="literal-pdf-source-adjudicated-v1",
        )
    literal, published_content = _literal_source_values(joined_field)
    official_content, note_literal = _resolve_literal_note_content(joined_field, published_content, literal_notes)
    choice = render_profile.telematic_transport_choice_rule_by_anchor.get(_render_profile_anchor(joined_field))
    official_literal, blank_source_marker, m341_adjudicated = _select_official_literal(
        joined_field,
        render_profile,
        official_content,
        literal,
        choice,
    )
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
        derivation_code=(
            "literal-telematic-choice-v1"
            if choice is not None
            else "literal-pdf-source-adjudicated-v1"
            if m341_adjudicated
            else "literal-note-exact-v1"
            if note_literal is not None
            else "literal-exact-v1"
        ),
    )


def _select_official_literal(
    joined_field: JoinedRecordDesignField,
    render_profile: RenderProfile,
    official_content: str,
    literal: str,
    choice: TelematicTransportChoiceRule | None,
) -> tuple[str, bool, bool]:
    """Apply exact source adjudications before falling back to printed content."""
    m341_adjudicated = _source_pinned_341_pdf_constant(joined_field, render_profile, official_content)
    if choice is not None:
        if official_content != choice.expected_source_content or literal != choice.selected_literal:
            raise RegistryValidationError("telematic transport choice no longer matches its exact source and literal")
        return choice.selected_literal, False, m341_adjudicated is not None
    source_constant = _source_pinned_literal_constant(joined_field, render_profile, official_content)
    if m341_adjudicated is not None:
        return m341_adjudicated, False, True
    if source_constant is not None:
        return source_constant, False, False
    official_literal, blank_source_marker = _parse_official_literal(joined_field, official_content)
    return official_literal, blank_source_marker, False


def _source_pinned_literal_constant(
    joined_field: JoinedRecordDesignField,
    render_profile: RenderProfile,
    official_content: str,
) -> str | None:
    """Read the first matching reviewed source pin in its established order."""
    for source_reader in (
        _source_pinned_349_constant,
        _source_pinned_190_transport_constant,
        _source_pinned_194_transport_constant,
        _source_pinned_345_transport_constant,
        _source_pinned_270_transport_constant,
        _source_pinned_165_transport_constant,
    ):
        source_literal = source_reader(joined_field, render_profile, official_content)
        if source_literal is not None:
            return source_literal
    return None


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
