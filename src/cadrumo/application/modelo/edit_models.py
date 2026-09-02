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

from pydantic import Field, field_validator, model_validator

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.identity import (
    BucketId,
    CalculationRevisionId,
    ContentDigest,
    ModeloEditBaselineId,
    WorkUnitId,
)
from ...core.period import Period
from ...core.time.utc import validate_utc_aware
from ...domain.calculations.registry.ids import BindingId, RevisionId
from ...domain.calculations.registry.schema_base import CasillaDataTypeField
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.filing.schema import ModeloScalar
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.row_models import ModeloDetailRow
from ..operations.models import OperationDefinitionId, OperationId
from ..operator_actions.models import ActionReference
from .edit_contract import (
    EditModel,
    ModeloEditCompatibilityTupleV1,
    ModeloEditExecutionEffect,
    ModeloEditMutationFamily,
    ModeloEditMutationResultReceiptV1,
)
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


class ModeloEditScalarIntentKind(StrEnum):
    """The two distinct scalar edit intents; address absence means UNCHANGED.

    ``REMOVE_OVERRIDE`` is deliberately NOT a member: it addresses the
    ``CalculationRevision.binding_overrides`` store, which is keyed by
    ``BindingId``, never ``CasillaId`` -- no casilla-addressed scalar intent
    can reach it. See :class:`ModeloEditBindingIntentKind`.
    """

    SET_TYPED_VALUE = "set_typed_value"
    CLEAR_DECLARED_VALUE = "clear_declared_value"


class ModeloEditRowIntentKind(StrEnum):
    """The closed repeatable-row edit intents; MOVE_ROW requires reorderable groups."""

    ADD_ROW = "add_row"
    UPDATE_ROW = "update_row"
    DELETE_ROW = "delete_row"
    MOVE_ROW = "move_row"


class ModeloEditDetailRowIntentKind(StrEnum):
    """The closed ``ModeloDetailRow`` edit intents, addressed by natural key.

    ``MOVE_ROW`` is deliberately NOT a member. A row's
    physical record occurrence number in the exported fichero is NOT a
    function of caller-supplied order at all: every row-producer resolver in
    :mod:`domain.calculations.registry.detail_record_bindings`
    (``resolve_atribucion_binding_row_values``, ``_build_related_party_rows``,
    ``_build_foreign_asset_rows``, and their siblings) sorts its rows by a
    content key -- ``(country_code, tax_id)`` or equivalent -- BEFORE
    ``enumerate(..., 1)`` assigns row indices, so two calls supplying the
    same rows in different orders render byte-identical ficheros (proven in
    :func:`~cadrumo.application.filing.tests.test_m184_socio_repeat_wiring.
    test_occurrence_order_is_a_pure_function_of_content_not_of_supply_order`).
    The AEAT diseno de registro for these record families identifies each
    repeated record by its declared content (member/counterparty NIF, asset
    identifier, clave/subclave) rather than by a required sequence -- there
    is no "declared order" for AEAT to read or for a reorder to change.
    Consistently, the calculation revision's content address is also
    order-BLIND (``_canonical_detail_rows`` sorts by ``(row_type,
    nif-like)`` specifically so "operators can supply rows in any order"). A
    pure reorder therefore computes the SAME revision id AND renders the
    SAME fichero bytes as the existing revision, so the guarded
    compare-and-swap persistence layer's duplicate-result branch would
    silently absorb it and return the existing revision -- the requested
    reorder would never actually persist, and even if it did nothing
    observable would change. Building MOVE_ROW against the current
    content-address shape would ship a control with no addressable effect.
    """

    ADD_ROW = "add_row"
    UPDATE_ROW = "update_row"
    DELETE_ROW = "delete_row"


class ModeloEditBindingIntentKind(StrEnum):
    """The two distinct binding-override edit intents; address absence means UNCHANGED.

    Mirrors ``SET_TYPED_VALUE``/``CLEAR_DECLARED_VALUE`` in shape, but these
    apply to the ``BindingId``-keyed ``binding_overrides`` store rather than a
    casilla's declared value -- the operator-facing ``--binding KEY=VALUE``
    CLI override and its withdrawal.
    """

    SET_OVERRIDE_VALUE = "set_override_value"
    REMOVE_OVERRIDE = "remove_override"


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


