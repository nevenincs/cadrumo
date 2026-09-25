"""The sole Modelo Workspace V1 assembly and dispatch entry point.

This module owns the one ordering-critical sequence every Workspace read must
follow: capture WORK exactly once, derive the REGISTRY coordinate only from
that captured :class:`~.work_selection.ModeloWorkResolution`, then evaluate
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

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`,
:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.hashing import content_hash_hex
from ...core.identity.continuidad import ContinuidadId
from ...core.identity.hex_ids import WorkUnitId
from ...core.period import Period
from ...core.schema_family_disposition import RegistrySchemaFamilyDisposition
from ...domain.calculations.registry.errors import RegistryFailureCondition, RegistryValidationError
from ...domain.calculations.registry.ids import BindingId, ExportFieldId
from ...domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
    modelo_localization_source,
    revision_locale_key,
)
from ...domain.calculations.registry.relation_prefill_bindings import RelationPrefillProvider
from ...domain.calculations.registry.schema import (
    REVISION_SCHEMA_FAMILY_FIELDS,
    BindingDefinition,
    FormulaDefinition,
    RegistrySnapshot,
    SchemaFamilyDispositionDeclaration,
)
from ...domain.calculations.registry.schema_formula import FormulaExpression, ParameterDefinition
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.calculations.registry.static_inspection import RegistryRevisionInspection
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState, CalculationSourceRef
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from ..operator_actions.models import ActionReference
from ..state_projection import ModeloReadinessRequest, ProjectionModeloReadiness
from .work_addressing import (
    ModeloExactWorkUnitTarget,
    ModeloVisibleFilingTarget,
    diverging_work_target_revision_axes,
)
from .work_selection import (
    ModeloWorkResolution,
    ModeloWorkSelectionMode,
    ModeloWorkSelectorRequest,
)
from .workspace_models import (
    ModeloWorkspaceBaselineV1,
    ModeloWorkspaceBindingReferenceV1,
    ModeloWorkspaceBoundedFacetV1,
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceCapabilityV1,
    ModeloWorkspaceCasillaReferenceV1,
    ModeloWorkspaceConstraintReferenceV1,
    ModeloWorkspaceContinuityReferenceV1,
    ModeloWorkspaceContributorIdentityV1,
    ModeloWorkspaceCursorV1,
    ModeloWorkspaceDomainRefusalV1,
    ModeloWorkspaceEvidenceFactV1,
    ModeloWorkspaceEvidenceHorizonV1,
    ModeloWorkspaceEvidenceReferenceV1,
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceExportExposureReferenceV1,
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
    ModeloWorkspaceGradedSnapshotResultV1,
    ModeloWorkspaceGradedSnapshotScopeV1,
    ModeloWorkspaceLegalEvidenceReferenceV1,
    ModeloWorkspaceLocaleDisposition,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceLocalizedTextV1,
    ModeloWorkspaceMaterializationRecordV1,
    ModeloWorkspaceParameterReferenceV1,
    ModeloWorkspaceProjectionV1,
    ModeloWorkspaceProvenanceRecordV1,
    ModeloWorkspaceRefusalCode,
    ModeloWorkspaceRefusedResultV1,
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
    ModeloWorkspaceSourceEvidenceReferenceV1,
    ModeloWorkspaceStaticInspectionResultV1,
    ModeloWorkspaceStaticInspectionScopeV1,
    ModeloWorkspaceTargetV1,
    ModeloWorkspaceTechnicalLabelV1,
    ModeloWorkspaceTextFactValueV1,
    ModeloWorkspaceWorkReviewFacetV1,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..state_projection_ports import StateProjectionReadPorts
    from .calculation_action_ports import CalculationActionPorts

from .workspace_producers import (
    MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_LOCALE_CATALOGUE_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_REGISTRY_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_WORK_PRODUCER_CONTRACT_V1,
    ModeloWorkspaceCalculationPortV1,
    ModeloWorkspaceContributingProjectionV1,
    ModeloWorkspaceEpochV1,
    ModeloWorkspaceFieldManifestPortV1,
    ModeloWorkspaceLocaleCatalogueBatchPortV1,
    ModeloWorkspaceLocaleCataloguePortV1,
    ModeloWorkspaceProducerContractV1,
    ModeloWorkspaceProducerStampV1,
    ModeloWorkspaceReadinessPortV1,
    ModeloWorkspaceRegistryPortV1,
    ModeloWorkspaceRegistryProjectionV1,
    ModeloWorkspaceWorkPortV1,
    RegistryAuthorityCapturePort,
)


class ModeloWorkspaceAbsentRegistryProjectionError(CadrumoError):
    """Raised when a registry capture returns without its promised projection."""


class ModeloWorkspaceAbsentReadinessProjectionError(CadrumoError):
    """Raised when a readiness capture returns without its promised report.

    The READINESS port is asked for exactly one request and contracts to
    answer it. An empty report set means the producer declined to measure a
    target it was handed, which is a port defect rather than a readiness
    verdict: there is no honest way to render "the producer did not answer" as
    a readiness the operator can act on.
    """


class ModeloWorkspaceUnresolvedWorkError(CadrumoError):
    """Raised when a workspace read reaches an unresolved work selection."""


STATIC_INSPECTION_WORK_REVIEW_FACET = ModeloWorkspaceWorkReviewFacetV1(
    disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
    review=None,
)


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

    This function never raises on a mismatch. Each independently evaluated
    assertion retains its typed ``MISMATCHED`` disposition in the resolved
    target, so callers receive the divergence without losing either axis.
    """
    requested_revision_id = resolution.requested_revision_id
    stored_revision_id = resolution.work_unit.revision_id if resolution.work_unit is not None else None

    law_revision_id = registry_projection.revision_id

    # The comparison itself is the shared authority's, not a local copy: this
    # surface differs from it only in DISPOSITION -- recording the divergence as
    # typed data rather than raising -- and two open-coded copies of one
    # normalisation drift silently.
    diverging = diverging_work_target_revision_axes(
        law_revision_id=law_revision_id,
        requested_revision_id=requested_revision_id,
        stored_revision_id=stored_revision_id,
    )
    mismatched: set[ModeloWorkspaceRevisionAssertionSource] = {
        source
        for axis, source in (
            ("requested", ModeloWorkspaceRevisionAssertionSource.REQUESTED),
            ("stored", ModeloWorkspaceRevisionAssertionSource.STORED),
        )
        if axis in diverging
    }

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
    authority: RegistryAuthorityCapturePort,
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
    resolved_modelo, resolved_filing_year, resolved_period = _resolved_obligation(resolution)

    registry_port = ModeloWorkspaceRegistryPortV1(
        authority=authority,
        modelo_id=resolved_modelo,
        filing_year=resolved_filing_year,
        period=resolved_period.registry_token,
        grade=grade,
    )
    registry_capture = registry_port.capture_projection_with_epoch()
    registry_projection = registry_capture.projection

    axes = resolve_modelo_workspace_revision_axes(resolution, registry_projection=registry_projection)
    return work_capture, registry_capture, axes


def _resolve_locale_summary_and_value(
    key: str,
    *,
    output_language: OutputLanguage,
) -> tuple[ModeloWorkspaceLocaleSummaryV1, str | None]:
    """Resolve one canonical locale coordinate plus its text value, for any key."""
    ((summary, value),) = _resolve_locale_summaries_and_values((key,), output_language=output_language)
    return summary, value


