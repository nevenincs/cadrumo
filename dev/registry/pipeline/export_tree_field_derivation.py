"""Derive exact generated export fields from parser, semantic, transport and reviewed render-profile evidence."""

from __future__ import annotations

import unicodedata
from typing import Final

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import (
    ExportValuePolicy,
)
from cadrumo.domain.calculations.registry.fixed_width_codec import (
    ExportJustification,
    ExportPadding,
)

from .export_field_literal_derivation import _literal_derivation
from .export_field_numeric_derivation import _numeric_derivation
from .export_field_numeric_source_pins import m714_numeric_values_for
from .export_field_render_profile_derivation import (
    _profile_signed_composite_derivation,
    _render_profile_anchor,
    _render_profile_numeric_derivation,
)
from .export_field_schema import _is_required, _is_required_admitting_blank_text, _schema_field
from .export_fragment_provenance import (
    ExportFieldDerivation,
    ExportFieldDerivationCode,
)
from .export_tree_models import ExportTreeTransportProfile
from .export_tree_serialization import require_safe_identifier
from .joined_record_design import JoinedRecordDesignField, design_view
from .note_literals import NoteLiteralDeclaration
from .render_profile_eligibility import (
    _has_absent_naturaleza,
    _is_numeric_aeat_type,
    _states_no_wire_fact,
    source_contact_name_field,
    source_iban_country_text_field,
    source_m270_birth_place_text_field,
)
from .render_profile_model import RenderProfile
from .render_profile_model_base import RenderProfileDesignIdentity
from .semantic_map import SemanticMapEntry
from .source_defects import (
    NoteGovernedAmountDeclaration,
    NoteStatedApplicabilityDeclaration,
    SourceDefectDeclaration,
)
from .source_signed_components import signed_component_policy_for
from .source_signed_triples import signed_triple_policy_for
from .source_stated_year_constant import source_stated_year_constant_for
from .source_text_date_components import text_date_component_policy_for
from .year_constraints import bounded_year_for

#: Text naturalezas, split by the naturaleza AEAT names rather than by the
#: vocabulary it names it in. A workbook prints the abbreviation; a PDF design
#: prints the word, which the shipped parser canonicalises to
#: ``Alfanumerico``/``Alfabetico``. Matched accent-folded, so the accented
#: spellings land here too. The split is load-bearing: these two sets are the
#: only thing that distinguishes the two text derivation codes, and reading
#: them as one set keyed on the abbreviation records every PDF-sourced
#: alphabetic field as the ALPHANUMERIC derivation, because the folded word
#: ``alfabetico`` is not the abbreviation ``a``.
_ALPHABETIC_TYPES: Final[frozenset[str]] = frozenset({"a", "alfabetico", "alphabetic"})


_ALPHANUMERIC_TYPES: Final[frozenset[str]] = frozenset({"an", "alfanumerico", "alphanumeric"})


#: A blank run states no text representation to derive one from. Where the
#: semantic map calls such a field a filler it never reaches here; where it
#: calls it a value-bearing field the two disagree, and the caller refuses
#: rather than recording a naturaleza the design does not state.
_BLANK_RUN_TYPES: Final[frozenset[str]] = frozenset({"blancos"})


def _normalise_field(
    joined_field: JoinedRecordDesignField,
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
    source_defects: tuple[SourceDefectDeclaration, ...] = (),
    literal_notes: tuple[NoteLiteralDeclaration, ...] = (),
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...] = (),
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...] = (),
) -> ExportFieldDerivation:
    """Derive one emitted field, deriving a declared part from its own printed text.

    A part is derived exactly as a whole cell carrying the part's offset,
    length, type and statement would be, so it earns no reading a printed cell
    could not. The derivation then records the real parser row beside the part
    it filled, and re-validates, so the attested coordinates are the part's.
    """
    part = joined_field.semantic_entry.part
    if part is None:
        return _normalise_cell(
            joined_field,
            transport_profile,
            render_profile,
            export_record_id=export_record_id,
            source_defects=source_defects,
            literal_notes=literal_notes,
            note_governed_amounts=note_governed_amounts,
            applicability_notes=applicability_notes,
        )
    view = joined_field.model_copy(update={"parser_field": design_view(joined_field)})
    derived = _normalise_cell(
        view,
        transport_profile,
        render_profile,
        export_record_id=export_record_id,
        source_defects=source_defects,
        literal_notes=literal_notes,
        note_governed_amounts=note_governed_amounts,
        applicability_notes=applicability_notes,
    )
    return ExportFieldDerivation.model_validate(
        {
            "export_record_id": derived.export_record_id,
            "parser_field": joined_field.parser_field,
            "semantic_entry": derived.semantic_entry,
            "field": derived.field,
            "normalization_schema_version": derived.normalization_schema_version,
            "derivation_code": derived.derivation_code,
            "verdict": derived.verdict,
        },
    )


