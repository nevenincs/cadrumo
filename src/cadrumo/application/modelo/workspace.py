"""The sole Modelo Workspace V1 assembly and dispatch entry point.

This module owns the one ordering-critical sequence every Workspace read must
follow: capture WORK exactly once, derive the REGISTRY coordinate only from
that captured :class:`~.work_addressing.ModeloWorkResolution`, then evaluate
the requested and stored revision axes independently against the SAME
REGISTRY capture through the sole pure assertion,
:func:`~.work_addressing.assert_work_target_revision`. Neither axis may ever
select the revision the other is judged by, and REGISTRY is never captured a
second time to answer a question the first capture already carries the
coordinates for.

Currently landed: the WORK-then-REGISTRY capture-and-assertion core
(:func:`resolve_modelo_workspace_revision_axes`), tested in isolation. The
full request/admission dispatch and the STATIC_INSPECTION and GRADED_SNAPSHOT
projection assemblies are NOT YET BUILT here; ``ModeloWorkspaceResolvedTargetV1``
also requires a ``review_status`` this module cannot yet source for the
STATIC_INSPECTION admission (see the exec record for the open question). Build
those once that is resolved -- do not infer the missing semantics.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core import RegistryAuthorityGrade, RegistrySchemaFamilyDisposition
from ...core.external_constants import OutputLanguage
from ...core.hashing import content_hash_hex
from ...domain.calculations.registry.errors import RegistryFailureCondition, RegistryValidationError
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.modelo_localization import casilla_occurrence_locale_key, revision_locale_key
from ...domain.calculations.registry.schema import (
    DataBindingDefinition,
    FormulaDefinition,
    ParameterDefinition,
    RegistrySnapshot,
    SchemaFamilyDispositionDeclaration,
)
from ...domain.calculations.registry.schema_formula import FormulaExpression
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition, RelationDefinition
from ...domain.calculations.registry.static_inspection import RegistryRevisionInspection
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol, VerificationReportCatalogueRepositoryProtocol
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState, CalculationSourceRef
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..ledger.preflight import LedgerPreflightIssue
from ..operator_actions import ActionReference
from ..registry.closure import RegistryClosureLimb
from ..state_projection import ModeloReadinessRequest, ProjectionModeloReadiness
from .work_addressing import (
    ModeloExactWorkUnitTarget,
    ModeloVisibleFilingTarget,
    ModeloWorkResolution,
    ModeloWorkSelectionMode,
    ModeloWorkSelectorRequest,
)
from .workspace_models import (
    ModeloWorkspaceEvidenceFactV1,
    ModeloWorkspaceTextFactValueV1,
    ModeloWorkspaceBaselineV1,
    ModeloWorkspaceBindingReferenceV1,
    ModeloWorkspaceBindingRequirementV1,
    ModeloWorkspaceBoundedFacetV1,
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceCapabilityV1,
    ModeloWorkspaceCasillaReferenceV1,
    ModeloWorkspaceConstraintReferenceV1,
    ModeloWorkspaceContributorIdentityV1,
    ModeloWorkspaceCursorV1,
    ModeloWorkspaceDomainRefusalV1,
    ModeloWorkspaceEvidenceHorizonV1,
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceFamilyDispositionV1,
    ModeloWorkspaceFormulaBindingOperandReferenceV1,
    ModeloWorkspaceFormulaCasillaOperandReferenceV1,
    ModeloWorkspaceFormulaDateBindingOperandReferenceV1,
    ModeloWorkspaceFormulaDispatchOperandReferenceV1,
    ModeloWorkspaceFormulaLiteralOperandReferenceV1,
    ModeloWorkspaceFormulaOperandReferenceV1,
    ModeloWorkspaceFormulaParameterOperandReferenceV1,
    ModeloWorkspaceFormulaReferenceV1,
    ModeloWorkspaceFormulaRelationOperandReferenceV1,
    ModeloWorkspaceGradedSnapshotResultV1,
    ModeloWorkspaceGradedSnapshotScopeV1,
    ModeloWorkspaceLedgerIssueV1,
    ModeloWorkspaceLedgerPeriodSubjectV1,
    ModeloWorkspaceLedgerTransactionSubjectV1,
    ModeloWorkspaceLocaleDisposition,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceLocalizedTextV1,
    ModeloWorkspaceMaterializationRecordV1,
    ModeloWorkspaceParameterReferenceV1,
    ModeloWorkspaceProfileRequirementV1,
    ModeloWorkspaceProjectionV1,
    ModeloWorkspaceProvenanceRecordV1,
    ModeloWorkspaceReadinessV1,
    ModeloWorkspaceRefusalCode,
    ModeloWorkspaceRefusedResultV1,
    ModeloWorkspaceRelationReferenceV1,
    ModeloWorkspaceRelationSourceEndpointReferenceV1,
    ModeloWorkspaceRelationTargetEndpointReferenceV1,
    ModeloWorkspaceRepeatedRowMaterializationRecordV1,
    ModeloWorkspaceRepeatedRowMaterializationV1,
    ModeloWorkspaceResolvedTargetV1,
    ModeloWorkspaceResultV1,
    ModeloWorkspaceRevisionAssertionDisposition,
    ModeloWorkspaceRevisionAssertionSource,
    ModeloWorkspaceRevisionAssertionV1,
    ModeloWorkspaceScalarMaterializationRecordV1,
    ModeloWorkspaceScalarMaterializationV1,
    ModeloWorkspaceSchemaClassification,
    ModeloWorkspaceSchemaIdentityV1,
    ModeloWorkspaceSchemaRecordV1,
    ModeloWorkspaceSnapshotScopeV1,
    ModeloWorkspaceStaticInspectionResultV1,
    ModeloWorkspaceStaticInspectionScopeV1,
    ModeloWorkspaceTargetV1,
    ModeloWorkspaceTechnicalLabelV1,
    ModeloWorkspaceWorkReviewFacetV1,
)
from .workspace_producers import (
    MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_CLOSURE_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_LOCALE_CATALOGUE_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_REGISTRY_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_WORK_PRODUCER_CONTRACT_V1,
    ModeloWorkspaceBoundedReviewPortV1,
    ModeloWorkspaceCalculationPortV1,
    ModeloWorkspaceClosurePortV1,
    ModeloWorkspaceContributingProjectionV1,
    ModeloWorkspaceEpochV1,
    ModeloWorkspaceFieldManifestPortV1,
    ModeloWorkspaceLocaleCataloguePortV1,
    ModeloWorkspaceProducerContractV1,
    ModeloWorkspaceProducerStampV1,
    ModeloWorkspaceReadinessPortV1,
    ModeloWorkspaceRegistryPortV1,
    ModeloWorkspaceRegistryProjectionV1,
    ModeloWorkspaceWorkPortV1,
)

if TYPE_CHECKING:
    from datetime import date

    from ...domain.calculations.registry.authority import ValidatedRegistryAuthority
    from ..registry.source_connectivity import SourceConnectivityCensusManifest


def modelo_work_selector_request_for_target(
    target: ModeloWorkspaceTargetV1,
    *,
    bucket_id: str,
) -> ModeloWorkSelectorRequest:
    """Project one Workspace target arm into the WORK capture's selector request.

    The Workspace-level target dataclasses already carry ``.to_work_address()``
    for the *legacy* single-read call sites, but Workspace's own WORK port
    captures over :class:`ModeloWorkSelectorRequest`, not
    :class:`~.work_addressing.ModeloWorkAddress` -- so the mapping is built
    directly from the target's own operands rather than round-tripping through
    the address shape.
    """
    if isinstance(target, ModeloWorkspaceExactWorkUnitTargetV1):
        exact: ModeloExactWorkUnitTarget = target.target
        return ModeloWorkSelectorRequest(
            work_unit_id=exact.work_unit_id,
            bucket_id=exact.bucket_id or bucket_id,
        )
    visible: ModeloVisibleFilingTarget = target.target
    return ModeloWorkSelectorRequest(
        modelo=ModeloCode(visible.modelo),
        filing_year=visible.filing_year,
        period=visible.period,
        revision_id=visible.registry_revision_id,
        bucket_id=visible.bucket_id or bucket_id,
    )


@dataclass(frozen=True, slots=True)
class ModeloWorkspaceRevisionAxes:
    """The law-determined revision plus both independently checked assertions.

    Carries the exact two :class:`ModeloWorkspaceRevisionAssertionV1` rows
    ``ModeloWorkspaceResolvedTargetV1`` requires, already in their final typed
    shape, so the caller assembling that record only has to plug them in.
    """

    law_selected_revision_id: str
    requested_revision_assertion: ModeloWorkspaceRevisionAssertionV1
    stored_revision_assertion: ModeloWorkspaceRevisionAssertionV1


def _revision_assertion(
    *,
    source: ModeloWorkspaceRevisionAssertionSource,
    asserted_revision_id: str | None,
    law_revision_id: str,
    mismatched_sources: set[ModeloWorkspaceRevisionAssertionSource],
) -> ModeloWorkspaceRevisionAssertionV1:
    if asserted_revision_id is None:
        disposition = ModeloWorkspaceRevisionAssertionDisposition.NOT_PRESENT
    elif source in mismatched_sources:
        disposition = ModeloWorkspaceRevisionAssertionDisposition.MISMATCHED
    else:
        disposition = ModeloWorkspaceRevisionAssertionDisposition.MATCHED
    return ModeloWorkspaceRevisionAssertionV1(
        source=source,
        disposition=disposition,
        asserted_revision_id=asserted_revision_id,
    )


def resolve_modelo_workspace_revision_axes(
    resolution: ModeloWorkResolution,
    *,
    registry_projection: ModeloWorkspaceRegistryProjectionV1,
) -> ModeloWorkspaceRevisionAxes:
    """Judge the requested and stored revision axes against one REGISTRY capture.

    ``resolution`` MUST be the WORK capture already taken for this same
    target; ``registry_projection`` MUST be the REGISTRY capture taken from
    the coordinates that resolution carries (``resolution.modelo``,
    ``resolution.filing_year``, ``resolution.period``) and from no other
    source. This function never captures REGISTRY itself -- it only evaluates
    the two axes against what the caller already captured.

    This function NEVER raises on a mismatch. ``ModeloWorkspaceRevisionAssertionV1``
    has a ``MISMATCHED`` disposition member precisely because the shared
    Workspace contract expects the mismatch surfaced as typed data, carried
    into ``ModeloWorkspaceRevisionMismatchRefusalV1`` by the assembly layer --
    an exception escaping here would destroy the very information that typed
    refusal exists to carry. A caller that wants the canonical translated
    mismatch text (for example to construct that refusal's prose) reuses the
    sole pure :func:`assert_work_target_revision` itself, over the same
    ``requested_revision_id`` / ``stored_revision_id`` / law revision triple
    this function computed its dispositions from; it is not called here.
    """
    requested_revision_id = resolution.requested_revision_id
    stored_revision_id = resolution.work_unit.revision_id if resolution.work_unit is not None else None

    law_revision_id = registry_projection.revision_id

    mismatched: set[ModeloWorkspaceRevisionAssertionSource] = set()
    for source, candidate in (
        (ModeloWorkspaceRevisionAssertionSource.REQUESTED, requested_revision_id),
        (ModeloWorkspaceRevisionAssertionSource.STORED, stored_revision_id),
    ):
        if candidate is not None and candidate.strip() != law_revision_id:
            mismatched.add(source)

    return ModeloWorkspaceRevisionAxes(
        law_selected_revision_id=law_revision_id,
        requested_revision_assertion=_revision_assertion(
            source=ModeloWorkspaceRevisionAssertionSource.REQUESTED,
            asserted_revision_id=requested_revision_id,
            law_revision_id=law_revision_id,
            mismatched_sources=mismatched,
        ),
        stored_revision_assertion=_revision_assertion(
            source=ModeloWorkspaceRevisionAssertionSource.STORED,
            asserted_revision_id=stored_revision_id,
            law_revision_id=law_revision_id,
            mismatched_sources=mismatched,
        ),
    )


def capture_modelo_workspace_target_captures(
    target: ModeloWorkspaceTargetV1,
    *,
    bucket_id: str,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
    authority: ValidatedRegistryAuthority,
    grade: RegistryAuthorityGrade | None = None,
) -> tuple[
    ModeloWorkspaceContributingProjectionV1[ModeloWorkResolution],
    ModeloWorkspaceContributingProjectionV1[ModeloWorkspaceRegistryProjectionV1],
    ModeloWorkspaceRevisionAxes,
]:
    """Capture WORK exactly once, then REGISTRY exactly once from its coordinates.

    Returns the full stamped-and-epoched captures, not just their bare
    projections, so a baseline assembler can fold the WORK/REGISTRY
    contributor stamps and epochs into its consistency digest without a
    second capture of either.

    This is the ordering-critical sequence itself: WORK is resolved first, its
    ``(modelo, filing_year, period)`` is read back to build the REGISTRY port
    -- never the target's own operands, which may name an exact work unit with
    no natural coordinates of their own -- and REGISTRY is captured exactly
    once from that single WORK-derived coordinate. ``grade=None`` (the
    default) requests STATIC_INSPECTION admission
    (``RegistryRevisionInspection``); passing a :class:`RegistryAuthorityGrade`
    requests GRADED_SNAPSHOT admission (``RegistrySnapshot``) through the
    exact same port and the exact same WORK-then-REGISTRY ordering -- the two
    admissions differ only in which authority object the one REGISTRY read
    returns, never in how many reads happen or in what order.
    """
    request = modelo_work_selector_request_for_target(target, bucket_id=bucket_id)
    work_port = ModeloWorkspaceWorkPortV1(
        request=request,
        catalogue_repository=catalogue_repository,
        mode=ModeloWorkSelectionMode.VISIBLE_OR_EXACT,
    )
    work_capture = work_port.capture_projection_with_epoch()
    resolution = work_capture.projection
    assert resolution.modelo is not None
    assert resolution.filing_year is not None
    assert resolution.period is not None

    registry_port = ModeloWorkspaceRegistryPortV1(
        authority=authority,
        modelo_id=resolution.modelo,
        filing_year=resolution.filing_year,
        period=resolution.period.registry_token,
        grade=grade,
    )
    registry_capture = registry_port.capture_projection_with_epoch()
    registry_projection = registry_capture.projection

    axes = resolve_modelo_workspace_revision_axes(resolution, registry_projection=registry_projection)
    return work_capture, registry_capture, axes


def capture_modelo_workspace_target_axes(
    target: ModeloWorkspaceTargetV1,
    *,
    bucket_id: str,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
    authority: ValidatedRegistryAuthority,
) -> tuple[ModeloWorkResolution, ModeloWorkspaceRegistryProjectionV1, ModeloWorkspaceRevisionAxes]:
    """Capture WORK exactly once, then REGISTRY exactly once from its coordinates.

    Thin convenience wrapper over :func:`capture_modelo_workspace_target_captures`
    exposing only the two bare projections plus the axes -- the shape every
    existing caller in this module already consumes. A caller that also needs
    the WORK/REGISTRY stamps and epochs (baseline assembly) calls the richer
    function directly instead of re-capturing.
    """
    work_capture, registry_capture, axes = capture_modelo_workspace_target_captures(
        target,
        bucket_id=bucket_id,
        catalogue_repository=catalogue_repository,
        authority=authority,
    )
    return work_capture.projection, registry_capture.projection, axes


def resolve_modelo_workspace_target(
    target: ModeloWorkspaceTargetV1,
    *,
    bucket_id: str,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
    authority: ValidatedRegistryAuthority,
) -> ModeloWorkspaceResolvedTargetV1:
    """Capture WORK-then-REGISTRY and assemble the shared resolved-target record.

    This is the shared shape both admissions build their projection or
    refusal on top of. It carries no mismatch judgement of its own beyond
    what ``ModeloWorkspaceRevisionAxes`` already computed: a caller finding
    either assertion at ``MISMATCHED`` builds
    ``ModeloWorkspaceRevisionMismatchRefusalV1`` from this same record rather
    than treating the mismatch as an exception -- this function never raises
    for a revision mismatch.
    """
    resolution, registry_projection, axes = capture_modelo_workspace_target_axes(
        target,
        bucket_id=bucket_id,
        catalogue_repository=catalogue_repository,
        authority=authority,
    )
    work_unit = resolution.work_unit
    assert resolution.modelo is not None
    assert resolution.filing_year is not None
    assert resolution.period is not None
    return ModeloWorkspaceResolvedTargetV1(
        bucket_id=resolution.bucket_id,
        modelo=resolution.modelo,
        filing_year=resolution.filing_year,
        period=resolution.period,
        law_selected_revision_id=axes.law_selected_revision_id,
        review_status=registry_projection.review_status,
        requested_revision_assertion=axes.requested_revision_assertion,
        stored_revision_assertion=axes.stored_revision_assertion,
        work_unit_id=work_unit.work_unit_id if work_unit is not None else None,
        work_state=work_unit.state if work_unit is not None else None,
    )


def _resolve_locale_summary_and_value(
    key: str,
    *,
    output_language: OutputLanguage,
) -> tuple[ModeloWorkspaceLocaleSummaryV1, str | None]:
    """Resolve one canonical locale coordinate plus its text value, for any key.

    Shared by the revision-level summary (:func:`capture_modelo_workspace_locale_summary`)
    and any per-record label resolution (schema_facet). Spanish is the source
    language for every catalogue entry (``aeat-locales-cli``), so a requested
    language whose own key is absent falls back to Spanish rather than to an
    arbitrary third language; Spanish absent as well is the suppressed floor,
    never a missing key propagated as an exception. The returned value is
    ``None`` only when even the Spanish source is absent -- callers needing a
    non-empty display string treat that as a distinct refusal, never a blank.
    """
    requested = ModeloWorkspaceLocaleCataloguePortV1(
        translation_key=key,
        locale=output_language.value,
    ).capture_projection_with_epoch()
    if requested.projection.value is not None:
        return (
            ModeloWorkspaceLocaleSummaryV1(
                requested_language=output_language,
                resolved_language=output_language,
                disposition=ModeloWorkspaceLocaleDisposition.EXACT,
                catalogue_digest=requested.projection.catalogue_digest,
            ),
            requested.projection.value,
        )
    if output_language is OutputLanguage.ES:
        return (
            ModeloWorkspaceLocaleSummaryV1(
                requested_language=output_language,
                resolved_language=OutputLanguage.ES,
                disposition=ModeloWorkspaceLocaleDisposition.SUPPRESSED,
                catalogue_digest=requested.projection.catalogue_digest,
            ),
            None,
        )
    spanish = ModeloWorkspaceLocaleCataloguePortV1(
        translation_key=key,
        locale=OutputLanguage.ES.value,
    ).capture_projection_with_epoch()
    disposition = (
        ModeloWorkspaceLocaleDisposition.SPANISH_FALLBACK
        if spanish.projection.value is not None
        else ModeloWorkspaceLocaleDisposition.SUPPRESSED
    )
    return (
        ModeloWorkspaceLocaleSummaryV1(
            requested_language=output_language,
            resolved_language=OutputLanguage.ES,
            disposition=disposition,
            catalogue_digest=spanish.projection.catalogue_digest,
        ),
        spanish.projection.value,
    )


def capture_modelo_workspace_locale_summary(
    resolved_target: ModeloWorkspaceResolvedTargetV1,
    *,
    output_language: OutputLanguage,
) -> ModeloWorkspaceLocaleSummaryV1:
    """Resolve the canonical locale coordinate for one resolved Workspace target.

    Tests the resolved target's own revision-level display key
    (:func:`revision_locale_key`) through the sole LOCALE_CATALOGUE port. This
    is the natural per-read canonical key -- one Workspace read names exactly
    one ``(modelo, revision)`` pair, and that pair's own display label is a
    key every Workspace read already needs regardless of which facet a caller
    goes on to request.
    """
    key = revision_locale_key(resolved_target.modelo, resolved_target.law_selected_revision_id)
    summary, _value = _resolve_locale_summary_and_value(key, output_language=output_language)
    return summary


# Canonical capability and refusal facade: the
# capability-to-producer mapping is fixed by which of the eight contributors
# static inspection structurally never reads ("Static inspection captures
# exactly registry, work, locale_catalogue, and field_manifest; it does not
# read bounded_review, calculation, readiness, or closure"), not by matching
# enum spellings. Every one of those four excluded contributors is UNMEASURED
# for this admission per the ADR's own rule -- "absence of a producer... is
# unmeasured, never available" -- which the ADR amendment clarifies covers an
# admission-structural exclusion, not only a graded producer that ran and
# declined to answer. NOT_APPLICABLE was the wrong disposition for this case;
# it is reserved for a producer that DID run and declared the fact
# inapplicable to the specific target.
#
# SCHEMA_INSPECTION is AVAILABLE (static inspection has its
# own field-manifest root, generate_modelo_workspace_field_manifest_for_inspection):
# field_manifest is a real contributor for this admission, so schema_inspection
# is the one capability static inspection answers AVAILABLE for.
_STATIC_INSPECTION_CAPABILITY_DISPOSITIONS: tuple[
    tuple[ModeloWorkspaceCapabilityName, ModeloWorkspaceProducerContractV1, ModeloWorkspaceCapabilityDisposition],
    ...,
] = (
    (
        ModeloWorkspaceCapabilityName.SCHEMA_INSPECTION,
        MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1,
        ModeloWorkspaceCapabilityDisposition.AVAILABLE,
    ),
    (
        ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION,
        MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1,
        ModeloWorkspaceCapabilityDisposition.UNMEASURED,
    ),
    (
        ModeloWorkspaceCapabilityName.VERIFICATION_READINESS,
        MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1,
        ModeloWorkspaceCapabilityDisposition.UNMEASURED,
    ),
    (
        ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS,
        MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1,
        ModeloWorkspaceCapabilityDisposition.UNMEASURED,
    ),
    (
        ModeloWorkspaceCapabilityName.FILING_EXPORT_READINESS,
        MODELO_WORKSPACE_CLOSURE_PRODUCER_CONTRACT_V1,
        ModeloWorkspaceCapabilityDisposition.UNMEASURED,
    ),
)


def static_inspection_modelo_workspace_capabilities(
    resolved_target: ModeloWorkspaceResolvedTargetV1,
) -> tuple[ModeloWorkspaceCapabilityV1, ...]:
    """Return the complete STATIC_INSPECTION capability denominator.

    Every row cites the capability's own canonical producer contributor per
    the canonical capability mapping; see the module-level comment above this function.
    ``schema_inspection`` is ``AVAILABLE`` -- field_manifest is a real
    STATIC_INSPECTION contributor. The other four are ``UNMEASURED``:
    their producers are contributors this admission structurally never reads.
    GRADED_SNAPSHOT's dispositions are a distinct, not-yet-answered question
    and MUST NOT be derived from this table.
    """
    return tuple(
        ModeloWorkspaceCapabilityV1(
            capability=capability,
            disposition=disposition,
            target=resolved_target,
            selected_revision_id=resolved_target.law_selected_revision_id,
            producer_owner=contract.contributor.owner,
            producer=contract.contributor.producer,
        )
        for capability, contract, disposition in _STATIC_INSPECTION_CAPABILITY_DISPOSITIONS
    )


def graded_snapshot_modelo_workspace_capabilities(
    resolved_target: ModeloWorkspaceResolvedTargetV1,
    *,
    calculation_revision: CalculationRevision | None,
) -> tuple[ModeloWorkspaceCapabilityV1, ...]:
    """Return the complete GRADED_SNAPSHOT capability denominator.

    ``available`` requires reading what a canonical producer WROTE,
    never deriving a verdict from downstream state. Per capability:

    - ``SCHEMA_INSPECTION`` is ``AVAILABLE`` unconditionally, same as
      STATIC_INSPECTION -- a deterministic generated denominator, not a
      producer-verdict question.
    - ``CALCULATION_MATERIALIZATION`` is ``AVAILABLE`` when a
      :class:`CalculationRevision` exists for the target's EXACT coordinate
      (``calculation_revision.work_unit_id == resolved_target.work_unit_id``,
      which is itself content-addressed on bucket/modelo/year/period/revision) --
      reading the calculate producer's own persisted object, never deriving
      "materialized" from e.g. non-empty ``casilla_values``.
    - ``VERIFICATION_READINESS`` is ``AVAILABLE`` when that same revision's
      ``state`` is ``VERIFICADO_COMPLETO``, a state the model itself only
      reaches with required ``verified_at``/``verified_by`` present -- a
      genuine separately-stamped verdict from the canonical verify producer.
    - ``FILING_DRAFT_READINESS`` is PERMANENTLY ``UNMEASURED``.
      :func:`~cadrumo.application.filing.build_draft` is pure and stateless:
      it persists nothing, emits no event, stamps no revision field. There is
      no producer to read a verdict FROM, and calling it to see whether it
      raises would be exactly the derivation this rule forbids. This is a
      structural finding, not a placeholder pending future wiring here -- see
      the producer-authority rule above.
    - ``FILING_EXPORT_READINESS`` is ``UNMEASURED`` pending a producer port:
      the approved stamp is a ``MODELO_EXPORTED`` bucket event carrying the
      exact revision id, but no declared contributor currently reads bucket event
      history, so this capability cannot yet cite a captured, epoch-safe
      projection the way the other four do. Wiring a ninth contributor is out
      of this change's scope; see the producer-authority rule above.
    """
    calculation_available = (
        calculation_revision is not None and calculation_revision.work_unit_id == resolved_target.work_unit_id
    )
    verification_available = (
        calculation_available
        and calculation_revision is not None
        and (calculation_revision.state is CalculationRevisionState.VERIFICADO_COMPLETO)
    )
    dispositions: tuple[
        tuple[ModeloWorkspaceCapabilityName, ModeloWorkspaceProducerContractV1, ModeloWorkspaceCapabilityDisposition],
        ...,
    ] = (
        (
            ModeloWorkspaceCapabilityName.SCHEMA_INSPECTION,
            MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1,
            ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        ),
        (
            ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION,
            MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1,
            ModeloWorkspaceCapabilityDisposition.AVAILABLE
            if calculation_available
            else ModeloWorkspaceCapabilityDisposition.UNMEASURED,
        ),
        (
            ModeloWorkspaceCapabilityName.VERIFICATION_READINESS,
            MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1,
            ModeloWorkspaceCapabilityDisposition.AVAILABLE
            if verification_available
            else ModeloWorkspaceCapabilityDisposition.UNMEASURED,
        ),
        (
            ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS,
            MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1,
            ModeloWorkspaceCapabilityDisposition.UNMEASURED,
        ),
        (
            ModeloWorkspaceCapabilityName.FILING_EXPORT_READINESS,
            MODELO_WORKSPACE_CLOSURE_PRODUCER_CONTRACT_V1,
            ModeloWorkspaceCapabilityDisposition.UNMEASURED,
        ),
    )
    return tuple(
        ModeloWorkspaceCapabilityV1(
            capability=capability,
            disposition=disposition,
            target=resolved_target,
            selected_revision_id=resolved_target.law_selected_revision_id,
            producer_owner=contract.contributor.owner,
            producer=contract.contributor.producer,
        )
        for capability, contract, disposition in dispositions
    )


__all__ = [
    "STATIC_INSPECTION_WORK_REVIEW_FACET",
    "ModeloWorkspaceMaterializationProvenanceMissingError",
    "ModeloWorkspaceRevisionAxes",
    "ModeloWorkspaceStaleCursorError",
    "binding_schema_records",
    "capture_modelo_workspace_locale_summary",
    "capture_modelo_workspace_target_axes",
    "capture_modelo_workspace_target_captures",
    "formula_expression_operand_references",
    "formula_operand_references_for_casilla",
    "formula_schema_records",
    "graded_snapshot_casilla_schema_records",
    "graded_snapshot_closure_limbs",
    "graded_snapshot_contributors",
    "graded_snapshot_evidence_horizon",
    "graded_snapshot_family_dispositions",
    "graded_snapshot_materialization_facet",
    "graded_snapshot_modelo_workspace_capabilities",
    "graded_snapshot_provenance_facet",
    "graded_snapshot_readiness",
    "graded_snapshot_schema_records",
    "modelo_work_selector_request_for_target",
    "paginate_modelo_workspace_facet",
    "parameter_schema_records",
    "relation_schema_records",
    "relation_source_endpoints_for_casilla",
    "relation_target_endpoints_for_binding",
    "resolve_graded_snapshot_baseline",
    "resolve_graded_snapshot_result",
    "resolve_graded_snapshot_schema_identity",
    "resolve_modelo_workspace_revision_axes",
    "resolve_modelo_workspace_target",
    "resolve_static_inspection_baseline",
    "resolve_static_inspection_result",
    "resolve_static_inspection_schema_identity",
    "static_inspection_casilla_schema_records",
    "static_inspection_contributors",
    "static_inspection_evidence_horizon",
    "static_inspection_family_dispositions",
    "static_inspection_modelo_workspace_capabilities",
    "static_inspection_schema_records",
]


# --- Schema, materialization and provenance projection:
# schema-record join semantics, each derived from the
# registry's own declared edge direction ---


def formula_expression_operand_references(
    formula_id: str,
    expression: FormulaExpression,
) -> tuple[ModeloWorkspaceFormulaOperandReferenceV1, ...]:
    """Walk one formula's own declared expression tree for every operand it reads.

    ``FormulaExpression`` is a self-recursive registry-declared tree: an
    operator node carries ``args``, a leaf carries exactly one populated
    identity field. This walks that exact structure and needs no inference --
    every operand kind maps 1:1 to the leaf field the registry already names
    it by (``casilla_id``, ``binding``, ``date_binding``, ``parameter``,
    ``relation``, ``literal``, ``dispatch_table``).

    This is the INPUT direction only: which identities this formula's own
    expression reads. The OUTPUT direction (which casilla this formula
    produces) is ``FormulaDefinition.target_casilla_id`` and is a
    provenance-facet concern ("Provenance is projected from the canonical
    calculation-source graph"), never a schema-record field -- the schema
    record's plural, multi-kind-discriminated ``formula_operands`` field
    exists to carry exactly this INPUT set, not the single producing edge.
    """
    if expression.op is not None:
        references: list[ModeloWorkspaceFormulaOperandReferenceV1] = []
        for arg in expression.args:
            references.extend(formula_expression_operand_references(formula_id, arg))
        return tuple(references)
    if expression.casilla_id is not None:
        return (
            ModeloWorkspaceFormulaCasillaOperandReferenceV1(formula_id=formula_id, casilla_id=expression.casilla_id),
        )
    if expression.binding is not None:
        return (ModeloWorkspaceFormulaBindingOperandReferenceV1(formula_id=formula_id, binding_id=expression.binding),)
    if expression.date_binding is not None:
        return (
            ModeloWorkspaceFormulaDateBindingOperandReferenceV1(
                formula_id=formula_id,
                binding_id=expression.date_binding,
            ),
        )
    if expression.parameter is not None:
        return (
            ModeloWorkspaceFormulaParameterOperandReferenceV1(formula_id=formula_id, parameter_id=expression.parameter),
        )
    if expression.relation is not None:
        return (
            ModeloWorkspaceFormulaRelationOperandReferenceV1(formula_id=formula_id, relation_id=expression.relation),
        )
    if expression.literal is not None:
        return (ModeloWorkspaceFormulaLiteralOperandReferenceV1(formula_id=formula_id),)
    if expression.dispatch_table is not None:
        return (
            ModeloWorkspaceFormulaDispatchOperandReferenceV1(
                formula_id=formula_id,
                parameter_ids=tuple(sorted(expression.dispatch_table.values())),
            ),
        )
    return ()


def formula_operand_references_for_casilla(
    formulas: tuple[FormulaDefinition, ...],
    casilla_id: str,
) -> tuple[ModeloWorkspaceFormulaCasillaOperandReferenceV1, ...]:
    """Return every formula-operand entry naming ``casilla_id`` as an INPUT.

    Deliberately never includes the formula whose ``target_casilla_id``
    equals ``casilla_id`` unless that same formula's own expression also
    reads ``casilla_id`` as an operand (a self-referential formula) -- being
    the OUTPUT of a formula is a different edge from being an INPUT to one,
    and this function answers only the input question.
    """
    matches: list[ModeloWorkspaceFormulaCasillaOperandReferenceV1] = []
    for formula in formulas:
        for reference in formula_expression_operand_references(formula.id, formula.expression):
            if (
                isinstance(reference, ModeloWorkspaceFormulaCasillaOperandReferenceV1)
                and reference.casilla_id == casilla_id
            ):
                matches.append(reference)
    return tuple(matches)


def relation_source_endpoints_for_casilla(
    relations: tuple[RelationDefinition, ...],
    casilla_id: str,
) -> tuple[ModeloWorkspaceRelationSourceEndpointReferenceV1, ...]:
    """Return the relation-source-endpoint rows whose declared source casilla matches.

    ``RelationDefinition.source_casilla_id`` names the source side
    explicitly; no inference is needed.
    """
    return tuple(
        ModeloWorkspaceRelationSourceEndpointReferenceV1(relation_id=relation.id, casilla_id=relation.source_casilla_id)
        for relation in relations
        if relation.source_casilla_id == casilla_id
    )


def relation_target_endpoints_for_binding(
    relations: tuple[RelationDefinition, ...],
    binding_id: str,
) -> tuple[ModeloWorkspaceRelationTargetEndpointReferenceV1, ...]:
    """Return the relation-target-endpoint rows whose declared target binding matches.

    ``RelationDefinition.target_binding`` names the target side explicitly;
    no inference is needed.
    """
    return tuple(
        ModeloWorkspaceRelationTargetEndpointReferenceV1(relation_id=relation.id, binding_id=relation.target_binding)
        for relation in relations
        if relation.target_binding == binding_id
    )


def resolve_static_inspection_schema_identity(
    inspection: RegistryRevisionInspection,
) -> ModeloWorkspaceSchemaIdentityV1:
    """Build the STATIC_INSPECTION schema identity from the one REGISTRY capture already held.

    ``schema_fingerprint`` is a content digest over the inspection's own
    declared identity sets (casilla and binding ids) -- the same shape
    ``_edit_services.py`` uses for its own, differently-typed
    ``ModeloEditSchemaIdentityV1`` (interface-ADR-governed), adapted to the
    flatter STATIC_INSPECTION type. ``field_manifest_digest`` is exclusively
    the inspection-rooted field manifest's own digest; the edit
    contract's ``CalculationCompletenessManifest`` digest has its own field
    (``completeness_manifest_digest``) on its own type and no longer shares
    this one.
    """
    field_manifest_port = ModeloWorkspaceFieldManifestPortV1(authority=inspection)
    field_manifest_capture = field_manifest_port.capture_projection_with_epoch()
    return ModeloWorkspaceSchemaIdentityV1(
        schema_id=f"modelo-{inspection.modelo_id}-{inspection.revision_id}".lower(),
        schema_fingerprint=content_hash_hex(
            {
                "casilla_ids": sorted(inspection.casilla_ids),
                "binding_ids": sorted(inspection.binding_ids),
            }
        ),
        field_manifest_digest=field_manifest_capture.projection.manifest_digest,
    )


def static_inspection_evidence_horizon(inspection: RegistryRevisionInspection) -> ModeloWorkspaceEvidenceHorizonV1:
    """Build the evidence horizon straight from the inspection's own retained source catalogue."""
    source_refs = tuple(sorted(inspection.source_ref_ids))
    return ModeloWorkspaceEvidenceHorizonV1(
        source_refs=source_refs,
        evidence_digest=content_hash_hex({"source_refs": source_refs}),
    )


def static_inspection_contributors() -> tuple[ModeloWorkspaceContributorIdentityV1, ...]:
    """Return the four contributor identities STATIC_INSPECTION actually reads.

    Matches the ADR's own admission-scope sentence exactly: "Static inspection
    captures exactly registry, work, locale_catalogue, and field_manifest."
    """
    return tuple(
        sorted(
            (
                MODELO_WORKSPACE_WORK_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_LOCALE_CATALOGUE_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_REGISTRY_PRODUCER_CONTRACT_V1.contributor,
            ),
            key=lambda contributor: (contributor.owner, contributor.producer),
        )
    )


def resolve_graded_snapshot_schema_identity(snapshot: RegistrySnapshot) -> ModeloWorkspaceSchemaIdentityV1:
    """Build the GRADED_SNAPSHOT schema identity from the one REGISTRY capture already held.

    Mirrors ``resolve_static_inspection_schema_identity``'s exact shape, over
    the snapshot's own declared identity sets. Unlike the inspection (which
    carries ``casilla_ids``/``binding_ids`` as bare id frozensets), the
    snapshot's ``revision.casillas``/``.bindings`` are full definition
    tuples; the fingerprint reduces them to the same id-set shape so
    the two admissions' schema fingerprints are comparable in kind.
    """
    field_manifest_port = ModeloWorkspaceFieldManifestPortV1(authority=snapshot)
    field_manifest_capture = field_manifest_port.capture_projection_with_epoch()
    return ModeloWorkspaceSchemaIdentityV1(
        schema_id=f"modelo-{snapshot.modelo.id}-{snapshot.revision.id}".lower(),
        schema_fingerprint=content_hash_hex(
            {
                "casilla_ids": sorted(casilla.id for casilla in snapshot.revision.casillas),
                "binding_ids": sorted(binding.id for binding in snapshot.revision.bindings),
            }
        ),
        field_manifest_digest=field_manifest_capture.projection.manifest_digest,
    )


def graded_snapshot_evidence_horizon(snapshot: RegistrySnapshot) -> ModeloWorkspaceEvidenceHorizonV1:
    """Build the evidence horizon straight from the snapshot's own retained source catalogue.

    ``RegistrySnapshot.sources`` is the graded-admission equivalent of
    ``RegistryRevisionInspection.source_ref_ids``: a mapping keyed by the same
    ``SourceRefId`` identity, so ``frozenset(snapshot.sources)`` gives the
    identical shape ``static_inspection_evidence_horizon`` reduces to.
    """
    source_refs = tuple(sorted(snapshot.sources))
    return ModeloWorkspaceEvidenceHorizonV1(
        source_refs=source_refs,
        evidence_digest=content_hash_hex({"source_refs": source_refs}),
    )


def graded_snapshot_contributors() -> tuple[ModeloWorkspaceContributorIdentityV1, ...]:
    """Return the eight contributor identities GRADED_SNAPSHOT actually reads.

    The same four STATIC_INSPECTION reads (registry, work, locale_catalogue,
    field_manifest) plus CALCULATION, BOUNDED_REVIEW, READINESS and CLOSURE --
    the complete registered contributor set. ``work_review`` is a required
    field on ``ModeloWorkspaceProjectionV1`` and GRADED_SNAPSHOT is the one
    ELIGIBLE admission for the real ``ModeloWorkReview`` (STATIC_INSPECTION
    gets the fixed ``UNMEASURED`` constant instead), so BOUNDED_REVIEW belongs
    in this denominator alongside CALCULATION; READINESS and CLOSURE populate
    the projection's ``readiness`` and ``registry_closure_limbs``, which are
    graded-only facts STATIC_INSPECTION never reads.

    This denominator is what every facet revalidates against, so it must state
    the reads that actually happen: a contributor omitted here is not merely an
    unpopulated field, it is a contributor tuple and epoch digest that under-
    report the assembly they pin.
    """
    return tuple(
        sorted(
            (
                MODELO_WORKSPACE_WORK_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_LOCALE_CATALOGUE_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_REGISTRY_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_CLOSURE_PRODUCER_CONTRACT_V1.contributor,
            ),
            key=lambda contributor: (contributor.owner, contributor.producer),
        )
    )


STATIC_INSPECTION_WORK_REVIEW_FACET = ModeloWorkspaceWorkReviewFacetV1(
    disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
    review=None,
)
"""STATIC_INSPECTION never reads bounded_review; this is the fixed, non-varying facet value."""


def resolve_static_inspection_baseline(
    target: ModeloWorkspaceResolvedTargetV1,
    *,
    schema_identity: ModeloWorkspaceSchemaIdentityV1,
    locale: ModeloWorkspaceLocaleSummaryV1,
    work_stamp: ModeloWorkspaceProducerStampV1,
    work_epoch: ModeloWorkspaceEpochV1,
    registry_stamp: ModeloWorkspaceProducerStampV1,
    registry_epoch: ModeloWorkspaceEpochV1,
    locale_stamp: ModeloWorkspaceProducerStampV1,
    locale_epoch: ModeloWorkspaceEpochV1,
    field_manifest_stamp: ModeloWorkspaceProducerStampV1,
    field_manifest_epoch: ModeloWorkspaceEpochV1,
) -> ModeloWorkspaceBaselineV1:
    """Assemble the STATIC_INSPECTION baseline from the four contributors' own stamps and epochs.

    Every stamp/epoch pair passed in MUST come from the exact same captures
    that produced ``target``, ``schema_identity`` and ``locale`` -- this
    function performs no capture of its own, only digesting what the caller
    already atomically observed.
    """
    stamps = (work_stamp, registry_stamp, locale_stamp, field_manifest_stamp)
    epochs = (work_epoch, registry_epoch, locale_epoch, field_manifest_epoch)
    contributor_stamp_digest = content_hash_hex([stamp.model_dump(mode="json") for stamp in stamps])
    contributor_epoch_digest = content_hash_hex([epoch.model_dump(mode="json") for epoch in epochs])
    token = content_hash_hex(
        {
            "contributor_stamp_digest": contributor_stamp_digest,
            "contributor_epoch_digest": contributor_epoch_digest,
            "target": target.model_dump(mode="json"),
            "selected_revision_id": target.law_selected_revision_id,
            "schema_identity": schema_identity.model_dump(mode="json"),
            "locale_catalogue_digest": locale.catalogue_digest,
        }
    )
    return ModeloWorkspaceBaselineV1(
        token=token,
        contributor_stamp_digest=contributor_stamp_digest,
        contributor_epoch_digest=contributor_epoch_digest,
        target=target,
        selected_revision_id=target.law_selected_revision_id,
        schema_identity=schema_identity,
        locale_catalogue_digest=locale.catalogue_digest,
    )


def resolve_graded_snapshot_baseline(
    target: ModeloWorkspaceResolvedTargetV1,
    *,
    schema_identity: ModeloWorkspaceSchemaIdentityV1,
    locale: ModeloWorkspaceLocaleSummaryV1,
    work_stamp: ModeloWorkspaceProducerStampV1,
    work_epoch: ModeloWorkspaceEpochV1,
    registry_stamp: ModeloWorkspaceProducerStampV1,
    registry_epoch: ModeloWorkspaceEpochV1,
    locale_stamp: ModeloWorkspaceProducerStampV1,
    locale_epoch: ModeloWorkspaceEpochV1,
    field_manifest_stamp: ModeloWorkspaceProducerStampV1,
    field_manifest_epoch: ModeloWorkspaceEpochV1,
    calculation_stamp: ModeloWorkspaceProducerStampV1,
    calculation_epoch: ModeloWorkspaceEpochV1,
    bounded_review_stamp: ModeloWorkspaceProducerStampV1,
    bounded_review_epoch: ModeloWorkspaceEpochV1,
    readiness_stamp: ModeloWorkspaceProducerStampV1,
    readiness_epoch: ModeloWorkspaceEpochV1,
    closure_stamp: ModeloWorkspaceProducerStampV1,
    closure_epoch: ModeloWorkspaceEpochV1,
) -> ModeloWorkspaceBaselineV1:
    """Assemble the GRADED_SNAPSHOT baseline from the eight contributors' own stamps and epochs.

    Mirrors ``resolve_static_inspection_baseline`` exactly, over the wider
    GRADED_SNAPSHOT contributor set (the four static ones plus CALCULATION,
    BOUNDED_REVIEW, READINESS and CLOSURE). It is a sibling function, not a
    parameterization of the static one: that function's arity is fixed at
    exactly four named pairs and cannot accept further pairs without a
    signature change. Every stamp/epoch pair passed
    in MUST come from the exact same captures that produced ``target``,
    ``schema_identity`` and ``locale`` -- this function performs no capture
    of its own, only digesting what the caller already atomically observed.
    A mid-assembly change to any one contributor changes its stamp or epoch,
    which changes ``contributor_stamp_digest``/``contributor_epoch_digest``,
    which changes the pinned baseline -- an inconsistent mix can never
    silently produce the same baseline as a consistent one.
    """
    stamps = (
        work_stamp,
        registry_stamp,
        locale_stamp,
        field_manifest_stamp,
        calculation_stamp,
        bounded_review_stamp,
        readiness_stamp,
        closure_stamp,
    )
    epochs = (
        work_epoch,
        registry_epoch,
        locale_epoch,
        field_manifest_epoch,
        calculation_epoch,
        bounded_review_epoch,
        readiness_epoch,
        closure_epoch,
    )
    contributor_stamp_digest = content_hash_hex([stamp.model_dump(mode="json") for stamp in stamps])
    contributor_epoch_digest = content_hash_hex([epoch.model_dump(mode="json") for epoch in epochs])
    token = content_hash_hex(
        {
            "contributor_stamp_digest": contributor_stamp_digest,
            "contributor_epoch_digest": contributor_epoch_digest,
            "target": target.model_dump(mode="json"),
            "selected_revision_id": target.law_selected_revision_id,
            "schema_identity": schema_identity.model_dump(mode="json"),
            "locale_catalogue_digest": locale.catalogue_digest,
        }
    )
    return ModeloWorkspaceBaselineV1(
        token=token,
        contributor_stamp_digest=contributor_stamp_digest,
        contributor_epoch_digest=contributor_epoch_digest,
        target=target,
        selected_revision_id=target.law_selected_revision_id,
        schema_identity=schema_identity,
        locale_catalogue_digest=locale.catalogue_digest,
    )


class ModeloWorkspaceStaleCursorError(ValueError):
    """Raised when a cursor's pinned coordinate no longer matches the current baseline.

    A stale cursor MUST refuse rather than silently return a different page:
    resuming it against data that moved would return records the caller did
    not ask for and has no way to detect.
    """


class ModeloWorkspaceMaterializationProvenanceMissingError(ValueError):
    """Raised when a repeated-row materialization value carries no provenance entry.

    ``CalculationRevision`` itself enforces
    ``set(row_casilla_values) == set(row_casilla_provenance)`` at construction,
    so this shape can never reach the facet through normal validated
    construction; the check exists as a belt-and-suspenders refusal the
    facet owns itself, never a silent fabricated grouping.
    """


def static_inspection_casilla_schema_records(
    inspection: RegistryRevisionInspection,
    target: ModeloWorkspaceResolvedTargetV1,
    *,
    output_language: OutputLanguage,
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per casilla identity, sorted for stable pagination.

    Bounded to identity: ``legal_refs`` and ``constraints`` are
    ``None`` (this admission's producer never carries `CasillaDefinition`
    data), never ``()``. ``formula_operands`` and ``relation_endpoints``
    consume the shared join functions directly rather than re-deriving either
    edge here.
    """
    formulas = inspection.formulas
    relations = inspection.relations
    records: list[ModeloWorkspaceSchemaRecordV1] = []
    for casilla_id in sorted(inspection.casilla_ids):
        key = casilla_occurrence_locale_key(target.modelo, target.law_selected_revision_id, casilla_id, "label")
        locale_summary, value = _resolve_locale_summary_and_value(key, output_language=output_language)
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceCasillaReferenceV1(casilla_id=casilla_id),
                record_family=("casillas",),
                data_type="casilla_id",
                label=ModeloWorkspaceLocalizedTextV1(
                    locale_key=key,
                    value=value if value is not None else casilla_id,
                    locale=locale_summary,
                ),
                classification=ModeloWorkspaceSchemaClassification.PROJECTED,
                family_disposition=RegistrySchemaFamilyDisposition.POPULATED,
                legal_refs=None,
                constraints=None,
                formula_operands=formula_operand_references_for_casilla(formulas, casilla_id),
                relation_endpoints=relation_source_endpoints_for_casilla(relations, casilla_id),
            )
        )
    return tuple(records)


def graded_snapshot_casilla_schema_records(
    casillas: tuple[CasillaDefinition, ...],
    formulas: tuple[FormulaDefinition, ...],
    relations: tuple[RelationDefinition, ...],
    target: ModeloWorkspaceResolvedTargetV1,
    *,
    output_language: OutputLanguage,
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per casilla DEFINITION, sorted for stable pagination.

    A ``RegistrySnapshot`` carries the full ``CasillaDefinition`` --
    including ``legal_refs`` and ``constraints`` -- that
    ``RegistryRevisionInspection`` deliberately excludes. This is the
    richer half the ``None``-vs-``()`` arms were designed to
    accommodate: ``legal_refs`` is the definition's own real tuple, and
    ``constraints`` is a single self-referential
    :class:`ModeloWorkspaceConstraintReferenceV1` when the definition
    declares a ``CasillaConstraints`` block, empty when it declares none --
    never ``None``, since this admission's producer DOES carry the data.
    ``formula_operands``/``relation_endpoints`` reuse the identical
    join functions the static walk uses, over the same registry-declared
    edges, so the two walks cannot disagree about which formula or relation
    touches a given casilla.
    """
    records: list[ModeloWorkspaceSchemaRecordV1] = []
    for casilla in sorted(casillas, key=lambda item: item.id):
        casilla_id = casilla.id
        key = casilla_occurrence_locale_key(target.modelo, target.law_selected_revision_id, casilla_id, "label")
        locale_summary, value = _resolve_locale_summary_and_value(key, output_language=output_language)
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceCasillaReferenceV1(casilla_id=casilla_id),
                record_family=("casillas",),
                data_type="casilla_id",
                label=ModeloWorkspaceLocalizedTextV1(
                    locale_key=key,
                    value=value if value is not None else casilla_id,
                    locale=locale_summary,
                ),
                classification=ModeloWorkspaceSchemaClassification.PROJECTED,
                family_disposition=RegistrySchemaFamilyDisposition.POPULATED,
                legal_refs=tuple(casilla.legal_refs),
                constraints=(
                    (ModeloWorkspaceConstraintReferenceV1(casilla_id=casilla_id),)
                    if casilla.constraints is not None
                    else ()
                ),
                formula_operands=formula_operand_references_for_casilla(formulas, casilla_id),
                relation_endpoints=relation_source_endpoints_for_casilla(relations, casilla_id),
            )
        )
    return tuple(records)


def graded_snapshot_schema_records(
    casillas: tuple[CasillaDefinition, ...],
    binding_ids: frozenset[BindingId],
    bindings: tuple[DataBindingDefinition, ...],
    formulas: tuple[FormulaDefinition, ...],
    relations: tuple[RelationDefinition, ...],
    parameters: tuple[ParameterDefinition, ...],
    target: ModeloWorkspaceResolvedTargetV1,
    *,
    output_language: OutputLanguage,
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Return the complete GRADED_SNAPSHOT schema_facet across all five reference kinds.

    BINDING, FORMULA, RELATION and PARAMETER rows call the exact same
    shared functions STATIC_INSPECTION calls (``binding_schema_records``,
    ``formula_schema_records``, ``relation_schema_records``,
    ``parameter_schema_records``) -- one implementation, not a parallel copy
    that could drift. Only CASILLA uses a graded-specific builder, because
    only CASILLA's underlying data genuinely differs between admissions.
    """
    records = (
        graded_snapshot_casilla_schema_records(casillas, formulas, relations, target, output_language=output_language)
        + binding_schema_records(binding_ids, bindings, relations)
        + formula_schema_records(formulas)
        + relation_schema_records(relations)
        + parameter_schema_records(parameters, formulas)
    )
    return tuple(sorted(records, key=lambda record: (record.reference.kind, str(record.reference))))


def binding_schema_records(
    binding_ids: frozenset[BindingId],
    bindings: tuple[DataBindingDefinition, ...],
    relations: tuple[RelationDefinition, ...],
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per binding identity, sorted for stable pagination.

    Narrowed from ``inspection: RegistryRevisionInspection`` to the raw
    tuples it read internally -- ``DataBindingDefinition`` and
    ``RelationDefinition`` are the identical type on both
    ``RegistryRevisionInspection`` and ``RegistrySnapshot.revision``, so this
    is ONE shared implementation both admissions call, never two copies that
    could drift. Unlike a casilla, ``DataBindingDefinition`` IS retained
    whole by both admissions, so ``legal_refs`` is the binding's own real
    (possibly empty) tuple, never ``None`` -- the absence rule applies
    only where an admission genuinely carries no such data. The
    label is ``ModeloWorkspaceTechnicalLabelV1``: no locale convention exists
    for binding identities.
    """
    bindings_by_id = {binding.id: binding for binding in bindings}
    records: list[ModeloWorkspaceSchemaRecordV1] = []
    for binding_id in sorted(binding_ids):
        binding = bindings_by_id.get(binding_id)
        legal_refs = tuple(binding.legal_refs) if binding is not None else None
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceBindingReferenceV1(binding_id=binding_id),
                record_family=("bindings",),
                data_type="binding_id",
                label=ModeloWorkspaceTechnicalLabelV1(identifier=binding_id),
                classification=ModeloWorkspaceSchemaClassification.PROJECTED,
                family_disposition=RegistrySchemaFamilyDisposition.POPULATED,
                legal_refs=legal_refs,
                constraints=(),
                relation_endpoints=relation_target_endpoints_for_binding(relations, binding_id),
            )
        )
    return tuple(records)


