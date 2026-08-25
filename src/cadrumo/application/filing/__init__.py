"""Public application facade for registry-backed filing drafts.

This package builds, reviews, approves, exports, verifies, imports, and
summarises local filing artefacts. All draft creation and validation consume
a :class:`RegistrySnapshot` to resolve the
active :class:`ModeloRevision`, its casilla
schema, relation inputs, and formula graph.

Major entry points:

* :func:`build_draft` constructs a validated
  :class:`ModeloDraft` from registry-backed inputs.
* :func:`approve_draft`, :func:`unapprove_draft`, and
  :func:`refresh_review_status` manage local review state and approval basis.
* :func:`export_draft` writes a local fichero-BOE artefact, and
  :func:`verify_export` re-reads that file through the registry export parser.
* :func:`import_filing_from_justificante` reconstructs a draft-level local
  receipt baseline and companion
  :class:`ModeloPresentado` audit record from a
  justificante PDF without treating the receipt as a casilla-value authority.
* :func:`build_complementaria`, :func:`list_amendments`, and
  :func:`load_amendment` build and read governed
  :class:`ModeloComplementaria` and
  :class:`ModeloSustitutiva` amendment records.
* :class:`ModeloHistoryRepository` persists encrypted lightweight
  :class:`ModeloHistory` summaries for local
  filing-history views.
* :func:`build_runtime_schema_provider` supplies the runtime registry view used
  by draft construction, review, export, and verification.

The facade deliberately separates local filing state from live submission.
Remote AEAT submission is not exposed here; attempted live writes are refused
by :class:`LiveSubmitForbiddenError`.

Imports from external PDFs stay evidence-scoped. A justificante import creates a
local draft plus submission-audit baseline, while casilla-complete declaration
and borrador parsing enter through the inbound adapter surfaces before
application services decide how that evidence participates in a work-unit
workflow.

Work-unit filing records for calculation revisions live in
:mod:`modelo` and :mod:`domain.modelos`. This package owns
draft-level construction, review, export, verification, justificante import,
local amendment construction, and lightweight local history; it does not create
:class:`ModeloRecord` entries or stamp :class:`ExternalEvidence`.

See Also:
    :mod:`modelo`
        Operator-facing modelo facade that carries calculation revisions into
        this filing surface.
    :func:`file_modelo_revision`
        Work-unit action that records a verified calculation revision as a
        current local :class:`ModeloRecord`.
    :func:`import_external_filing_evidence`
        External-evidence import path that creates an evidenced
        :class:`ModeloRecord` baseline for amendments.
    :mod:`domain.justificante`
        Receipt-metadata domain used by justificante PDF imports and
        receipt-bound external evidence.
    :mod:`domain.filing`
        Canonical draft records, values, provenance, validation findings, and
        review helpers.
    :mod:`domain.submission`
        Local-only submission audit records populated by justificante import;
        this is not an AEAT live-submit path.
    :mod:`domain.calculations.registry`
        Registry authority, snapshots, export layouts, and formula execution
        used by this application facade.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

from ...core import STR_KEYED_MAPPING_ADAPTER
from ...core import BindingSourceKind as _BindingSourceKind
from ...core import CasillaId as _CasillaId
from ...core import Period as _Period
from ...core.errors import BaseSeverity as _BaseSeverity
from ...core.parsing import parse_bool as _parse_bool
from ...core.parsing import parse_iso8601_date as _parse_iso8601_date
from ...core.resources import resources as _resources
from ...core.time import now as _utc_now
from ...domain.calculations.registry.ids import BindingId as _BindingId
from ...domain.calculations.registry.schema import CasillaDefinition as _CasillaDefinition
from ...domain.calculations.registry.schema import DataBindingDefinition as _DataBindingDefinition
from ...domain.calculations.registry.schema_input_kind import InputKind as _InputKind
from ...domain.calculations.registry.ids import LegalRefId as _LegalRefId
from ...domain.calculations.registry.formula_runtime import RegistryCalculationEntry as _RegistryCalculationEntry
from ...domain.calculations.registry.formula_runtime import RegistryCalculationResult as _RegistryCalculationResult
from ...domain.calculations.registry.schema import RegistrySnapshot as _RegistrySnapshot
from ...domain.calculations.registry.errors import RegistrySnapshotError as _RegistrySnapshotError
from ...domain.calculations.registry.schema import RegistrySnapshotRef as _RegistrySnapshotRef
from ...domain.calculations.registry.errors import RegistryValidationError as _RegistryValidationError
from ...domain.calculations.registry.ids import RelationId as _RelationId
from ...domain.calculations.registry.ids import SourceRefId as _SourceRefId
from ...domain.calculations.registry.bindings import bound_casilla_binding_ids as _registry_bound_casilla_binding_ids
from ...domain.calculations.registry.formula_runtime import calculate_registry_snapshot as _calculate_registry_snapshot
from ...domain.calculations.registry.casilla_membership import casilla_noncanonical_reference_tokens as _casilla_noncanonical_reference_tokens
from ...domain.calculations.registry.casilla_membership import declared_casilla_ids as _declared_casilla_ids
from ...domain.calculations.registry.runtime_graph import enum_consumed_binding_ids as _enum_consumed_binding_ids
from ...domain.calculations.registry.runtime_graph import expression_binding_refs as _expression_binding_refs
from ...domain.calculations.registry.schema_scalars import registry_scalar_value_type as _registry_scalar_value_type
from ...domain.calculations.registry.runtime_graph import revision_date_binding_ids as _revision_date_binding_ids
from ...domain.calculations.registry.schema_scalars import validate_registry_text_scalar as _validate_registry_text_scalar
from ...domain.filing import (
    CasillaCollection as _CasillaCollection,
)
from ...domain.filing import (
    CasillaSchemaProvider as _CasillaSchemaProvider,
)
from ...domain.filing import (
    DeadlineChecker as _DeadlineChecker,
)
from ...domain.filing import (
    ModeloBindingValue as _ModeloBindingValue,
)
from ...domain.filing import (
    ModeloCasillaProvenance as _ModeloCasillaProvenance,
)
from ...domain.filing import (
    ModeloDraft as _ModeloDraft,
)
from ...domain.filing import (
    ModeloInputs as _ModeloInputs,
)
from ...domain.filing import (
    ModeloProfile as _ModeloProfile,
)
from ...domain.filing import (
    ModeloScalar as _ModeloScalar,
)
from ...domain.filing import (
    ModeloValidationFinding as _ModeloValidationFinding,
)
from ...domain.filing import (
    ModeloValidator as _ModeloValidator,
)
from ...domain.filing import (
    ModeloValue as _ModeloValue,
)
from ...domain.filing import (
    ModeloValueKind as _ModeloValueKind,
)
from ...domain.filing import (
    apply_validation as _apply_validation,
)
from ...domain.filing import (
    compute_modelo_draft_id as _compute_modelo_draft_id,
)
from ...domain.filing import (
    registry_schema_version as _registry_schema_version,
)
from ...domain.period import calculation_filing_date as _calculation_filing_date
from ...domain.submission import ModeloDraftStatus as _ModeloDraftStatus
from ._calculate import (
    DeclaracionCalculateSummary,
    summarise_calculation,
)
from ._complementaria import build_complementaria, list_amendments, load_amendment
from ._export import (
    DeclaracionExportFormat,
    DeclaracionExportResult,
    DeclaracionVerifyResult,
    DeclaracionVerifyVerdict,
    FilingEnvelopeOccurrence,
    FilingEnvelopeRenderRequest,
    FilingEnvelopeRenderResult,
    FilingExportConsumedResult,
    FilingExportPayloadConsumer,
    FilingExportValidatedPayload,
    assert_export_artifact_matches_receipt,
    export_draft,
    export_layout_renderability_reason,
    render_envelope_prefix_field,
    render_filing_envelope,
    verify_export,
)
from ._export_parity import did_page_required, required_applicable_casilla_ids
from ._export_producer import m303_rectificativa_motive_producer_values
from ._export_proof import (
    FilingExportConformanceAuthority,
    FilingExportConformanceReceipt,
    FilingExportConformanceRenderInputs,
    FilingExportConformanceRequest,
    FilingExportConformanceVectorEvidence,
    FilingExportDictionaryValue,
    FilingExportGeneratedOutput,
    FilingExportOfficialProbe,
    FilingExportProof,
    FilingExportProofAssessment,
    FilingExportProofAuthority,
    FilingExportProofChannel,
    FilingExportProofCoordinate,
    FilingExportProofRefusal,
    FilingExportProofRefusalReason,
    FilingExportPublicProvenance,
    FilingExportSecureCustodyRecord,
    FilingExportSecureReplayCustody,
    FilingExportSecureReplayEvidence,
    FilingExportSecureReplayReceipt,
    FilingExportSecureReplayRequest,
    FilingExportSecureReplaySourceAuthority,
    FilingExportSourcePinnedProbeExpectation,
    prove_export_conformance,
    prove_secure_export_replay,
)
from ._history_models import ModeloHistory, ModeloHistoryEntry
from ._history_repository import ModeloHistoryRepository
from ._import import JustificanteImportResult, import_filing_from_justificante
from ._m303_exonerado_390 import project_m303_exonerado_390_value_arrival
from ._m303_export_applicability import validate_m303_export_applicability
from ._producer_snapshot import (
    M202_UNSUPPORTED_PRODUCER_IDS,
    AmendmentEvidence,
    ChargeAccountSelection,
    DeclarationContactFacts,
    FilingElectionFacts,
    FilingModelProfileFacts,
    FilingProducerSnapshot,
    FilingProducerSnapshotError,
    GeneralFilingProfileFacts,
    M202UnsupportedProducerId,
    M303FilingFacts,
    M303InsolvencyFilingFact,
    M303InsolvencyFilingSubtype,
    Modelo111ProfileFacts,
    Modelo202ActivityFacts,
    Modelo202ProducerProfile,
    PresenterIdentity,
    RefundAccountSelection,
    SelectedFilingAccount,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
    resolve_m303_filing_facts,
)
from ._profile_filing_retention import (
    FilingRetentionAuthority,
    try_record_filing_retention_snapshot,
)
from ._projection import FilingProjectionValue, FilingRecordRenderContext
from ._review import (
    ModeloApprovalStaleReason,
    approval_stale_reasons,
    approve_draft,
    compute_current_approval_basis,
    compute_review_checksum,
    describe_stale_reason,
    empty_prior_filing_observations_fingerprint,
    empty_profile_activity_fingerprint,
    refresh_review_status,
    unapprove_draft,
)
from ._runtime_repository import modelo_record_repository_for_application
from .errors import ModeloApplicationError, ModeloCalculateError
from .errors import ModeloApplicationError as _ModeloBuilderError
from .runtime import (
    ModeloOperatorProfile,
    build_runtime_schema_provider,
    filing_profile_from_taxpayer,
    load_default_filing_profile,
)


def build_draft(
    *,
    modelo: str,
    period: _Period,
    profile: _ModeloProfile,
    inputs: _ModeloInputs,
    schema_provider: _CasillaSchemaProvider,
    deadline_checker: _DeadlineChecker | None = None,
    fail_on_warning: bool = False,
) -> _ModeloDraft:
    """Build and validate a filing draft from a registry snapshot.

    Args:
        modelo: Stable modelo string ID.
        period: Typed :class:`Period` built from a filing year and
            bare registry token.
        profile: :class:`ModeloProfile` the draft would be
            built for.
        inputs: Raw :class:`ModeloInputs`.
        schema_provider: Registry-backed
            :class:`CasillaSchemaProvider`.
        deadline_checker: Optional
            :class:`DeadlineChecker`.
        fail_on_warning: Raise when validation produces any warning or error.

    Returns:
        A fully constructed and validated
        :class:`ModeloDraft`.

    Raises:
        :class:`ModeloBuilderError`: If the registry has no
            matching snapshot, inputs are malformed, or strict validation fails.
    """
    snapshot = _load_registry_snapshot(modelo=modelo, period=period)
    filing_year, registry_period = _registry_period(period)
    snapshot_ref = _RegistrySnapshotRef(
        modelo=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        modelo_year=filing_year,
        period=registry_period,
    )
    collection = schema_provider.get_collection(modelo)
    expected_schema_version = _registry_schema_version(
        modelo=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
    )
    if collection.schema_version != expected_schema_version:
        raise _ModeloBuilderError(
            translated_message="application.filing.build_draft.errors.schema_version_snapshot_mismatch",
            context={
                "modelo": snapshot.modelo.id,
                "provider_schema_version": collection.schema_version,
                "expected_schema_version": expected_schema_version,
                "revision_id": snapshot.revision.id,
            },
        )
    input_channels = _draft_input_channels(snapshot, inputs)
    result = _calculate_draft_result(
        snapshot=snapshot,
        period=period,
        input_channels=input_channels,
    )
    value_tuple = _draft_values(
        snapshot=snapshot,
        collection=collection,
        result=result,
        input_channels=input_channels,
    )
    created_at = _utc_now()
    draft = _draft_record(
        modelo=modelo,
        period=period,
        profile=profile,
        snapshot_ref=snapshot_ref,
        values=value_tuple,
        binding_values=input_channels.filing_binding_values,
        casilla_provenance=_draft_casilla_provenance(snapshot),
        created_at=created_at,
        schema_version=collection.schema_version,
    )
    return _validate_built_draft(
        draft,
        schema_provider=schema_provider,
        deadline_checker=deadline_checker,
        fail_on_warning=fail_on_warning,
    )


class _DraftInputChannels(NamedTuple):
    casilla_inputs: dict[_CasillaId, Decimal]
    text_casilla_inputs: dict[_CasillaId, str]
    binding_inputs: dict[_BindingId, Decimal]
    enum_binding_inputs: dict[_BindingId, str]
    date_binding_inputs: dict[_BindingId, date]
    relation_inputs: dict[_RelationId, Decimal]
    filing_binding_values: list[_ModeloBindingValue]


def _draft_input_channels(
    snapshot: _RegistrySnapshot,
    inputs: _ModeloInputs,
) -> _DraftInputChannels:
    casilla_ids = set(_declared_casilla_ids(snapshot.revision))
    text_casilla_data_types = _text_casilla_data_types(snapshot)
    bindings = {binding.id: binding for binding in snapshot.revision.bindings}
    calculation_binding_ids = _formula_binding_ids(snapshot) | _bound_casilla_binding_ids(snapshot)
    enum_binding_ids = _enum_consumed_binding_ids(snapshot.revision)
    date_binding_ids = _date_binding_ids(snapshot)
    relation_ids = _relation_ids(snapshot)
    # Date and relation ids ride dedicated engine channels; never coerce their
    # values through the Decimal binding channel (an ISO date is not a Decimal).
    decimal_binding_ids = calculation_binding_ids - enum_binding_ids - date_binding_ids - relation_ids
    _validate_filing_input_keys(
        inputs,
        accepted_ids=casilla_ids | set(bindings) | relation_ids,
        snapshot=snapshot,
    )
    # Date bindings (e.g. taxpayer birth_date for age_at_year_end) and period
    # relations (e.g. prior pagos fraccionados) travel on dedicated engine
    # channels, not the Decimal binding channel. Replay callers merge the
    # calculation revision's BindingId and RelationId snapshots into this flat
    # input map; extract them here by their registry id-sets and route them.
    return _DraftInputChannels(
        casilla_inputs=_decimal_inputs_for_ids(inputs, casilla_ids - set(text_casilla_data_types)),
        text_casilla_inputs=_text_inputs_for_ids(inputs, text_casilla_data_types),
        binding_inputs=_decimal_inputs_for_ids(inputs, decimal_binding_ids),
        enum_binding_inputs=_string_inputs_for_ids(inputs, enum_binding_ids),
        date_binding_inputs=_date_inputs_for_ids(inputs, date_binding_ids),
        relation_inputs=_decimal_inputs_for_ids(inputs, relation_ids),
        filing_binding_values=_filing_binding_values(
            inputs,
            bindings,
            enum_binding_ids,
            frozenset(date_binding_ids),
        ),
    )


def _calculate_draft_result(
    *,
    snapshot: _RegistrySnapshot,
    period: _Period,
    input_channels: _DraftInputChannels,
) -> _RegistryCalculationResult:
    try:
        return _calculate_registry_snapshot(
            snapshot,
            inputs=input_channels.casilla_inputs,
            date_context={"filing_period": _filing_period_date(period)},
            binding_values=input_channels.binding_inputs,
            enum_binding_values=input_channels.enum_binding_inputs or None,
            relation_values=input_channels.relation_inputs or None,
            date_binding_values=input_channels.date_binding_inputs or None,
            text_inputs=input_channels.text_casilla_inputs or None,
        )
    except _RegistryValidationError as exc:
        raise _ModeloBuilderError(
            translated_message="application.filing.build_draft.errors.registry_calculation_failed",
            context={
                "modelo": snapshot.modelo.id,
                "revision_id": snapshot.revision.id,
                "registry_error_type": type(exc).__name__,
            },
        ) from exc


def _draft_values(
    *,
    snapshot: _RegistrySnapshot,
    collection: _CasillaCollection,
    result: _RegistryCalculationResult,
    input_channels: _DraftInputChannels,
) -> tuple[_ModeloValue, ...]:
    # A computed casilla's formula_trace_casilla_ids documents the static casilla inputs its
    # formula declares (the validator checks the trace against
    # ``CasillaSchema.formula_input_casilla_ids``). It must NOT be the branch-dependent
    # runtime operand set: ``if_then_else`` short-circuits, so a conditional
    # formula (e.g. M303 ``iva.prorrata-porcentaje``) emits operand_casilla_refs
    # for only the branch actually taken — a subset of the declared inputs —
    # which the formula-divergence rule then rejects, leaving the draft in
    # BORRADOR. Read the deterministic declared input set from the schema
    # collection instead.
    formula_input_casilla_ids_by_casilla = {
        schema.casilla_id: tuple(schema.formula_input_casilla_ids)
        for schema in collection.all()
        if schema.formula is not None
    }
    entries = {entry.target_casilla_id: entry for entry in result.entries}
    values = (
        _draft_value_for_casilla(
            casilla=casilla,
            entries=entries,
            result=result,
            formula_input_casilla_ids_by_casilla=formula_input_casilla_ids_by_casilla,
            input_channels=input_channels,
        )
        for casilla in snapshot.revision.casillas
    )
    return tuple(sorted(values, key=lambda value: value.casilla_id))


def _draft_value_for_casilla(
    *,
    casilla: _CasillaDefinition,
    entries: Mapping[_CasillaId, _RegistryCalculationEntry],
    result: _RegistryCalculationResult,
    formula_input_casilla_ids_by_casilla: Mapping[_CasillaId, tuple[_CasillaId, ...]],
    input_channels: _DraftInputChannels,
) -> _ModeloValue:
    if casilla.id in entries:
        entry = entries[casilla.id]
        trace = formula_input_casilla_ids_by_casilla.get(casilla.id)
        if trace is None:
            trace = entry.operand_casilla_refs
        return _ModeloValue(
            casilla_id=casilla.id,
            value=result.values[casilla.id],
            kind=_ModeloValueKind.COMPUTED,
            source=f"registry formula {entry.formula_id}",
            formula_trace_casilla_ids=trace,
        )
    if casilla.input_kind == _InputKind.BOUND:
        value = result.values.get(casilla.id)
        if value is not None:
            return _ModeloValue(
                casilla_id=casilla.id,
                value=value,
                kind=_ModeloValueKind.INHERITED,
                source=f"registry binding {casilla.binding}",
            )
    if casilla.id in input_channels.casilla_inputs:
        return _ModeloValue(
            casilla_id=casilla.id,
            value=input_channels.casilla_inputs[casilla.id],
            kind=_ModeloValueKind.LITERAL,
            source="registry input",
        )
    if casilla.id in input_channels.text_casilla_inputs:
        return _ModeloValue(
            casilla_id=casilla.id,
            value=input_channels.text_casilla_inputs[casilla.id],
            kind=_ModeloValueKind.LITERAL,
            source="registry input",
        )
    return _ModeloValue(
        casilla_id=casilla.id,
        value=None,
        kind=_ModeloValueKind.EMPTY,
        source="registry schema",
    )


def _draft_casilla_provenance(
    snapshot: _RegistrySnapshot,
) -> tuple[_ModeloCasillaProvenance, ...]:
    return tuple(
        _ModeloCasillaProvenance(
            casilla_id=casilla.id,
            formula_id=casilla.formula,
            legal_refs=tuple(casilla.legal_refs),
            source_refs=tuple(casilla.source_refs),
        )
        for casilla in sorted(snapshot.revision.casillas, key=lambda item: item.id)
    )


def _draft_record(
    *,
    modelo: str,
    period: _Period,
    profile: _ModeloProfile,
    snapshot_ref: _RegistrySnapshotRef,
    values: tuple[_ModeloValue, ...],
    binding_values: list[_ModeloBindingValue],
    casilla_provenance: tuple[_ModeloCasillaProvenance, ...],
    created_at: datetime,
    schema_version: str,
) -> _ModeloDraft:
    binding_value_tuple = tuple(sorted(binding_values, key=lambda value: value.binding_id))
    # Propagate identity from the validated profile substrate into the
    # draft. ``profile.tax_id`` is already validated against the AEAT
    # checksum via ``SubjectTaxId`` on the profile model, so the
    # post-validation result type-checks at the ModeloDraft boundary
    # and survives every downstream encrypted-persistence roundtrip.
    return _ModeloDraft(
        draft_id=_compute_modelo_draft_id(
            modelo=modelo,
            period=period,
            profile_tax_id=profile.tax_id,
            snapshot_ref=snapshot_ref,
            values=values,
            binding_values=binding_value_tuple,
        ),
        modelo=modelo,
        period=period,
        profile_tax_id=profile.tax_id,
        subject_tax_id=profile.tax_id,
        snapshot_ref=snapshot_ref,
        status=_ModeloDraftStatus.BORRADOR,
        values=values,
        binding_values=binding_value_tuple,
        casilla_provenance=casilla_provenance,
        created_at=created_at,
        updated_at=created_at,
        schema_version=schema_version,
    )


def _validate_built_draft(
    draft: _ModeloDraft,
    *,
    schema_provider: _CasillaSchemaProvider,
    deadline_checker: _DeadlineChecker | None,
    fail_on_warning: bool,
) -> _ModeloDraft:
    validator = _ModeloValidator(schema_provider=schema_provider, deadline_checker=deadline_checker)
    findings = validator.validate(draft)
    if fail_on_warning and findings:
        raise _ModeloBuilderError(
            translated_message="application.filing.build_draft.errors.findings_under_fail_on_warning",
            context={
                "modelo": draft.modelo,
                "finding_count": len(findings),
                "codes": tuple(finding.code for finding in findings),
            },
        )
    return _apply_validation(draft, findings)


def _load_registry_snapshot(*, modelo: str, period: _Period) -> _RegistrySnapshot:
    """Resolve the registry snapshot for ``modelo`` in ``period`` from the authority.

    Deliberately uncached at this layer. Registry snapshots are already cached
    beneath this call, and that cache chain is invalidated by the complete
    registry-tree fingerprint: resetting the process resource registry rebuilds
    the authority, whose tree load is keyed on that fingerprint, so changed
    sources re-derive. A memo here would sit *above* the loader keyed only on
    ``(modelo, period)`` — no fingerprint, no TTL, and outside that reset
    protocol — so it would keep serving the pre-change snapshot for the life of
    the process even after a correct reset, which means computing a filing under
    a superseded revision's norms. Resolving through the authority costs well
    under a microsecond on the warm path, so the memo bought nothing that could
    justify that.

    Revision selection stays law-determined: only ``filing_year`` and the bare
    registry period token are passed, never a stored revision id.
    """
    filing_year, registry_period = _registry_period(period)
    try:
        authority = _resources().modelos.authority
        return authority.snapshot(
            modelo,
            filing_year=filing_year,
            period=registry_period,
        )
    except (_RegistrySnapshotError, _RegistryValidationError) as exc:
        raise _ModeloBuilderError(
            translated_message="application.filing.build_draft.errors.registry_snapshot_unavailable",
            context={
                "modelo": modelo,
                "filing_year": filing_year,
                "period": registry_period,
                "registry_error_type": type(exc).__name__,
            },
        ) from exc


def _registry_period(period: object) -> tuple[int, str]:
    if not isinstance(period, _Period):
        raise _ModeloBuilderError(
            translated_message="application.filing.build_draft.errors.period_type_invalid",
            context={"observed_type": type(period).__name__},
        )
    return period.filing_year, period.registry_token


def _filing_period_date(period: _Period) -> date:
    """Return the shared calculation filing date for a typed draft period."""
    _registry_period(period)
    return _calculation_filing_date(period)


def _formula_binding_ids(snapshot: _RegistrySnapshot) -> set[_BindingId]:
    return {
        binding_id
        for formula in snapshot.revision.formulas
        for binding_id in _expression_binding_refs(formula.expression)
    }


def _bound_casilla_binding_ids(snapshot: _RegistrySnapshot) -> set[_BindingId]:
    return {
        binding_id
        for casilla in snapshot.revision.casillas
        if casilla.input_kind == _InputKind.BOUND
        for binding_id in _registry_bound_casilla_binding_ids(casilla)
    }


def _date_binding_ids(snapshot: _RegistrySnapshot) -> set[_BindingId]:
    """Collect every date_binding id referenced by the revision's formulas.

    Date bindings (date-valued profile facts such as ``birth_date``,
    consumed by ``age_at_year_end``) travel on the engine's
    ``date_binding_values`` channel, distinct from the Decimal binding
    channel. A draft replay must supply them or the formula runtime
    refuses the calculation. Delegates to the canonical
    :func:`revision_date_binding_ids` registry query (single source of truth).
    """
    return set(_revision_date_binding_ids(snapshot.revision))


def _relation_ids(snapshot: _RegistrySnapshot) -> set[_RelationId]:
    """Collect the cross-model relation ids declared on the revision.

    Period relations (e.g. prior pagos fraccionados aggregated into the
    annual settlement) are supplied to the engine on the dedicated
    ``relation_values`` channel. A draft replay extracts them from the
    persisted inputs by this id-set; relations not present in the inputs
    are simply absent from the resolved relation map.
    """
    return {relation.id for relation in snapshot.revision.relations}


def _text_casilla_data_types(snapshot: _RegistrySnapshot) -> dict[_CasillaId, str]:
    """Map casillas assigned to the registry's typed text-scalar channel."""
    return {
        casilla.id: casilla.data_type
        for casilla in snapshot.revision.casillas
        if _registry_scalar_value_type(casilla.data_type) == "str"
    }