class ModeloEditVersionHeader(EditModel):
    """Minimal pre-dispatch shape read before target or financial input parsing."""

    edit_contract_version: Annotated[int, Field(ge=1)]


class ModeloEditScalarAddressV1(EditModel):
    """A canonical semantic scalar address, keyed by the registry casilla identity."""

    kind: Literal["scalar"] = "scalar"
    casilla_id: CasillaId


class ModeloEditBindingAddressV1(EditModel):
    """A canonical binding-override address, keyed by the registry binding identity.

    Distinct from :class:`ModeloEditScalarAddressV1`: a binding override
    addresses ``CalculationRevision.binding_overrides``, which is keyed by
    ``BindingId``, never ``CasillaId`` -- most overridable bindings (a
    fichero-BOE record-field ``manual_input`` binding, most notably) have no
    casilla at all to address through.
    """

    kind: Literal["binding"] = "binding"
    binding_id: BindingId


class ModeloEditExistingRowAddressV1(EditModel):
    """The application-issued canonical coordinate of one persisted repeated row."""

    kind: Literal["existing_row"] = "existing_row"
    binding_id: BindingId
    row_index: Annotated[int, Field(ge=1)]


class ModeloEditNewRowCorrelationV1(EditModel):
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


class ModeloEditDetailRowAddressV1(EditModel):
    """The natural-key address of one ``ModeloDetailRow``, never position or a minted id.

    ``detail_row_kind`` is the discriminated ``ModeloDetailRow.row_type`` value
    (e.g. ``"miembro"``, ``"contraparte"``). ``natural_key`` is the row's own
    already-declared identity field, joined with ``|`` for a compound key
    (M349 operador/rectificación key on ``nif_comunitario|clave_operacion``,
    since one counterparty can carry more than one operation type) -- never a
    minted or positional identity. This mirrors the codebase's established
    whole-set-replacement convention for repeating declared rows
    (``RetencionObservationRepository.replace_observations``): rows are
    addressed by the business key they already carry, and an absent key is
    sufficient to express removal with no separate "explicitly deleted" axis,
    because a row (unlike a scalar) has no ambiguous middle state between
    "declared" and "absent".
    """

    kind: Literal["detail_row"] = "detail_row"
    detail_row_kind: _BoundedCode
    natural_key: Annotated[str, Field(min_length=1, max_length=256)]


type ModeloEditAddressV1 = Annotated[
    ModeloEditScalarAddressV1
    | ModeloEditBindingAddressV1
    | ModeloEditExistingRowAddressV1
    | ModeloEditNewRowCorrelationV1
    | ModeloEditDetailRowAddressV1,
    Field(discriminator="kind"),
]


#: The registry's casilla data-type vocabulary, reached at its definition rather
#: than mirrored. Metadata only, not a value: the parse service selects its grammar
#: from this axis, and the permitted surface carries no casilla value. The mirror this
#: replaced was a hand-maintained copy of the same nineteen members, so a member added
#: to the registry never reached it.
ModeloEditCasillaDataType = CasillaDataTypeField


class ModeloEditWritableScalarSurfaceEntryV1(EditModel):
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


class ModeloEditNonWritableScalarSurfaceEntryV1(EditModel):
    """One scalar address the baseline exposes as read-only, with its reason."""

    kind: Literal["non_writable_scalar"] = "non_writable_scalar"
    casilla_id: CasillaId
    reason: ModeloEditNonWritableReason


class ModeloEditWritableRowGroupSurfaceEntryV1(EditModel):
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


class ModeloEditNonWritableRowGroupSurfaceEntryV1(EditModel):
    """One repeated-row group the baseline exposes as read-only, with its reason."""

    kind: Literal["non_writable_row_group"] = "non_writable_row_group"
    binding_id: BindingId
    reason: ModeloEditNonWritableReason