def formula_schema_records(
    formulas: tuple[FormulaDefinition, ...],
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per formula, carrying its own full operand set.

    Narrowed from ``inspection: RegistryRevisionInspection`` to the raw
    ``formulas`` tuple -- ``FormulaDefinition`` is the identical type on both
    admissions, so this is ONE shared implementation. A FORMULA row's
    ``formula_operands`` is that formula's own complete input list (every
    operand its expression declares, of every kind) -- the mirror of a
    CASILLA row's ``formula_operands``, which lists only the subset naming
    that one casilla. Both readings are the same field walked from opposite
    ends of the identical join.
    """
    records: list[ModeloWorkspaceSchemaRecordV1] = []
    for formula in sorted(formulas, key=lambda item: item.id):
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceFormulaReferenceV1(formula_id=formula.id),
                record_family=("formulas",),
                data_type="formula_id",
                label=ModeloWorkspaceTechnicalLabelV1(identifier=formula.id),
                classification=ModeloWorkspaceSchemaClassification.PROJECTED,
                family_disposition=RegistrySchemaFamilyDisposition.POPULATED,
                legal_refs=tuple(formula.legal_refs),
                constraints=(),
                formula_operands=formula_expression_operand_references(formula.id, formula.expression),
            )
        )
    return tuple(records)


def relation_schema_records(
    relations: tuple[RelationDefinition, ...],
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per relation, carrying both of its own endpoints.

    Narrowed from ``inspection: RegistryRevisionInspection`` to the raw
    ``relations`` tuple -- ``RelationDefinition`` is the identical type on
    both admissions, so this is ONE shared implementation. A RELATION row
    states its own two endpoints directly from the registry-declared fields
    (``source_casilla_id``, ``target_binding``) -- it is the one reference
    kind that is never ambiguous about which side it claims, since it names
    both.
    """
    records: list[ModeloWorkspaceSchemaRecordV1] = []
    for relation in sorted(relations, key=lambda item: item.id):
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceRelationReferenceV1(relation_id=relation.id),
                record_family=("relations",),
                data_type="relation_id",
                label=ModeloWorkspaceTechnicalLabelV1(identifier=relation.id),
                classification=ModeloWorkspaceSchemaClassification.PROJECTED,
                family_disposition=RegistrySchemaFamilyDisposition.POPULATED,
                legal_refs=tuple(relation.legal_refs),
                constraints=(),
                relation_endpoints=(
                    ModeloWorkspaceRelationSourceEndpointReferenceV1(
                        relation_id=relation.id,
                        casilla_id=relation.source_casilla_id,
                    ),
                    ModeloWorkspaceRelationTargetEndpointReferenceV1(
                        relation_id=relation.id,
                        binding_id=relation.target_binding,
                    ),
                ),
            )
        )
    return tuple(records)