def _validate_filing_input_keys(
    inputs: _ModeloInputs,
    *,
    accepted_ids: set[_BindingId | _CasillaId | _RelationId],
    snapshot: _RegistrySnapshot,
) -> None:
    """Reject input keys that are not canonical registry input ids."""
    non_string = tuple(repr(key) for key in inputs if type(key) is not str)
    if non_string:
        raise _ModeloBuilderError(
            translated_message="application.filing.build_draft.errors.input_key_not_string",
            context={
                "offending_count": len(non_string),
                "input_keys": tuple(sorted(non_string)),
            },
        )

    padded = tuple(key for key in inputs if key != key.strip())
    if padded:
        raise _ModeloBuilderError(
            translated_message="application.filing.build_draft.errors.input_key_padded",
            context={
                "offending_count": len(padded),
                "input_keys": tuple(sorted(padded)),
            },
        )

    noncanonical_tokens = _casilla_noncanonical_reference_tokens(snapshot.revision)
    supplied_noncanonical = tuple(key for key in inputs if key in noncanonical_tokens)
    if supplied_noncanonical:
        raise _ModeloBuilderError(
            translated_message="application.filing.build_draft.errors.input_key_noncanonical_casilla",
            context={
                "modelo": snapshot.modelo.id,
                "offending_count": len(supplied_noncanonical),
                "input_keys": tuple(sorted(supplied_noncanonical)),
                "noncanonical_references": tuple(
                    {
                        "token": key,
                        "canonical_casilla_ids": tuple(noncanonical_tokens[key]),
                    }
                    for key in sorted(supplied_noncanonical)
                ),
            },
        )

    unknown = tuple(key for key in inputs if key not in accepted_ids)
    if unknown:
        raise _ModeloBuilderError(
            translated_message="application.filing.build_draft.errors.input_key_unknown",
            context={
                "modelo": snapshot.modelo.id,
                "schema_version": _registry_schema_version(
                    modelo=snapshot.modelo.id,
                    revision_id=snapshot.revision.id,
                ),
                "offending_count": len(unknown),
                "input_keys": tuple(sorted(unknown)),
            },
        )