def _resolve_locale_summaries_and_values(
    keys: Sequence[str],
    *,
    output_language: OutputLanguage,
) -> tuple[tuple[ModeloWorkspaceLocaleSummaryV1, str | None], ...]:
    """Resolve canonical locale coordinates plus text values for keys, in key order.

    Shared by the revision-level summary (:func:`capture_modelo_workspace_locale_summary`)
    and any per-record label resolution (schema_facet). Spanish is the source
    language for every catalogue entry (``aeat-locales-cli``), so a requested
    language whose own key is absent falls back to Spanish rather than to an
    arbitrary third language; Spanish absent as well is the suppressed floor,
    never a missing key propagated as an exception. A returned value is
    ``None`` only when even the Spanish source is absent -- callers needing a
    non-empty display string treat that as a distinct refusal, never a blank.

    All keys of one call are read over one catalogue window per language, so a
    schema facet's labels provably come from one catalogue state.
    """
    requested = ModeloWorkspaceLocaleCatalogueBatchPortV1(
        translation_keys=keys,
        locale=output_language.value,
    ).capture_projections_with_epoch()
    fallback_keys = tuple(
        capture.projection.translation_key
        for capture in requested
        if capture.projection.value is None and output_language is not OutputLanguage.ES
    )
    spanish = {
        capture.projection.translation_key: capture
        for capture in (
            ModeloWorkspaceLocaleCatalogueBatchPortV1(
                translation_keys=fallback_keys,
                locale=OutputLanguage.ES.value,
            ).capture_projections_with_epoch()
            if fallback_keys
            else ()
        )
    }
    resolved: list[tuple[ModeloWorkspaceLocaleSummaryV1, str | None]] = []
    for capture in requested:
        if capture.projection.value is not None:
            resolved.append(
                (
                    ModeloWorkspaceLocaleSummaryV1(
                        requested_language=output_language,
                        resolved_language=output_language,
                        disposition=ModeloWorkspaceLocaleDisposition.EXACT,
                        catalogue_digest=capture.projection.catalogue_digest,
                    ),
                    capture.projection.value,
                )
            )
            continue
        if output_language is OutputLanguage.ES:
            resolved.append(
                (
                    ModeloWorkspaceLocaleSummaryV1(
                        requested_language=output_language,
                        resolved_language=OutputLanguage.ES,
                        disposition=ModeloWorkspaceLocaleDisposition.SUPPRESSED,
                        catalogue_digest=capture.projection.catalogue_digest,
                    ),
                    None,
                )
            )
            continue
        fallback = spanish[capture.projection.translation_key]
        disposition = (
            ModeloWorkspaceLocaleDisposition.SPANISH_FALLBACK
            if fallback.projection.value is not None
            else ModeloWorkspaceLocaleDisposition.SUPPRESSED
        )
        resolved.append(
            (
                ModeloWorkspaceLocaleSummaryV1(
                    requested_language=output_language,
                    resolved_language=OutputLanguage.ES,
                    disposition=disposition,
                    catalogue_digest=fallback.projection.catalogue_digest,
                ),
                fallback.projection.value,
            )
        )
    return tuple(resolved)


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
# capability-to-producer mapping is fixed by which of the contributors
# static inspection structurally never reads ("Static inspection captures
# exactly registry, work, locale_catalogue, and field_manifest; it does not
# read bounded_review, calculation, or readiness"), not by matching
# enum spellings. Every one of those three excluded contributors is UNMEASURED
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
)


#: The registry schema family whose content each capability actually rests on.
#: A capability answer that cites no family could only explain itself by
#: restating its own disposition, which is not an explanation.
_WORKSPACE_CAPABILITY_SOURCE_FAMILIES: Final[dict[ModeloWorkspaceCapabilityName, str]] = {
    ModeloWorkspaceCapabilityName.SCHEMA_INSPECTION: "casillas",
    ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION: "formulas",
    ModeloWorkspaceCapabilityName.VERIFICATION_READINESS: "verification_expectations",
    ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS: "export_layouts",
}

#: The catalogued operator action that advances each capability when it is not
#: available. These are catalogue ids, resolved through the sole
#: :data:`OPERATOR_ACTION_CATALOGUE` authority rather than spelled at a call
#: site: an id this repository does not declare must fail loudly, not render as
#: a dead button.
_WORKSPACE_CAPABILITY_RECOVERY_ACTIONS: Final[dict[ModeloWorkspaceCapabilityName, str]] = {
    ModeloWorkspaceCapabilityName.SCHEMA_INSPECTION: "operator.modelo.work.status",
    ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION: "operator.modelo.work.calculate",
    ModeloWorkspaceCapabilityName.VERIFICATION_READINESS: "operator.modelo.work.verify",
    ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS: "operator.modelo.work.status",
}

_WORK_UNIT_ACTION_ARGUMENT = "work_unit_id"


def modelo_workspace_recovery_action(
    action_id: str,
    *,
    work_unit_id: WorkUnitId | None,
) -> ActionReference | None:
    """Return the catalogued recovery action, or ``None`` when it is unaddressable.

    The action is looked up in :data:`OPERATOR_ACTION_CATALOGUE`, so an id this
    build does not declare raises here rather than reaching an operator as a
    reference to a command that does not exist.

    Addressability is decided by the catalogue's own argument specifications,
    never by a local list: an action every specification of which can be
    supplied is offered, and one that binds a ``work_unit_id`` the resolved
    target does not carry is not. Offering it anyway would name a remedy the
    operator cannot invoke, which is worse than offering none.
    """
    entry = OPERATOR_ACTION_CATALOGUE.lookup(action_id)
    requires_work_unit = any(
        specification.argument_name == _WORK_UNIT_ACTION_ARGUMENT for specification in entry.argument_specifications
    )
    if requires_work_unit and work_unit_id is None:
        return None
    return ActionReference(action_id=entry.action_id)


@dataclass(frozen=True, slots=True)
class ModeloWorkspaceCapabilityExplanation:
    """Why one capability answered as it did, in the payload's own typed shapes.

    Assembled once and applied to BOTH admissions. The explanation is a
    function of the registry's own declarations and the resolved target, not
    of which admission is asking, so a static inspection and a graded snapshot
    cannot explain the same capability differently.
    """

    source_disposition: RegistrySchemaFamilyDisposition | None
    facts: tuple[ModeloWorkspaceEvidenceFactV1, ...]
    evidence: tuple[ModeloWorkspaceEvidenceReferenceV1, ...]
    recovery_action: ActionReference | None


def _schema_family_disposition(
    family: str,
    *,
    declarations: Mapping[str, SchemaFamilyDispositionDeclaration],
    declared_member_count: int | None,
) -> RegistrySchemaFamilyDisposition | None:
    """Read one family's declared disposition, or ``None`` when unmeasurable here.

    ``NOT_APPLICABLE`` is the revision's own cited claim and outranks a member
    count, which is why it is checked first. A family this admission cannot
    count at all (``declared_member_count is None`` -- a static inspection has
    no export layouts and no verification expectations) yields ``None``:
    "this producer does not carry this family", which is a different statement
    from ``BLOCKED_PENDING_EVIDENCE``'s "the family is empty and nobody said
    why", and collapsing the two would invent a registry defect out of an
    admission boundary.
    """
    if family in declarations:
        return RegistrySchemaFamilyDisposition.NOT_APPLICABLE
    if declared_member_count is None:
        return None
    if declared_member_count > 0:
        return RegistrySchemaFamilyDisposition.POPULATED
    return RegistrySchemaFamilyDisposition.BLOCKED_PENDING_EVIDENCE


