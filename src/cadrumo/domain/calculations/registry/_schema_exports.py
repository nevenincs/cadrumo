"""Export and fixed-width record schema models.

This module owns the wire-facing declaration models so casilla and relation
surfaces remain independent of fixed-width rendering policy.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, field_validator, model_validator

from ....core import (
    CasillaId,
    DeclaracionIdioma,
    ExportLayoutFormat,
    FilingProducerKey,
    FilingProjectionRef,
    M303DifferentiatedDeductionProjectionRef,
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
    M303ProrrataActivityProjectionRef,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
    filing_projection_ref_casilla_id,
)
from .._export_field_kind import CasillaFieldKind, CasillaFieldKindValue
from ._errors import RegistryValidationError
from ._export_semantics import (
    ExportComputedKey,
    ExportDraftAttribute,
    ExportSemanticPayloadAxis,
    export_semantic_payload_axis,
)
from ._export_value_policy import ExportValuePolicy, ExportValuePolicyValue, export_value_policy_wire_length
from ._fixed_width_codec import (
    ExportEncodingValue,
    ExportJustificationValue,
    ExportPaddingValue,
    validate_fixed_width_shape,
)
from ._ids import BindingId, ExportFieldId, ExportLayoutId, RecordId, SourceRefId
from ._record_spec import ENCODING_ALIAS_MAP
from ._schema_base import LegalRefs, RegistryModel, SourceRefs

__all__ = [
    "DeclaracionIdiomaValue",
    "ExportComputedKey",
    "ExportDraftAttribute",
    "ExportFieldDefinition",
    "ExportLayoutDefinition",
    "ExportLayoutFormatValue",
    "ExportRecordDefinition",
    "ExportSemanticPayloadAxis",
    "ExportValuePolicyValue",
    "OneBasedExportOffset",
    "ProjectionEndpointDeclaration",
    "RecordDiscriminator",
]

type OneBasedExportOffset = Annotated[int, Field(ge=1)]
"""A positive one-based byte coordinate in an AEAT fixed-width export record."""

#: lookup rather than repeated per policy. A policy absent from this table has
#: no reviewed wire shape and is refused.
_VALUE_POLICY_SHAPES: Mapping[ExportValuePolicy, tuple[str, str, str, bool, str | None]] = {
    ExportValuePolicy.SELECTED_1_UNSELECTED_0: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.UNSIGNED_INTEGER: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.ENUMERATED_DIGITS: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.FOUR_DIGIT_YEAR: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.TWO_DIGIT_MONTH: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.TWO_DIGIT_DAY: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.IMPLIED_DECIMAL: ("decimal", "left_zero", "right", True, None),
    ExportValuePolicy.YYYYMMDD: ("date", "none", "none", False, "aaaammdd"),
    ExportValuePolicy.DDMMYYYY: ("date", "none", "none", False, "ddmmaaaa"),
    ExportValuePolicy.DIGIT_STRING: ("text", "none", "none", False, None),
    ExportValuePolicy.IDENTIFIER_DIGITS: ("text", "none", "none", False, None),
}

_VALUE_POLICY_UNRENDERABLE_KINDS = {CasillaFieldKind.FILLER, CasillaFieldKind.LITERAL, CasillaFieldKind.CHECKSUM}


def _is_canonical_digit_run(value: str, length: int) -> bool:
    """Accept only a zero-canonical ASCII digit run that fits the wire slot.

    ``str(int(value))`` rejects a leading-zero spelling: the slot pads on the
    wire, so ``"01"`` and ``"1"`` would otherwise both address the same
    enumerated member under two spellings.
    """
    return bool(value) and value.isascii() and value.isdigit() and str(int(value)) == value and len(value) <= length


class ProjectionEndpointDeclaration(RegistryModel):
    """Revision-owned admission and evidence for one typed filing endpoint.

    The declaration is deliberately independent of a generated layout.  It
    makes the semantic endpoint identity and its legal/source grounding an
    immutable revision fact before record-design coordinates are generated.
    """

    projection_ref: FilingProjectionRef
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @field_validator("projection_ref", mode="before")
    @classmethod
    def _require_loader_hydrated_projection_ref(cls, value: object) -> object:
        """Refuse raw reference payloads outside the sole registry TOML compiler."""
        if isinstance(
            value,
            M303ProrrataActivityProjectionRef
            | M303DifferentiatedDeductionProjectionRef
            | M303RegimenSimplificadoActivityProjectionRef
            | M303RegimenSimplificadoFactProjectionRef
            | M303RegimenSimplificadoModuleProjectionRef
            | M303Exonerado390ActivityProjectionRef
            | M303Exonerado390OperacionesTercerosProjectionRef,
        ):
            return value
        raise RegistryValidationError(
            "projection_ref must be a loader-hydrated FilingProjectionRef; raw mappings and strings are forbidden",
        )


class ExportFieldDefinition(RegistryModel):
    id: ExportFieldId
    offset: OneBasedExportOffset | None = None
    length: int | None = Field(default=None, gt=0)
    kind: CasillaFieldKindValue
    casilla_id: CasillaId | None = None
    binding: BindingId | None = None
    literal: str | None = None
    producer_key: FilingProducerKey | None = None
    projection_ref: FilingProjectionRef | None = None
    draft_attribute: ExportDraftAttribute | None = None
    computed_key: ExportComputedKey | None = None
    data_type: Literal["text", "integer", "decimal", "money", "date", "boolean"]
    required: bool
    padding: ExportPaddingValue
    justification: ExportJustificationValue
    date_format: str | None = None
    decimals: int | None = Field(default=None, ge=0)
    signed: bool
    value_policy: ExportValuePolicyValue = None
    allowed_values: tuple[str, ...] | None = None
    legal_refs: LegalRefs
    source_refs: SourceRefs

    @property
    def endpoint_casilla_id(self) -> CasillaId | None:
        """Return the exact numbered endpoint carried by this field, if any."""
        if self.casilla_id is not None:
            return self.casilla_id
        if self.projection_ref is None:
            return None
        return filing_projection_ref_casilla_id(self.projection_ref)

    @field_validator("allowed_values")
    @classmethod
    def _canonicalise_allowed_values(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        return None if value is None else tuple(sorted(value))

    @field_validator("projection_ref", mode="before")
    @classmethod
    def _require_loader_hydrated_projection_ref(cls, value: object) -> object:
        """Refuse raw projection identities outside the canonical TOML loader."""
        if value is None or isinstance(
            value,
            M303ProrrataActivityProjectionRef
            | M303DifferentiatedDeductionProjectionRef
            | M303RegimenSimplificadoActivityProjectionRef
            | M303RegimenSimplificadoFactProjectionRef
            | M303RegimenSimplificadoModuleProjectionRef
            | M303Exonerado390ActivityProjectionRef
            | M303Exonerado390OperacionesTercerosProjectionRef,
        ):
            return value
        raise RegistryValidationError(
            "projection_ref must be a loader-hydrated FilingProjectionRef; raw mappings and strings are forbidden",
        )

    @model_validator(mode="after")
    def _validate_field_kind(self) -> ExportFieldDefinition:
        _validate_field_semantic_payload(self)
        _validate_field_render_shape(self)
        return self

    def wire_shape(self) -> tuple[str, str, str, bool, str | None]:
        """Project the declared shape onto the axes a value policy constrains."""
        return _export_field_wire_shape(self)

    def validate_allowed_values(self) -> None:
        """Constrain an exact reviewed semantic integer domain."""
        if failure := _allowed_values_failure(self):
            raise RegistryValidationError(failure)

    def validate_value_policy(self) -> None:
        """Require each explicit policy to match its complete fixed-width shape."""
        if self.value_policy is None:
            return
        if self.kind in _VALUE_POLICY_UNRENDERABLE_KINDS:
            raise RegistryValidationError(
                f"export field {self.id!r} cannot declare value_policy on kind {self.kind!r}",
            )
        if self.signed or _VALUE_POLICY_SHAPES.get(self.value_policy) != self.wire_shape():
            raise RegistryValidationError(
                f"export field {self.id!r} value_policy {self.value_policy.value!r} conflicts with its field shape",
            )
        expected_length = export_value_policy_wire_length(self.value_policy)
        if expected_length is not None and self.length != expected_length:
            raise RegistryValidationError(
                f"export field {self.id!r} value_policy {self.value_policy!r} requires length {expected_length}",
            )
        if self.value_policy is ExportValuePolicy.ENUMERATED_DIGITS and self.allowed_values is None:
            raise RegistryValidationError(
                f"export field {self.id!r} value_policy {self.value_policy.value!r} requires allowed_values",
            )

    def validate_decimals(self) -> None:
        """Require an explicit scale on every decimal field.

        AEAT fixed-width slots carry decimals implicitly: the diseño de registro
        declares them as "N enteros y M decimales" filling the whole slot, with
        no separator byte.  The scale is not derivable from the length -- Modelo
        200 pairs length 9 with 2 decimals and length 7 with 4 -- so it has to be
        declared per field, and a field that omits it cannot be rendered.
        """
        if self.kind == CasillaFieldKind.FILLER:
            return
        if self.data_type == "decimal":
            if self.decimals is None:
                raise RegistryValidationError(f"decimal export field {self.id!r} must declare decimals")
            if self.length is not None and self.decimals >= self.length:
                raise RegistryValidationError(
                    f"decimal export field {self.id!r} declares {self.decimals} decimals "
                    f"which leaves no integer digits in its {self.length}-byte slot",
                )
        elif self.decimals is not None:
            raise RegistryValidationError(
                f"export field {self.id!r} declares decimals but its data_type is {self.data_type!r}",
            )


def _field_semantic_payloads(field: ExportFieldDefinition) -> dict[ExportSemanticPayloadAxis, object | None]:
    return {
        ExportSemanticPayloadAxis.CASILLA_ID: field.casilla_id,
        ExportSemanticPayloadAxis.BINDING: field.binding,
        ExportSemanticPayloadAxis.LITERAL: field.literal,
        ExportSemanticPayloadAxis.PRODUCER_KEY: field.producer_key,
        ExportSemanticPayloadAxis.PROJECTION_REF: field.projection_ref,
        ExportSemanticPayloadAxis.DRAFT_ATTRIBUTE: field.draft_attribute,
        ExportSemanticPayloadAxis.COMPUTED_KEY: field.computed_key,
    }


def _validate_field_semantic_payload(field: ExportFieldDefinition) -> None:
    payloads = _field_semantic_payloads(field)
    required = export_semantic_payload_axis(field.kind)
    declared = tuple(axis for axis, value in payloads.items() if value is not None)
    if failure := _semantic_payload_failure(field, required=required, declared=declared):
        raise RegistryValidationError(failure)
    if field.kind == CasillaFieldKind.FILLER and field.length is None:
        raise RegistryValidationError(f"export field {field.id!r} filler must declare length")


def _semantic_payload_failure(
    field: ExportFieldDefinition,
    *,
    required: ExportSemanticPayloadAxis | None,
    declared: tuple[ExportSemanticPayloadAxis, ...],
) -> str | None:
    if required is None:
        if declared:
            return (
                f"export field {field.id!r} kind {field.kind.value!r} must not declare semantic payloads: "
                f"{', '.join(axis.value for axis in declared)}"
            )
        return None
    if declared != (required,):
        declared_description = ", ".join(axis.value for axis in declared) if declared else "none"
        return (
            f"export field {field.id!r} kind {field.kind.value!r} must declare only {required.value}; "
            f"declared {declared_description}"
        )
    return None


def _validate_field_render_shape(field: ExportFieldDefinition) -> None:
    field.validate_decimals()
    validate_fixed_width_shape(field)
    field.validate_value_policy()
    field.validate_allowed_values()


def _export_field_wire_shape(field: ExportFieldDefinition) -> tuple[str, str, str, bool, str | None]:
    """Project one field's declared shape onto policy-constrained wire axes."""
    return (
        field.data_type,
        field.padding,
        field.justification,
        field.decimals is not None,
        field.date_format,
    )