def _date_inputs_for_ids(inputs: _ModeloInputs, input_ids: set[_BindingId]) -> dict[_BindingId, date]:
    """Extract ISO-date-shaped inputs for ``input_ids`` as ``date`` values."""
    date_inputs: dict[_BindingId, date] = {}
    for binding_id in input_ids:
        value = inputs.get(binding_id)
        if value is None:
            continue
        if isinstance(value, date):
            date_inputs[binding_id] = value
            continue
        if isinstance(value, str):
            try:
                parsed = _parse_iso8601_date(value)
            except ValueError as exc:
                raise _ModeloBuilderError(
                    translated_message="application.filing.build_draft.errors.date_binding_not_iso",
                    context={"binding_id": binding_id, "supplied_value": value},
                ) from exc
            if parsed is None:
                raise _ModeloBuilderError(
                    translated_message="application.filing.build_draft.errors.date_binding_not_iso",
                    context={"binding_id": binding_id, "supplied_value": value},
                )
            date_inputs[binding_id] = parsed
    return date_inputs


def _decimal_inputs_for_ids[InputId: str](
    inputs: _ModeloInputs,
    input_ids: set[InputId],
) -> dict[InputId, Decimal]:
    decimal_inputs: dict[InputId, Decimal] = {}
    for input_id in input_ids:
        value = inputs.get(input_id)
        if value is None:
            continue
        decimal_inputs[input_id] = _decimal_input(input_id, value)
    return decimal_inputs


