"""Strict, frontend-neutral records for the Modelo Edit Contract V1.

Behind :mod:`cadrumo.application.modelo`, this family owns edit admission and
parsing, authoritative preflight, an exact compare-and-swap mutation
baseline, typed scalar and repeatable-row intents, mutation capability
projection, and the safe result receipt for a guarded calculation edit. It
never owns TUI state, operation lifecycle or custody, registry meaning,
calculation formulas, or persistence adapters -- see
:class:`~domain.calculations.registry.schema.ModeloRevision` for the
registry-owned schema these edits address.

A :class:`ModeloWorkspaceBaselineV1` read-consistency token is never accepted
as mutation authority; admission independently re-resolves every coordinate
this family authorizes against.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG, CasillaId, OutputLanguage, Period
from ...core.identity import (
    BucketId,
    CalculationRevisionId,
    ContentDigest,
    ModeloEditBaselineId,
    ModeloEditMutationResultReceiptId,
    WorkUnitId,
)
from ...core.time import validate_utc_aware
from ...domain.buckets import BucketEventId
from ...domain.calculations.registry.ids import BindingId, RevisionId
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.filing import ModeloScalar
from ...domain.modelos import ModeloCode
from ..operations.models import OperationDefinitionId, OperationId, OperationReference
from ..operations.registry import OperationSchemaIdentityV1
from ..operator_actions import ActionReference
from .workspace_models import (
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceTargetV1,
)

_MAX_FINDINGS = 500
_MAX_INTENTS = 500
_MAX_SURFACE_ENTRIES = 2000
_MAX_MESSAGE_ARGUMENTS = 16
_MAX_EVIDENCE_REFERENCES = 64
_MAX_CAPABILITY_ROWS = 64
_MAX_ROW_VALUES = 200

type _BoundedText = Annotated[str, Field(min_length=1, max_length=256)]
type _BoundedCode = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$")]
type _ClientRowCorrelationId = Annotated[str, Field(min_length=1, max_length=128)]
type _BoundedRefList = Annotated[tuple[_BoundedText, ...], Field(max_length=_MAX_EVIDENCE_REFERENCES)]


class _EditModel(BaseModel):
    """The common fail-closed boundary posture for Edit Contract V1 records."""

    model_config = STRICT_FROZEN_CONFIG


class ModeloEditMutationFamily(StrEnum):
    """The closed set of edit-executed effects this V1 contract covers."""

    CALCULATE = "calculate"
    RECALCULATE = "recalculate"


class ModeloEditScalarIntentKind(StrEnum):
    """The three distinct scalar edit intents; address absence means UNCHANGED."""

    SET_TYPED_VALUE = "set_typed_value"
    CLEAR_DECLARED_VALUE = "clear_declared_value"
    REMOVE_OVERRIDE = "remove_override"


class ModeloEditRowIntentKind(StrEnum):
    """The closed repeatable-row edit intents; MOVE_ROW requires reorderable groups."""

    ADD_ROW = "add_row"
    UPDATE_ROW = "update_row"
    DELETE_ROW = "delete_row"
    MOVE_ROW = "move_row"


class ModeloEditNonWritableReason(StrEnum):
    """Why one permitted-surface address is not writable in this baseline."""

    COMPUTED_BY_FORMULA = "computed_by_formula"
    SCHEMA_DECLARED_READ_ONLY = "schema_declared_read_only"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"


class ModeloEditFindingSeverity(StrEnum):
    """The closed severity denominator for one preflight finding."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ModeloEditExecutionEffect(StrEnum):
    """The two possible outcomes of one guarded compare-and-swap execution."""

    UPDATED = "updated"
    NONE = "none"


class ModeloEditRefusalCode(StrEnum):
    """The closed refusal-boundary denominator for the edit contract.

    ``STALE_EDIT_BASELINE`` never appears on :class:`ModeloEditDomainRefusalV1`;
    it is carried only by the structured :class:`ModeloEditStaleBaselineRefusalV1`,
    the same split ``ModeloWorkspaceDomainRefusalV1`` draws for its own
    two-axis mismatch.
    """

    TARGET_ABSENT = "target_absent"
    TARGET_AMBIGUOUS = "target_ambiguous"
    ADMISSION_DENIED = "admission_denied"
    UNSUPPORTED_SCHEMA_KIND = "unsupported_schema_kind"
    DISALLOWED_INTENT = "disallowed_intent"
    PARSE_FAILED = "parse_failed"
    VALIDATION_FAILED = "validation_failed"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    WORK_CATALOGUE_CONFLICT = "work_catalogue_conflict"
    CALCULATION_HEAD_CONFLICT = "calculation_head_conflict"
    REGISTRY_SCHEMA_CONFLICT = "registry_schema_conflict"
    SURFACE_CONFLICT = "surface_conflict"
    BASELINE_EXPIRED = "baseline_expired"
    STALE_EDIT_BASELINE = "stale_edit_baseline"


