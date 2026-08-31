"""Export and fixed-width record schema models.

This module owns the wire-facing declaration models so casilla and relation
surfaces remain independent of fixed-width rendering policy.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BeforeValidator, Field, field_validator, model_validator

from ....core import DeclaracionIdioma, ExportLayoutFormat
from ....core.filing_producer_key import FilingProducerKey
from ....core.filing_projection_ref import (
    FilingProjectionRef,
    filing_projection_ref_casilla_id,
    hydrate_filing_projection_ref,
)
from ....core.casilla_id import CasillaId
from ..export_field_kind import CasillaFieldKind, CasillaFieldKindValue
from .errors import RegistryValidationError
from .export_semantics import (
    ExportComputedKey,
    ExportDraftAttribute,
    ExportSemanticPayloadAxis,
    export_semantic_payload_axis,
)
from .export_value_policy import ExportValuePolicy, ExportValuePolicyValue, export_value_policy_wire_length
from .fixed_width_codec import (
    ExportEncodingValue,
    ExportJustificationValue,
    ExportPaddingValue,
    validate_fixed_width_shape,
)
from .ids import BindingId, ExportFieldId, ExportLayoutId, RecordId, SourceRefId
from .record_spec import ENCODING_ALIAS_MAP
from .schema_base import LegalRefs, RegistryModel, SourceRefs

__all__ = [
    "DeclaracionIdiomaValue",
    "ExportFieldDataType",
    "ExportFieldDefinition",
    "ExportLayoutDefinition",
    "ExportLayoutFormatValue",
    "ExportRecordDefinition",
    "FilingEnvelopeCloserDerivation",
    "FilingEnvelopeDefinition",
    "FilingEnvelopePrefixFieldDeclaration",
    "FilingEnvelopePrefixRole",
    "FilingEnvelopeTotalDerivation",
    "OneBasedExportOffset",
    "ProjectionEndpointDeclaration",
    "RecordDiscriminator",
]

type OneBasedExportOffset = Annotated[int, Field(ge=1)]
"""A positive one-based byte coordinate in an AEAT fixed-width export record."""


type ExportFieldDataType = Literal["text", "integer", "decimal", "money", "date", "boolean"]
"""The canonical wire-facing scalar vocabulary for an export field's rendered/parsed shape.

Deliberately narrower than :class:`~._schema_surfaces.CasillaDefinition`'s own
``data_type`` (18 members, e.g. ``nif``, ``ratio``, ``iban``) and
:class:`~._schema_formula.ParameterDefinition`'s own ``data_type`` (8 members,
e.g. ``ratio``, ``bracket_table``) -- an export or binding field is never one
of those richer casilla- or formula-level shapes, only the six primitives a
fixed-width/XML-dictionary wire slot can actually encode. This is the sole
declaration: :attr:`ExportFieldDefinition.data_type` and
:data:`~._binding_selector_utils.BindingExportDataType` both alias it rather
than re-declaring the six literals.
"""


class FilingEnvelopePrefixRole(StrEnum):
    """Closed roles an AEAT variable-envelope prefix declares, in source order.

    ONE vocabulary for every modelo, because the designs share one grammar: the
    thirty-five bundled 328-byte envelopes all open with the ``<T…>`` record
    identifier and an ``<AUX>`` block carrying the product identity between
    reserved spans. What differs between designs is which of these roles a given
    design prints and how wide each one is -- both facts the declaration carries
    -- not what the roles MEAN.

    Declared in this order deliberately: a declaration's roles must appear as a
    subsequence of this tuple, so a design that omits a role stays admissible
    while one that reorders the grammar refuses.

    :attr:`COMPOSED_OPENING_TAG` is the one genuine alternative rather than an
    omission. Some designs (Modelo 200, 100, 714) print the whole seventeen-byte
    ``<T200020250A0000>`` identifier as ONE source row instead of the six
    separate rows Modelo 303 prints, so the two spellings are mutually exclusive
    and :class:`FilingEnvelopeDefinition` refuses a declaration carrying both.
    """

    COMPOSED_OPENING_TAG = "composed_opening_tag"
    OPENING_TAG = "opening_tag"
    MODELO = "modelo"
    DISCRIMINANT = "discriminant"
    FILING_YEAR = "filing_year"
    PERIOD = "period"
    RECORD_TYPE = "record_type"
    AUX_OPENING_TAG = "aux_opening_tag"
    PRE_PROGRAM_FILLER = "pre_program_filler"
    PROGRAM_IDENTIFIER = "program_identifier"
    BETWEEN_IDENTITIES_FILLER = "between_identities_filler"
    DEVELOPER_TAX_ID = "developer_tax_id"
    POST_DEVELOPER_FILLER = "post_developer_filler"
    AUX_CLOSING_TAG = "aux_closing_tag"


#: The six roles a :attr:`FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG` fuses.
_OPENING_TAG_COMPONENT_ROLES: tuple[FilingEnvelopePrefixRole, ...] = (
    FilingEnvelopePrefixRole.OPENING_TAG,
    FilingEnvelopePrefixRole.MODELO,
    FilingEnvelopePrefixRole.DISCRIMINANT,
    FilingEnvelopePrefixRole.FILING_YEAR,
    FilingEnvelopePrefixRole.PERIOD,
    FilingEnvelopePrefixRole.RECORD_TYPE,
)


class FilingEnvelopeCloserDerivation(StrEnum):
    """Closed algorithms deriving a variable envelope's closing identifier."""

    RELATIVE_CLOSER_V1 = "relative-closer-v1"