def parameter_schema_records(
    parameters: tuple[ParameterDefinition, ...],
    formulas: tuple[FormulaDefinition, ...],
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per parameter, keyed off every formula that dispatches to it.

    Narrowed from ``inspection: RegistryRevisionInspection`` to the raw
    ``parameters``/``formulas`` tuples -- ``ParameterDefinition`` and
    ``FormulaDefinition`` are the identical type on both admissions, so this
    is ONE shared implementation. A parameter has no direct outbound edge of
    its own in the registry schema; the only declared connection is a
    formula's own ``dispatch_table`` operand naming it, which
    :func:`formula_expression_operand_references` already extracts as
    ``ModeloWorkspaceFormulaParameterOperandReferenceV1`` and
    ``ModeloWorkspaceFormulaDispatchOperandReferenceV1`` entries.
    """
    parameter_operands: dict[str, list[ModeloWorkspaceFormulaOperandReferenceV1]] = {}
    for formula in formulas:
        for reference in formula_expression_operand_references(formula.id, formula.expression):
            if isinstance(reference, ModeloWorkspaceFormulaParameterOperandReferenceV1):
                parameter_operands.setdefault(reference.parameter_id, []).append(reference)
            elif isinstance(reference, ModeloWorkspaceFormulaDispatchOperandReferenceV1):
                for parameter_id in reference.parameter_ids:
                    parameter_operands.setdefault(parameter_id, []).append(reference)

    records: list[ModeloWorkspaceSchemaRecordV1] = []
    for parameter in sorted(parameters, key=lambda item: item.id):
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceParameterReferenceV1(parameter_id=parameter.id),
                record_family=("parameters",),
                data_type="parameter_id",
                label=ModeloWorkspaceTechnicalLabelV1(identifier=parameter.id),
                classification=ModeloWorkspaceSchemaClassification.PROJECTED,
                family_disposition=RegistrySchemaFamilyDisposition.POPULATED,
                legal_refs=tuple(parameter.legal_refs),
                constraints=(),
                formula_operands=tuple(parameter_operands.get(parameter.id, ())),
            )
        )
    return tuple(records)


def static_inspection_schema_records(
    inspection: RegistryRevisionInspection,
    target: ModeloWorkspaceResolvedTargetV1,
    *,
    output_language: OutputLanguage,
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Return the complete STATIC_INSPECTION schema_facet across all five reference kinds.

    Sorted by ``(reference.kind, identity)`` so the whole sequence, and
    therefore pagination over it, is deterministic and stable across
    identical repeated reads.
    """
    records = (
        static_inspection_casilla_schema_records(inspection, target, output_language=output_language)
        + binding_schema_records(inspection.binding_ids, inspection.bindings, inspection.relations)
        + formula_schema_records(inspection.formulas)
        + relation_schema_records(inspection.relations)
        + parameter_schema_records(inspection.parameters, inspection.formulas)
    )
    return tuple(sorted(records, key=lambda record: (record.reference.kind, str(record.reference))))


def paginate_modelo_workspace_facet[RecordT](
    facet_type: type[ModeloWorkspaceBoundedFacetV1[RecordT]],
    records: tuple[RecordT, ...],
    *,
    facet: ModeloWorkspaceFacetName,
    target: ModeloWorkspaceResolvedTargetV1,
    schema_identity: ModeloWorkspaceSchemaIdentityV1,
    baseline: ModeloWorkspaceBaselineV1,
    contributors: tuple[ModeloWorkspaceContributorIdentityV1, ...],
    disposition: ModeloWorkspaceCapabilityDisposition,
    page_size: int,
    cursor: ModeloWorkspaceCursorV1 | None = None,
) -> ModeloWorkspaceBoundedFacetV1[RecordT]:
    """Return one bounded, cursor-consistent page from the complete ``records`` sequence.

    ``records`` MUST already be in the caller's canonical stable order --
    pagination consumes an offset over that fixed order, never re-derives it.
    A ``cursor`` from a DIFFERENT baseline, revision, schema identity, facet,
    or contributor epoch refuses outright rather than silently starting over
    or returning a page from the wrong coordinate.

    This is the ONE paginator for every bounded facet. It exists as a single
    authority because ``ModeloWorkspaceBoundedFacetV1`` requires ``has_more``
    to agree with ``next_cursor``: a facet built by truncating records and
    setting ``has_more`` without minting the matching cursor does not merely
    lose pagination, it fails model validation outright and takes the whole
    projection down with it. Minting the cursor is therefore not a
    convenience this helper offers, it is the only way to construct an
    overflowing facet at all, and every facet routes through here so that no
    call site can rediscover that the hard way.

    ``facet_type`` is the caller's own concrete parametrization (for example
    ``ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1]``). It is
    passed rather than parametrized here from ``RecordT`` because a type
    parameter is only a ``TypeVar`` at runtime: pydantic would build the
    model with the record field effectively unvalidated, silently trading
    this boundary's strictness for the generalisation.
    """
    if cursor is not None:
        if (
            cursor.baseline != baseline
            or cursor.selected_revision_id != target.law_selected_revision_id
            or cursor.schema_identity != schema_identity
            or cursor.facet is not facet
            or cursor.contributor_epoch_digest != baseline.contributor_epoch_digest
        ):
            raise ModeloWorkspaceStaleCursorError(
                f"workspace {facet.value} facet cursor no longer matches the current baseline coordinate"
            )
        offset = int(cursor.continuation)
    else:
        offset = 0

    page = records[offset : offset + page_size]
    next_offset = offset + len(page)
    has_more = next_offset < len(records)
    next_cursor = (
        ModeloWorkspaceCursorV1(
            baseline=baseline,
            selected_revision_id=target.law_selected_revision_id,
            schema_identity=schema_identity,
            facet=facet,
            contributor_epoch_digest=baseline.contributor_epoch_digest,
            continuation=str(next_offset),
        )
        if has_more
        else None
    )
    return facet_type(
        selected_revision_id=target.law_selected_revision_id,
        schema_identity=schema_identity,
        baseline=baseline,
        contributor_epoch_digest=baseline.contributor_epoch_digest,
        contributors=contributors,
        facet=facet,
        disposition=disposition,
        records=page,
        page_size=page_size,
        next_cursor=next_cursor,
        has_more=has_more,
    )


def _not_applicable_family_dispositions(
    family_dispositions: Mapping[str, SchemaFamilyDispositionDeclaration],
) -> tuple[ModeloWorkspaceFamilyDispositionV1, ...]:
    """Project only the family dispositions the declarations mapping can honestly attest to.

    ``RegistryRevisionInspection.family_dispositions`` and
    ``ModeloRevision.family_dispositions`` are the identical mapping (the
    inspection copies it straight from the revision at construction), so
    this one function is shared by both admissions rather than written
    twice. It carries exactly the families the revision has explicitly
    declared NOT_APPLICABLE, each grounded with its own
    reason/legal_refs/source_refs -- a substantive claim the registry itself
    made. A family absent from this mapping is not reported here at all:
    silently defaulting an unreported family to POPULATED or
    BLOCKED_PENDING_EVIDENCE would assert a fact this data has no basis for.
    Reporting nothing is honest; guessing is not.
    """
    return tuple(
        sorted(
            (
                ModeloWorkspaceFamilyDispositionV1(
                    family=family,
                    disposition=RegistrySchemaFamilyDisposition.NOT_APPLICABLE,
                    legal_refs=tuple(declaration.legal_refs),
                    source_refs=tuple(declaration.source_refs),
                )
                for family, declaration in family_dispositions.items()
            ),
            key=lambda item: item.family,
        )
    )


def static_inspection_family_dispositions(
    inspection: RegistryRevisionInspection,
) -> tuple[ModeloWorkspaceFamilyDispositionV1, ...]:
    """Project only the family dispositions the inspection can honestly attest to.

    See :func:`_not_applicable_family_dispositions` for the shared logic;
    the inspection carries no data for most schema families (it strips
    everything but casilla/binding/formula/relation/parameter/projection-endpoint/
    workbook-parity/live-cross-reference identifiers).
    """
    return _not_applicable_family_dispositions(inspection.family_dispositions)


def graded_snapshot_family_dispositions(
    snapshot: RegistrySnapshot,
) -> tuple[ModeloWorkspaceFamilyDispositionV1, ...]:
    """Project only the family dispositions the snapshot's revision has explicitly declared.

    See :func:`_not_applicable_family_dispositions` for the shared logic.
    """
    return _not_applicable_family_dispositions(snapshot.revision.family_dispositions)


def resolve_static_inspection_result(
    target: ModeloWorkspaceTargetV1,
    *,
    bucket_id: str,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
    authority: ValidatedRegistryAuthority,
    output_language: OutputLanguage,
    page_size: int = 200,
) -> ModeloWorkspaceStaticInspectionResultV1:
    """Assemble the complete, single-page STATIC_INSPECTION result for one target.

    ``page_size`` defaults to 200, the schema facet's own maximum page size
    (``ModeloWorkspaceBoundedFacetV1``'s ``_MAX_FACET_PAGE_SIZE``), so a
    revision whose schema fits within that bound returns in one page; a
    caller working through a larger schema paginates via ``next_cursor``
    exactly as :func:`paginate_modelo_workspace_facet` proves.

    Captures WORK then REGISTRY exactly once each (the ordering-critical
    core), then builds every remaining piece from that one REGISTRY
    capture's inspection: schema identity, locale summary, evidence horizon,
    family dispositions, contributors, baseline, the five-kind schema_facet,
    the fixed work_review facet, and the capability denominator. No second
    registry or work read occurs anywhere in this function.
    """
    work_capture, registry_capture, axes = capture_modelo_workspace_target_captures(
        target,
        bucket_id=bucket_id,
        catalogue_repository=catalogue_repository,
        authority=authority,
    )
    resolution = work_capture.projection
    registry_projection = registry_capture.projection
    inspection = registry_projection.inspection
    assert inspection is not None

    work_unit = resolution.work_unit
    assert resolution.modelo is not None
    assert resolution.filing_year is not None
    assert resolution.period is not None
    resolved_target = ModeloWorkspaceResolvedTargetV1(
        bucket_id=resolution.bucket_id,
        modelo=resolution.modelo,
        filing_year=resolution.filing_year,
        period=resolution.period,
        law_selected_revision_id=axes.law_selected_revision_id,
        review_status=registry_projection.review_status,
        requested_revision_assertion=axes.requested_revision_assertion,
        stored_revision_assertion=axes.stored_revision_assertion,
        work_unit_id=work_unit.work_unit_id if work_unit is not None else None,
        work_state=work_unit.state if work_unit is not None else None,
    )

    schema_identity = resolve_static_inspection_schema_identity(inspection)
    locale = capture_modelo_workspace_locale_summary(resolved_target, output_language=output_language)
    locale_key = revision_locale_key(resolved_target.modelo, resolved_target.law_selected_revision_id)
    locale_capture = ModeloWorkspaceLocaleCataloguePortV1(
        translation_key=locale_key,
        locale=output_language.value,
    ).capture_projection_with_epoch()
    field_manifest_port = ModeloWorkspaceFieldManifestPortV1(authority=inspection)
    field_manifest_capture = field_manifest_port.capture_projection_with_epoch()

    baseline = resolve_static_inspection_baseline(
        resolved_target,
        schema_identity=schema_identity,
        locale=locale,
        work_stamp=work_capture.stamp,
        work_epoch=work_capture.epoch,
        registry_stamp=registry_capture.stamp,
        registry_epoch=registry_capture.epoch,
        locale_stamp=locale_capture.stamp,
        locale_epoch=locale_capture.epoch,
        field_manifest_stamp=field_manifest_capture.stamp,
        field_manifest_epoch=field_manifest_capture.epoch,
    )
    contributors = static_inspection_contributors()

    records = static_inspection_schema_records(inspection, resolved_target, output_language=output_language)
    schema_facet = paginate_modelo_workspace_facet(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1],
        records,
        facet=ModeloWorkspaceFacetName.SCHEMA,
        target=resolved_target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=page_size,
    )

    evidence_horizon = static_inspection_evidence_horizon(inspection)
    family_dispositions = static_inspection_family_dispositions(inspection)
    capabilities = static_inspection_modelo_workspace_capabilities(resolved_target)

    projection = ModeloWorkspaceProjectionV1(
        admission=ModeloWorkspaceStaticInspectionScopeV1(),
        target=resolved_target,
        schema_identity=schema_identity,
        locale=locale,
        evidence_horizon=evidence_horizon,
        family_dispositions=family_dispositions,
        contributors=contributors,
        baseline=baseline,
        schema_facet=schema_facet,
        work_review=STATIC_INSPECTION_WORK_REVIEW_FACET,
        capabilities=capabilities,
    )
    return ModeloWorkspaceStaticInspectionResultV1(projection=projection)