def _allowed_values_failure(field: ExportFieldDefinition) -> str | None:
    """Return the first contradiction in an enumerated-digit domain."""
    allowed_values = field.allowed_values
    if allowed_values is None:
        return None
    if field.value_policy is not ExportValuePolicy.ENUMERATED_DIGITS:
        return (
            f"export field {field.id!r} allowed_values requires value_policy "
            f"{ExportValuePolicy.ENUMERATED_DIGITS.value!r}"
        )
    if not allowed_values or len(set(allowed_values)) != len(allowed_values):
        return f"export field {field.id!r} allowed_values must be non-empty and unique"
    if _allowed_values_shape_is_invalid(field):
        return (
            f"export field {field.id!r} allowed_values requires an unsigned right-justified "
            "left-zero-padded fixed-width integer"
        )
    assert field.length is not None
    invalid = tuple(value for value in allowed_values if not _is_canonical_digit_run(value, field.length))
    if invalid:
        return f"export field {field.id!r} allowed_values contains noncanonical or out-of-width entries: {invalid!r}"
    return None


def _allowed_values_shape_is_invalid(field: ExportFieldDefinition) -> bool:
    """Return whether a field cannot render enumerated digits canonically."""
    return (
        field.kind in _VALUE_POLICY_UNRENDERABLE_KINDS
        or field.signed
        or field.length is None
        or _export_field_wire_shape(field) != _VALUE_POLICY_SHAPES[ExportValuePolicy.ENUMERATED_DIGITS]
    )