class FilingEnvelopeTotalDerivation(StrEnum):
    """Closed algorithms deriving a variable envelope's declared total."""

    EMITTED_BYTE_TOTAL_V1 = "emitted-byte-total-v1"


def _coerce_envelope_prefix_role(value: object) -> object:
    """Hydrate the authored layout token into its closed prefix role."""
    if isinstance(value, FilingEnvelopePrefixRole):
        return value
    if isinstance(value, str):
        try:
            return FilingEnvelopePrefixRole(value)
        except ValueError as exc:
            raise ValueError(
                f"unknown filing-envelope prefix role {value!r}; "
                f"expected one of {[member.value for member in FilingEnvelopePrefixRole]}",
            ) from exc
    raise ValueError("filing-envelope prefix role must be a string")


def _coerce_envelope_closer_derivation(value: object) -> object:
    if isinstance(value, FilingEnvelopeCloserDerivation):
        return value
    if isinstance(value, str):
        try:
            return FilingEnvelopeCloserDerivation(value)
        except ValueError as exc:
            raise ValueError(f"unknown filing-envelope closer derivation {value!r}") from exc
    raise ValueError("filing-envelope closer derivation must be a string")


def _coerce_envelope_total_derivation(value: object) -> object:
    if isinstance(value, FilingEnvelopeTotalDerivation):
        return value
    if isinstance(value, str):
        try:
            return FilingEnvelopeTotalDerivation(value)
        except ValueError as exc:
            raise ValueError(f"unknown filing-envelope total derivation {value!r}") from exc
    raise ValueError("filing-envelope total derivation must be a string")


type FilingEnvelopePrefixRoleValue = Annotated[
    FilingEnvelopePrefixRole,
    BeforeValidator(_coerce_envelope_prefix_role),
]
type FilingEnvelopeCloserDerivationValue = Annotated[
    FilingEnvelopeCloserDerivation,
    BeforeValidator(_coerce_envelope_closer_derivation),
]
type FilingEnvelopeTotalDerivationValue = Annotated[
    FilingEnvelopeTotalDerivation,
    BeforeValidator(_coerce_envelope_total_derivation),
]


class FilingEnvelopePrefixFieldDeclaration(RegistryModel):
    """One reviewed envelope prefix role and its exact emitted byte length."""

    role: FilingEnvelopePrefixRoleValue
    length: int = Field(gt=0)