def _text_inputs_for_ids(inputs: _ModeloInputs, input_data_types: Mapping[_CasillaId, str]) -> dict[_CasillaId, str]:
    text_inputs: dict[_CasillaId, str] = {}
    for input_id, data_type in input_data_types.items():
        value = inputs.get(input_id)
        if value is None:
            continue
        if not isinstance(value, str):
            raise _ModeloBuilderError(
                translated_message="application.filing.build_draft.errors.text_casilla_not_string",
                context={
                    "casilla_id": input_id,
                    "data_type": data_type,
                    "observed_type": type(value).__name__,
                },
            )
        try:
            text_inputs[input_id] = _validate_registry_text_scalar(data_type, value)
        except _RegistryValidationError as exc:
            raise _ModeloBuilderError(
                translated_message="application.filing.build_draft.errors.text_casilla_invalid",
                context={
                    "casilla_id": input_id,
                    "data_type": data_type,
                    "registry_error_type": type(exc).__name__,
                },
            ) from exc
    return text_inputs


def _string_inputs_for_ids(inputs: _ModeloInputs, input_ids: frozenset[_BindingId]) -> dict[_BindingId, str]:
    # Enum-channel bindings carry string values; skip None and non-string entries.
    string_inputs: dict[_BindingId, str] = {}
    for binding_id in input_ids:
        value = inputs.get(binding_id)
        if value is None:
            continue
        if not isinstance(value, str):
            continue
        string_inputs[binding_id] = value
    return string_inputs