class RecordDiscriminator(RegistryModel):
    """Record-shape discriminator for record types that share literal prefixes.

    A record's literal-prefix matcher cannot tell two records apart when they
    share their leading literal fields (AEAT models several Tipo-2 record
    sub-shapes that all start with the same record-type literal). The
    discriminator declares a contiguous byte range whose populated-or-blank
    pattern uniquely identifies this record subtype, letting the parser pick
    the correct record while reading binding-row sequences.
    """

    offset: OneBasedExportOffset
    length: int = Field(gt=0)
    requires: Literal["blank", "non_blank"]


class ExportRecordDefinition(RegistryModel):
    id: RecordId
    record_type: str
    order: int = Field(ge=0)
    encoding: ExportEncodingValue
    line_ending: Literal["crlf", "lf", "none"]
    required: bool = True
    repeat: Literal["binding_rows", "projection_rows"] | None = None
    binding_record: str | None = None
    row_field_casilla_ids: Mapping[str, CasillaId] = Field(default_factory=dict)
    discriminator: RecordDiscriminator | None = None
    requires_positive_casilla_id: CasillaId | None = None
    fields: tuple[ExportFieldDefinition, ...] = Field(default_factory=tuple)

    @field_validator("binding_record")
    @classmethod
    def _binding_record_non_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise RegistryValidationError("export record binding_record must be non-empty")
        return value

    def repeat_field_family_failure(self, *, allow_unresolved_binding_record: bool = True) -> str | None:
        """Return the exact repeat/payload-family contradiction, if any."""
        has_binding = any(field.kind == CasillaFieldKind.BINDING for field in self.fields)
        has_projection = any(field.kind == CasillaFieldKind.PROJECTION for field in self.fields)
        return _repeat_field_family_failure(
            repeat=self.repeat,
            binding_record_declared=self.binding_record is not None,
            has_binding=has_binding,
            has_projection=has_projection,
            allow_unresolved_binding_record=allow_unresolved_binding_record,
        )

    @model_validator(mode="after")
    def _repeat_matches_field_family(self) -> ExportRecordDefinition:
        if failure := self.repeat_field_family_failure():
            raise RegistryValidationError(failure)
        return self