class ModeloEditWritableBindingOverrideSurfaceEntryV1(EditModel):
    """One binding the baseline admits the operator-facing ``--binding`` override for.

    Distinct from a scalar or row-group entry: it addresses
    ``CalculationRevision.binding_overrides`` (``BindingId``-keyed), never a
    casilla, because most eligible bindings -- a fichero-BOE record-field
    ``manual_input`` binding, most notably -- have no casilla to address
    through at all.
    """

    kind: Literal["writable_binding_override"] = "writable_binding_override"
    binding_id: BindingId
    allowed_intents: Annotated[tuple[ModeloEditBindingIntentKind, ...], Field(min_length=1, max_length=2)]

    @field_validator("allowed_intents")
    @classmethod
    def _require_unique_allowed_binding_intents(
        cls, value: tuple[ModeloEditBindingIntentKind, ...]
    ) -> tuple[ModeloEditBindingIntentKind, ...]:
        if len(set(value)) != len(value):
            raise ValueError("writable binding-override surface entry must declare each allowed intent at most once")
        return value


class ModeloEditNonWritableBindingOverrideSurfaceEntryV1(EditModel):
    """One binding the baseline exposes as override-locked, with its reason."""

    kind: Literal["non_writable_binding_override"] = "non_writable_binding_override"
    binding_id: BindingId
    reason: ModeloEditNonWritableReason


class ModeloEditWritableDetailRowSurfaceEntryV1(EditModel):
    """One ``ModeloDetailRow`` kind the baseline admits for writing, natural-key addressed.

    Distinct from the (permanently empty) ``BindingId``-keyed row-group axis:
    this addresses the genuine repeatable, taxpayer-typed ``ModeloDetailRow``
    mechanism, admitted per the same real, enforced per-modelo eligibility
    table that
    :func:`~._calculation_modelo_adjustments.require_detail_rows_declared_for_their_owning_modelo`
    refuses a mismatched row against.
    """

    kind: Literal["writable_detail_row"] = "writable_detail_row"
    detail_row_kind: _BoundedCode
    allowed_intents: Annotated[tuple[ModeloEditDetailRowIntentKind, ...], Field(min_length=1, max_length=3)]

    @field_validator("allowed_intents")
    @classmethod
    def _require_unique_allowed_detail_row_intents(
        cls, value: tuple[ModeloEditDetailRowIntentKind, ...]
    ) -> tuple[ModeloEditDetailRowIntentKind, ...]:
        if len(set(value)) != len(value):
            raise ValueError("writable detail-row surface entry must declare each allowed intent at most once")
        return value


type ModeloEditPermittedSurfaceEntryV1 = Annotated[
    ModeloEditWritableScalarSurfaceEntryV1
    | ModeloEditNonWritableScalarSurfaceEntryV1
    | ModeloEditWritableRowGroupSurfaceEntryV1
    | ModeloEditNonWritableRowGroupSurfaceEntryV1
    | ModeloEditWritableBindingOverrideSurfaceEntryV1
    | ModeloEditNonWritableBindingOverrideSurfaceEntryV1
    | ModeloEditWritableDetailRowSurfaceEntryV1,
    Field(discriminator="kind"),
]


def _surface_entry_address(entry: ModeloEditPermittedSurfaceEntryV1) -> tuple[str, str]:
    if isinstance(entry, (ModeloEditWritableScalarSurfaceEntryV1, ModeloEditNonWritableScalarSurfaceEntryV1)):
        return ("scalar", entry.casilla_id)
    if isinstance(
        entry, (ModeloEditWritableBindingOverrideSurfaceEntryV1, ModeloEditNonWritableBindingOverrideSurfaceEntryV1)
    ):
        return ("binding_override", entry.binding_id)
    if isinstance(entry, ModeloEditWritableDetailRowSurfaceEntryV1):
        return ("detail_row", entry.detail_row_kind)
    return ("row_group", entry.binding_id)