_GRADED_SNAPSHOT_RESPONSIBLE_OWNER = "application.modelo.workspace"


def resolve_graded_snapshot_result(
    target: ModeloWorkspaceTargetV1,
    *,
    required_grade: RegistryAuthorityGrade,
    bucket_id: str,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    authority: ValidatedRegistryAuthority,
    census: SourceConnectivityCensusManifest,
    as_of: date,
    output_language: OutputLanguage,
    page_size: int = 200,
) -> ModeloWorkspaceResultV1:
    """Assemble the complete GRADED_SNAPSHOT result for one target, or refuse honestly.

    Mirrors ``resolve_static_inspection_result``'s discipline: WORK captured
    exactly once, REGISTRY captured exactly once from WORK's own resolved
    coordinate (never the target's raw operands). CALCULATION and
    BOUNDED_REVIEW are each captured exactly once. LOCALE_CATALOGUE and
    FIELD_MANIFEST are each captured twice -- once inside
    ``capture_modelo_workspace_locale_summary``/
    ``resolve_graded_snapshot_schema_identity`` to resolve their content, and
    once more here to fold their stamp/epoch into the baseline -- the exact
    same inherited shape ``resolve_static_inspection_result`` already has;
    both reads observe the same immutable content, so this cannot desync the
    baseline, but it is not a single read and is not claimed as one. The
    baseline is pinned from the stamps/epochs those captures hold -- no
    contributor's CONTENT is read a second time from a different capture.

    Refuses ``TARGET_NOT_FOUND`` immediately after the WORK capture when no
    work unit exists at all for the target's natural coordinate, and
    ``CALCULATION_UNAVAILABLE`` when a work unit DOES exist there but carries
    no calculation revision yet -- both BEFORE the REGISTRY grade admission,
    the first facts that make a graded result impossible, not the last check
    that happens to fail. Refuses
    ``AUTHORITY_GRADE_UNAVAILABLE`` around the REGISTRY capture when the
    revision's declared grade cannot satisfy ``required_grade``, distinguished
    from any other :class:`RegistryValidationError` by its typed
    ``registry_failure`` condition rather than message text.

    ``census`` and ``as_of`` are the CLOSURE contributor's own operands. They
    are declared here rather than read inside the join because the assembly
    protocol forbids a live owner read hidden in the assembler: every
    contributor is captured through its port exactly once, from operands the
    caller supplied or an earlier capture resolved.

    ``work_review`` is the exact frozen :class:`ModeloWorkReview` the
    BOUNDED_REVIEW port captures -- never independently re-derived or
    reinterpreted here, per the ADR's canonical-bounded-review-facet
    constraint. GRADED_SNAPSHOT is an ELIGIBLE admission for it (static
    inspection is not), so this never reuses
    ``STATIC_INSPECTION_WORK_REVIEW_FACET``.
    """
    request = modelo_work_selector_request_for_target(target, bucket_id=bucket_id)
    work_port = ModeloWorkspaceWorkPortV1(
        request=request,
        catalogue_repository=catalogue_repository,
        mode=ModeloWorkSelectionMode.VISIBLE_OR_EXACT,
    )
    work_capture = work_port.capture_projection_with_epoch()
    resolution = work_capture.projection
    assert resolution.modelo is not None
    assert resolution.filing_year is not None
    assert resolution.period is not None

    work_unit = resolution.work_unit
    if work_unit is None:
        return ModeloWorkspaceRefusedResultV1(
            refusal=ModeloWorkspaceDomainRefusalV1(
                code=ModeloWorkspaceRefusalCode.TARGET_NOT_FOUND,
                boundary="admission",
                requested_target=target,
                selected_target=None,
                responsible_owner=_GRADED_SNAPSHOT_RESPONSIBLE_OWNER,
                reconsideration_condition="create a work unit for this target, then request a graded snapshot again",
                recovery_action=ActionReference(action_id="operator.modelo.work.create"),
            )
        )
    if work_unit.current_calculation_revision_id is None:
        return ModeloWorkspaceRefusedResultV1(
            refusal=ModeloWorkspaceDomainRefusalV1(
                code=ModeloWorkspaceRefusalCode.CALCULATION_UNAVAILABLE,
                boundary="admission",
                requested_target=target,
                selected_target=None,
                facts=(
                    ModeloWorkspaceEvidenceFactV1(
                        name="work_unit_id",
                        value=ModeloWorkspaceTextFactValueV1(value=str(work_unit.work_unit_id)),
                    ),
                ),
                responsible_owner=_GRADED_SNAPSHOT_RESPONSIBLE_OWNER,
                reconsideration_condition="calculate this work unit, then request a graded snapshot again",
                recovery_action=ActionReference(action_id="operator.modelo.work.calculate"),
            )
        )

    registry_port = ModeloWorkspaceRegistryPortV1(
        authority=authority,
        modelo_id=resolution.modelo,
        filing_year=resolution.filing_year,
        period=resolution.period.registry_token,
        grade=required_grade,
    )
    try:
        registry_capture = registry_port.capture_projection_with_epoch()
    except RegistryValidationError as exc:
        if (
            exc.registry_failure is not None
            and exc.registry_failure.condition is RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT
        ):
            return ModeloWorkspaceRefusedResultV1(
                refusal=ModeloWorkspaceDomainRefusalV1(
                    code=ModeloWorkspaceRefusalCode.AUTHORITY_GRADE_UNAVAILABLE,
                    boundary="admission",
                    requested_target=target,
                    selected_target=None,
                    responsible_owner=_GRADED_SNAPSHOT_RESPONSIBLE_OWNER,
                    reconsideration_condition="request a grade the selected revision's declared authority can satisfy",
                )
            )
        raise
    registry_projection = registry_capture.projection
    snapshot = registry_projection.snapshot
    assert snapshot is not None

    axes = resolve_modelo_workspace_revision_axes(resolution, registry_projection=registry_projection)
    resolved_target = ModeloWorkspaceResolvedTargetV1(
        bucket_id=resolution.bucket_id,
        modelo=resolution.modelo,
        filing_year=resolution.filing_year,
        period=resolution.period,
        law_selected_revision_id=axes.law_selected_revision_id,
        review_status=registry_projection.review_status,
        requested_revision_assertion=axes.requested_revision_assertion,
        stored_revision_assertion=axes.stored_revision_assertion,
        work_unit_id=work_unit.work_unit_id,
        work_state=work_unit.state,
    )

    calculation_capture = ModeloWorkspaceCalculationPortV1(
        calculation_revision_id=work_unit.current_calculation_revision_id,
        calculation_repository=calculation_repository,
    ).capture_projection_with_epoch()
    calculation_revision = calculation_capture.projection

    bounded_review_capture = ModeloWorkspaceBoundedReviewPortV1(
        bucket_id=resolved_target.bucket_id,
        modelo=resolved_target.modelo,
        filing_year=resolved_target.filing_year,
        period=resolved_target.period,
        authority=authority,
        work_unit_repository=catalogue_repository,
        calculation_repository=calculation_repository,
        verification_repository=verification_repository,
    ).capture_projection_with_epoch()
    work_review = ModeloWorkspaceWorkReviewFacetV1(
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        review=bounded_review_capture.projection,
    )

    readiness_capture = ModeloWorkspaceReadinessPortV1(
        requests=(
            ModeloReadinessRequest(
                modelo=resolved_target.modelo,
                revision_id=resolved_target.law_selected_revision_id,
                filing_year=resolved_target.filing_year,
                period=resolved_target.period,
            ),
        ),
        active_profile_id=resolved_target.bucket_id,
    ).capture_projection_with_epoch()
    readiness = graded_snapshot_readiness(readiness_capture.projection.reports[0])

    closure_capture = ModeloWorkspaceClosurePortV1(
        authority=authority,
        census=census,
        as_of=as_of,
    ).capture_projection_with_epoch()
    registry_closure_limbs = graded_snapshot_closure_limbs(
        closure_capture.projection.limbs,
        target=resolved_target,
    )

    schema_identity = resolve_graded_snapshot_schema_identity(snapshot)
    locale = capture_modelo_workspace_locale_summary(resolved_target, output_language=output_language)
    locale_key = revision_locale_key(resolved_target.modelo, resolved_target.law_selected_revision_id)
    locale_capture = ModeloWorkspaceLocaleCataloguePortV1(
        translation_key=locale_key,
        locale=output_language.value,
    ).capture_projection_with_epoch()
    field_manifest_port = ModeloWorkspaceFieldManifestPortV1(authority=snapshot)
    field_manifest_capture = field_manifest_port.capture_projection_with_epoch()

    baseline = resolve_graded_snapshot_baseline(
        resolved_target,
        schema_identity=schema_identity,
        locale=locale,
        work_stamp=work_capture.stamp,
        work_epoch=work_capture.epoch,
        registry_stamp=registry_capture.stamp,
        registry_epoch=registry_capture.epoch,
        locale_stamp=locale_capture.stamp,
        locale_epoch=locale_capture.epoch,
        field_manifest_stamp=field_manifest_capture.stamp,
        field_manifest_epoch=field_manifest_capture.epoch,
        calculation_stamp=calculation_capture.stamp,
        calculation_epoch=calculation_capture.epoch,
        bounded_review_stamp=bounded_review_capture.stamp,
        bounded_review_epoch=bounded_review_capture.epoch,
        readiness_stamp=readiness_capture.stamp,
        readiness_epoch=readiness_capture.epoch,
        closure_stamp=closure_capture.stamp,
        closure_epoch=closure_capture.epoch,
    )
    contributors = graded_snapshot_contributors()

    records = graded_snapshot_schema_records(
        snapshot.revision.casillas,
        frozenset(binding.id for binding in snapshot.revision.bindings),
        snapshot.revision.bindings,
        snapshot.revision.formulas,
        snapshot.revision.relations,
        snapshot.revision.parameters,
        resolved_target,
        output_language=output_language,
    )
    schema_facet = paginate_modelo_workspace_facet(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1],
        records,
        facet=ModeloWorkspaceFacetName.SCHEMA,
        target=resolved_target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=page_size,
    )

    evidence_horizon = graded_snapshot_evidence_horizon(snapshot)
    family_dispositions = graded_snapshot_family_dispositions(snapshot)
    capabilities = graded_snapshot_modelo_workspace_capabilities(
        resolved_target, calculation_revision=calculation_revision
    )

    materialization_records = graded_snapshot_materialization_facet(calculation_revision)
    materialization_facet = paginate_modelo_workspace_facet(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1],
        materialization_records,
        facet=ModeloWorkspaceFacetName.MATERIALIZATION,
        target=resolved_target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=page_size,
    )

    provenance_records = graded_snapshot_provenance_facet(calculation_revision.source_provenance)
    provenance_facet = paginate_modelo_workspace_facet(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceProvenanceRecordV1],
        provenance_records,
        facet=ModeloWorkspaceFacetName.PROVENANCE,
        target=resolved_target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=page_size,
    )

    projection = ModeloWorkspaceProjectionV1(
        admission=ModeloWorkspaceGradedSnapshotScopeV1(
            scope=ModeloWorkspaceSnapshotScopeV1(
                required_grade=required_grade,
                declared_grade=snapshot.revision.effective_authority_grade,
                snapshot_scope_digest=content_hash_hex(
                    {
                        "required_grade": required_grade.value,
                        "declared_grade": snapshot.revision.effective_authority_grade.value,
                        "selected_revision_id": resolved_target.law_selected_revision_id,
                    }
                ),
            )
        ),
        target=resolved_target,
        schema_identity=schema_identity,
        locale=locale,
        evidence_horizon=evidence_horizon,
        family_dispositions=family_dispositions,
        contributors=contributors,
        baseline=baseline,
        schema_facet=schema_facet,
        materialization_facet=materialization_facet,
        provenance_facet=provenance_facet,
        work_review=work_review,
        readiness=readiness,
        registry_closure_limbs=registry_closure_limbs,
        capabilities=capabilities,
    )
    return ModeloWorkspaceGradedSnapshotResultV1(projection=projection)