def _binding_provenance(
    binding: _DataBindingDefinition,
) -> tuple[_BindingSourceKind, tuple[_LegalRefId, ...], tuple[_SourceRefId, ...]]:
    """Extract the typed source kind and grounding from a binding definition.

    The ``binding`` is the registry ``DataBindingDefinition`` already held by
    the filing builder; its ``source`` is a typed
    :class:`BindingSourceKind` and its ``legal_refs`` / ``source_refs``
    carry the binding's regulatory grounding. Carrying them onto every
    :class:`ModeloBindingValue` brings bound values to
    provenance parity with casillas (the casilla half already populates
    :class:`ModeloCasillaProvenance`).
    """
    source = binding.source
    legal_refs = binding.legal_refs
    source_refs = binding.source_refs
    if not legal_refs or not source_refs:
        raise _ModeloBuilderError(
            translated_message="application.filing.build_draft.errors.binding_provenance_missing",
            context={
                "binding_id": str(binding.id),
                "source": source.value,
                "legal_ref_count": len(legal_refs),
                "source_ref_count": len(source_refs),
            },
        )
    return source, legal_refs, source_refs


def _filing_binding_values(
    inputs: _ModeloInputs,
    bindings: Mapping[_BindingId, _DataBindingDefinition],
    enum_binding_ids: frozenset[_BindingId] = frozenset(),
    non_decimal_binding_ids: frozenset[_BindingId] = frozenset(),
) -> list[_ModeloBindingValue]:
    values: list[_ModeloBindingValue] = []
    for binding_id, binding in bindings.items():
        if binding_id in enum_binding_ids or binding_id in non_decimal_binding_ids:
            # Enum-channel bindings, date bindings, and period relations flow
            # through _calculate_registry_snapshot's dedicated channels
            # (enum_binding_values / date_binding_values / relation_values);
            # they carry no fichero-BOE addressing and must not be coerced to
            # Decimal here.
            continue
        if binding_id not in inputs:
            continue
        raw_value = inputs[binding_id]
        source, legal_refs, source_refs = _binding_provenance(binding)
        if isinstance(raw_value, list | tuple):
            values.extend(
                _ModeloBindingValue(
                    binding_id=binding_id,
                    value=_binding_input(binding_id, row_value, binding),
                    kind=_ModeloValueKind.LITERAL,
                    source=source,
                    legal_refs=legal_refs,
                    source_refs=source_refs,
                    row_index=index,
                )
                for index, row_value in enumerate(raw_value, start=1)
            )
            continue
        if isinstance(raw_value, Mapping):
            values.extend(
                _ModeloBindingValue(
                    binding_id=binding_id,
                    value=_binding_input(binding_id, row_value, binding),
                    kind=_ModeloValueKind.LITERAL,
                    source=source,
                    legal_refs=legal_refs,
                    source_refs=source_refs,
                    row_index=_binding_row_index(binding_id, row_key),
                )
                for row_key, row_value in raw_value.items()
            )
            continue
        values.append(
            _ModeloBindingValue(
                binding_id=binding_id,
                value=_binding_input(binding_id, raw_value, binding),
                kind=_ModeloValueKind.LITERAL,
                source=source,
                legal_refs=legal_refs,
                source_refs=source_refs,
            ),
        )
    return values