class FilingEnvelopeDefinition(RegistryModel):
    """Static variable-envelope declaration carried by a generated layout.

    This is a declaration of the envelope grammar, not an instance filing
    payload.  Period, product identity values, body occurrences, bytes, totals,
    and digests are deliberately absent: the application filing boundary owns
    those facts when it renders an approved draft.

    Modelo-agnostic BY CONSTRUCTION rather than by convention. Every fact that
    used to be a Modelo 303 constant in code -- the ``DP30300`` identity, the
    thirteen-slot prefix, the 328-byte extent -- is declared data here, so the
    same type carries Modelo 200's eight-slot composed-tag prefix and Modelo
    309's thirteen without a branch. The modelo itself is deliberately NOT a
    field: the layout is owned by exactly one revision of one modelo, and the
    render path reads that identity from the selected snapshot rather than
    letting a second, drift-capable spelling of it exist here.
    """

    schema_version: Literal[1] = 1
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    record_identity: str = Field(min_length=1)
    prefix_fields: tuple[FilingEnvelopePrefixFieldDeclaration, ...] = Field(min_length=1)
    prefix_extent: int = Field(gt=0)
    body_record_ids: tuple[RecordId, ...] = Field(min_length=1)
    product_identity_requirement: Literal["aeat-product-software-identity-v1"]
    closer_derivation: FilingEnvelopeCloserDerivationValue
    total_derivation: FilingEnvelopeTotalDerivationValue

    @model_validator(mode="after")
    def _require_complete_static_grammar(self) -> FilingEnvelopeDefinition:
        roles = tuple(field.role for field in self.prefix_fields)
        if len(set(roles)) != len(roles):
            raise RegistryValidationError(
                f"filing envelope {self.record_identity!r} prefix declaration repeats a role: {roles!r}",
            )
        if not _is_subsequence(roles, tuple(FilingEnvelopePrefixRole)):
            raise RegistryValidationError(
                f"filing envelope {self.record_identity!r} prefix roles must appear in canonical source order",
            )
        _require_one_opening_tag_spelling(self.record_identity, roles)
        declared_extent = sum(field.length for field in self.prefix_fields)
        if declared_extent != self.prefix_extent:
            raise RegistryValidationError(
                f"filing envelope {self.record_identity!r} declares a {self.prefix_extent}-byte prefix extent "
                f"but its prefix fields sum to {declared_extent}",
            )
        if len(set(self.body_record_ids)) != len(self.body_record_ids):
            raise RegistryValidationError(
                f"filing envelope {self.record_identity!r} body record declarations must be unique and ordered",
            )
        return self


#: Wire version of the auxiliary-envelope header declaration. Named rather than
#: written as a bare default so the number has one home: a reader can find every
#: site bound to this format, and a version bump cannot land on the model while a
#: writer stamping the old number silently disagrees with it.
AUXILIARY_ENVELOPE_HEADER_SCHEMA_VERSION: Final[Literal[1]] = 1