def graded_snapshot_materialization_facet(
    calculation_revision: CalculationRevision,
) -> tuple[ModeloWorkspaceMaterializationRecordV1, ...]:
    """Project one calculation revision's scalar and repeated-row values, unmodified.

    Scalar values come straight from ``casilla_values``. Repeated-row values
    come from ``row_casilla_values`` (keyed ``(casilla_id, row_index)``),
    grouped by the ``source_binding_id`` each row's own
    ``row_casilla_provenance`` entry names -- the registry-declared identity
    of WHICH binding produced that repeated row, never re-derived or
    guessed. A row value with no provenance entry cannot be attributed to a
    binding and is refused rather than silently grouped under a fabricated
    identity.
    """
    scalar_records = tuple(
        ModeloWorkspaceScalarMaterializationRecordV1(
            scalar=ModeloWorkspaceScalarMaterializationV1(casilla_id=casilla_id, value=value)
        )
        for casilla_id, value in sorted(calculation_revision.casilla_values.items())
    )

    grouped: dict[tuple[str, int], list[tuple[str, Decimal]]] = {}
    for (casilla_id, row_index), value in calculation_revision.row_casilla_values.items():
        provenance = calculation_revision.row_casilla_provenance.get((casilla_id, row_index))
        if provenance is None:
            raise ModeloWorkspaceMaterializationProvenanceMissingError(
                f"calculation revision row casilla value {(casilla_id, row_index)!r} has no "
                "row_casilla_provenance entry naming its source binding"
            )
        grouped.setdefault((provenance.source_binding_id, row_index), []).append((casilla_id, value))

    repeated_records = tuple(
        ModeloWorkspaceRepeatedRowMaterializationRecordV1(
            repeated_row=ModeloWorkspaceRepeatedRowMaterializationV1(
                binding_id=binding_id,
                row_index=row_index,
                values=tuple(
                    ModeloWorkspaceScalarMaterializationV1(casilla_id=casilla_id, value=value)
                    for casilla_id, value in sorted(items)
                ),
            )
        )
        for (binding_id, row_index), items in sorted(grouped.items())
    )
    return scalar_records + repeated_records