def _repeat_field_family_failure(
    *,
    repeat: Literal["binding_rows", "projection_rows"] | None,
    binding_record_declared: bool,
    has_binding: bool,
    has_projection: bool,
    allow_unresolved_binding_record: bool,
) -> str | None:
    claims_binding = has_binding or binding_record_declared
    if claims_binding and has_projection:
        return "export record cannot mix binding and projection fields"
    if repeat == "projection_rows":
        return _projection_repeat_failure(claims_binding, has_projection)
    if repeat == "binding_rows":
        return _binding_repeat_failure(
            has_binding, has_projection, binding_record_declared, allow_unresolved_binding_record
        )
    return _fixed_binding_failure(has_binding, binding_record_declared, allow_unresolved_binding_record)


def _projection_repeat_failure(claims_binding: bool, has_projection: bool) -> str | None:
    if claims_binding:
        return "projection-row export record cannot contain binding fields"
    return None if has_projection else "export record repeats projection rows but has no projection fields"


def _binding_repeat_failure(
    has_binding: bool,
    has_projection: bool,
    binding_record_declared: bool,
    allow_unresolved_binding_record: bool,
) -> str | None:
    if has_projection:
        return "binding-row export record cannot contain projection fields"
    if not has_binding and not binding_record_declared:
        return "export record repeats binding rows but has no binding fields"
    if not allow_unresolved_binding_record and not has_binding:
        return "binding-row export record did not materialize binding fields"
    return None


def _fixed_binding_failure(
    has_binding: bool,
    binding_record_declared: bool,
    allow_unresolved_binding_record: bool,
) -> str | None:
    if not allow_unresolved_binding_record and binding_record_declared and not has_binding:
        return "fixed binding export record did not materialize binding fields"
    return None