class AuxiliaryEnvelopeHeaderDefinition(RegistryModel):
    """Static total-less page-zero header declaration carried by a generated layout.

    The fixed 328-byte header that opens a design whose records are fixed
    (Modelo 232's ``DR23200``; Modelo 390's page zero). It shares the filing
    envelope's prefix grammar -- the same thirteen roles in canonical order and
    the same emitted literals -- and declares no body, closer or total: the
    layout's records are the payload.

    A declaration, not an instance payload, for the same reason its envelope
    sibling is: period and product-identity values are filing-instance facts
    the application filing boundary owns at render time.
    """

    schema_version: Literal[1] = AUXILIARY_ENVELOPE_HEADER_SCHEMA_VERSION
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    record_identity: str = Field(min_length=1)
    prefix_fields: tuple[FilingEnvelopePrefixFieldDeclaration, ...] = Field(min_length=13, max_length=13)
    prefix_extent: int = Field(gt=0)
    product_identity_requirement: Literal["aeat-product-software-identity-v1"]

    @model_validator(mode="after")
    def _require_complete_static_header(self) -> AuxiliaryEnvelopeHeaderDefinition:
        roles = tuple(field.role for field in self.prefix_fields)
        if len(set(roles)) != len(roles):
            raise RegistryValidationError(
                f"auxiliary envelope header {self.record_identity!r} prefix declaration repeats a role: {roles!r}",
            )
        if not _is_subsequence(roles, tuple(FilingEnvelopePrefixRole)):
            raise RegistryValidationError(
                f"auxiliary envelope header {self.record_identity!r} prefix roles must appear in "
                "canonical source order",
            )
        if FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG in roles:
            raise RegistryValidationError(
                f"auxiliary envelope header {self.record_identity!r} may not carry a composed opening tag",
            )
        declared_extent = sum(field.length for field in self.prefix_fields)
        if declared_extent != self.prefix_extent:
            raise RegistryValidationError(
                f"auxiliary envelope header {self.record_identity!r} declares a {self.prefix_extent}-byte "
                f"extent but its prefix fields sum to {declared_extent}",
            )
        return self


def _is_subsequence(candidate: tuple[object, ...], universe: tuple[object, ...]) -> bool:
    """Return whether ``candidate`` appears within ``universe`` in order."""
    remaining = iter(universe)
    return all(item in remaining for item in candidate)


def _require_one_opening_tag_spelling(
    record_identity: str,
    roles: tuple[FilingEnvelopePrefixRole, ...],
) -> None:
    """Refuse a prefix declaring both opening-tag spellings, or neither."""
    composed = FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG in roles
    components = tuple(role for role in _OPENING_TAG_COMPONENT_ROLES if role in roles)
    if composed and components:
        raise RegistryValidationError(
            f"filing envelope {record_identity!r} declares the composed opening tag alongside its "
            f"component roles {tuple(role.value for role in components)!r}; the two spellings are exclusive",
        )
    if not composed and components != _OPENING_TAG_COMPONENT_ROLES:
        raise RegistryValidationError(
            f"filing envelope {record_identity!r} must declare either the composed opening tag or every "
            f"one of its six component roles; declared {tuple(role.value for role in components)!r}",
        )


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
    # Both halves of a split quantity occupy an integer slot: each writes a
    # zero-padded, right-justified digit run of its own width, and the decimal
    # point is implied by the BOUNDARY between them rather than declared on
    # either. Declaring the fractional half "decimal" would ask it for a scale
    # it does not have -- its digits ARE the scale.
    ExportValuePolicy.INTEGER_PART: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.FRACTIONAL_DIGITS: ("integer", "left_zero", "right", False, None),
    ExportValuePolicy.YYYYMMDD: ("date", "none", "none", False, "aaaammdd"),
    ExportValuePolicy.DDMMYYYY: ("date", "none", "none", False, "ddmmaaaa"),
    ExportValuePolicy.DIGIT_STRING: ("text", "none", "none", False, None),
    ExportValuePolicy.IDENTIFIER_DIGITS: ("text", "none", "none", False, None),
    # Blank-filled and left-justified, like every other alphanumeric slot. The
    # digit-identity policies above take "none"/"none" because an identifier
    # must fill its slot exactly; prose does not, and zero-filling it would
    # corrupt the value rather than pad it.
    ExportValuePolicy.MISTYPED_ALPHANUMERIC_TEXT: ("text", "right_space", "left", False, None),
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
    def _compile_projection_ref_through_the_canonical_compiler(cls, value: object) -> object:
        """Compile a still-raw reference through the one canonical compiler.

        The declaration is persisted and re-read, so a guard demanding an
        already-typed reference could never admit its own serialised form. The
        invariant that matters is that the compiler produced it, and delegating
        here keeps exactly that while refusing every malformed payload it
        always refused.
        """
        try:
            return hydrate_filing_projection_ref(value)
        except ValueError as error:
            raise RegistryValidationError(
                f"projection_ref is not a valid filing projection reference: {error}",
            ) from error