class ModeloEditVersionHeader(_EditModel):
    """Minimal pre-dispatch shape read before target or financial input parsing."""

    edit_contract_version: Annotated[int, Field(ge=1)]


class ModeloEditCompatibilityTupleV1(_EditModel):
    """Every distinct current-only version and digest axis this edit binds to.

    No member is collapsed into a generic shared ``version``, and a manifest
    version never substitutes for a definition or contract-set digest.
    """

    workspace_contract_version: Literal[1] = 1
    edit_contract_version: Literal[1] = 1
    operation_manifest_version: Literal[1] = 1
    contract_set_digest: ContentDigest
    operation_definition_id: OperationDefinitionId
    definition_contract_digest: ContentDigest
    request_schema: OperationSchemaIdentityV1
    result_schema: OperationSchemaIdentityV1
    observation_contract_version: Literal[1] = 1
    review_projection_contract_version: Literal[1] | None
    review_schema: OperationSchemaIdentityV1 | None
    workspace_refresh_target_version: Literal[1] = 1
    workspace_refresh_target_schema: OperationSchemaIdentityV1
    financial_operand_protocol_version: Literal[1] = 1
    financial_operand_schema: OperationSchemaIdentityV1

    @model_validator(mode="after")
    def _require_consistent_review_declaration(self) -> ModeloEditCompatibilityTupleV1:
        has_version = self.review_projection_contract_version is not None
        has_schema = self.review_schema is not None
        if has_version != has_schema:
            raise ValueError("edit compatibility REVIEW axis must declare version and schema together or neither")
        return self


def read_modelo_edit_version_header(payload: dict[str, object]) -> ModeloEditVersionHeader | None:
    """Return the version header if present, without parsing anything else.

    The exact version dispatcher reads only ``edit_contract_version`` before a
    target or financial input is parsed, so an unsupported version refuses
    before any secure state is touched.
    """
    value = payload.get("edit_contract_version")
    if not isinstance(value, int):
        return None
    return ModeloEditVersionHeader(edit_contract_version=value)


class ModeloEditScalarAddressV1(_EditModel):
    """A canonical semantic scalar address, keyed by the registry casilla identity."""

    kind: Literal["scalar"] = "scalar"
    casilla_id: CasillaId


class ModeloEditExistingRowAddressV1(_EditModel):
    """The application-issued canonical coordinate of one persisted repeated row."""

    kind: Literal["existing_row"] = "existing_row"
    binding_id: BindingId
    row_index: Annotated[int, Field(ge=1)]


class ModeloEditNewRowCorrelationV1(_EditModel):
    """An opaque client correlation for a row not yet assigned persistence identity.

    Carries no persistence meaning; the canonical row coordinate is minted by
    the result and mapped back to this correlation. Positional widget indexes
    are never identity.
    """

    kind: Literal["new_row"] = "new_row"
    binding_id: BindingId
    client_correlation_id: _ClientRowCorrelationId


type ModeloEditRowAddressV1 = Annotated[
    ModeloEditExistingRowAddressV1 | ModeloEditNewRowCorrelationV1,
    Field(discriminator="kind"),
]

type ModeloEditAddressV1 = Annotated[
    ModeloEditScalarAddressV1 | ModeloEditExistingRowAddressV1 | ModeloEditNewRowCorrelationV1,
    Field(discriminator="kind"),
]


type ModeloEditCasillaDataType = Literal[
    "decimal",
    "money",
    "integer",
    "ratio",
    "text",
    "boolean",
    "nif",
    "year",
    "period_code",
    "country_code",
    "iban",
    "name",
    "nif_iva",
    "ccaa_code",
    "province_code",
    "postal_code",
    "municipality_code",
    "bic",
    "date",
]
"""The exact registry ``CasillaDefinition.data_type`` closed set, mirrored here.

Metadata only, not a value: the parse service selects its grammar from this
axis, and the permitted surface carries no casilla value.
"""