def _schema_family_evidence(
    family: str,
    *,
    declarations: Mapping[str, SchemaFamilyDispositionDeclaration],
) -> tuple[ModeloWorkspaceEvidenceReferenceV1, ...]:
    """Return the references the revision cited for this family, if it cited any.

    Only an inapplicability declaration carries references that are ABOUT the
    family: it is a substantive legal claim and the registry requires it to
    name what it stands on. A populated family's members each carry their own
    grounding, which the schema facet's per-record ``legal_refs`` and
    ``source_refs`` already expose row by row; restating an unbounded union of
    them here would have to truncate, and a truncated evidence list reads as a
    complete one.
    """
    declaration = declarations.get(family)
    if declaration is None:
        return ()
    references: list[ModeloWorkspaceEvidenceReferenceV1] = [
        ModeloWorkspaceLegalEvidenceReferenceV1(legal_ref_id=legal_ref_id)
        for legal_ref_id in sorted(declaration.legal_refs)
    ]
    references.extend(
        ModeloWorkspaceSourceEvidenceReferenceV1(source_ref_id=source_ref_id)
        for source_ref_id in sorted(declaration.source_refs)
    )
    return tuple(references)


def modelo_workspace_capability_explanation(
    capability: ModeloWorkspaceCapabilityName,
    *,
    declarations: Mapping[str, SchemaFamilyDispositionDeclaration],
    declared_member_count: int | None,
    work_unit_id: WorkUnitId | None,
) -> ModeloWorkspaceCapabilityExplanation:
    """Explain one capability from the registry's declarations and the resolved target."""
    family = _WORKSPACE_CAPABILITY_SOURCE_FAMILIES[capability]
    disposition = _schema_family_disposition(
        family,
        declarations=declarations,
        declared_member_count=declared_member_count,
    )
    facts: list[ModeloWorkspaceEvidenceFactV1] = [
        ModeloWorkspaceEvidenceFactV1(
            name="source_family",
            value=ModeloWorkspaceTextFactValueV1(value=family),
        )
    ]
    if declared_member_count is not None:
        facts.append(
            ModeloWorkspaceEvidenceFactV1(
                name="declared_members",
                value=ModeloWorkspaceTextFactValueV1(value=str(declared_member_count)),
            )
        )
    return ModeloWorkspaceCapabilityExplanation(
        source_disposition=disposition,
        facts=tuple(facts),
        evidence=_schema_family_evidence(family, declarations=declarations),
        recovery_action=modelo_workspace_recovery_action(
            _WORKSPACE_CAPABILITY_RECOVERY_ACTIONS[capability],
            work_unit_id=work_unit_id,
        ),
    )


def _capability_row(
    capability: ModeloWorkspaceCapabilityName,
    *,
    disposition: ModeloWorkspaceCapabilityDisposition,
    contract: ModeloWorkspaceProducerContractV1,
    resolved_target: ModeloWorkspaceResolvedTargetV1,
    declarations: Mapping[str, SchemaFamilyDispositionDeclaration],
    declared_member_count: int | None,
) -> ModeloWorkspaceCapabilityV1:
    """Assemble one capability row with its explanation, for either admission."""
    explanation = modelo_workspace_capability_explanation(
        capability,
        declarations=declarations,
        declared_member_count=declared_member_count,
        work_unit_id=resolved_target.work_unit_id,
    )
    return ModeloWorkspaceCapabilityV1(
        capability=capability,
        disposition=disposition,
        target=resolved_target,
        selected_revision_id=resolved_target.law_selected_revision_id,
        producer_owner=contract.contributor.owner,
        producer=contract.contributor.producer,
        evidence=explanation.evidence,
        facts=explanation.facts,
        source_disposition=explanation.source_disposition,
        recovery_action=explanation.recovery_action,
    )


def static_inspection_schema_family_member_counts(
    inspection: RegistryRevisionInspection,
) -> dict[str, int]:
    """Count only the schema families a static inspection actually retains.

    A family absent from this mapping is one the inspection does not carry, and
    the absence is read as "unmeasured" rather than "empty" downstream. The
    inspection deliberately strips everything but its identity and declaration
    sets, so export layouts and verification expectations are absent here by
    construction, not by omission.
    """
    return {
        "casillas": len(inspection.casilla_ids),
        "bindings": len(inspection.binding_ids),
        "formulas": len(inspection.formulas),
        "parameters": len(inspection.parameters),
        "projection_endpoints": len(inspection.projection_endpoints),
        "workbook_parity_refs": len(inspection.workbook_parity_refs),
        "live_cross_references": len(inspection.live_cross_references),
    }


def static_inspection_modelo_workspace_capabilities(
    inspection: RegistryRevisionInspection,
    resolved_target: ModeloWorkspaceResolvedTargetV1,
) -> tuple[ModeloWorkspaceCapabilityV1, ...]:
    """Return the complete STATIC_INSPECTION capability denominator.

    Every row cites the capability's own canonical producer contributor per
    the canonical capability mapping; see the module-level comment above this function.
    ``schema_inspection`` is ``AVAILABLE`` -- field_manifest is a real
    STATIC_INSPECTION contributor. The other three are ``UNMEASURED``:
    their producers are contributors this admission structurally never reads.
    GRADED_SNAPSHOT's dispositions are a distinct question answered by
    :func:`graded_snapshot_modelo_workspace_capabilities` and MUST NOT be
    derived from this table.

    Each row's explanation comes from the inspection's own declarations
    through the shared
    :func:`modelo_workspace_capability_explanation`. The inspection carries
    the casilla and formula families, so those two are counted; it carries
    neither export layouts nor verification expectations, so those two report
    an unmeasured source disposition rather than a fabricated empty one.
    """
    counts = static_inspection_schema_family_member_counts(inspection)
    return tuple(
        _capability_row(
            capability,
            disposition=disposition,
            contract=contract,
            resolved_target=resolved_target,
            declarations=inspection.family_dispositions,
            declared_member_count=counts.get(_WORKSPACE_CAPABILITY_SOURCE_FAMILIES[capability]),
        )
        for capability, contract, disposition in _STATIC_INSPECTION_CAPABILITY_DISPOSITIONS
    )


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
    if expression.literal is not None:
        return (ModeloWorkspaceFormulaLiteralOperandReferenceV1(formula_id=formula_id),)
    if expression.dispatch_table is not None:
        return (
            ModeloWorkspaceFormulaDispatchOperandReferenceV1(
                formula_id=formula_id,
                # Several dispatch keys may select one parameter; the operand is the set read.
                parameter_ids=tuple(sorted(set(expression.dispatch_table.values()))),
            ),
        )
    return ()


def casilla_continuity_references(
    continuidad_id: ContinuidadId | None,
) -> tuple[ModeloWorkspaceContinuityReferenceV1, ...]:
    """Return the continuity row for one casilla's declared continuity key.

    One casilla declares at most one ``continuidad_id``, so this is a
    zero-or-one tuple rather than a set: the plural field shape belongs to the
    schema record, which carries several reference kinds, not to this fact.
    An undeclared key yields the empty tuple, which says the revision claims no
    cross-revision continuity for this row -- never a fabricated chain.

    Shared by both admissions: a static inspection reads the key from its own
    ``casilla_continuity`` projection and a graded snapshot from the
    ``CasillaDefinition`` it holds, but the projection itself is identical and
    is written once here.
    """
    if continuidad_id is None:
        return ()
    return (ModeloWorkspaceContinuityReferenceV1(continuidad_id=continuidad_id),)


def casilla_export_exposure_references(
    casilla_id: CasillaId,
    export_refs: tuple[ExportFieldId, ...],
) -> tuple[ModeloWorkspaceExportExposureReferenceV1, ...]:
    """Return one exposure row per export field that carries this casilla.

    Order is the compiler's own emission order
    (:func:`~cadrumo.domain.calculations.registry.export_field_casilla.derive_casilla_export_refs`),
    preserved rather than re-sorted: which record slot carries a casilla first
    is part of the official layout's meaning, and a lexical re-sort would
    silently restate it.
    """
    return tuple(
        ModeloWorkspaceExportExposureReferenceV1(casilla_id=casilla_id, export_field_id=export_field_id)
        for export_field_id in export_refs
    )


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