class ModeloEditSchemaIdentityV1(EditModel):
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
    structurally unrelated concept -- the field-CLASSIFICATION manifest,
    a deterministic walk over the public registry TYPE denominator for
    display rendering. Reusing one field name for both silently made two
    genuinely different values compare unequal under one name; see the
    edit-contract ADR amendment this type was added by.
    """

    schema_id: _BoundedCode
    schema_fingerprint: ContentDigest
    completeness_manifest_digest: ContentDigest


class ModeloEditBaselineV1(EditModel):
    """One admitted, independently re-resolved compare-and-swap edit coordinate.

    Contains only safe coordinates and no values. It is a compare-and-swap
    coordinate, not actor authorization or proof that the operation remains
    available.

    NEVER COMPARED BY RECORD EQUALITY. This carries its own admission identity
    and lifetime -- ``issued_at``, ``expires_at`` and ``baseline_id`` -- so two
    admissions of an UNCHANGED tree are never equal, and ``==`` between two of
    these can only ever report "different". Staleness is asked of
    :func:`~application.modelo._edit_services.reconfirm_modelo_edit_baseline`,
    which judges the coordinate axes the guarded commit point judges.

    The distinction matters because
    :class:`~application.modelo.workspace_models.ModeloWorkspaceBaselineV1`
    shares the name and has the OPPOSITE contract: it is content-derived,
    carries no timestamp, and is compared by equality on purpose. An editor
    session once carried that pattern here, and its stale signal was
    permanently on -- worse than absent, because a warning that always fires
    teaches the operator to dismiss it.
    """

    edit_contract_version: Literal[1] = 1
    compatibility: ModeloEditCompatibilityTupleV1
    bucket_id: BucketId
    modelo: ModeloCode
    filing_year: FilingYear
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


class ModeloEditPermittedSurfacePageRequestV1(EditModel):
    """One continuation request for an application-issued permitted-surface page.

    Echoes the baseline, schema fingerprint, and surface digest; a mismatch on
    read invalidates the whole admission rather than returning a partial page.
    """

    baseline_id: ModeloEditBaselineId
    schema_fingerprint: ContentDigest
    permitted_surface_digest: ContentDigest
    cursor: _BoundedText | None = None


class ModeloEditPermittedSurfacePageV1(EditModel):
    """One bounded page of a baseline's permitted edit surface."""

    baseline_id: ModeloEditBaselineId
    schema_fingerprint: ContentDigest
    permitted_surface_digest: ContentDigest
    entries: Annotated[tuple[ModeloEditPermittedSurfaceEntryV1, ...], Field(max_length=_MAX_SURFACE_ENTRIES)]
    next_cursor: _BoundedText | None = None


class ModeloEditAdmissionRequestV1(EditModel):
    """One request to admit an edit baseline for a target and mutation family."""

    edit_contract_version: Literal[1] = 1
    target: ModeloWorkspaceTargetV1
    mutation_family: ModeloEditMutationFamily


class ModeloEditAdmittedV1(EditModel):
    """A successful admission carrying the exact re-resolved baseline."""

    outcome: Literal["admitted"] = "admitted"
    baseline: ModeloEditBaselineV1


class ModeloEditParsedValueV1(EditModel):
    """A successfully parsed canonical typed value for one scalar address.

    Never echoes the transient raw lexeme that produced it.
    """

    outcome: Literal["parsed"] = "parsed"
    address: ModeloEditScalarAddressV1
    value: ModeloScalar


class ModeloEditPreflightEvaluatedV1(EditModel):
    """A completed preflight evaluation carrying every finding.

    A green (empty-error) preflight is review material, not authorization;
    execution independently repeats every concurrency and capability check.
    """

    outcome: Literal["evaluated"] = "evaluated"
    baseline_id: ModeloEditBaselineId
    findings: Annotated[tuple[ModeloEditFindingV1, ...], Field(max_length=_MAX_FINDINGS)]


class ModeloEditVersionRefusalV1(EditModel):
    """Minimal refusal produced before a rejected request target is parsed."""

    kind: Literal["unsupported_version"] = "unsupported_version"
    requested_version: Annotated[int, Field(ge=1)] | None
    supported_version: Literal[1] = 1


class ModeloEditCompatibilityRefusalV1(EditModel):
    """Refusal produced when the requested compatibility tuple is unsupported."""

    kind: Literal["unsupported_compatibility"] = "unsupported_compatibility"
    edit_contract_version: Literal[1] = 1
    requested_axis: _BoundedCode
    responsible_owner: _BoundedCode
    reconsideration_condition: _BoundedText


class ModeloEditStaleBaselineRefusalV1(EditModel):
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


class ModeloEditDomainRefusalV1(EditModel):
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

    SET_OVERRIDE_VALUE_NOT_YET_WIRED = "set_override_value_not_yet_wired"
    REMOVE_OVERRIDE_NOT_YET_WIRED = "remove_override_not_yet_wired"
    ADD_ROW_NOT_YET_WIRED = "add_row_not_yet_wired"
    UPDATE_ROW_NOT_YET_WIRED = "update_row_not_yet_wired"
    DELETE_ROW_NOT_YET_WIRED = "delete_row_not_yet_wired"
    MOVE_ROW_NOT_YET_WIRED = "move_row_not_yet_wired"
    RECALCULATE_NOT_YET_WIRED = "recalculate_not_yet_wired"