def graded_snapshot_provenance_facet(
    source_provenance: tuple[CalculationSourceRef, ...],
) -> tuple[ModeloWorkspaceProvenanceRecordV1, ...]:
    """Project the persisted resolver-mesh lineage into per-casilla provenance records.

    A :class:`CalculationSourceRef` carries ``source_casilla_ids``
    (previously dropped at the application->domain boundary,
    an omission rather than a documented decision) naming which casilla(s), if
    any, its resolution feeds. One ref fans out into one
    :class:`ModeloWorkspaceProvenanceRecordV1` per casilla it names. A ref
    whose originating resolver call site never associated a casilla (an empty
    ``source_casilla_ids``) still produces exactly ONE record, with
    ``subject=None`` -- an audit reader must see every contributing source,
    including the unattributed ones, rather than have them silently vanish
    from the facet. This is common today: most resolver call sites do not yet
    populate the link.
    """
    records: list[ModeloWorkspaceProvenanceRecordV1] = []
    for ref in source_provenance:
        if not ref.source_casilla_ids:
            records.append(ModeloWorkspaceProvenanceRecordV1(subject=None, calculation_source=ref))
            continue
        for casilla_id in sorted(ref.source_casilla_ids):
            records.append(
                ModeloWorkspaceProvenanceRecordV1(
                    subject=ModeloWorkspaceCasillaReferenceV1(casilla_id=casilla_id),
                    calculation_source=ref,
                )
            )
    return tuple(records)