def _normalise_cell(
    joined_field: JoinedRecordDesignField,
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
    source_defects: tuple[SourceDefectDeclaration, ...] = (),
    literal_notes: tuple[NoteLiteralDeclaration, ...] = (),
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...] = (),
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...] = (),
) -> ExportFieldDerivation:
    semantic_entry = joined_field.semantic_entry
    require_safe_identifier(str(semantic_entry.export_field_id), subject="export field id")
    year_derivation = _source_year_derivation(
        joined_field, transport_profile, render_profile, export_record_id=export_record_id
    )
    if year_derivation is not None:
        return year_derivation
    component_derivation = _signed_component_derivation(
        joined_field, transport_profile, export_record_id=export_record_id
    )
    if component_derivation is not None:
        return component_derivation
    triple_derivation = _signed_triple_derivation(joined_field, transport_profile, export_record_id=export_record_id)
    if triple_derivation is not None:
        return triple_derivation
    date_derivation = _text_date_component_derivation(
        joined_field, transport_profile, export_record_id=export_record_id
    )
    if date_derivation is not None:
        return date_derivation
    return _derive_declared_field(
        joined_field,
        transport_profile,
        render_profile,
        export_record_id=export_record_id,
        source_defects=source_defects,
        literal_notes=literal_notes,
        note_governed_amounts=note_governed_amounts,
        applicability_notes=applicability_notes,
    )