class ModeloEditWritableScalarSurfaceEntryV1(_EditModel):
    """One scalar address the baseline admits for writing, with its allowed intents."""

    kind: Literal["writable_scalar"] = "writable_scalar"
    casilla_id: CasillaId
    data_type: ModeloEditCasillaDataType
    allowed_intents: Annotated[tuple[ModeloEditScalarIntentKind, ...], Field(min_length=1, max_length=3)]

    @field_validator("allowed_intents")
    @classmethod
    def _require_unique_allowed_intents(
        cls, value: tuple[ModeloEditScalarIntentKind, ...]
    ) -> tuple[ModeloEditScalarIntentKind, ...]:
        if len(set(value)) != len(value):
            raise ValueError("writable scalar surface entry must declare each allowed intent at most once")
        return value


class ModeloEditNonWritableScalarSurfaceEntryV1(_EditModel):
    """One scalar address the baseline exposes as read-only, with its reason."""

    kind: Literal["non_writable_scalar"] = "non_writable_scalar"
    casilla_id: CasillaId
    reason: ModeloEditNonWritableReason


class ModeloEditWritableRowGroupSurfaceEntryV1(_EditModel):
    """One repeated-row group the baseline admits for writing."""

    kind: Literal["writable_row_group"] = "writable_row_group"
    binding_id: BindingId
    allowed_intents: Annotated[tuple[ModeloEditRowIntentKind, ...], Field(min_length=1, max_length=4)]
    reorderable: bool
    max_rows: Annotated[int, Field(ge=1)] | None = None

    @field_validator("allowed_intents")
    @classmethod
    def _require_unique_allowed_row_intents(
        cls, value: tuple[ModeloEditRowIntentKind, ...]
    ) -> tuple[ModeloEditRowIntentKind, ...]:
        if len(set(value)) != len(value):
            raise ValueError("writable row-group surface entry must declare each allowed intent at most once")
        return value

    @model_validator(mode="after")
    def _require_reorderable_for_move(self) -> ModeloEditWritableRowGroupSurfaceEntryV1:
        if ModeloEditRowIntentKind.MOVE_ROW in self.allowed_intents and not self.reorderable:
            raise ValueError("MOVE_ROW may be allowed only when the row group is declared reorderable")
        return self


class ModeloEditNonWritableRowGroupSurfaceEntryV1(_EditModel):
    """One repeated-row group the baseline exposes as read-only, with its reason."""

    kind: Literal["non_writable_row_group"] = "non_writable_row_group"
    binding_id: BindingId
    reason: ModeloEditNonWritableReason


type ModeloEditPermittedSurfaceEntryV1 = Annotated[
    ModeloEditWritableScalarSurfaceEntryV1
    | ModeloEditNonWritableScalarSurfaceEntryV1
    | ModeloEditWritableRowGroupSurfaceEntryV1
    | ModeloEditNonWritableRowGroupSurfaceEntryV1,
    Field(discriminator="kind"),
]


def _surface_entry_address(entry: ModeloEditPermittedSurfaceEntryV1) -> tuple[str, str]:
    if isinstance(entry, (ModeloEditWritableScalarSurfaceEntryV1, ModeloEditNonWritableScalarSurfaceEntryV1)):
        return ("scalar", entry.casilla_id)
    return ("row_group", entry.binding_id)


class ModeloEditSchemaIdentityV1(_EditModel):
    """The edit contract's own schema identity: a compare-and-swap coordinate, not a display fact.

    Deliberately its own type rather than a reuse of
    :class:`~.workspace_models.ModeloWorkspaceSchemaIdentityV1` -- the two
    types share a shape (an id, a fingerprint, and a manifest digest) but not
    a meaning. ``completeness_manifest_digest`` digests the registry's
    :class:`~domain.calculations.registry.schema_surfaces.CalculationCompletenessManifest`
    (the required calculation-closure casilla set: a TAX-SEMANTIC
    completeness declaration), so a compare-and-swap re-check catches the
    registry's declared completeness rules changing between admission and
    commit. The Workspace type's ``field_manifest_digest`` digests a
    structurally unrelated concept -- the S278 field-CLASSIFICATION manifest,
    a deterministic walk over the public registry TYPE denominator for
    display rendering. Reusing one field name for both silently made two
    genuinely different values compare unequal under one name; see the
    edit-contract ADR amendment this type was added by.
    """

    schema_id: _BoundedCode
    schema_fingerprint: ContentDigest
    completeness_manifest_digest: ContentDigest