def _graded_snapshot_ledger_issue(issue: LedgerPreflightIssue) -> ModeloWorkspaceLedgerIssueV1:
    """Project one canonical ledger-preflight issue, preserving its subject axis.

    ``LedgerPreflightIssue.transaction_id`` is
    ``TransactionId | Literal["__period__"]`` for the period-level case (an
    unsupported period with no date span). The Workspace subject is a
    discriminated union rather than a bare id so that case is represented as
    itself, never dropped and never pinned to a fabricated transaction.
    """
    subject: ModeloWorkspaceLedgerTransactionSubjectV1 | ModeloWorkspaceLedgerPeriodSubjectV1
    if issue.transaction_id == "__period__":
        subject = ModeloWorkspaceLedgerPeriodSubjectV1()
    else:
        subject = ModeloWorkspaceLedgerTransactionSubjectV1(transaction_id=issue.transaction_id)
    return ModeloWorkspaceLedgerIssueV1(subject=subject, reason=issue.reason, detail=issue.detail)


def graded_snapshot_closure_limbs(
    limbs: tuple[RegistryClosureLimb, ...],
    *,
    target: ModeloWorkspaceResolvedTargetV1,
) -> tuple[RegistryClosureLimb, ...]:
    """Select this target's own closure limbs from the captured registry-wide set.

    The closure capture republishes every validated revision's limbs, because
    the release predicate it serves is a whole-registry question. A workspace
    projection answers a single ``(modelo, revision)`` question, and
    :class:`ModeloWorkspaceProjectionV1` refuses a limb carrying any other
    coordinate, so the capture is narrowed here by that exact coordinate.

    This is a selection, never a derivation: each retained limb is the frozen
    record the composers built, passed through unmodified. A target the
    closure report does not cover yields an empty tuple rather than a
    fabricated limb -- absence of a measurement is not a satisfied limb.
    """
    return tuple(
        limb for limb in limbs if limb.modelo == target.modelo and limb.revision == target.law_selected_revision_id
    )