def _source_year_derivation(
    joined_field: JoinedRecordDesignField,
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    bounded = _source_bounded_year_derivation(
        joined_field, transport_profile, render_profile, export_record_id=export_record_id
    )
    if bounded is not None:
        return bounded
    return _source_stated_year_constant_derivation(joined_field, transport_profile, export_record_id=export_record_id)


def _signed_component_derivation(
    joined_field: JoinedRecordDesignField,
    transport_profile: ExportTreeTransportProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    component_policy = signed_component_policy_for(
        joined_field,
        modelo=str(transport_profile.modelo),
        source_ref=str(transport_profile.source_ref),
        source_sha256=transport_profile.source_sha256,
        epoch=transport_profile.design_epoch,
    )
    if component_policy is None:
        return None
    is_sign = component_policy is ExportValuePolicy.SIGNED_COMPONENT_SIGN
    return _schema_field(
        joined_field,
        data_type="text" if is_sign else "money",
        required=_is_required(joined_field.parser_field.validation),
        padding=ExportPadding.NONE if is_sign else ExportPadding.LEFT_ZERO,
        justification=ExportJustification.NONE if is_sign else ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        value_policy=component_policy,
        derivation_code="source-signed-component-v1",
    )


def _signed_triple_derivation(
    joined_field: JoinedRecordDesignField,
    transport_profile: ExportTreeTransportProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    triple_policy = signed_triple_policy_for(
        joined_field,
        modelo=str(transport_profile.modelo),
        epoch=transport_profile.design_epoch,
        source_ref=str(transport_profile.source_ref),
        source_sha256=transport_profile.source_sha256,
    )
    if triple_policy is None:
        return None
    sign_part = triple_policy in {
        ExportValuePolicy.SIGNED_COMPONENT_SIGN,
        ExportValuePolicy.SIGNED_COMPONENT_ZERO_SIGN,
    }
    return _schema_field(
        joined_field,
        data_type="text" if sign_part else "integer",
        required=_is_required(joined_field.parser_field.validation),
        padding=ExportPadding.NONE if sign_part else ExportPadding.LEFT_ZERO,
        justification=ExportJustification.NONE if sign_part else ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        value_policy=triple_policy,
        derivation_code="source-signed-triple-v1",
    )


def _text_date_component_derivation(
    joined_field: JoinedRecordDesignField,
    transport_profile: ExportTreeTransportProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    date_policy = text_date_component_policy_for(
        joined_field,
        modelo=str(transport_profile.modelo),
        epoch=transport_profile.design_epoch,
        source_ref=str(transport_profile.source_ref),
        source_sha256=transport_profile.source_sha256,
    )
    if date_policy is None:
        return None
    return _schema_field(
        joined_field,
        data_type="integer",
        required=_is_required(joined_field.parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        value_policy=date_policy,
        derivation_code="source-text-date-component-v1",
    )


def _source_bounded_year_derivation(
    joined_field: JoinedRecordDesignField,
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    """Derive an exact source-bounded filing year before ordinary field routing."""
    parser_field = joined_field.parser_field
    semantic_entry = joined_field.semantic_entry
    year_constraint = bounded_year_for(
        source_ref=str(transport_profile.source_ref),
        source_sha256=transport_profile.source_sha256,
        sheet=parser_field.sheet,
        source_cell=parser_field.source_cell,
        published_statement=parser_field.content,
    )
    if year_constraint is None:
        return None
    if not (
        parser_field.aeat_type.casefold() == "num"
        and parser_field.length == 4
        and semantic_entry.kind is CasillaFieldKind.DRAFT
        and semantic_entry.draft_attribute == "filing_year"
    ):
        raise RegistryValidationError("source-bounded year requires a four-position Num draft filing_year field")
    year_rule = render_profile.singleton_rule_by_anchor.get(_render_profile_anchor(joined_field))
    if year_rule is None or year_rule.value_policy is not ExportValuePolicy.FOUR_DIGIT_YEAR:
        raise RegistryValidationError("source-bounded year requires an exact reviewed four-digit-year rule")
    return _schema_field(
        joined_field,
        data_type="integer",
        required=_is_required(parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        value_policy=ExportValuePolicy.FOUR_DIGIT_YEAR,
        minimum_year=year_constraint.minimum_year,
        derivation_code="numeric-source-bounded-year-v1",
    )


def _source_stated_year_constant_derivation(
    joined_field: JoinedRecordDesignField,
    transport_profile: ExportTreeTransportProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    """Read M131's pinned EEEE exercise without inventing a fixed year literal."""
    field = joined_field.parser_field
    declaration = source_stated_year_constant_for(
        source_ref=str(transport_profile.source_ref),
        source_sha256=transport_profile.source_sha256,
        field=field,
    )
    if declaration is None:
        return None
    entry = joined_field.semantic_entry
    if not (
        field.aeat_type == "Num"
        and field.length == 4
        and field.offset == 103
        and field.ordinal == "10"
        and entry.kind is CasillaFieldKind.DRAFT
        and entry.draft_attribute == "filing_year"
    ):
        raise RegistryValidationError("source-stated year constant requires its exact four-digit filing_year slot")
    return _schema_field(
        joined_field,
        data_type="integer",
        required=_is_required(field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        value_policy=ExportValuePolicy.FOUR_DIGIT_YEAR,
        derivation_code="numeric-source-stated-year-constant-v1",
    )


def _derive_declared_field(
    joined_field: JoinedRecordDesignField,
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
    source_defects: tuple[SourceDefectDeclaration, ...],
    literal_notes: tuple[NoteLiteralDeclaration, ...],
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...],
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...],
) -> ExportFieldDerivation:
    semantic_entry = joined_field.semantic_entry
    if semantic_entry.kind is CasillaFieldKind.LITERAL:
        return _literal_derivation(
            joined_field,
            encoding=transport_profile.encoding,
            render_profile=render_profile,
            export_record_id=export_record_id,
            source_defects=source_defects,
            literal_notes=literal_notes,
        )
    if semantic_entry.kind is CasillaFieldKind.FILLER:
        return _schema_field(
            joined_field,
            data_type="text",
            required=False,
            padding=ExportPadding.RIGHT_SPACE,
            justification=ExportJustification.LEFT,
            signed=False,
            export_record_id=export_record_id,
            derivation_code="filler-v1",
        )
    if semantic_entry.kind is CasillaFieldKind.CHECKSUM:
        raise RegistryValidationError(
            f"official field {semantic_entry.export_field_id!r} has checksum semantics with no reviewed normalizer",
        )
    return _derive_by_aeat_type(
        joined_field,
        render_profile,
        export_record_id=export_record_id,
        note_governed_amounts=note_governed_amounts,
        applicability_notes=applicability_notes,
    )


def _derive_by_aeat_type(
    joined_field: JoinedRecordDesignField,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...],
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...],
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    semantic_entry = joined_field.semantic_entry
    type_code = _normalised_aeat_type(parser_field.aeat_type)
    if type_code in _BLANK_RUN_TYPES:
        raise RegistryValidationError(
            f"official field {semantic_entry.export_field_id!r} declares blank-run naturaleza "
            f"{parser_field.aeat_type!r}, which states no text representation, but the semantic "
            f"map does not declare it a filler",
        )
    if type_code in _ALPHABETIC_TYPES or type_code in _ALPHANUMERIC_TYPES:
        return _text_field_derivation(
            joined_field,
            render_profile,
            type_code,
            export_record_id=export_record_id,
        )
    if _is_numeric_aeat_type(parser_field.aeat_type):
        return _numeric_field_derivation(
            joined_field,
            render_profile,
            export_record_id=export_record_id,
            note_governed_amounts=note_governed_amounts,
            applicability_notes=applicability_notes,
        )
    if _has_absent_naturaleza(parser_field):
        return _derive_absent_naturaleza(
            joined_field,
            semantic_entry,
            render_profile,
            export_record_id=export_record_id,
        )
    raise RegistryValidationError(
        f"official field {semantic_entry.export_field_id!r} declares unsupported AEAT type {parser_field.aeat_type!r}",
    )


def _normalised_aeat_type(aeat_type: str) -> str:
    return unicodedata.normalize("NFKD", aeat_type.strip()).encode("ascii", "ignore").decode("ascii").casefold()


def _derive_absent_naturaleza(
    joined_field: JoinedRecordDesignField,
    semantic_entry: SemanticMapEntry,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    identity = render_profile.design_identity
    birth_place = _m270_birth_place_derivation(
        joined_field, semantic_entry, render_profile, identity, export_record_id=export_record_id
    )
    if birth_place is not None:
        return birth_place
    iban_country = _iban_country_derivation(
        joined_field, semantic_entry, render_profile, identity, export_record_id=export_record_id
    )
    if iban_country is not None:
        return iban_country
    contact_name = _contact_name_derivation(
        joined_field, semantic_entry, render_profile, identity, export_record_id=export_record_id
    )
    if contact_name is not None:
        return contact_name
    # The official design printed no naturaleza, so there is nothing to
    # derive a representation from; the reviewed profile governs this field.
    return _render_profile_numeric_derivation(
        joined_field,
        render_profile,
        export_record_id=export_record_id,
    )


def _m270_birth_place_derivation(
    joined_field: JoinedRecordDesignField,
    semantic_entry: SemanticMapEntry,
    render_profile: RenderProfile,
    identity: RenderProfileDesignIdentity,
    *,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    parser_field = joined_field.parser_field
    if not source_m270_birth_place_text_field(
        parser_field,
        source_ref=str(identity.source_ref),
        source_sha256=identity.source_sha256,
    ):
        return None
    expected_casilla = "perc.ciudad-nacimiento" if parser_field.offset == 461 else "perc.codigo-pais-nacimiento"
    if semantic_entry.kind is not CasillaFieldKind.CASILLA or str(semantic_entry.casilla_id) != expected_casilla:
        raise RegistryValidationError("M270 birth-place source row lacks its exact typed component casilla")
    return _text_field_derivation(
        joined_field,
        render_profile,
        "alfabetico" if parser_field.offset == 496 else "alfanumerico",
        export_record_id=export_record_id,
    )


def _iban_country_derivation(
    joined_field: JoinedRecordDesignField,
    semantic_entry: SemanticMapEntry,
    render_profile: RenderProfile,
    identity: RenderProfileDesignIdentity,
    *,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    parser_field = joined_field.parser_field
    if not source_iban_country_text_field(
        parser_field,
        source_ref=str(identity.source_ref),
        source_sha256=identity.source_sha256,
    ):
        return None
    if semantic_entry.kind is not CasillaFieldKind.CASILLA or str(semantic_entry.casilla_id) != "iban-codigo-pais":
        raise RegistryValidationError("IBAN country source row lacks its exact typed casilla")
    return _text_field_derivation(joined_field, render_profile, "alfabetico", export_record_id=export_record_id)


def _contact_name_derivation(
    joined_field: JoinedRecordDesignField,
    semantic_entry: SemanticMapEntry,
    render_profile: RenderProfile,
    identity: RenderProfileDesignIdentity,
    *,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    parser_field = joined_field.parser_field
    if not source_contact_name_field(
        parser_field,
        source_ref=str(identity.source_ref),
        source_sha256=identity.source_sha256,
    ):
        return None
    if (
        semantic_entry.kind is not CasillaFieldKind.HEADER
        or str(semantic_entry.producer_key) != "contact_person.full_name"
    ):
        raise RegistryValidationError("contact-name source row lacks its exact typed contact producer")
    return _text_field_derivation(joined_field, render_profile, "alfanumerico", export_record_id=export_record_id)


def _text_field_derivation(
    joined_field: JoinedRecordDesignField,
    render_profile: RenderProfile,
    type_code: str,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    composite = next(
        (rule for rule in render_profile.signed_composite_rules if rule.anchor == _render_profile_anchor(joined_field)),
        None,
    )
    if composite is not None:
        return _profile_signed_composite_derivation(
            joined_field,
            composite,
            export_record_id=export_record_id,
        )
    derivation_code: ExportFieldDerivationCode = "text-a-v1" if type_code in _ALPHABETIC_TYPES else "text-an-v1"
    parser_field = joined_field.parser_field
    required = (
        _is_required_admitting_blank_text(parser_field.validation, parser_field.content)
        if joined_field.semantic_entry.kind in {CasillaFieldKind.CASILLA, CasillaFieldKind.COMPUTED}
        else _is_required(parser_field.validation)
    )
    return _schema_field(
        joined_field,
        data_type="text",
        required=required,
        padding=ExportPadding.RIGHT_SPACE,
        justification=ExportJustification.LEFT,
        signed=False,
        export_record_id=export_record_id,
        derivation_code=derivation_code,
    )


def _numeric_field_derivation(
    joined_field: JoinedRecordDesignField,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...],
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...],
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    # Use the profile's same applicability-aware predicate as its eligibility
    # check, so the renderer and profile agree about cells that state no wire fact.
    if _states_no_wire_fact(parser_field, applicability_notes=applicability_notes):
        return _render_profile_numeric_derivation(
            joined_field,
            render_profile,
            export_record_id=export_record_id,
        )
    pinned_values = m714_numeric_values_for(joined_field, render_profile.design_identity)
    if pinned_values is not None:
        return _schema_field(
            joined_field,
            data_type="integer",
            required=_is_required(parser_field.validation),
            padding=ExportPadding.LEFT_ZERO,
            justification=ExportJustification.RIGHT,
            signed=False,
            export_record_id=export_record_id,
            value_policy=ExportValuePolicy.ENUMERATED_DIGITS if pinned_values else None,
            allowed_values=pinned_values or None,
            derivation_code="numeric-enumeration-v1" if pinned_values else "numeric-integer-v1",
        )
    return _numeric_derivation(
        joined_field,
        export_record_id=export_record_id,
        note_governed_amounts=note_governed_amounts,
    )