class ModeloEditBaselineV1(_EditModel):
    """One admitted, independently re-resolved compare-and-swap edit coordinate.

    Contains only safe coordinates and no values. It is a compare-and-swap
    coordinate, not actor authorization or proof that the operation remains
    available.
    """

    edit_contract_version: Literal[1] = 1
    compatibility: ModeloEditCompatibilityTupleV1
    bucket_id: BucketId
    modelo: ModeloCode
    filing_year: Annotated[int, Field(ge=2000, le=2100)]
    period: Period
    work_unit_id: WorkUnitId
    work_catalogue_revision: ContentDigest
    calculation_catalogue_revision: ContentDigest
    current_calculation_revision_id: CalculationRevisionId | None
    law_selected_revision_id: RevisionId
    schema_identity: ModeloEditSchemaIdentityV1
    schema_version: Annotated[int, Field(ge=1)]
    permitted_surface: Annotated[tuple[ModeloEditPermittedSurfaceEntryV1, ...], Field(max_length=_MAX_SURFACE_ENTRIES)]
    permitted_surface_digest: ContentDigest
    mutation_family: ModeloEditMutationFamily
    issued_at: datetime
    expires_at: datetime
    baseline_id: ModeloEditBaselineId

    @field_validator("permitted_surface")
    @classmethod
    def _require_unique_surface_addresses(
        cls, value: tuple[ModeloEditPermittedSurfaceEntryV1, ...]
    ) -> tuple[ModeloEditPermittedSurfaceEntryV1, ...]:
        addresses = [_surface_entry_address(entry) for entry in value]
        if len(set(addresses)) != len(addresses):
            raise ValueError("edit baseline permitted surface must address each casilla or row group once")
        return value

    @model_validator(mode="after")
    def _require_ordered_validity_window(self) -> ModeloEditBaselineV1:
        validate_utc_aware(self.issued_at)
        validate_utc_aware(self.expires_at)
        if self.expires_at <= self.issued_at:
            raise ValueError("edit baseline expiry must be strictly after its issue time")
        return self


class ModeloEditPermittedSurfacePageRequestV1(_EditModel):
    """One continuation request for an application-issued permitted-surface page.

    Echoes the baseline, schema fingerprint, and surface digest; a mismatch on
    read invalidates the whole admission rather than returning a partial page.
    """

    baseline_id: ModeloEditBaselineId
    schema_fingerprint: ContentDigest
    permitted_surface_digest: ContentDigest
    cursor: _BoundedText | None = None


class ModeloEditPermittedSurfacePageV1(_EditModel):
    """One bounded page of a baseline's permitted edit surface."""

    baseline_id: ModeloEditBaselineId
    schema_fingerprint: ContentDigest
    permitted_surface_digest: ContentDigest
    entries: Annotated[tuple[ModeloEditPermittedSurfaceEntryV1, ...], Field(max_length=_MAX_SURFACE_ENTRIES)]
    next_cursor: _BoundedText | None = None


class ModeloEditAdmissionRequestV1(_EditModel):
    """One request to admit an edit baseline for a target and mutation family."""

    edit_contract_version: Literal[1] = 1
    target: ModeloWorkspaceTargetV1
    mutation_family: ModeloEditMutationFamily


class ModeloEditAdmittedV1(_EditModel):
    """A successful admission carrying the exact re-resolved baseline."""

    outcome: Literal["admitted"] = "admitted"
    baseline: ModeloEditBaselineV1


class ModeloEditParsedValueV1(_EditModel):
    """A successfully parsed canonical typed value for one scalar address.

    Never echoes the transient raw lexeme that produced it.
    """

    outcome: Literal["parsed"] = "parsed"
    address: ModeloEditScalarAddressV1
    value: ModeloScalar


class ModeloEditPreflightEvaluatedV1(_EditModel):
    """A completed preflight evaluation carrying every finding.

    A green (empty-error) preflight is review material, not authorization;
    execution independently repeats every concurrency and capability check.
    """

    outcome: Literal["evaluated"] = "evaluated"
    baseline_id: ModeloEditBaselineId
    findings: Annotated[tuple[ModeloEditFindingV1, ...], Field(max_length=_MAX_FINDINGS)]