class ModeloEditUnsupportedIntentRefusalV1(EditModel):
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


class ModeloEditRefusedV1(EditModel):
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


class ModeloEditFindingV1(EditModel):
    """One preflight finding at a semantic address or global scope."""

    code: _BoundedCode
    severity: ModeloEditFindingSeverity
    address: ModeloEditAddressV1 | None = None
    message_arguments: Annotated[tuple[_BoundedText, ...], Field(max_length=_MAX_MESSAGE_ARGUMENTS)] = ()
    evidence: _BoundedRefList = ()


ModeloEditPreflightEvaluatedV1.model_rebuild()


class ModeloEditParseRequestV1(EditModel):
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


class ModeloScalarEditIntentV1(EditModel):
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


class ModeloBindingEditIntentV1(EditModel):
    """One binding-override edit intent; zero and false remain distinct from UNCHANGED.

    Addresses ``CalculationRevision.binding_overrides`` directly by
    ``BindingId``. Never carries a value for ``REMOVE_OVERRIDE``: withdrawing
    an override is expressed by absence of a value, not a typed zero.
    """

    address: ModeloEditBindingAddressV1
    kind: ModeloEditBindingIntentKind
    value: ModeloScalar | None = None

    @model_validator(mode="after")
    def _require_value_only_for_set_override(self) -> ModeloBindingEditIntentV1:
        if self.kind is ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE and self.value is None:
            raise ValueError("SET_OVERRIDE_VALUE binding intent requires a typed value")
        if self.kind is not ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE and self.value is not None:
            raise ValueError("only SET_OVERRIDE_VALUE may carry a binding intent value")
        return self


class ModeloRowEditIntentV1(EditModel):
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


class ModeloDetailRowEditIntentV1(EditModel):
    """One ``ModeloDetailRow`` edit intent, addressed by the row's own natural key.

    ADD_ROW and UPDATE_ROW submit a complete typed ``ModeloDetailRow``.
    DELETE_ROW names only the natural key: removal is expressed by the row's
    absence from the executor's reconstructed set, with no separate
    "explicitly deleted" axis, per :class:`ModeloEditDetailRowAddressV1`.
    No MOVE intent exists -- see :class:`ModeloEditDetailRowIntentKind`.
    """

    address: ModeloEditDetailRowAddressV1
    kind: ModeloEditDetailRowIntentKind
    row: ModeloDetailRow | None = None

    @model_validator(mode="after")
    def _require_shape_matches_kind(self) -> ModeloDetailRowEditIntentV1:
        if self.kind in (ModeloEditDetailRowIntentKind.ADD_ROW, ModeloEditDetailRowIntentKind.UPDATE_ROW):
            if self.row is None:
                raise ValueError("ADD_ROW/UPDATE_ROW detail-row intent requires a complete typed row")
        elif self.kind is ModeloEditDetailRowIntentKind.DELETE_ROW and self.row is not None:
            raise ValueError("DELETE_ROW detail-row intent requires only the natural-key address")
        return self


def _intent_address_key(
    address: ModeloEditScalarAddressV1
    | ModeloEditBindingAddressV1
    | ModeloEditRowAddressV1
    | ModeloEditDetailRowAddressV1,
) -> tuple[str, str]:
    if isinstance(address, ModeloEditScalarAddressV1):
        return ("scalar", address.casilla_id)
    if isinstance(address, ModeloEditBindingAddressV1):
        return ("binding_override", address.binding_id)
    if isinstance(address, ModeloEditDetailRowAddressV1):
        return ("detail_row", f"{address.detail_row_kind}:{address.natural_key}")
    if isinstance(address, ModeloEditExistingRowAddressV1):
        return ("existing_row", f"{address.binding_id}:{address.row_index}")
    return ("new_row", f"{address.binding_id}:{address.client_correlation_id}")