def fold_slots(bindings: tuple[BindingDefinition, ...]) -> tuple[tuple[BindingId, RelationPrefillProvider], ...]:
    """Return every relation-prefill slot among a revision's bindings.

    The fold is declared by the binding itself now, so the slot identity and
    the fold identity are the same id; both workspace endpoint rows are built
    from this one pairing rather than from a second family that could name a
    binding this revision does not declare.
    """
    return tuple(
        (binding.id, binding.provider) for binding in bindings if isinstance(binding.provider, RelationPrefillProvider)
    )


def relation_source_endpoints_for_casilla(
    bindings: tuple[BindingDefinition, ...],
    casilla_id: str,
    *,
    source_modelo: str,
) -> tuple[ModeloWorkspaceRelationSourceEndpointReferenceV1, ...]:
    """Return the fold-source-endpoint rows whose declared source casilla matches.

    A source casilla id is only meaningful inside its own modelo, so a fold
    reading another modelo never matches a same-spelled casilla of this one.
    """
    return tuple(
        ModeloWorkspaceRelationSourceEndpointReferenceV1(relation_id=binding_id, casilla_id=source_casilla_id)
        for binding_id, provider in fold_slots(bindings)
        if str(provider.source_modelo) == source_modelo
        for source_casilla_id in provider.declared_source_casilla_ids
        if source_casilla_id == casilla_id
    )