class ExportFieldDefinition(RegistryModel):
    """Declare one field's position, value, and rendering constraints in an export."""

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
    data_type: ExportFieldDataType
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
    def _compile_projection_ref_through_the_canonical_compiler(cls, value: object) -> object:
        """Compile a still-raw projection identity through the one canonical compiler.

        An export field is embedded in the provenance manifest and re-read from
        JSON, where a reference can only arrive as a mapping. Delegating keeps
        the invariant that the compiler produced every reference, and every
        malformed payload refuses exactly as before.
        """
        if value is None:
            return None
        try:
            return hydrate_filing_projection_ref(value)
        except ValueError as error:
            raise RegistryValidationError(
                f"projection_ref is not a valid filing projection reference: {error}",
            ) from error

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
    """Declare one record type and its ordered field authority in an export layout."""

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
    """Declare the complete wire layout used to render an official export."""

    id: ExportLayoutId
    format: ExportLayoutFormatValue = ExportLayoutFormat.FIXED_WIDTH
    dictionary_source_ref: SourceRefId | None = None
    source_refs: SourceRefs
    legal_refs: LegalRefs
    records: tuple[ExportRecordDefinition, ...] = Field(default_factory=tuple)
    filing_envelope: FilingEnvelopeDefinition | None = None
    """Variable-composition wrapper this fixed-width layout's records live inside.

    Absent for the majority of layouts, whose records ARE the payload. Present
    where the official design declares a ``Total: Variable`` envelope, in which
    case the records are its body members rather than the whole file.
    """

    auxiliary_envelope_header: AuxiliaryEnvelopeHeaderDefinition | None = None
    """Total-less 328-byte page-zero header emitted before this layout's records.

    Absent for every layout whose design declares no such header. Present where
    the design prints one (Modelo 232's ``DR23200``; Modelo 390's page zero):
    the records remain the payload and the header is emitted as their prefix.
    A layout declaring both this and a filing envelope is refused, since no
    design composes a variable body behind a total-less page-zero header.
    """

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
    if layout.filing_envelope is not None:
        raise RegistryValidationError(
            f"export layout {layout.id!r} declares a filing envelope on an XML-dictionary layout",
        )
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
    envelope = layout.filing_envelope
    auxiliary_header = layout.auxiliary_envelope_header
    if envelope is not None and auxiliary_header is not None:
        raise RegistryValidationError(
            f"export layout {layout.id!r} declares both a filing envelope and an auxiliary envelope "
            "header, which no design composes",
        )
    if envelope is None:
        if auxiliary_header is None:
            return
        if layout.format is not ExportLayoutFormat.FIXED_WIDTH:
            raise RegistryValidationError(
                f"export layout {layout.id!r} declares an auxiliary envelope header on a non-fixed-width layout",
            )
        if auxiliary_header.source_ref not in layout.source_refs:
            raise RegistryValidationError(
                f"export layout {layout.id!r} auxiliary envelope header source must be included in source_refs",
            )
        return
    if layout.format is not ExportLayoutFormat.FIXED_WIDTH:
        raise RegistryValidationError(
            f"export layout {layout.id!r} declares a filing envelope on a non-fixed-width layout",
        )
    if envelope.source_ref not in layout.source_refs:
        raise RegistryValidationError(
            f"export layout {layout.id!r} filing-envelope source must be included in source_refs",
        )
    record_ids = tuple(record.id for record in layout.records)
    if record_ids != envelope.body_record_ids:
        raise RegistryValidationError(
            f"export layout {layout.id!r} filing-envelope body records must retain the exact layout order",
        )


def _normalise_fichero_boe_encoding(declared: str) -> str:
    """Return the canonical form of a fichero-BOE encoding declaration."""
    return ENCODING_ALIAS_MAP.get(declared.strip().lower(), declared.strip().lower())