def _coerce_export_layout_format(value: object) -> object:
    """Coerce a TOML string literal to the canonical export-layout format member.

    Registry models validate in STRICT mode, so a bare ``"fixed_width"`` read out
    of a manifest is not silently accepted as the enum it spells. Hydration is
    therefore explicit at the boundary, which is where the registry authority
    rule puts it: the TOML tree stays free-form text and the compiled objects
    carry typed members. Same shape as the input-kind coercion beside it, and the
    refusal names the accepted set rather than leaving an author with a bare
    type error.
    """
    if isinstance(value, ExportLayoutFormat):
        return value
    if isinstance(value, str):
        try:
            return ExportLayoutFormat(value)
        except ValueError:
            raise RegistryValidationError(
                f"export layout format {value!r} is not a recognised ExportLayoutFormat member; "
                f"expected one of {[member.value for member in ExportLayoutFormat]}",
            ) from None
    raise RegistryValidationError(f"export layout format must be a string, got {type(value).__name__!r}")


ExportLayoutFormatValue = Annotated[ExportLayoutFormat, BeforeValidator(_coerce_export_layout_format)]
"""Annotated export-layout format that hydrates TOML string literals to members."""


def _coerce_declaracion_idioma(value: object) -> DeclaracionIdioma | None:
    """Hydrate an ``Aux/Idioma`` TOML token to its member.

    Mirrors :func:`_coerce_export_layout_format`: the registry TOML stores AEAT's
    plain single-character token, and strict validation would otherwise reject the
    string outright. A token outside the schema's ``(E|G|C|V){1}`` pattern is
    refused by name, with the accepted set spelled out, rather than as a bare type
    error an author cannot act on.
    """
    if value is None or isinstance(value, DeclaracionIdioma):
        return value
    if isinstance(value, str):
        try:
            return DeclaracionIdioma(value)
        except ValueError:
            raise RegistryValidationError(
                f"export layout aux_idioma {value!r} is not a language the AEAT declaration accepts; "
                f"expected one of {[member.value for member in DeclaracionIdioma]}",
            ) from None
    raise RegistryValidationError(f"export layout aux_idioma must be a string, got {type(value).__name__!r}")


DeclaracionIdiomaValue = Annotated[DeclaracionIdioma | None, BeforeValidator(_coerce_declaracion_idioma)]
"""Annotated ``Aux/Idioma`` language that hydrates TOML string literals to members."""


class XmlDictionaryPathOverride(RegistryModel):
    """One official dictionary row whose declared path AEAT itself got wrong.

    The bundled ``.properties`` dictionaries are official AEAT evidence bytes and
    are never edited: their value is that they are what AEAT published, defects
    included. So where a row's path contradicts AEAT's own XSD, the correction is
    declared here instead, beside the layout that consumes it.

    Each override carries the evidence for itself in ``reason``. That is not
    decoration: the override asserts that AEAT's own published dictionary is
    wrong about a row, which is a claim a later reader must be able to audit
    rather than take on trust. "It disagrees with the XSD" is not sufficient
    grounds on its own, because AEAT republishes these schemas mid-year — so
    which of two AEAT artefacts to believe is a reviewed judgement about a
    specific row, never a fact derivable from the disagreement itself.
    """

    field_id: str = Field(min_length=1, max_length=64)
    path: str = Field(min_length=1, max_length=512)
    reason: str = Field(min_length=1, max_length=1024)