def relation_target_endpoints_for_binding(
    bindings: tuple[BindingDefinition, ...],
    binding_id: str,
) -> tuple[ModeloWorkspaceRelationTargetEndpointReferenceV1, ...]:
    """Return the fold-target-endpoint row for a binding that is itself a fold slot."""
    return tuple(
        ModeloWorkspaceRelationTargetEndpointReferenceV1(relation_id=slot_id, binding_id=slot_id)
        for slot_id, _ in fold_slots(bindings)
        if slot_id == binding_id
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


def _resolved_obligation(resolution: ModeloWorkResolution) -> tuple[ModeloCode, int, Period]:
    """Return the modelo, ejercicio and period a resolved selection names.

    ``ModeloWorkResolution`` leaves all three optional because an unresolved
    selection carries none of them. Every caller here has already selected a
    work unit, so absence is a defect rather than a state to render -- and it
    is refused rather than asserted, because an ``assert`` disappears under
    ``python -O`` and would let a partial obligation reach the registry port.
    """
    if resolution.modelo is None or resolution.filing_year is None or resolution.period is None:
        raise ModeloWorkspaceUnresolvedWorkError(
            "work selection resolved without a complete modelo/ejercicio/period address",
        )
    return resolution.modelo, resolution.filing_year, resolution.period


class ModeloWorkspaceStaleCursorError(CadrumoError):
    """Raised when a cursor's pinned coordinate no longer matches the current baseline.

    A stale cursor MUST refuse rather than silently return a different page:
    resuming it against data that moved would return records the caller did
    not ask for and has no way to detect.
    """


def static_inspection_casilla_schema_records(
    inspection: RegistryRevisionInspection,
    target: ModeloWorkspaceResolvedTargetV1,
    *,
    output_language: OutputLanguage,
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per casilla identity, sorted for stable pagination.

    Bounded to identity: ``legal_refs`` and ``constraints`` are
    ``None`` (this admission's producer never carries the casilla's own
    grounding or constraint block), never ``()``. ``formula_operands`` and
    ``relation_endpoints`` consume the shared join functions directly rather
    than re-deriving either edge here.

    ``continuity`` and ``export_exposure`` ARE carried, because the inspection
    retains both as its own declared projections
    (``casilla_continuity`` from ``CasillaDefinition.continuidad_id``,
    ``casilla_export_refs`` from the compiler-derived
    ``CasillaDefinition.export_refs``). A casilla declaring neither yields the
    empty tuple, which here honestly reads "the revision declares no
    continuity chain / no export field addresses this casilla" rather than
    "this admission cannot see".
    """
    formulas = inspection.formulas
    casilla_ids = sorted(inspection.casilla_ids)
    keys: list[str] = []
    for casilla_id in casilla_ids:
        chain = inspection.casilla_localization_keys.get(casilla_id) or (
            casilla_occurrence_locale_key(
                target.modelo, target.law_selected_revision_id, casilla_id, ModeloLocalizationFieldKind.LABEL
            ),
        )
        source = modelo_localization_source(chain, locale=output_language.value)
        keys.append(chain[0] if source is None else source[0])
    labels = _resolve_locale_summaries_and_values(keys, output_language=output_language)
    records: list[ModeloWorkspaceSchemaRecordV1] = []
    for casilla_id, key, (locale_summary, value) in zip(casilla_ids, keys, labels, strict=True):
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceCasillaReferenceV1(casilla_id=casilla_id),
                record_family=("casillas",),
                section_path=inspection.casilla_sections.get(casilla_id, ()),
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
                continuity=casilla_continuity_references(inspection.casilla_continuity.get(casilla_id)),
                export_exposure=casilla_export_exposure_references(
                    casilla_id,
                    inspection.casilla_export_refs.get(casilla_id, ()),
                ),
                formula_operands=formula_operand_references_for_casilla(formulas, casilla_id),
                relation_endpoints=relation_source_endpoints_for_casilla(
                    inspection.bindings,
                    casilla_id,
                    source_modelo=str(target.modelo),
                ),
            )
        )
    return tuple(records)


def binding_schema_records(
    binding_ids: frozenset[BindingId],
    bindings: tuple[BindingDefinition, ...],
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per binding identity, sorted for stable pagination.

    Narrowed from ``inspection: RegistryRevisionInspection`` to the raw
    tuples it read internally -- ``BindingDefinition`` is the identical type
    on both ``RegistryRevisionInspection`` and ``RegistrySnapshot.revision``, so this
    is ONE shared implementation both admissions call, never two copies that
    could drift. Unlike a casilla, ``BindingDefinition`` IS retained
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
        source_refs = tuple(binding.source_refs) if binding is not None else ()
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceBindingReferenceV1(binding_id=binding_id),
                record_family=("bindings",),
                data_type="binding_id",
                label=ModeloWorkspaceTechnicalLabelV1(identifier=binding_id),
                classification=ModeloWorkspaceSchemaClassification.PROJECTED,
                family_disposition=RegistrySchemaFamilyDisposition.POPULATED,
                legal_refs=legal_refs,
                source_refs=source_refs,
                constraints=(),
                relation_endpoints=relation_target_endpoints_for_binding(bindings, binding_id),
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
        + binding_schema_records(inspection.binding_ids, inspection.bindings)
        + formula_schema_records(inspection.formulas)
        + parameter_schema_records(inspection.parameters, inspection.formulas)
    )
    return tuple(sorted(records, key=lambda record: (record.reference.kind, str(record.reference))))


def _facet_cursor(
    cursor: ModeloWorkspaceCursorV1 | None,
    facet: ModeloWorkspaceFacetName,
) -> ModeloWorkspaceCursorV1 | None:
    """Return ``cursor`` when it addresses ``facet``, otherwise ``None``.

    A result assembles several facets from one call, so a caller holds at
    most one cursor at a time and the cursor itself names which facet it
    continues. Routing on that name keeps the other facets at their first
    page instead of applying one facet's offset to another's records.
    """
    return cursor if cursor is not None and cursor.facet is facet else None


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


def resolve_static_inspection_result(
    target: ModeloWorkspaceTargetV1,
    *,
    bucket_id: str,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
    authority: RegistryAuthorityCapturePort,
    output_language: OutputLanguage,
    page_size: int = 200,
    cursor: ModeloWorkspaceCursorV1 | None = None,
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
    if cursor is not None and cursor.facet is not ModeloWorkspaceFacetName.SCHEMA:
        raise ModeloWorkspaceStaleCursorError(
            f"static inspection paginates only the schema facet; cursor names {cursor.facet.value}"
        )

    work_capture, registry_capture, axes = capture_modelo_workspace_target_captures(
        target,
        bucket_id=bucket_id,
        catalogue_repository=catalogue_repository,
        authority=authority,
    )
    resolution = work_capture.projection
    registry_projection = registry_capture.projection
    inspection = registry_projection.inspection
    if inspection is None:
        raise ModeloWorkspaceAbsentRegistryProjectionError(
            "registry capture returned no inspection for the resolved revision",
        )

    work_unit = resolution.work_unit
    resolved_modelo, resolved_filing_year, resolved_period = _resolved_obligation(resolution)
    resolved_target = ModeloWorkspaceResolvedTargetV1(
        bucket_id=resolution.bucket_id,
        modelo=resolved_modelo,
        filing_year=resolved_filing_year,
        period=resolved_period,
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
        cursor=_facet_cursor(cursor, ModeloWorkspaceFacetName.SCHEMA),
        target=resolved_target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=page_size,
    )

    evidence_horizon = static_inspection_evidence_horizon(inspection)
    family_dispositions = static_inspection_family_dispositions(inspection)
    capabilities = static_inspection_modelo_workspace_capabilities(inspection, resolved_target)

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


# --- GRADED_SNAPSHOT admission ------------------------------------------------
#
# ONE CHANNEL PER OUTCOME, and the split is deliberate rather than historical.
#
# A TAXPAYER-FACING outcome is one the operator can act on: no work unit exists
# at this target yet, the work unit carries no calculation revision yet, or the
# selected revision's declared authority cannot satisfy the grade that was
# requested. Each returns
# ``ModeloWorkspaceRefusedResultV1(refusal=ModeloWorkspaceDomainRefusalV1(...))``
# carrying the refusal code, the resolved target where one exists, the safe
# facts behind it, the registry family disposition that explains it, and the
# catalogued action that advances it. None of them raises.
#
# A PROGRAMMER INVARIANT is one no operator can influence and no message can
# usefully describe, so each keeps raising its existing ``CadrumoError``
# subclass rather than being dressed as a refusal:
#
# * ``ModeloWorkspaceStaleCursorError`` -- a cursor is minted by this module and
#   pinned to a baseline this module computed. Presenting one from another read,
#   or naming a facet the admission does not paginate, is a caller defect; there
#   is no operator remedy to name.
# * ``ModeloWorkspaceAbsentRegistryProjectionError`` -- the REGISTRY port
#   returned without the admission shape its own contract promises. That is a
#   broken port, not a state of the taxpayer's data.
# * ``ModeloWorkspaceUnresolvedWorkError`` -- the WORK port reported a resolved
#   selection with an incomplete modelo/ejercicio/period address. The selector's
#   own ABSENT state is a refusal (``TARGET_NOT_FOUND``); this is the different
#   case of a selection that claims to have resolved and did not.
#
# The refusal codes and the errors are therefore disjoint: nothing is reported
# both ways, and no outcome is reported neither way.

_GRADED_SNAPSHOT_RESPONSIBLE_OWNER = "modelo.workspace"

_GRADED_SNAPSHOT_PAGINATED_FACETS = frozenset(
    {
        ModeloWorkspaceFacetName.SCHEMA,
        ModeloWorkspaceFacetName.MATERIALIZATION,
        ModeloWorkspaceFacetName.PROVENANCE,
    }
)

GRADED_SNAPSHOT_WORK_REVIEW_FACET = ModeloWorkspaceWorkReviewFacetV1(
    disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
    review=None,
)
"""GRADED_SNAPSHOT does not read the bounded-review producer, so it declares the
review unmeasured rather than assembling one of its own.

Separate from ``STATIC_INSPECTION_WORK_REVIEW_FACET`` despite holding the same
value: the two constants record different reasons, and folding them into one
would make a later change to either admission's review posture silently change
the other's.
"""


class ModeloWorkspaceMaterializationProvenanceMissingError(CadrumoError):
    """Raised when a persisted repeated-row value names no source binding.

    A persistence invariant rather than a refusal: every ``row_casilla_values``
    entry is written together with its ``row_casilla_provenance`` entry, so a
    value without one is a corrupt revision, not a state the operator can
    resolve by acting.
    """


def graded_snapshot_refusal(
    code: ModeloWorkspaceRefusalCode,
    *,
    requested_target: ModeloWorkspaceTargetV1,
    selected_target: ModeloWorkspaceResolvedTargetV1 | None,
    capability: ModeloWorkspaceCapabilityName | None,
    reconsideration_condition: str,
    facts: tuple[ModeloWorkspaceEvidenceFactV1, ...],
    evidence: tuple[ModeloWorkspaceEvidenceReferenceV1, ...],
    source_disposition: RegistrySchemaFamilyDisposition | None,
    recovery_action: ActionReference | None,
) -> ModeloWorkspaceRefusedResultV1:
    """Build the one refused-result shape this admission returns.

    Every field is required at the call site, including the ones the payload
    would happily default. A default here would let a caller omit the
    capability the refusal is about, or the target it was measured at, and the
    omission would read to a consumer exactly like a producer that measured and
    found nothing.
    """
    return ModeloWorkspaceRefusedResultV1(
        refusal=ModeloWorkspaceDomainRefusalV1(
            code=code,
            boundary="admission",
            capability=capability,
            requested_target=requested_target,
            selected_target=selected_target,
            facts=facts,
            evidence=evidence,
            responsible_owner=_GRADED_SNAPSHOT_RESPONSIBLE_OWNER,
            reconsideration_condition=reconsideration_condition,
            source_disposition=source_disposition,
            recovery_action=recovery_action,
        )
    )


def graded_snapshot_schema_family_member_counts(snapshot: RegistrySnapshot) -> dict[str, int]:
    """Count every schema family the snapshot's revision actually declares.

    A graded snapshot holds the whole ``ModeloRevision``, so unlike a static
    inspection it can count every enrolled family and none is unmeasured. The
    family names come from the registry's own enrolled-family declaration
    rather than a local list, so a family added to the revision enrols itself
    here.

    Args:
        snapshot: The admitted
            :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            whose revision declares the families to count.

    Returns:
        One member count per enrolled schema family.
    """
    return {family: len(getattr(snapshot.revision, family)) for family in REVISION_SCHEMA_FAMILY_FIELDS}


def resolve_graded_snapshot_schema_identity(snapshot: RegistrySnapshot) -> ModeloWorkspaceSchemaIdentityV1:
    """Build the GRADED_SNAPSHOT schema identity from the one REGISTRY capture already held.

    Mirrors :func:`resolve_static_inspection_schema_identity`'s exact shape over
    the snapshot's own declared identity sets. The inspection carries bare id
    frozensets where the snapshot carries full definition tuples; the
    fingerprint reduces the latter to the former's shape so the two admissions'
    schema fingerprints are comparable in kind.

    Args:
        snapshot: The admitted
            :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            whose declared identity sets the fingerprint reduces.

    Returns:
        The schema identity for this graded admission.
    """
    field_manifest_capture = ModeloWorkspaceFieldManifestPortV1(authority=snapshot).capture_projection_with_epoch()
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
    """Build the evidence horizon from the snapshot's own retained source catalogue.

    ``RegistrySnapshot.sources`` is keyed by the same ``SourceRefId`` identity
    the inspection's ``source_ref_ids`` holds, so both admissions reduce to the
    identical horizon shape.

    Args:
        snapshot: The admitted
            :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            whose retained source catalogue the horizon is read from.

    Returns:
        The evidence horizon this graded projection rests on.
    """
    source_refs = tuple(sorted(snapshot.sources))
    return ModeloWorkspaceEvidenceHorizonV1(
        source_refs=source_refs,
        evidence_digest=content_hash_hex({"source_refs": source_refs}),
    )


def graded_snapshot_contributors() -> tuple[ModeloWorkspaceContributorIdentityV1, ...]:
    """Return the six contributor identities GRADED_SNAPSHOT actually reads.

    The four STATIC_INSPECTION reads (registry, work, locale_catalogue,
    field_manifest) plus CALCULATION, which supplies the materialization and
    provenance facets, and READINESS, which supplies the readiness projection.

    BOUNDED_REVIEW is deliberately absent: this admission does not assemble a
    work review, and it says so through
    :data:`GRADED_SNAPSHOT_WORK_REVIEW_FACET` rather than by listing a
    contributor it never captures. A contributor named here but never captured
    would corrupt the epoch digest every facet revalidates against.
    """
    return tuple(
        sorted(
            (
                MODELO_WORKSPACE_WORK_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_LOCALE_CATALOGUE_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_REGISTRY_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1.contributor,
            ),
            key=lambda contributor: (contributor.owner, contributor.producer),
        )
    )


def resolve_graded_snapshot_baseline(
    target: ModeloWorkspaceResolvedTargetV1,
    *,
    schema_identity: ModeloWorkspaceSchemaIdentityV1,
    locale: ModeloWorkspaceLocaleSummaryV1,
    stamps: tuple[ModeloWorkspaceProducerStampV1, ...],
    epochs: tuple[ModeloWorkspaceEpochV1, ...],
) -> ModeloWorkspaceBaselineV1:
    """Assemble the GRADED_SNAPSHOT baseline from its contributors' stamps and epochs.

    Takes the stamps and epochs as tuples rather than one named pair per
    contributor. The static admission's set is fixed at four and can be spelled
    out; this admission's set is whatever :func:`graded_snapshot_contributors`
    declares, and a signature that fixed the arity would need rewriting every
    time that declaration changed -- exactly the drift the shared declaration
    exists to prevent. Every stamp and epoch passed in MUST come from the same
    captures that produced ``target``, ``schema_identity`` and ``locale``; this
    function captures nothing of its own.
    """
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


def graded_snapshot_family_dispositions(
    snapshot: RegistrySnapshot,
) -> tuple[ModeloWorkspaceFamilyDispositionV1, ...]:
    """Project only the family dispositions the snapshot's revision has declared.

    See :func:`_not_applicable_family_dispositions` for the shared logic; this
    is the graded half of the identical projection.

    Args:
        snapshot: The admitted
            :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            whose revision declares the inapplicability claims.

    Returns:
        One row per family the revision declared not applicable.
    """
    return _not_applicable_family_dispositions(snapshot.revision.family_dispositions)


def graded_snapshot_casilla_schema_records(
    casillas: tuple[CasillaDefinition, ...],
    bindings: tuple[BindingDefinition, ...],
    formulas: tuple[FormulaDefinition, ...],
    target: ModeloWorkspaceResolvedTargetV1,
    *,
    output_language: OutputLanguage,
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per casilla DEFINITION, sorted for stable pagination.

    A graded snapshot carries the full :class:`CasillaDefinition` -- including
    ``legal_refs``, ``source_refs`` and ``constraints`` -- that a static
    inspection deliberately excludes. This is the richer half the
    ``None``-versus-``()`` arms exist for: ``legal_refs`` is the definition's
    own real tuple, and ``constraints`` is a single self-referential reference
    when the definition declares a constraints block and empty when it declares
    none -- never ``None``, since this producer DOES carry the data.

    ``continuity``, ``export_exposure``, ``formula_operands`` and
    ``relation_endpoints`` all reuse the identical join functions the static
    walk uses, over the same registry-declared edges, so the two walks cannot
    disagree about which formula, fold or export field touches a casilla.
    """
    ordered = sorted(casillas, key=lambda item: item.id)
    keys = [
        casilla_occurrence_locale_key(
            target.modelo, target.law_selected_revision_id, casilla.id, ModeloLocalizationFieldKind.LABEL
        )
        for casilla in ordered
    ]
    labels = _resolve_locale_summaries_and_values(keys, output_language=output_language)
    records: list[ModeloWorkspaceSchemaRecordV1] = []
    for casilla, key, (locale_summary, value) in zip(ordered, keys, labels, strict=True):
        casilla_id = casilla.id
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceCasillaReferenceV1(casilla_id=casilla_id),
                record_family=("casillas",),
                section_path=tuple(casilla.section),
                data_type="casilla_id",
                label=ModeloWorkspaceLocalizedTextV1(
                    locale_key=key,
                    value=value if value is not None else casilla_id,
                    locale=locale_summary,
                ),
                classification=ModeloWorkspaceSchemaClassification.PROJECTED,
                family_disposition=RegistrySchemaFamilyDisposition.POPULATED,
                legal_refs=tuple(casilla.legal_refs),
                source_refs=tuple(casilla.source_refs),
                constraints=(
                    (ModeloWorkspaceConstraintReferenceV1(casilla_id=casilla_id),)
                    if casilla.constraints is not None
                    else ()
                ),
                continuity=casilla_continuity_references(casilla.continuidad_id),
                export_exposure=casilla_export_exposure_references(casilla_id, tuple(casilla.export_refs)),
                formula_operands=formula_operand_references_for_casilla(formulas, casilla_id),
                relation_endpoints=relation_source_endpoints_for_casilla(
                    bindings,
                    casilla_id,
                    source_modelo=str(target.modelo),
                ),
            )
        )
    return tuple(records)