def graded_snapshot_readiness(readiness: ProjectionModeloReadiness) -> ModeloWorkspaceReadinessV1:
    """Project the canonical ``ProjectionModeloReadiness`` producer output, unmodified.

    Every field maps 1:1 onto its Workspace equivalent -- this is a pure
    axis-preserving pass-through over the one existing readiness producer,
    never a re-derivation of any readiness axis. ``ledger_issues`` is the one
    axis that needed a shape change rather than a straight copy, since its
    subject can be a period rather than a transaction.
    """
    return ModeloWorkspaceReadinessV1(
        profile_id=readiness.profile_id,
        modelo=ModeloCode(readiness.modelo),
        revision_id=readiness.revision_id,
        filing_year=readiness.filing_year,
        period=readiness.period,
        missing=tuple(
            ModeloWorkspaceProfileRequirementV1(
                selector=requirement.selector,
                section_key=requirement.section_key,
                field_key=requirement.field_key,
                label=requirement.label,
                legal_refs=requirement.legal_refs,
                modelos=tuple(ModeloCode(modelo) for modelo in requirement.modelos),
            )
            for requirement in readiness.missing
        ),
        profile_ready=readiness.profile_ready,
        per_operation_requirements_assessed=readiness.per_operation_requirements_assessed,
        profile_refusal=readiness.profile_refusal,
        registry_ready=readiness.registry_ready,
        registry_refusal=readiness.registry_refusal,
        binding_ready=readiness.binding_ready,
        missing_bindings=tuple(
            ModeloWorkspaceBindingRequirementV1(
                binding_id=requirement.binding_id,
                source=requirement.source,
                input_channel=requirement.input_channel,
            )
            for requirement in readiness.missing_bindings
        ),
        ledger_preflight_required=readiness.ledger_preflight_required,
        ledger_ready=readiness.ledger_ready,
        ledger_period=readiness.ledger_period,
        ledger_checked_transaction_count=readiness.ledger_checked_transaction_count,
        ledger_issues=tuple(_graded_snapshot_ledger_issue(issue) for issue in readiness.ledger_issues),
        ready=readiness.ready,
    )