def _refuse_binding_row_index(binding_id: _BindingId, row_key: object) -> _ModeloBuilderError:
    """Return the refusal for a row key that is not a positive integer."""
    return _ModeloBuilderError(
        translated_message="application.filing.build_draft.errors.binding_row_key_not_positive_integer",
        context={
            "binding_id": binding_id,
            "observed_type": type(row_key).__name__,
            "minimum_row_key": 1,
        },
    )


def _binding_row_index(binding_id: _BindingId, row_key: object) -> int:
    if isinstance(row_key, bool):
        raise _refuse_binding_row_index(binding_id, row_key)
    if isinstance(row_key, int):
        index = row_key
    elif isinstance(row_key, str):
        try:
            index = int(row_key)
        except ValueError as exc:
            raise _refuse_binding_row_index(binding_id, row_key) from exc
    else:
        raise _refuse_binding_row_index(binding_id, row_key)
    if index < 1:
        raise _refuse_binding_row_index(binding_id, row_key)
    return index


def _binding_data_type(binding: object) -> str:
    """Return the declared scalar type for one binding input.

    The decimal default is correct for a scalar binding, which declares neither a
    ``data_type`` nor a ``row_field`` and is a money value by construction. It is
    NOT correct for a detail-record row field, whose type depends entirely on
    which field it is: a ``valuation_amount`` is money and a ``party_tax_id`` is a
    NIF. An undeclared row field therefore refuses rather than defaulting, because
    the alternative is emitting a name or a tax id into a filing artefact as a
    decimal, which is byte-valid and wrong and indistinguishable from a real value.

    A row field's scalar type is registry data: the binding declares ``data_type``
    on its selector, typed as the closed export vocabulary so an unsupported value
    is refused at registry build rather than at emission. That is the same key,
    carrying the same fact, that a fixed-width export projection declares -- the
    two differ only in how the value is positioned -- so this reads the
    declaration and never infers a type from the row field's NAME, which could not
    be correct in general: ``operation_kind_code`` is a typed enum on modelo 232
    and a plain string on modelo 360.
    """
    selector: object = getattr(binding, "selector", None)
    if isinstance(selector, Mapping):
        metadata = STR_KEYED_MAPPING_ADAPTER.validate_python(selector)
        raw_data_type = metadata.get("data_type")
        row_field = metadata.get("row_field")
    else:
        raw_data_type = getattr(selector, "data_type", None)
        row_field = getattr(selector, "row_field", None)
    if raw_data_type is not None:
        return str(raw_data_type)
    if isinstance(row_field, str):
        raise _ModeloBuilderError(
            translated_message="application.filing.build_draft.errors.binding_data_type_unsupported",
            context={"binding_id": str(getattr(binding, "id", row_field)), "data_type": row_field},
        )
    return "decimal"