class ExportLayoutDefinition(RegistryModel):
    id: ExportLayoutId
    format: ExportLayoutFormatValue = ExportLayoutFormat.FIXED_WIDTH
    dictionary_source_ref: SourceRefId | None = None
    source_refs: SourceRefs
    legal_refs: LegalRefs
    records: tuple[ExportRecordDefinition, ...] = Field(default_factory=tuple)
    dictionary_path_overrides: tuple[XmlDictionaryPathOverride, ...] = Field(default_factory=tuple)
    """Dictionary rows whose AEAT-declared path is corrected before use.

    Applied where the dictionary is read rather than where it is rendered,
    because the writer and the export parser resolve their rows from the same
    call: a correction applied to only one of them would make an artefact verify
    as drift against itself.
    """

    aux_idioma: DeclaracionIdiomaValue = None
    """Language the declaration's mandatory ``Aux/Idioma`` element declares.

    The AEAT dictionary that drives an ``xml_dictionary`` render describes no
    ``Aux`` row at all, in any bundled revision, while every XSD makes the block
    mandatory and first — so the value cannot come from the dictionary and is
    declared here instead, beside the format that requires it.
    """

    aux_version: str | None = Field(default=None, min_length=1, max_length=4)
    """Producer token the declaration's mandatory ``Aux/VERSION`` element carries.

    Deliberately has NO default, and that is load-bearing rather than caution.
    AEAT declares the element as ``tipo_String4L`` — four characters against a
    permissive pattern, with no enumeration, no annotation, and no worked example
    carrying a genuine value anywhere in the bundled corpus. So a plausible token
    such as ``"1.00"`` would VALIDATE while asserting something nothing verified,
    the document would start passing our own checks, and the gap would stop being
    reported at all.

    Two sources that look authoritative are not. A real AEAT-submitted
    declaration in the fixture corpus carries ``<VERSION>2.02</VERSION>``, which
    is a redaction placeholder — the sanitiser assigned sequential field-position
    indices, and its siblings include an ``ECIVIL`` of ``6`` where the schema
    admits only 1-4. And the registry's own ``LegalParameter`` surface, the
    obvious home for a "declared parameter", requires a legal citation this value
    has none of; declaring it there would have meant inventing one.

    Absent, the export refuses rather than emitting a partial ``Aux`` — which
    would be invalid regardless, since the element is ``minOccurs="1"``.
    """

    @model_validator(mode="after")
    def _validate_layout_format(self) -> ExportLayoutDefinition:
        if self.format is ExportLayoutFormat.XML_DICTIONARY:
            _validate_xml_dictionary_layout(self)
        else:
            _validate_non_xml_layout(self)
        return self

    @model_validator(mode="after")
    def _validate_encoding_consistency(self) -> ExportLayoutDefinition:
        """Enforce one encoding per fixed-width export layout.

        AEAT publishes one wire encoding per modelo-year fichero-BOE
        spec; mixing encodings across records inside a single layout
        is a registry-author error that would produce a payload no
        single decoder can faithfully re-parse. ``latin-1`` and
        ``iso-8859-1`` are normalised to the same encoding before
        comparison (Python codec aliases for the same charset).

        Cross-domain encoding-lock: every record within one layout
        must declare an encoding that normalises to the same value.
        XML-dictionary layouts have no record-level encoding (the
        records tuple is typically empty), so this check is a no-op
        for them.
        """
        if self.format is not ExportLayoutFormat.FIXED_WIDTH:
            return self
        normalised: dict[str, str] = {}
        for record in self.records:
            normalised[record.id] = _normalise_fichero_boe_encoding(record.encoding)
        unique_encodings = set(normalised.values())
        if len(unique_encodings) > 1:
            per_record = ", ".join(f"{record_id}={encoding!r}" for record_id, encoding in sorted(normalised.items()))
            raise RegistryValidationError(
                f"export layout {self.id!r} declares inconsistent encodings "
                f"across its records: {per_record}. A single fichero-BOE "
                f"layout must use one wire encoding so the published payload "
                f"decodes uniformly.",
            )
        return self


def _validate_xml_dictionary_layout(layout: ExportLayoutDefinition) -> None:
    if layout.dictionary_source_ref is None:
        raise RegistryValidationError(f"export layout {layout.id!r} must declare dictionary_source_ref")
    if layout.dictionary_source_ref not in layout.source_refs:
        raise RegistryValidationError(
            f"export layout {layout.id!r} dictionary source must be included in source_refs",
        )
    if layout.aux_idioma is None:
        raise RegistryValidationError(
            f"export layout {layout.id!r} must declare aux_idioma: the declaration's Aux block is "
            "mandatory in every AEAT XSD and no dictionary declares its rows",
        )
    override_fields = [override.field_id for override in layout.dictionary_path_overrides]
    duplicates = sorted({name for name in override_fields if override_fields.count(name) > 1})
    if duplicates:
        raise RegistryValidationError(
            f"export layout {layout.id!r} declares more than one dictionary path override for "
            f"{duplicates!r}, so which correction applies is ambiguous",
        )


def _validate_non_xml_layout(layout: ExportLayoutDefinition) -> None:
    if layout.aux_idioma is not None or layout.aux_version is not None:
        raise RegistryValidationError(
            f"export layout {layout.id!r} declares Aux identity on a {layout.format} layout, which has no Aux block",
        )
    if layout.dictionary_path_overrides:
        raise RegistryValidationError(
            f"export layout {layout.id!r} declares dictionary path overrides on a {layout.format} layout, "
            "which reads no dictionary",
        )


def _normalise_fichero_boe_encoding(declared: str) -> str:
    """Return the canonical form of a fichero-BOE encoding declaration."""
    return ENCODING_ALIAS_MAP.get(declared.strip().lower(), declared.strip().lower())