class ModeloEditSubmissionV1(EditModel):
    """One baseline plus its complete normalized ordered intent set.

    Carries no frontend state. Duplicate or contradictory address intents
    refuse before execution.
    """

    edit_contract_version: Literal[1] = 1
    baseline: ModeloEditBaselineV1
    mutation_family: ModeloEditMutationFamily
    scalar_intents: Annotated[tuple[ModeloScalarEditIntentV1, ...], Field(max_length=_MAX_INTENTS)] = ()
    binding_intents: Annotated[tuple[ModeloBindingEditIntentV1, ...], Field(max_length=_MAX_INTENTS)] = ()
    row_intents: Annotated[tuple[ModeloRowEditIntentV1, ...], Field(max_length=_MAX_INTENTS)] = ()
    detail_row_intents: Annotated[tuple[ModeloDetailRowEditIntentV1, ...], Field(max_length=_MAX_INTENTS)] = ()

    @model_validator(mode="after")
    def _require_consistent_submission(self) -> ModeloEditSubmissionV1:
        if self.mutation_family is not self.baseline.mutation_family:
            raise ValueError("edit submission mutation family must match its baseline")
        keys = [_intent_address_key(intent.address) for intent in self.scalar_intents]
        keys.extend(_intent_address_key(intent.address) for intent in self.binding_intents)
        keys.extend(_intent_address_key(intent.address) for intent in self.row_intents)
        keys.extend(_intent_address_key(intent.address) for intent in self.detail_row_intents)
        if len(set(keys)) != len(keys):
            raise ValueError(
                "edit submission must not address the same casilla, binding, row, or detail row more than once"
            )
        return self


class ModeloEditPreflightRequestV1(EditModel):
    """One preflight request over a baseline and its complete ordered intent set."""

    edit_contract_version: Literal[1] = 1
    submission: ModeloEditSubmissionV1


class ModeloEditApplyRequestV1(EditModel):
    """The guarded apply request only the enrolled operation executor may invoke."""

    edit_contract_version: Literal[1] = 1
    operation_id: OperationId
    submission: ModeloEditSubmissionV1


class ModeloMutationCapabilityRequestV1(EditModel):
    """One request for the closed mutation-capability projection over a target."""

    edit_contract_version: Literal[1] = 1
    target: ModeloWorkspaceTargetV1


class ModeloMutationCapabilityRowV1(EditModel):
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


class ModeloMutationCapabilityProjectionV1(EditModel):
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


class ModeloEditExecutionUpdatedV1(EditModel):
    """The successful compare-and-swap arm carrying the authoritative receipt."""

    effect: Literal[ModeloEditExecutionEffect.UPDATED] = ModeloEditExecutionEffect.UPDATED
    receipt: ModeloEditMutationResultReceiptV1


class ModeloEditExecutionNoEffectV1(EditModel):
    """The failed compare-and-swap arm; writes nothing and names the refusal."""

    effect: Literal[ModeloEditExecutionEffect.NONE] = ModeloEditExecutionEffect.NONE
    refusal: ModeloEditRefusalV1


type ModeloEditExecutionResultV1 = Annotated[
    ModeloEditExecutionUpdatedV1 | ModeloEditExecutionNoEffectV1,
    Field(discriminator="effect"),
]


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


__all__ = [
    "ModeloBindingEditIntentV1",
    "ModeloDetailRowEditIntentV1",
    "ModeloEditAddressV1",
    "ModeloEditAdmissionRequestV1",
    "ModeloEditAdmissionResultV1",
    "ModeloEditAdmittedV1",
    "ModeloEditApplyRequestV1",
    "ModeloEditBaselineV1",
    "ModeloEditBindingAddressV1",
    "ModeloEditBindingIntentKind",
    "ModeloEditCasillaDataType",
    "ModeloEditCompatibilityRefusalV1",
    "ModeloEditCompatibilityTupleV1",
    "ModeloEditDetailRowAddressV1",
    "ModeloEditDetailRowIntentKind",
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
    "ModeloEditNonWritableBindingOverrideSurfaceEntryV1",
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
    "ModeloEditWritableBindingOverrideSurfaceEntryV1",
    "ModeloEditWritableDetailRowSurfaceEntryV1",
    "ModeloEditWritableRowGroupSurfaceEntryV1",
    "ModeloEditWritableScalarSurfaceEntryV1",
    "ModeloMutationCapabilityProjectionV1",
    "ModeloMutationCapabilityRequestV1",
    "ModeloMutationCapabilityRowV1",
    "ModeloRowEditIntentV1",
    "ModeloScalarEditIntentV1",
    "read_modelo_edit_version_header",
]