def _binding_input(binding_id: _BindingId, value: object, binding: object) -> _ModeloScalar:
    """Route one binding input to the channel its declared data type belongs to.

    The runtime family comes from the registry classifier rather than a local
    comparison against literal type names. The registry owns the scalar
    taxonomy, so a family it adds — the eleven specific text families beyond
    generic ``text``, for instance — is routed here without this function
    being edited, and a data type the registry does not declare is refused by
    the classifier instead of falling through a chain of string equalities.
    """
    data_type = _binding_data_type(binding)
    try:
        family = _registry_scalar_value_type(data_type)
    except _RegistryValidationError as exc:
        raise _ModeloBuilderError(
            translated_message="application.filing.build_draft.errors.binding_data_type_unsupported",
            context={"binding_id": binding_id, "data_type": data_type},
        ) from exc
    if family == "str":
        # Coerce first so the generic ``text`` channel keeps accepting a
        # non-string scalar (an integer ``rectified_year``); the canonical
        # validator is an identity for ``text`` and a real check for the
        # specific families, which previously bypassed their validators.
        try:
            return _validate_registry_text_scalar(data_type, str(value))
        except _RegistryValidationError as exc:
            raise _ModeloBuilderError(
                translated_message="application.filing.build_draft.errors.binding_text_value_invalid",
                context={
                    "binding_id": binding_id,
                    "data_type": data_type,
                    "registry_error_type": type(exc).__name__,
                },
            ) from exc
    if family == "int":
        decimal_value = _decimal_input(binding_id, value)
        if decimal_value != decimal_value.to_integral_value():
            raise _ModeloBuilderError(
                translated_message="application.filing.build_draft.errors.binding_value_not_integer",
                context={"binding_id": binding_id, "data_type": data_type},
            )
        return int(decimal_value)
    if family == "bool":
        return _boolean_input(binding_id, value)
    if family == "decimal":
        return _decimal_input(binding_id, value)
    raise _ModeloBuilderError(
        translated_message="application.filing.build_draft.errors.binding_family_has_no_input_channel",
        context={
            "binding_id": binding_id,
            "data_type": data_type,
            "value_family": family,
        },
    )


def _refuse_decimal_input(input_id: str, value: object) -> _ModeloBuilderError:
    """Return the refusal for an input that cannot carry a Decimal amount."""
    return _ModeloBuilderError(
        translated_message="application.filing.build_draft.errors.input_not_decimal",
        context={"input_id": input_id, "observed_type": type(value).__name__},
    )


def _decimal_input(input_id: str, value: object) -> Decimal:
    if isinstance(value, bool):
        raise _refuse_decimal_input(input_id, value)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | str):
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise _refuse_decimal_input(input_id, value) from exc
    raise _refuse_decimal_input(input_id, value)


