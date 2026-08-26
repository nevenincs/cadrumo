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

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...core import OutputLanguage, RegistrySchemaFamilyDisposition, content_hash_hex
from ...domain.calculations.registry.modelo_localization import casilla_occurrence_locale_key, revision_locale_key
from ...domain.calculations.registry.schema import FormulaDefinition, RelationDefinition
from ...domain.calculations.registry.schema_formula import FormulaExpression
from ...domain.calculations.registry.static_inspection import RegistryRevisionInspection
from ...domain.modelos import ModeloCode
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from .work_addressing import (
    ModeloExactWorkUnitTarget,
    ModeloVisibleFilingTarget,
    ModeloWorkResolution,
    ModeloWorkSelectionMode,
    ModeloWorkSelectorRequest,
)
from .workspace_models import (
    ModeloWorkspaceBaselineV1,
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceCapabilityV1,
    ModeloWorkspaceBindingReferenceV1,
    ModeloWorkspaceBoundedFacetV1,
    ModeloWorkspaceCasillaReferenceV1,
    ModeloWorkspaceContributorIdentityV1,
    ModeloWorkspaceCursorV1,
    ModeloWorkspaceEvidenceHorizonV1,
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceFamilyDispositionV1,
    ModeloWorkspaceFormulaReferenceV1,
    ModeloWorkspaceFormulaBindingOperandReferenceV1,
    ModeloWorkspaceFormulaCasillaOperandReferenceV1,
    ModeloWorkspaceFormulaDateBindingOperandReferenceV1,
    ModeloWorkspaceFormulaDispatchOperandReferenceV1,
    ModeloWorkspaceFormulaLiteralOperandReferenceV1,
    ModeloWorkspaceFormulaOperandReferenceV1,
    ModeloWorkspaceFormulaParameterOperandReferenceV1,
    ModeloWorkspaceFormulaRelationOperandReferenceV1,
    ModeloWorkspaceLocaleDisposition,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceLocalizedTextV1,
    ModeloWorkspaceParameterReferenceV1,
    ModeloWorkspaceRelationReferenceV1,
    ModeloWorkspaceRelationSourceEndpointReferenceV1,
    ModeloWorkspaceRelationTargetEndpointReferenceV1,
    ModeloWorkspaceProjectionV1,
    ModeloWorkspaceResolvedTargetV1,
    ModeloWorkspaceSchemaClassification,
    ModeloWorkspaceSchemaIdentityV1,
    ModeloWorkspaceStaticInspectionResultV1,
    ModeloWorkspaceStaticInspectionScopeV1,
    ModeloWorkspaceTechnicalLabelV1,
    ModeloWorkspaceSchemaRecordV1,
    ModeloWorkspaceWorkReviewFacetV1,
    ModeloWorkspaceRevisionAssertionDisposition,
    ModeloWorkspaceRevisionAssertionSource,
    ModeloWorkspaceRevisionAssertionV1,
    ModeloWorkspaceTargetV1,
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
    ModeloWorkspaceContributingProjectionV1,
    ModeloWorkspaceEpochV1,
    ModeloWorkspaceFieldManifestPortV1,
    ModeloWorkspaceLocaleCataloguePortV1,
    ModeloWorkspaceProducerContractV1,
    ModeloWorkspaceProducerStampV1,
    ModeloWorkspaceRegistryPortV1,
    ModeloWorkspaceRegistryProjectionV1,
    ModeloWorkspaceWorkPortV1,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import ValidatedRegistryAuthority


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
    once from that single WORK-derived coordinate. Static admission
    (``grade=None``) is the only grade this function requests; a graded
    snapshot capture is a separate, not-yet-built caller that passes a
    ``grade`` through the same port.
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


# S279 (ADR amendment "Canonical capability and refusal facade"): the
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
# SCHEMA_INSPECTION is AVAILABLE (W03.P20.S278 resolved static inspection's
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
    the S279 ADR amendment; see the module-level comment above this function.
    ``schema_inspection`` is ``AVAILABLE`` -- field_manifest is a real
    STATIC_INSPECTION contributor per S278. The other four are ``UNMEASURED``:
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


__all__ = [
    "ModeloWorkspaceRevisionAxes",
    "capture_modelo_workspace_locale_summary",
    "capture_modelo_workspace_target_axes",
    "capture_modelo_workspace_target_captures",
    "formula_expression_operand_references",
    "formula_operand_references_for_casilla",
    "modelo_work_selector_request_for_target",
    "relation_source_endpoints_for_casilla",
    "relation_target_endpoints_for_binding",
    "resolve_modelo_workspace_revision_axes",
    "resolve_modelo_workspace_target",
    "STATIC_INSPECTION_WORK_REVIEW_FACET",
    "resolve_static_inspection_baseline",
    "resolve_static_inspection_schema_identity",
    "static_inspection_contributors",
    "static_inspection_evidence_horizon",
    "static_inspection_modelo_workspace_capabilities",
    "ModeloWorkspaceStaleCursorError",
    "paginate_static_inspection_schema_facet",
    "static_inspection_casilla_schema_records",
    "static_inspection_binding_schema_records",
    "static_inspection_formula_schema_records",
    "static_inspection_relation_schema_records",
    "static_inspection_parameter_schema_records",
    "static_inspection_schema_records",
    "static_inspection_family_dispositions",
    "resolve_static_inspection_result",
]


# --- S277 (ADR amendment "Schema, materialization, and provenance
# projection"): schema-record join semantics, each derived from the
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
        return (ModeloWorkspaceFormulaCasillaOperandReferenceV1(formula_id=formula_id, casilla_id=expression.casilla_id),)
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
        return (ModeloWorkspaceFormulaRelationOperandReferenceV1(formula_id=formula_id, relation_id=expression.relation),)
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
    the S278 inspection-rooted field manifest's own digest; the edit
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


STATIC_INSPECTION_WORK_REVIEW_FACET = ModeloWorkspaceWorkReviewFacetV1(
    disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
    review=None,
)
"""STATIC_INSPECTION never reads bounded_review (S279); this is the fixed, non-varying facet value."""


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


class ModeloWorkspaceStaleCursorError(ValueError):
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

    Bounded to identity per S283: ``legal_refs`` and ``constraints`` are
    ``None`` (this admission's producer never carries `CasillaDefinition`
    data), never ``()``. ``formula_operands`` and ``relation_endpoints``
    consume the S277 join functions directly rather than re-deriving either
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
                section_path=("casillas",),
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


def static_inspection_binding_schema_records(
    inspection: RegistryRevisionInspection,
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per binding identity, sorted for stable pagination.

    Unlike a casilla, ``DataBindingDefinition`` IS retained whole by the
    inspection, so ``legal_refs`` is the binding's own real (possibly empty)
    tuple, never ``None`` -- S283's absence rule applies only where the
    inspection genuinely carries no such data. Per S284, the label is
    ``ModeloWorkspaceTechnicalLabelV1``: no locale convention exists for
    binding identities.
    """
    bindings_by_id = {binding.id: binding for binding in inspection.bindings}
    relations = inspection.relations
    records: list[ModeloWorkspaceSchemaRecordV1] = []
    for binding_id in sorted(inspection.binding_ids):
        binding = bindings_by_id.get(binding_id)
        legal_refs = tuple(binding.legal_refs) if binding is not None else None
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceBindingReferenceV1(binding_id=binding_id),
                section_path=("bindings",),
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


def static_inspection_formula_schema_records(
    inspection: RegistryRevisionInspection,
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per formula, carrying its own full operand set.

    A FORMULA row's ``formula_operands`` is that formula's own complete
    input list (every operand its expression declares, of every kind) --
    the mirror of a CASILLA row's ``formula_operands``, which lists only the
    subset naming that one casilla. Both readings are the same field walked
    from opposite ends of the identical S277 join.
    """
    records: list[ModeloWorkspaceSchemaRecordV1] = []
    for formula in sorted(inspection.formulas, key=lambda item: item.id):
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceFormulaReferenceV1(formula_id=formula.id),
                section_path=("formulas",),
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


def static_inspection_relation_schema_records(
    inspection: RegistryRevisionInspection,
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per relation, carrying both of its own endpoints.

    A RELATION row states its own two endpoints directly from the
    registry-declared fields (``source_casilla_id``, ``target_binding``) --
    it is the one reference kind that is never ambiguous about which side it
    claims, since it names both.
    """
    records: list[ModeloWorkspaceSchemaRecordV1] = []
    for relation in sorted(inspection.relations, key=lambda item: item.id):
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceRelationReferenceV1(relation_id=relation.id),
                section_path=("relations",),
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


def static_inspection_parameter_schema_records(
    inspection: RegistryRevisionInspection,
) -> tuple[ModeloWorkspaceSchemaRecordV1, ...]:
    """Build one schema record per parameter, keyed off every formula that dispatches to it.

    A parameter has no direct outbound edge of its own in the registry
    schema; the only declared connection is a formula's own
    ``dispatch_table`` operand naming it, which
    :func:`formula_expression_operand_references` already extracts as
    ``ModeloWorkspaceFormulaParameterOperandReferenceV1`` and
    ``ModeloWorkspaceFormulaDispatchOperandReferenceV1`` entries.
    """
    formulas = inspection.formulas
    parameter_operands: dict[str, list[ModeloWorkspaceFormulaOperandReferenceV1]] = {}
    for formula in formulas:
        for reference in formula_expression_operand_references(formula.id, formula.expression):
            if isinstance(reference, ModeloWorkspaceFormulaParameterOperandReferenceV1):
                parameter_operands.setdefault(reference.parameter_id, []).append(reference)
            elif isinstance(reference, ModeloWorkspaceFormulaDispatchOperandReferenceV1):
                for parameter_id in reference.parameter_ids:
                    parameter_operands.setdefault(parameter_id, []).append(reference)

    records: list[ModeloWorkspaceSchemaRecordV1] = []
    for parameter in sorted(inspection.parameters, key=lambda item: item.id):
        records.append(
            ModeloWorkspaceSchemaRecordV1(
                reference=ModeloWorkspaceParameterReferenceV1(parameter_id=parameter.id),
                section_path=("parameters",),
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
        + static_inspection_binding_schema_records(inspection)
        + static_inspection_formula_schema_records(inspection)
        + static_inspection_relation_schema_records(inspection)
        + static_inspection_parameter_schema_records(inspection)
    )
    return tuple(sorted(records, key=lambda record: (record.reference.kind, str(record.reference))))


def paginate_static_inspection_schema_facet(
    records: tuple[ModeloWorkspaceSchemaRecordV1, ...],
    *,
    target: ModeloWorkspaceResolvedTargetV1,
    schema_identity: ModeloWorkspaceSchemaIdentityV1,
    baseline: ModeloWorkspaceBaselineV1,
    contributors: tuple[ModeloWorkspaceContributorIdentityV1, ...],
    disposition: ModeloWorkspaceCapabilityDisposition,
    page_size: int,
    cursor: ModeloWorkspaceCursorV1 | None = None,
) -> ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1]:
    """Return one bounded, cursor-consistent page from the complete ``records`` sequence.

    ``records`` MUST already be in the caller's canonical stable order --
    pagination consumes an offset over that fixed order, never re-derives it.
    A ``cursor`` from a DIFFERENT baseline, revision, schema identity, or
    contributor epoch refuses outright rather than silently starting over or
    returning a page from the wrong coordinate.
    """
    if cursor is not None:
        if (
            cursor.baseline != baseline
            or cursor.selected_revision_id != target.law_selected_revision_id
            or cursor.schema_identity != schema_identity
            or cursor.facet is not ModeloWorkspaceFacetName.SCHEMA
            or cursor.contributor_epoch_digest != baseline.contributor_epoch_digest
        ):
            raise ModeloWorkspaceStaleCursorError(
                "workspace schema facet cursor no longer matches the current baseline coordinate"
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
            facet=ModeloWorkspaceFacetName.SCHEMA,
            contributor_epoch_digest=baseline.contributor_epoch_digest,
            continuation=str(next_offset),
        )
        if has_more
        else None
    )
    return ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1](
        selected_revision_id=target.law_selected_revision_id,
        schema_identity=schema_identity,
        baseline=baseline,
        contributor_epoch_digest=baseline.contributor_epoch_digest,
        contributors=contributors,
        facet=ModeloWorkspaceFacetName.SCHEMA,
        disposition=disposition,
        records=page,
        page_size=page_size,
        next_cursor=next_cursor,
        has_more=has_more,
    )


def static_inspection_family_dispositions(
    inspection: RegistryRevisionInspection,
) -> tuple[ModeloWorkspaceFamilyDispositionV1, ...]:
    """Project only the family dispositions the inspection can honestly attest to.

    ``inspection.family_dispositions`` carries exactly the families the
    revision has explicitly declared NOT_APPLICABLE, each grounded with its
    own reason/legal_refs/source_refs -- a substantive claim the registry
    itself made. A family absent from that mapping is not reported here at
    all: the inspection carries no data for most schema families (it strips
    everything but casilla/binding/formula/relation/parameter/projection-endpoint/
    workbook-parity/live-cross-reference identifiers), so silently
    defaulting an unreported family to POPULATED or BLOCKED_PENDING_EVIDENCE
    would assert a fact the inspection has no basis for. Reporting nothing is
    honest; guessing is not.
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
                for family, declaration in inspection.family_dispositions.items()
            ),
            key=lambda item: item.family,
        )
    )


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
    exactly as :func:`paginate_static_inspection_schema_facet` proves.

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
    schema_facet = paginate_static_inspection_schema_facet(
        records,
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
