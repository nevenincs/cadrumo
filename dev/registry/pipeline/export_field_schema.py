"""Canonical schema-field construction and validation for generated export fields."""

from __future__ import annotations

import re
import unicodedata
from typing import Final, Literal

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import (
    ExportValuePolicy,
)
from cadrumo.domain.calculations.registry.fixed_width_codec import (
    ExportJustification,
    ExportPadding,
    ExportSignPosition,
)
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
)

from .export_fragment_provenance import (
    EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION,
    ExportFieldDerivation,
    ExportFieldDerivationCode,
)
from .joined_record_design import JoinedRecordDesignField


def _require_numeric_extent(joined_field: JoinedRecordDesignField, *, expected_length: int) -> None:
    actual_length = joined_field.parser_field.length
    if actual_length != expected_length:
        raise RegistryValidationError(
            f"official numeric field {joined_field.semantic_entry.export_field_id!r} has {actual_length} bytes, "
            f"but content declares {expected_length}",
        )


def _schema_field(
    joined_field: JoinedRecordDesignField,
    *,
    data_type: Literal["text", "integer", "decimal", "money", "date", "boolean"],
    required: bool,
    padding: ExportPadding,
    justification: ExportJustification,
    signed: bool,
    sign_position: ExportSignPosition | None = None,
    export_record_id: str,
    derivation_code: ExportFieldDerivationCode,
    date_format: str | None = None,
    decimals: int | None = None,
    value_policy: ExportValuePolicy | None = None,
    allowed_values: tuple[str, ...] | None = None,
    minimum_year: int | None = None,
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    semantic_entry = joined_field.semantic_entry
    return ExportFieldDerivation(
        export_record_id=export_record_id,
        parser_field=parser_field,
        semantic_entry=semantic_entry,
        field=ExportFieldDefinition.model_validate(
            {
                "id": semantic_entry.export_field_id,
                "offset": parser_field.offset,
                "length": parser_field.length,
                "kind": semantic_entry.kind,
                "casilla_id": semantic_entry.casilla_id,
                "binding": semantic_entry.binding,
                "literal": semantic_entry.literal,
                "producer_key": semantic_entry.producer_key,
                "projection_ref": semantic_entry.projection_ref,
                "draft_attribute": semantic_entry.draft_attribute,
                "computed_key": semantic_entry.computed_key,
                "data_type": data_type,
                "required": required,
                "padding": padding,
                "justification": justification,
                "date_format": date_format,
                "decimals": decimals,
                "signed": signed,
                "sign_position": sign_position,
                "required_for": _qualified_requirement(parser_field.validation),
                "design_type": _design_type(parser_field.aeat_type, data_type),
                "value_policy": value_policy,
                "allowed_values": allowed_values,
                "minimum_year": minimum_year,
                "legal_refs": semantic_entry.legal_refs,
                "source_refs": semantic_entry.source_refs,
            },
        ),
        normalization_schema_version=EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION,
        derivation_code=derivation_code,
    )


#: The requirement wordings this project has adjudicated as unconditional,
#: written as the designs write them once punctuation and case are set aside.
#:
#: ``obligatorio pi`` is modelo 303's "Tipo Declaracion" cell. "PI" is not a
#: condition on the requirement: it is the label under which the same design's
#: Nota 1 lists the admitted declaration types ("PI: El tipo de declaracion puede
#: ser: C ... D ... G ... I ... N ... V ..."), so the cell states a requirement
#: and points at its value list. Read as a qualifier, it shipped the one field
#: every 303 filing must carry as not required.
_UNCONDITIONAL_REQUIREMENTS: Final[frozenset[str]] = frozenset({"obligatorio", "obligatorio pi"})


#: The qualified requirement wordings this project has adjudicated, mapped to
#: the taxpayer legal form they name. Modelo 390's sujeto pasivo nombre reads
#: "OBLIGATORIO (persona fisica)": required for a natural person, meaningless for
#: an entity, so it is carried as ``required_for`` and evaluated per filing.
_QUALIFIED_REQUIREMENTS: Final[dict[str, Literal["natural_person"]]] = {
    "obligatorio (persona fisica)": "natural_person",
}


#: Trailing punctuation a design may put after the requirement word. It ends a
#: sentence; it does not qualify the requirement, and reading it as though it
#: did is what silently downgraded twelve stated requirements in modelo 390.
_REQUIREMENT_SENTENCE_PUNCTUATION: Final[str] = ".:;"


def _design_type(aeat_type: str, data_type: str) -> Literal["N", "Num"] | None:
    """Return the design's numeric type for a sign-bearing field, when it prints one exactly.

    Only the design's own two-letter vocabulary is carried; a spelled-out type
    such as "Numerico" states no sign, and a text slot has none to hold.
    """
    code = aeat_type.strip()
    if data_type not in {"money", "decimal", "integer"} or code not in {"N", "Num"}:
        return None
    return "N" if code == "N" else "Num"


def _qualified_requirement(validation: str | None) -> Literal["natural_person"] | None:
    """Return the taxpayer legal form a qualified requirement names, or ``None``.

    Accents are set aside because the designs spell the same qualifier both
    ways. A field carrying one is not required unconditionally; the schema
    admits the condition on a producer-supplied header field only, so a
    qualified wording on any other field refuses at generation instead of
    being dropped.
    """
    if validation is None:
        return None
    folded = unicodedata.normalize("NFKD", validation.strip().rstrip(_REQUIREMENT_SENTENCE_PUNCTUATION).strip())
    ascii_only = "".join(character for character in folded if not unicodedata.combining(character))
    return _QUALIFIED_REQUIREMENTS.get(ascii_only.casefold())


def _is_required(validation: str | None) -> bool:
    """Read whether the design states this field's requirement unconditionally.

    A cell is one of three things and only two are answerable here. A SILENT
    cell makes no requirement claim. A cell stating the bare requirement word,
    which a design may end as a sentence, states an unconditional requirement.
    A cell stating a QUALIFIED requirement -- modelo 390's
    ``OBLIGATORIO (persona fisica)`` -- is neither, and this function's boolean
    result cannot carry it; ``_qualified_requirement`` reads it instead. Modelo
    303's ``Obligatorio PI`` looks qualified and is not; see
    ``_UNCONDITIONAL_REQUIREMENTS``.

    Only the first two are repaired here. The comparison used to demand exact
    equality with the bare word, so ``OBLIGATORIO.`` fell through to ``False``
    and twelve stated requirements shipped as no requirement, defeated by a
    full stop. Trailing sentence punctuation is now set aside before the
    comparison.

    A qualified cell stays unrequired here: its requirement holds only for a
    taxpayer of one legal form, which a layout cannot know, so it is carried as
    a condition the export evaluates against the filing's own taxpayer.
    """
    if validation is None:
        return False
    return (
        validation.strip().rstrip(_REQUIREMENT_SENTENCE_PUNCTUATION).strip().casefold() in _UNCONDITIONAL_REQUIREMENTS
    )


#: A design ``Contenido`` cell naming blank as one of the position's admitted
#: contents -- DR145's ``blanco o "C" (compl.)``, DR490's ``C o blanco``.
_ADMITTED_BLANK: Final = re.compile(r"\bblancos?\b", re.IGNORECASE)


def _is_required_casilla_text(validation: str | None, content: str | None) -> bool:
    """Read whether an operator-entered text casilla has no blank representation.

    A layout field's ``required`` is narrower than AEAT's ``obligatorio``: it
    states that the field has NO blank representation, so the codec refuses an
    absent value instead of writing the field's blank fill. A design can mark a
    position obligatorio -- the record always carries it -- while its own
    contenido admits blank as a value. DR145 row 2, ``Indicador de página
    complementaria``, is ``obligatorio`` with contenido ``blanco o "C"
    (compl.)``: the principal page's indicator IS blank. Reading the
    obligatoriness alone left that page with no renderable value.

    Only operator-entered casillas are read this way. Leaving such a casilla
    empty selects the blank the design admits, and the casilla's own
    declaration constrains every non-blank value. A producer-backed field still
    states its value explicitly.
    """
    return _is_required(validation) and not (content is not None and _ADMITTED_BLANK.search(content))