def _boolean_input(input_id: str, value: object) -> bool:
    """Coerce a binding input to a boolean, refusing a word nothing can read.

    Resolves through the one canonical vocabulary rather than the two sets
    that used to be spelled out here. Those sets were not a superset of the
    canonical one and not a subset either: they took ``s`` which the canonical
    vocabulary lacked, and missed ``sí`` which it had. Two overlapping
    dialects of the same idea is how ``si`` came to mean yes at this boundary
    and no at the maritime reader.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        parsed = _parse_bool(value)
        if parsed is not None:
            return parsed
    raise _ModeloBuilderError(
        translated_message="application.filing.build_draft.errors.binding_value_not_boolean",
        context={"binding_id": input_id, "observed_type": type(value).__name__},
    )


def validate_draft(
    draft: _ModeloDraft,
    *,
    bucket_id: str,
    schema_provider: _CasillaSchemaProvider,
    deadline_checker: _DeadlineChecker | None = None,
) -> _ModeloDraft:
    """Re-run validation against an existing draft.

    The returned draft preserves ``draft_id`` because the hash
    excludes findings, status, ``updated_at`` and ``notes``.

    Args:
        draft: The :class:`ModeloDraft` to re-validate.
        bucket_id: Stable bucket identifier; forwarded to
            :func:`refresh_review_status` after validation.
        schema_provider: :class:`CasillaSchemaProvider`
            resolving the casilla collection for the draft's modelo.
        deadline_checker: Optional :class:`DeadlineChecker`
            Protocol implementation.

    Returns:
        A new :class:`ModeloDraft` with refreshed findings,
        status and ``updated_at``.
    """
    validator = _ModeloValidator(
        schema_provider=schema_provider,
        deadline_checker=deadline_checker,
    )
    findings = validator.validate(draft)
    refreshed = _apply_validation(draft, findings)
    refreshed = refresh_review_status(
        refreshed,
        bucket_id=bucket_id,
        schema_provider=schema_provider,
    )
    # Defensive sanity check: re-validation must never change identity.
    assert refreshed.draft_id == draft.draft_id, "validate_draft must preserve draft_id"
    return refreshed


_SEVERITY_RANK: dict[str, int] = {
    _BaseSeverity.INFO: 0,
    _BaseSeverity.WARNING: 1,
    _BaseSeverity.ERROR: 2,
}


def iter_findings(
    draft: _ModeloDraft,
    *,
    severity_at_least: str = "WARNING",
) -> Iterator[_ModeloValidationFinding]:
    """Yield findings filtered by minimum severity.

    Args:
        draft: The :class:`ModeloDraft` to scan for
            validation findings.
        severity_at_least: Minimum severity to yield, one of
            ``"INFO"``, ``"WARNING"``, ``"ERROR"``. Defaults to
            ``"WARNING"``.

    Yields:
        Each :class:`ModeloValidationFinding` whose severity
        meets or exceeds the threshold, in declaration order.

    Raises:
        ModeloCalculateError: When ``severity_at_least`` is not a known
            severity name (``"INFO"``, ``"WARNING"``, or ``"ERROR"``).
    """
    try:
        threshold = _SEVERITY_RANK[_BaseSeverity[severity_at_least]]
    except KeyError as exc:
        raise ModeloCalculateError(
            translated_message="application.filing.errors.unknown_severity_threshold",
            context={
                "severity_at_least": severity_at_least,
                "accepted_severities": tuple(member.name for member in _BaseSeverity),
            },
        ) from exc
    for finding in draft.findings:
        if _SEVERITY_RANK[finding.severity] >= threshold:
            yield finding


__all__ = [
    "M202_UNSUPPORTED_PRODUCER_IDS",
    "AmendmentEvidence",
    "ChargeAccountSelection",
    "DeclaracionCalculateSummary",
    "DeclaracionExportFormat",
    "DeclaracionExportResult",
    "DeclaracionVerifyResult",
    "DeclaracionVerifyVerdict",
    "DeclarationContactFacts",
    "FilingElectionFacts",
    "FilingEnvelopeOccurrence",
    "FilingEnvelopeRenderRequest",
    "FilingEnvelopeRenderResult",
    "FilingExportConformanceAuthority",
    "FilingExportConformanceReceipt",
    "FilingExportConformanceRenderInputs",
    "FilingExportConformanceRequest",
    "FilingExportConformanceVectorEvidence",
    "FilingExportConsumedResult",
    "FilingExportDictionaryValue",
    "FilingExportGeneratedOutput",
    "FilingExportOfficialProbe",
    "FilingExportPayloadConsumer",
    "FilingExportProof",
    "FilingExportProofAssessment",
    "FilingExportProofAuthority",
    "FilingExportProofChannel",
    "FilingExportProofCoordinate",
    "FilingExportProofRefusal",
    "FilingExportProofRefusalReason",
    "FilingExportPublicProvenance",
    "FilingExportSecureCustodyRecord",
    "FilingExportSecureReplayCustody",
    "FilingExportSecureReplayEvidence",
    "FilingExportSecureReplayReceipt",
    "FilingExportSecureReplayRequest",
    "FilingExportSecureReplaySourceAuthority",
    "FilingExportSourcePinnedProbeExpectation",
    "FilingExportValidatedPayload",
    "FilingModelProfileFacts",
    "FilingProducerSnapshot",
    "FilingProducerSnapshotError",
    "FilingProjectionValue",
    "FilingRecordRenderContext",
    "FilingRetentionAuthority",
    "GeneralFilingProfileFacts",
    "JustificanteImportResult",
    "M202UnsupportedProducerId",
    "M303FilingFacts",
    "M303InsolvencyFilingFact",
    "M303InsolvencyFilingSubtype",
    "Modelo111ProfileFacts",
    "Modelo202ActivityFacts",
    "Modelo202ProducerProfile",
    "ModeloApplicationError",
    "ModeloApprovalStaleReason",
    "ModeloCalculateError",
    "ModeloHistory",
    "ModeloHistoryEntry",
    "ModeloHistoryRepository",
    "ModeloOperatorProfile",
    "PresenterIdentity",
    "RefundAccountSelection",
    "SelectedFilingAccount",
    "TaxpayerIdentityFacts",
    "approval_stale_reasons",
    "approve_draft",
    "assert_export_artifact_matches_receipt",
    "build_complementaria",
    "build_draft",
    "build_filing_producer_snapshot",
    "build_runtime_schema_provider",
    "compute_current_approval_basis",
    "compute_review_checksum",
    "describe_stale_reason",
    "did_page_required",
    "empty_prior_filing_observations_fingerprint",
    "empty_profile_activity_fingerprint",
    "export_draft",
    "export_layout_renderability_reason",
    "filing_profile_from_taxpayer",
    "import_filing_from_justificante",
    "iter_findings",
    "list_amendments",
    "load_amendment",
    "load_default_filing_profile",
    "m303_rectificativa_motive_producer_values",
    "modelo_record_repository_for_application",
    "project_m303_exonerado_390_value_arrival",
    "prove_export_conformance",
    "prove_secure_export_replay",
    "refresh_review_status",
    "render_envelope_prefix_field",
    "render_filing_envelope",
    "required_applicable_casilla_ids",
    "resolve_m303_filing_facts",
    "summarise_calculation",
    "try_record_filing_retention_snapshot",
    "unapprove_draft",
    "validate_m303_export_applicability",
    "verify_export",
]