def graded_snapshot_schema_records(
    snapshot: RegistrySnapshot,
    target: ModeloWorkspaceResolvedTargetV1,
    *,
    output_language: OutputLanguage,
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Return the complete GRADED_SNAPSHOT schema_facet across every reference kind.

    BINDING, FORMULA and PARAMETER rows call the exact same shared functions
    STATIC_INSPECTION calls -- one implementation, not a parallel copy that
    could drift. Only CASILLA uses a graded-specific builder, because only
    CASILLA's underlying data genuinely differs between the two admissions.

    Args:
        snapshot: The admitted
            :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            whose revision supplies every reference kind.
        target: The resolved target the records are labelled for.
        output_language: The language each label is resolved in.

    Returns:
        The complete schema facet in its canonical stable order.
    """
    revision = snapshot.revision
    records = (
        graded_snapshot_casilla_schema_records(
            revision.casillas,
            revision.bindings,
            revision.formulas,
            target,
            output_language=output_language,
        )
        + binding_schema_records(frozenset(binding.id for binding in revision.bindings), revision.bindings)
        + formula_schema_records(revision.formulas)
        + parameter_schema_records(revision.parameters, revision.formulas)
    )
    return tuple(sorted(records, key=lambda record: (record.reference.kind, str(record.reference))))


def graded_snapshot_materialization_records(
    calculation_revision: CalculationRevision,
) -> tuple[ModeloWorkspaceMaterializationRecordV1, ...]:
    """Project one calculation revision's scalar and repeated-row values, unmodified.

    Scalar values come straight from ``casilla_values``. Repeated-row values
    come from ``row_casilla_values``, grouped by the ``source_binding_id`` the
    row's own ``row_casilla_provenance`` entry names -- the registry-declared
    identity of WHICH binding produced that row, never re-derived from an
    identifier's shape. A row value with no provenance entry cannot be
    attributed and is refused rather than grouped under a fabricated identity.

    Args:
        calculation_revision: The captured
            :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            whose persisted values are projected unmodified.

    Returns:
        Every scalar record followed by every repeated-row record.
    """
    scalar_records: tuple[ModeloWorkspaceMaterializationRecordV1, ...] = tuple(
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
        grouped.setdefault((str(provenance.source_binding_id), row_index), []).append((casilla_id, value))

    repeated_records: tuple[ModeloWorkspaceMaterializationRecordV1, ...] = tuple(
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


def graded_snapshot_provenance_records(
    source_provenance: tuple[CalculationSourceRef, ...],
) -> tuple[ModeloWorkspaceProvenanceRecordV1, ...]:
    """Project the persisted resolver lineage into per-casilla provenance records.

    A :class:`CalculationSourceRef` carries ``source_casilla_ids`` naming which
    casillas, if any, its resolution feeds. One ref fans out into one record per
    casilla it names. A ref whose resolver call site associated no casilla still
    produces exactly ONE record, with ``subject=None``: an audit reader must see
    every contributing source, including the unattributed ones, rather than have
    them vanish from the facet.
    """
    records: list[ModeloWorkspaceProvenanceRecordV1] = []
    for ref in source_provenance:
        if not ref.source_casilla_ids:
            records.append(ModeloWorkspaceProvenanceRecordV1(subject=None, calculation_source=ref))
            continue
        records.extend(
            ModeloWorkspaceProvenanceRecordV1(
                subject=ModeloWorkspaceCasillaReferenceV1(casilla_id=casilla_id),
                calculation_source=ref,
            )
            for casilla_id in sorted(ref.source_casilla_ids)
        )
    return tuple(records)


def graded_snapshot_modelo_workspace_capabilities(
    snapshot: RegistrySnapshot,
    resolved_target: ModeloWorkspaceResolvedTargetV1,
    *,
    calculation_revision: CalculationRevision,
    readiness: ProjectionModeloReadiness,
) -> tuple[ModeloWorkspaceCapabilityV1, ...]:
    """Return the complete GRADED_SNAPSHOT capability denominator.

    ``AVAILABLE`` requires reading what a canonical producer WROTE, never
    deriving a verdict from downstream state:

    * ``SCHEMA_INSPECTION`` is ``AVAILABLE`` unconditionally, as for a static
      inspection -- a deterministic generated denominator, not a producer
      verdict.
    * ``CALCULATION_MATERIALIZATION`` is ``AVAILABLE`` when the captured
      revision belongs to this target's own work unit, which reads the
      calculate producer's own persisted object rather than inferring
      "materialized" from non-empty values.
    * ``VERIFICATION_READINESS`` is ``AVAILABLE`` when that same revision's
      state is ``VERIFICADO_COMPLETO``, a state the record only reaches with
      its ``verified_at``/``verified_by`` stamps present -- a separately
      stamped verdict from the verify producer.
    * ``FILING_DRAFT_READINESS`` reads the READINESS producer's own ``ready``
      verdict for this exact target. ``ready`` false is ``UNMEASURED`` rather
      than ``REFUSED``: the producer measured and found the target not ready,
      which the readiness projection itself states axis by axis; a capability
      row is not the place to restate it as a refusal.

    Args:
        snapshot: The admitted
            :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            whose declarations explain each capability answer.
        resolved_target: The target every row is pinned to.
        calculation_revision: The captured
            :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            whose own persisted state settles the two calculate-side answers.
        readiness: The readiness producer's own verdict for this target.

    Returns:
        The complete capability denominator, one row per capability.
    """
    calculation_available = calculation_revision.work_unit_id == resolved_target.work_unit_id
    verification_available = calculation_available and (
        calculation_revision.state is CalculationRevisionState.VERIFICADO_COMPLETO
    )
    counts = graded_snapshot_schema_family_member_counts(snapshot)
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
            ModeloWorkspaceCapabilityDisposition.AVAILABLE
            if readiness.ready
            else ModeloWorkspaceCapabilityDisposition.UNMEASURED,
        ),
    )
    return tuple(
        _capability_row(
            capability,
            disposition=disposition,
            contract=contract,
            resolved_target=resolved_target,
            declarations=snapshot.revision.family_dispositions,
            declared_member_count=counts.get(_WORKSPACE_CAPABILITY_SOURCE_FAMILIES[capability]),
        )
        for capability, contract, disposition in dispositions
    )


def resolve_graded_snapshot_result(
    target: ModeloWorkspaceTargetV1,
    *,
    required_grade: RegistryAuthorityGrade,
    bucket_id: str,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_ports: CalculationActionPorts,
    readiness_read_ports: StateProjectionReadPorts,
    operation: PinnedAuthorityOperation,
    output_language: OutputLanguage,
    page_size: int = 200,
    cursor: ModeloWorkspaceCursorV1 | None = None,
) -> ModeloWorkspaceResultV1:
    """Assemble the complete GRADED_SNAPSHOT result for one target, or refuse honestly.

    Mirrors :func:`resolve_static_inspection_result`'s discipline: WORK is
    captured exactly once, REGISTRY exactly once from WORK's own resolved
    coordinate rather than from the target's raw operands, and CALCULATION and
    READINESS exactly once each. ``operation`` serves as both the registry
    authority and the pinned authority the calculation and readiness producers
    read through, so every contributor sees one generation of the registry.

    The three refusals are ordered by what makes a graded result impossible
    first, not by which check happens to fail last:

    * ``TARGET_NOT_FOUND`` immediately after the WORK capture, when no work
      unit exists at the target's natural coordinate. No resolved target
      exists to attach, so the refusal carries ``selected_target=None``
      honestly rather than a fabricated one.
    * ``AUTHORITY_GRADE_UNAVAILABLE`` around the REGISTRY capture, recognised
      by the typed ``RegistryFailureCondition`` on the raised validation error
      rather than by message text.
    * ``CALCULATION_UNAVAILABLE`` after the target resolves, when the work
      unit exists but carries no calculation revision yet. Checked after the
      registry capture, not before it, so the refusal can name the resolved
      target the operator is being sent back to -- a graded read needs that
      capture anyway, so nothing is read that a success would not have read.

    ``work_review`` is :data:`GRADED_SNAPSHOT_WORK_REVIEW_FACET`: this
    admission reads no bounded-review producer and declares the review
    unmeasured rather than assembling one of its own.
    """
    if cursor is not None and cursor.facet not in _GRADED_SNAPSHOT_PAGINATED_FACETS:
        raise ModeloWorkspaceStaleCursorError(
            "graded snapshot paginates the schema, materialization and provenance facets; "
            f"cursor names {cursor.facet.value}"
        )

    work_capture = ModeloWorkspaceWorkPortV1(
        request=modelo_work_selector_request_for_target(target, bucket_id=bucket_id),
        catalogue_repository=catalogue_repository,
        mode=ModeloWorkSelectionMode.VISIBLE_OR_EXACT,
    ).capture_projection_with_epoch()
    resolution = work_capture.projection
    resolved_modelo, resolved_filing_year, resolved_period = _resolved_obligation(resolution)

    work_unit = resolution.work_unit
    if work_unit is None:
        return graded_snapshot_refusal(
            ModeloWorkspaceRefusalCode.TARGET_NOT_FOUND,
            requested_target=target,
            selected_target=None,
            capability=ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION,
            reconsideration_condition="create a work unit for this target, then request a graded snapshot again",
            facts=(
                ModeloWorkspaceEvidenceFactV1(
                    name="modelo",
                    value=ModeloWorkspaceTextFactValueV1(value=str(resolved_modelo)),
                ),
                ModeloWorkspaceEvidenceFactV1(
                    name="period",
                    value=ModeloWorkspaceTextFactValueV1(value=resolved_period.registry_token),
                ),
            ),
            evidence=(),
            source_disposition=None,
            recovery_action=modelo_workspace_recovery_action(
                "operator.modelo.work.create",
                work_unit_id=None,
            ),
        )

    try:
        registry_capture = ModeloWorkspaceRegistryPortV1(
            authority=operation,
            modelo_id=resolved_modelo,
            filing_year=resolved_filing_year,
            period=resolved_period.registry_token,
            grade=required_grade,
        ).capture_projection_with_epoch()
    except RegistryValidationError as exc:
        failure = exc.registry_failure
        if failure is None or failure.condition is not RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT:
            raise
        return graded_snapshot_refusal(
            ModeloWorkspaceRefusalCode.AUTHORITY_GRADE_UNAVAILABLE,
            requested_target=target,
            selected_target=None,
            capability=ModeloWorkspaceCapabilityName.SCHEMA_INSPECTION,
            reconsideration_condition="request a grade the selected revision's declared authority can satisfy",
            facts=(
                ModeloWorkspaceEvidenceFactV1(
                    name="required_grade",
                    value=ModeloWorkspaceTextFactValueV1(value=required_grade.value),
                ),
            ),
            evidence=(),
            source_disposition=None,
            recovery_action=modelo_workspace_recovery_action(
                "operator.modelo.work.status",
                work_unit_id=work_unit.work_unit_id,
            ),
        )

    registry_projection = registry_capture.projection
    snapshot = registry_projection.snapshot
    if snapshot is None:
        raise ModeloWorkspaceAbsentRegistryProjectionError(
            "registry capture returned no snapshot for the resolved revision",
        )

    axes = resolve_modelo_workspace_revision_axes(resolution, registry_projection=registry_projection)
    resolved_target = ModeloWorkspaceResolvedTargetV1(
        bucket_id=resolution.bucket_id,
        modelo=resolved_modelo,
        filing_year=resolved_filing_year,
        period=resolved_period,
        law_selected_revision_id=axes.law_selected_revision_id,
        review_status=registry_projection.review_status,
        requested_revision_assertion=axes.requested_revision_assertion,
        stored_revision_assertion=axes.stored_revision_assertion,
        work_unit_id=work_unit.work_unit_id,
        work_state=work_unit.state,
    )

    calculation_revision_id = work_unit.current_calculation_revision_id
    if calculation_revision_id is None:
        return graded_snapshot_refusal(
            ModeloWorkspaceRefusalCode.CALCULATION_UNAVAILABLE,
            requested_target=target,
            selected_target=resolved_target,
            capability=ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION,
            reconsideration_condition="calculate this work unit, then request a graded snapshot again",
            facts=(
                ModeloWorkspaceEvidenceFactV1(
                    name="work_unit_id",
                    value=ModeloWorkspaceTextFactValueV1(value=str(work_unit.work_unit_id)),
                ),
            ),
            evidence=_schema_family_evidence(
                _WORKSPACE_CAPABILITY_SOURCE_FAMILIES[ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION],
                declarations=snapshot.revision.family_dispositions,
            ),
            source_disposition=_schema_family_disposition(
                _WORKSPACE_CAPABILITY_SOURCE_FAMILIES[ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION],
                declarations=snapshot.revision.family_dispositions,
                declared_member_count=len(snapshot.revision.formulas),
            ),
            recovery_action=modelo_workspace_recovery_action(
                "operator.modelo.work.calculate",
                work_unit_id=resolved_target.work_unit_id,
            ),
        )

    calculation_capture = ModeloWorkspaceCalculationPortV1(
        calculation_revision_id=calculation_revision_id,
        ports=calculation_ports,
    ).capture_projection_with_epoch()
    calculation_revision = calculation_capture.projection

    readiness_capture = ModeloWorkspaceReadinessPortV1(
        requests=(
            ModeloReadinessRequest(
                modelo=str(resolved_target.modelo),
                revision_id=resolved_target.law_selected_revision_id,
                filing_year=resolved_target.filing_year,
                period=resolved_target.period,
            ),
        ),
        active_profile_id=resolved_target.bucket_id,
        read_ports=readiness_read_ports,
        operation=operation,
    ).capture_projection_with_epoch()
    readiness_reports = readiness_capture.projection.reports
    if not readiness_reports:
        raise ModeloWorkspaceAbsentReadinessProjectionError(
            "readiness capture returned no report for the resolved target",
        )
    readiness = readiness_reports[0]

    schema_identity = resolve_graded_snapshot_schema_identity(snapshot)
    locale = capture_modelo_workspace_locale_summary(resolved_target, output_language=output_language)
    locale_capture = ModeloWorkspaceLocaleCataloguePortV1(
        translation_key=revision_locale_key(resolved_target.modelo, resolved_target.law_selected_revision_id),
        locale=output_language.value,
    ).capture_projection_with_epoch()
    field_manifest_capture = ModeloWorkspaceFieldManifestPortV1(authority=snapshot).capture_projection_with_epoch()

    captures = (
        work_capture,
        registry_capture,
        locale_capture,
        field_manifest_capture,
        calculation_capture,
        readiness_capture,
    )
    baseline = resolve_graded_snapshot_baseline(
        resolved_target,
        schema_identity=schema_identity,
        locale=locale,
        stamps=tuple(capture.stamp for capture in captures),
        epochs=tuple(capture.epoch for capture in captures),
    )
    contributors = graded_snapshot_contributors()

    schema_facet = paginate_modelo_workspace_facet(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1],
        graded_snapshot_schema_records(snapshot, resolved_target, output_language=output_language),
        facet=ModeloWorkspaceFacetName.SCHEMA,
        cursor=_facet_cursor(cursor, ModeloWorkspaceFacetName.SCHEMA),
        target=resolved_target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=page_size,
    )
    materialization_facet = paginate_modelo_workspace_facet(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceMaterializationRecordV1],
        graded_snapshot_materialization_records(calculation_revision),
        facet=ModeloWorkspaceFacetName.MATERIALIZATION,
        cursor=_facet_cursor(cursor, ModeloWorkspaceFacetName.MATERIALIZATION),
        target=resolved_target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=page_size,
    )
    provenance_facet = paginate_modelo_workspace_facet(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceProvenanceRecordV1],
        graded_snapshot_provenance_records(calculation_revision.source_provenance),
        facet=ModeloWorkspaceFacetName.PROVENANCE,
        cursor=_facet_cursor(cursor, ModeloWorkspaceFacetName.PROVENANCE),
        target=resolved_target,
        schema_identity=schema_identity,
        baseline=baseline,
        contributors=contributors,
        disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
        page_size=page_size,
    )

    declared_grade = snapshot.revision.effective_authority_grade
    projection = ModeloWorkspaceProjectionV1(
        admission=ModeloWorkspaceGradedSnapshotScopeV1(
            scope=ModeloWorkspaceSnapshotScopeV1(
                required_grade=required_grade,
                declared_grade=declared_grade,
                snapshot_scope_digest=content_hash_hex(
                    {
                        "required_grade": required_grade.value,
                        "declared_grade": declared_grade.value,
                        "selected_revision_id": resolved_target.law_selected_revision_id,
                    }
                ),
            )
        ),
        target=resolved_target,
        schema_identity=schema_identity,
        locale=locale,
        evidence_horizon=graded_snapshot_evidence_horizon(snapshot),
        family_dispositions=graded_snapshot_family_dispositions(snapshot),
        contributors=contributors,
        baseline=baseline,
        schema_facet=schema_facet,
        materialization_facet=materialization_facet,
        provenance_facet=provenance_facet,
        work_review=GRADED_SNAPSHOT_WORK_REVIEW_FACET,
        readiness=readiness,
        capabilities=graded_snapshot_modelo_workspace_capabilities(
            snapshot,
            resolved_target,
            calculation_revision=calculation_revision,
            readiness=readiness,
        ),
    )
    return ModeloWorkspaceGradedSnapshotResultV1(projection=projection)