class ModeloEditVersionRefusalV1(_EditModel):
    """Minimal refusal produced before a rejected request target is parsed."""

    kind: Literal["unsupported_version"] = "unsupported_version"
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1


class ModeloEditCompatibilityRefusalV1(_EditModel):
    """Refusal produced when the requested compatibility tuple is unsupported."""

    kind: Literal["unsupported_compatibility"] = "unsupported_compatibility"
    edit_contract_version: Literal[1] = 1
    requested_axis: _BoundedCode
    responsible_owner: _BoundedCode
    reconsideration_condition: _BoundedText


class ModeloEditStaleBaselineRefusalV1(_EditModel):
    """The compare-and-swap refusal naming every coordinate that disagreed.

    Writes nothing and settles the domain effect as ``NONE``. Never silently
    rebases, merges, or retries against a new baseline.
    """

    kind: Literal["stale_edit_baseline"] = "stale_edit_baseline"
    edit_contract_version: Literal[1] = 1
    baseline_id: ModeloEditBaselineId
    mismatching_coordinates: Annotated[tuple[_BoundedCode, ...], Field(min_length=1, max_length=8)]
    responsible_owner: _BoundedCode
    reconsideration_condition: _BoundedText
    recovery_action: ActionReference | None = None

    @field_validator("mismatching_coordinates")
    @classmethod
    def _require_unique_mismatching_coordinates(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("stale edit baseline refusal coordinates must be unique")
        return value


class ModeloEditDomainRefusalV1(_EditModel):
    """Typed post-admission refusal without a partial projection or raw exception."""

    kind: Literal["domain"] = "domain"
    edit_contract_version: Literal[1] = 1
    code: ModeloEditRefusalCode
    address: ModeloEditAddressV1 | None = None
    facts: Annotated[tuple[_BoundedText, ...], Field(max_length=_MAX_MESSAGE_ARGUMENTS)] = ()
    evidence: _BoundedRefList = ()
    responsible_owner: _BoundedCode
    reconsideration_condition: _BoundedText
    recovery_action: ActionReference | None = None

    @model_validator(mode="after")
    def _reject_untyped_stale_baseline(self) -> ModeloEditDomainRefusalV1:
        if self.code is ModeloEditRefusalCode.STALE_EDIT_BASELINE:
            raise ValueError("a stale edit baseline requires the typed compare-and-swap refusal")
        return self


class ModeloEditUnsupportedIntentReason(StrEnum):
    """One closed reason per intent kind this V1 executor cannot yet reach.

    Named for what capability is missing, never for the internal plan Step
    that will supply it: a plan Step id is process metadata, and this reason
    ships inside a public runtime contract. The Step-to-reason mapping is
    recorded where cross-referencing code to project tracking belongs -- the
    Step Record that implements each reason, never the reverse.
    """

    REMOVE_OVERRIDE_NOT_YET_WIRED = "remove_override_not_yet_wired"
    ADD_ROW_NOT_YET_WIRED = "add_row_not_yet_wired"
    UPDATE_ROW_NOT_YET_WIRED = "update_row_not_yet_wired"
    DELETE_ROW_NOT_YET_WIRED = "delete_row_not_yet_wired"
    MOVE_ROW_NOT_YET_WIRED = "move_row_not_yet_wired"
    RECALCULATE_NOT_YET_WIRED = "recalculate_not_yet_wired"


class ModeloEditUnsupportedIntentRefusalV1(_EditModel):
    """A syntactically admitted intent this V1 executor cannot yet execute.

    Distinct from :class:`ModeloEditDomainRefusalV1`'s ``DISALLOWED_INTENT``:
    that code means the baseline's permitted surface never admitted the
    address. This refusal means the address and intent ARE admitted, but the
    calculation boundary this executor delegates to has no input shape for
    this intent kind yet, so a caller can tell a not-yet-built path from a
    genuinely invalid one.
    """

    kind: Literal["unsupported_intent"] = "unsupported_intent"
    edit_contract_version: Literal[1] = 1
    address: ModeloEditAddressV1 | None = None
    reason: ModeloEditUnsupportedIntentReason
    responsible_owner: _BoundedCode
    reconsideration_condition: _BoundedText


type ModeloEditRefusalV1 = Annotated[
    ModeloEditVersionRefusalV1
    | ModeloEditCompatibilityRefusalV1
    | ModeloEditStaleBaselineRefusalV1
    | ModeloEditDomainRefusalV1
    | ModeloEditUnsupportedIntentRefusalV1,
    Field(discriminator="kind"),
]


class ModeloEditRefusedV1(_EditModel):
    """The result arm that exposes a refusal without calling it a partial success."""

    outcome: Literal["refused"] = "refused"
    refusal: ModeloEditRefusalV1


type ModeloEditAdmissionResultV1 = Annotated[
    ModeloEditAdmittedV1 | ModeloEditRefusedV1,
    Field(discriminator="outcome"),
]

type ModeloEditParseResultV1 = Annotated[
    ModeloEditParsedValueV1 | ModeloEditRefusedV1,
    Field(discriminator="outcome"),
]

type ModeloEditPreflightResultV1 = Annotated[
    ModeloEditPreflightEvaluatedV1 | ModeloEditRefusedV1,
    Field(discriminator="outcome"),
]


class ModeloEditFindingV1(_EditModel):
    """One preflight finding at a semantic address or global scope."""

    code: _BoundedCode
    severity: ModeloEditFindingSeverity
    address: ModeloEditAddressV1 | None = None
    message_arguments: Annotated[tuple[_BoundedText, ...], Field(max_length=_MAX_MESSAGE_ARGUMENTS)] = ()
    evidence: _BoundedRefList = ()


ModeloEditPreflightEvaluatedV1.model_rebuild()


class ModeloEditParseRequestV1(_EditModel):
    """One parse request for a single semantic address and transient raw lexeme.

    Carries the complete admitted baseline rather than an opaque id: the
    contract mints no server-side baseline store, so the frontend retains the
    admission result in memory and resupplies it on every subsequent call, the
    same posture :class:`ModeloEditSubmissionV1` takes for preflight and apply.
    The raw lexeme is never echoed by any result derived from this request.
    """

    edit_contract_version: Literal[1] = 1
    baseline: ModeloEditBaselineV1
    address: ModeloEditScalarAddressV1
    input_kind: InputKind
    locale: OutputLanguage
    raw_lexeme: _BoundedText


class ModeloScalarEditIntentV1(_EditModel):
    """One scalar edit intent; zero, false, and empty text remain distinct states."""

    address: ModeloEditScalarAddressV1
    kind: ModeloEditScalarIntentKind
    value: ModeloScalar | None = None

    @model_validator(mode="after")
    def _require_value_only_for_set(self) -> ModeloScalarEditIntentV1:
        if self.kind is ModeloEditScalarIntentKind.SET_TYPED_VALUE and self.value is None:
            raise ValueError("SET_TYPED_VALUE scalar intent requires a typed value")
        if self.kind is not ModeloEditScalarIntentKind.SET_TYPED_VALUE and self.value is not None:
            raise ValueError("only SET_TYPED_VALUE may carry a scalar intent value")
        return self


class ModeloRowEditIntentV1(_EditModel):
    """One repeatable-row edit intent addressed by canonical or correlation identity."""

    address: ModeloEditRowAddressV1
    kind: ModeloEditRowIntentKind
    row: Annotated[tuple[ModeloScalarEditIntentV1, ...], Field(max_length=_MAX_ROW_VALUES)] | None = None
    move_to_index: Annotated[int, Field(ge=1)] | None = None

    @model_validator(mode="after")
    def _require_shape_matches_kind(self) -> ModeloRowEditIntentV1:
        is_new = isinstance(self.address, ModeloEditNewRowCorrelationV1)
        if self.kind is ModeloEditRowIntentKind.ADD_ROW:
            if not is_new or not self.row:
                raise ValueError("ADD_ROW requires a new-row correlation address and a complete typed row")
            if self.move_to_index is not None:
                raise ValueError("ADD_ROW may not carry a move_to_index")
        elif self.kind is ModeloEditRowIntentKind.UPDATE_ROW:
            if is_new or not self.row:
                raise ValueError("UPDATE_ROW requires the canonical existing-row address and a complete typed row")
            if self.move_to_index is not None:
                raise ValueError("UPDATE_ROW may not carry a move_to_index")
        elif self.kind is ModeloEditRowIntentKind.DELETE_ROW:
            if is_new or self.row is not None or self.move_to_index is not None:
                raise ValueError("DELETE_ROW requires only the canonical existing-row address")
        elif self.kind is ModeloEditRowIntentKind.MOVE_ROW:
            if is_new or self.row is not None or self.move_to_index is None:
                raise ValueError("MOVE_ROW requires the canonical existing-row address and a move_to_index")
        return self


def _intent_address_key(address: ModeloEditScalarAddressV1 | ModeloEditRowAddressV1) -> tuple[str, str]:
    if isinstance(address, ModeloEditScalarAddressV1):
        return ("scalar", address.casilla_id)
    if isinstance(address, ModeloEditExistingRowAddressV1):
        return ("existing_row", f"{address.binding_id}:{address.row_index}")
    return ("new_row", f"{address.binding_id}:{address.client_correlation_id}")


class ModeloEditSubmissionV1(_EditModel):
    """One baseline plus its complete normalized ordered intent set.

    Carries no frontend state. Duplicate or contradictory address intents
    refuse before execution.
    """

    edit_contract_version: Literal[1] = 1
    baseline: ModeloEditBaselineV1
    mutation_family: ModeloEditMutationFamily
    scalar_intents: Annotated[tuple[ModeloScalarEditIntentV1, ...], Field(max_length=_MAX_INTENTS)] = ()
    row_intents: Annotated[tuple[ModeloRowEditIntentV1, ...], Field(max_length=_MAX_INTENTS)] = ()

    @model_validator(mode="after")
    def _require_consistent_submission(self) -> ModeloEditSubmissionV1:
        if self.mutation_family is not self.baseline.mutation_family:
            raise ValueError("edit submission mutation family must match its baseline")
        keys = [_intent_address_key(intent.address) for intent in self.scalar_intents]
        keys.extend(_intent_address_key(intent.address) for intent in self.row_intents)
        if len(set(keys)) != len(keys):
            raise ValueError("edit submission must not address the same casilla or row more than once")
        return self


class ModeloEditPreflightRequestV1(_EditModel):
    """One preflight request over a baseline and its complete ordered intent set."""

    edit_contract_version: Literal[1] = 1
    submission: ModeloEditSubmissionV1


class ModeloEditApplyRequestV1(_EditModel):
    """The guarded apply request only the enrolled operation executor may invoke."""

    edit_contract_version: Literal[1] = 1
    operation_id: OperationId
    submission: ModeloEditSubmissionV1


class ModeloMutationCapabilityRequestV1(_EditModel):
    """One request for the closed mutation-capability projection over a target."""

    edit_contract_version: Literal[1] = 1
    target: ModeloWorkspaceTargetV1


class ModeloMutationCapabilityRowV1(_EditModel):
    """One closed capability row for a mutation candidate; composed, never inferred."""

    mutation_id: _BoundedCode
    owning_producer: _BoundedCode
    revision_id: RevisionId
    disposition: ModeloWorkspaceCapabilityDisposition
    evidence: _BoundedRefList = ()
    reconsideration_condition: _BoundedText | None = None
    recovery_action: ActionReference | None = None
    operation_definition_id: OperationDefinitionId | None = None

    @model_validator(mode="after")
    def _require_definition_when_available(self) -> ModeloMutationCapabilityRowV1:
        if self.disposition is ModeloWorkspaceCapabilityDisposition.AVAILABLE and self.operation_definition_id is None:
            raise ValueError("an AVAILABLE mutation capability row requires its registered operation definition")
        return self


class ModeloMutationCapabilityProjectionV1(_EditModel):
    """The complete closed capability denominator for one edit target."""

    edit_contract_version: Literal[1] = 1
    rows: Annotated[tuple[ModeloMutationCapabilityRowV1, ...], Field(max_length=_MAX_CAPABILITY_ROWS)]

    @field_validator("rows")
    @classmethod
    def _require_unique_mutation_ids(
        cls, value: tuple[ModeloMutationCapabilityRowV1, ...]
    ) -> tuple[ModeloMutationCapabilityRowV1, ...]:
        ids = [row.mutation_id for row in value]
        if len(set(ids)) != len(ids):
            raise ValueError("mutation capability projection rows must have unique mutation ids")
        return value


class ModeloEditMutationResultReceiptV1(_EditModel):
    """The safe domain proof co-committed with one guarded compare-and-swap edit.

    Carries no financial value, raw input, row content, or input digest. A
    matching receipt proves ``UPDATED``; a proven failed compare-and-swap
    proves ``NONE``.

    ``bucket_event_id`` is ``None`` on a duplicate-result confirmation: an
    identical content-addressed revision already exists, so this commit
    advances or confirms only the work-unit pointer and emits no fresh
    ``MODELO_CALCULATION_CREATED`` event to reference. It is always present
    when the commit created the revision.
    """

    receipt_id: ModeloEditMutationResultReceiptId
    operation_id: OperationId
    mutation_family: ModeloEditMutationFamily
    baseline_id: ModeloEditBaselineId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    bucket_event_id: BucketEventId | None
    effect: Literal[ModeloEditExecutionEffect.UPDATED] = ModeloEditExecutionEffect.UPDATED
    committed_at: datetime
    result_destination: OperationReference

    @model_validator(mode="after")
    def _require_utc_commit_time(self) -> ModeloEditMutationResultReceiptV1:
        validate_utc_aware(self.committed_at)
        return self


class ModeloEditExecutionUpdatedV1(_EditModel):
    """The successful compare-and-swap arm carrying the authoritative receipt."""

    effect: Literal[ModeloEditExecutionEffect.UPDATED] = ModeloEditExecutionEffect.UPDATED
    receipt: ModeloEditMutationResultReceiptV1


class ModeloEditExecutionNoEffectV1(_EditModel):
    """The failed compare-and-swap arm; writes nothing and names the refusal."""

    effect: Literal[ModeloEditExecutionEffect.NONE] = ModeloEditExecutionEffect.NONE
    refusal: ModeloEditRefusalV1


type ModeloEditExecutionResultV1 = Annotated[
    ModeloEditExecutionUpdatedV1 | ModeloEditExecutionNoEffectV1,
    Field(discriminator="effect"),
]


__all__ = [
    "ModeloEditAddressV1",
    "ModeloEditAdmissionRequestV1",
    "ModeloEditAdmissionResultV1",
    "ModeloEditAdmittedV1",
    "ModeloEditApplyRequestV1",
    "ModeloEditBaselineV1",
    "ModeloEditCasillaDataType",
    "ModeloEditCompatibilityRefusalV1",
    "ModeloEditCompatibilityTupleV1",
    "ModeloEditDomainRefusalV1",
    "ModeloEditExecutionEffect",
    "ModeloEditExecutionNoEffectV1",
    "ModeloEditExecutionResultV1",
    "ModeloEditExecutionUpdatedV1",
    "ModeloEditExistingRowAddressV1",
    "ModeloEditFindingSeverity",
    "ModeloEditFindingV1",
    "ModeloEditMutationFamily",
    "ModeloEditMutationResultReceiptV1",
    "ModeloEditNewRowCorrelationV1",
    "ModeloEditNonWritableReason",
    "ModeloEditNonWritableRowGroupSurfaceEntryV1",
    "ModeloEditNonWritableScalarSurfaceEntryV1",
    "ModeloEditParseRequestV1",
    "ModeloEditParseResultV1",
    "ModeloEditParsedValueV1",
    "ModeloEditPermittedSurfaceEntryV1",
    "ModeloEditPermittedSurfacePageRequestV1",
    "ModeloEditPermittedSurfacePageV1",
    "ModeloEditPreflightEvaluatedV1",
    "ModeloEditPreflightRequestV1",
    "ModeloEditPreflightResultV1",
    "ModeloEditRefusalCode",
    "ModeloEditRefusalV1",
    "ModeloEditRefusedV1",
    "ModeloEditRowAddressV1",
    "ModeloEditRowIntentKind",
    "ModeloEditScalarAddressV1",
    "ModeloEditScalarIntentKind",
    "ModeloEditSchemaIdentityV1",
    "ModeloEditStaleBaselineRefusalV1",
    "ModeloEditSubmissionV1",
    "ModeloEditUnsupportedIntentReason",
    "ModeloEditUnsupportedIntentRefusalV1",
    "ModeloEditVersionHeader",
    "ModeloEditVersionRefusalV1",
    "ModeloEditWritableRowGroupSurfaceEntryV1",
    "ModeloEditWritableScalarSurfaceEntryV1",
    "ModeloMutationCapabilityProjectionV1",
    "ModeloMutationCapabilityRequestV1",
    "ModeloMutationCapabilityRowV1",
    "ModeloRowEditIntentV1",
    "ModeloScalarEditIntentV1",
    "read_modelo_edit_version_header",
]
