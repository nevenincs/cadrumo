"""Graded Modelo Workspace projection and admission."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.errors.hierarchy import CadrumoError, InternalInvariantError
from ...core.external_constants import OutputLanguage
from ...core.hashing import content_hash_hex
from ...core.identity.hex_ids import WorkUnitId
from ...core.period import Period
from ...core.schema_family_disposition import RegistrySchemaFamilyDisposition
from ...domain.calculations.registry.errors import RegistryFailureCondition, RegistryValidationError
from ...domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
    revision_locale_key,
)
from ...domain.calculations.registry.schema import (
    REVISION_SCHEMA_FAMILY_FIELDS,
    BindingDefinition,
    FormulaDefinition,
    RegistrySnapshot,
)
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.calculation_revision_sources import CalculationSourceRef
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..operator_actions.models import ActionReference
from ..state_projection_models import ModeloReadinessRequest, ProjectionModeloReadiness
from .work_selection import (
    ModeloWorkSelectionMode,
)
from .workspace_models import (
    ModeloWorkspaceBaselineV1,
    ModeloWorkspaceBoundedFacetV1,
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceCapabilityV1,
    ModeloWorkspaceCasillaReferenceV1,
    ModeloWorkspaceConstraintReferenceV1,
    ModeloWorkspaceContributorIdentityV1,
    ModeloWorkspaceCursorV1,
    ModeloWorkspaceDomainRefusalV1,
    ModeloWorkspaceEvidenceFactV1,
    ModeloWorkspaceEvidenceHorizonV1,
    ModeloWorkspaceEvidenceReferenceV1,
    ModeloWorkspaceFacetName,
    ModeloWorkspaceFamilyDispositionV1,
    ModeloWorkspaceGradedSnapshotResultV1,
    ModeloWorkspaceGradedSnapshotScopeV1,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceLocalizedTextV1,
    ModeloWorkspaceMaterializationRecordV1,
    ModeloWorkspaceProjectionV1,
    ModeloWorkspaceProvenanceRecordV1,
    ModeloWorkspaceRefusalCode,
    ModeloWorkspaceRefusedResultV1,
    ModeloWorkspaceRepeatedRowMaterializationRecordV1,
    ModeloWorkspaceRepeatedRowMaterializationV1,
    ModeloWorkspaceResolvedTargetV1,
    ModeloWorkspaceResultV1,
    ModeloWorkspaceScalarMaterializationRecordV1,
    ModeloWorkspaceScalarMaterializationV1,
    ModeloWorkspaceSchemaClassification,
    ModeloWorkspaceSchemaIdentityV1,
    ModeloWorkspaceSchemaRecordV1,
    ModeloWorkspaceSnapshotScopeV1,
    ModeloWorkspaceTargetV1,
    ModeloWorkspaceTextFactValueV1,
    ModeloWorkspaceWorkReviewFacetV1,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.modelos.protocols import VerificationReportCatalogueRepositoryProtocol
    from ..state_projection_ports import StateProjectionReadPorts
    from .calculation_action_ports import CalculationActionPorts
    from .work_review import ModeloWorkReview

from .workspace import (
    WORKSPACE_CAPABILITY_SOURCE_FAMILIES,
    WORKSPACE_RESPONSIBLE_OWNER,
    ModeloWorkspaceAbsentReadinessProjectionError,
    ModeloWorkspaceAbsentRegistryProjectionError,
    capability_row,
    capture_modelo_workspace_locale_summary,
    contributors_still_current,
    modelo_work_selector_request_for_target,
    modelo_workspace_recovery_action,
    resolve_locale_summaries_and_values,
    resolve_modelo_workspace_revision_axes,
    resolved_obligation,
    schema_family_disposition,
    schema_family_evidence,
    workspace_changed_refusal,
)
from .workspace_producers import (
    MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_LOCALE_CATALOGUE_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_REGISTRY_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_WORK_PRODUCER_CONTRACT_V1,
    ModeloWorkspaceBoundedReviewPortV1,
    ModeloWorkspaceCalculationPortV1,
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
from .workspace_schema import (
    ModeloWorkspaceStaleCursorError,
    binding_schema_records,
    casilla_continuity_references,
    casilla_export_exposure_references,
    facet_cursor,
    formula_operand_references_for_casilla,
    formula_schema_records,
    not_applicable_family_dispositions,
    paginate_modelo_workspace_facet,
    parameter_schema_records,
    relation_source_endpoints_for_casilla,
)

_GRADED_SNAPSHOT_PAGINATED_FACETS = frozenset(
    {
        ModeloWorkspaceFacetName.SCHEMA,
        ModeloWorkspaceFacetName.MATERIALIZATION,
        ModeloWorkspaceFacetName.PROVENANCE,
    }
)


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
            responsible_owner=WORKSPACE_RESPONSIBLE_OWNER,
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
    """Return the seven contributor identities GRADED_SNAPSHOT reads.

    The four STATIC_INSPECTION reads (registry, work, locale_catalogue,
    field_manifest) plus CALCULATION, which supplies the materialization and
    provenance facets, READINESS, which supplies the readiness projection, and
    BOUNDED_REVIEW, which supplies the work review the Results and Verification
    destinations partition and report from. Every contributor named here is
    captured exactly once per admission; one named but never captured would
    corrupt the epoch digest every facet revalidates against.
    """
    return tuple(
        sorted(
            (
                MODELO_WORKSPACE_WORK_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_LOCALE_CATALOGUE_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_REGISTRY_PRODUCER_CONTRACT_V1.contributor,
                MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1.contributor,
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

    See :func:`not_applicable_family_dispositions` for the shared logic; this
    is the graded half of the identical projection.

    Args:
        snapshot: The admitted
            :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            whose revision declares the inapplicability claims.

    Returns:
        One row per family the revision declared not applicable.
    """
    return not_applicable_family_dispositions(snapshot.revision.family_dispositions)


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
    labels = resolve_locale_summaries_and_values(keys, output_language=output_language)
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
        grouped.setdefault((provenance.source_binding_id, row_index), []).append((casilla_id, value))

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
    review: ModeloWorkReview,
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
    * ``VERIFICATION_READINESS`` is owned by the bounded review, as in a
      static inspection, and is ``AVAILABLE`` when the review reports that
      same revision in state ``VERIFICADO_COMPLETO``, a state the record only
      reaches with its ``verified_at``/``verified_by`` stamps present -- a
      separately stamped verdict from the verify producer.
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
            whose own persisted state settles the materialization answer.
        review: The captured work review, which settles verification readiness.
        readiness: The readiness producer's own verdict for this target.

    Returns:
        The complete capability denominator, one row per capability.
    """
    calculation_available = calculation_revision.work_unit_id == resolved_target.work_unit_id
    verification_available = (
        calculation_available
        and review.calculation_revision_id == calculation_revision.calculation_revision_id
        and review.lifecycle_state is CalculationRevisionState.VERIFICADO_COMPLETO
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
            MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1,
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
        capability_row(
            capability,
            disposition=disposition,
            contract=contract,
            resolved_target=resolved_target,
            declarations=snapshot.revision.family_dispositions,
            declared_member_count=counts.get(WORKSPACE_CAPABILITY_SOURCE_FAMILIES[capability]),
        )
        for capability, contract, disposition in dispositions
    )


def _require_graded_snapshot_cursor(cursor: ModeloWorkspaceCursorV1 | None) -> None:
    """Require a paginated graded facet before any contributor is captured."""
    if cursor is not None and cursor.facet not in _GRADED_SNAPSHOT_PAGINATED_FACETS:
        raise ModeloWorkspaceStaleCursorError(
            "graded snapshot paginates the schema, materialization and provenance facets; "
            f"cursor names {cursor.facet.value}"
        )


def _require_graded_registry_snapshot(registry_projection: ModeloWorkspaceRegistryProjectionV1) -> RegistrySnapshot:
    """Require the one captured registry snapshot before resolving its revision axes."""
    snapshot = registry_projection.snapshot
    if snapshot is None:
        raise ModeloWorkspaceAbsentRegistryProjectionError(
            "registry capture returned no snapshot for the resolved revision",
        )

    return snapshot


def _require_graded_readiness(readiness_reports: tuple[ProjectionModeloReadiness, ...]) -> ProjectionModeloReadiness:
    """Require the exact target readiness report from its one captured result."""
    if not readiness_reports:
        raise ModeloWorkspaceAbsentReadinessProjectionError(
            "readiness capture returned no report for the resolved target",
        )
    readiness = readiness_reports[0]

    return readiness


def resolve_graded_snapshot_result(
    target: ModeloWorkspaceTargetV1,
    *,
    required_grade: RegistryAuthorityGrade,
    bucket_id: str,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_ports: CalculationActionPorts,
    verification_repository: VerificationReportCatalogueRepositoryProtocol,
    readiness_read_ports: StateProjectionReadPorts,
    operation: PinnedAuthorityOperation,
    output_language: OutputLanguage,
    page_size: int = 200,
    cursor: ModeloWorkspaceCursorV1 | None = None,
) -> ModeloWorkspaceResultV1:
    """Capture the current contributors and assemble a graded snapshot."""
    _require_graded_snapshot_cursor(cursor)
    work_port = ModeloWorkspaceWorkPortV1(
        request=modelo_work_selector_request_for_target(target, bucket_id=bucket_id),
        catalogue_repository=catalogue_repository,
        mode=ModeloWorkSelectionMode.VISIBLE_OR_EXACT,
    )
    work_capture = work_port.capture_projection_with_epoch()
    resolution = work_capture.projection
    resolved_modelo, resolved_filing_year, resolved_period = resolved_obligation(resolution)
    work_unit = resolution.work_unit
    if work_unit is None:
        return _missing_work_refusal(target, resolved_modelo, resolved_period)
    registry_port = ModeloWorkspaceRegistryPortV1(
        authority=operation,
        modelo_id=resolved_modelo,
        filing_year=resolved_filing_year,
        period=resolved_period.registry_token,
        grade=required_grade,
    )
    try:
        registry_capture = registry_port.capture_projection_with_epoch()
    except RegistryValidationError as exc:
        failure = exc.registry_failure
        if failure is None or failure.condition is not RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT:
            raise
        return _authority_refusal(target, required_grade, work_unit.work_unit_id)
    registry_projection = registry_capture.projection
    snapshot = _require_graded_registry_snapshot(registry_projection)
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
        return _calculation_refusal(target, resolved_target, snapshot, work_unit.work_unit_id)
    calculation_port = ModeloWorkspaceCalculationPortV1(
        calculation_revision_id=calculation_revision_id,
        ports=calculation_ports,
    )
    calculation_capture = calculation_port.capture_projection_with_epoch()
    calculation_revision = calculation_capture.projection
    review_port = ModeloWorkspaceBoundedReviewPortV1(
        bucket_id=resolved_target.bucket_id,
        modelo=resolved_target.modelo,
        filing_year=resolved_target.filing_year,
        period=resolved_target.period,
        operation=operation,
        work_unit_repository=catalogue_repository,
        calculation_repository=calculation_ports.calculation_repository,
        verification_repository=verification_repository,
    )
    review_capture = review_port.capture_projection_with_epoch()
    review = review_capture.projection
    if review.work_unit_id != resolved_target.work_unit_id:
        raise InternalInvariantError(
            "the bounded review resolved a different work unit than the graded admission it contributes to"
        )
    readiness_port = ModeloWorkspaceReadinessPortV1(
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
    )
    readiness_capture = readiness_port.capture_projection_with_epoch()
    readiness_reports = readiness_capture.projection.reports
    readiness = _require_graded_readiness(readiness_reports)
    schema_identity = resolve_graded_snapshot_schema_identity(snapshot)
    locale = capture_modelo_workspace_locale_summary(resolved_target, output_language=output_language)
    locale_port = ModeloWorkspaceLocaleCataloguePortV1(
        translation_key=revision_locale_key(resolved_target.modelo, resolved_target.law_selected_revision_id),
        locale=output_language.value,
    )
    locale_capture = locale_port.capture_projection_with_epoch()
    field_manifest_port = ModeloWorkspaceFieldManifestPortV1(authority=snapshot)
    field_manifest_capture = field_manifest_port.capture_projection_with_epoch()
    if not contributors_still_current(
        (
            (work_port, work_capture.epoch),
            (registry_port, registry_capture.epoch),
            (locale_port, locale_capture.epoch),
            (field_manifest_port, field_manifest_capture.epoch),
            (calculation_port, calculation_capture.epoch),
            (review_port, review_capture.epoch),
            (readiness_port, readiness_capture.epoch),
        )
    ):
        return workspace_changed_refusal(target, resolved_target)
    captures = (
        work_capture,
        registry_capture,
        locale_capture,
        field_manifest_capture,
        calculation_capture,
        review_capture,
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
    return _assemble_graded_projection(
        snapshot=snapshot,
        resolved_target=resolved_target,
        calculation_revision=calculation_revision,
        review=review,
        readiness=readiness,
        required_grade=required_grade,
        output_language=output_language,
        page_size=page_size,
        cursor=cursor,
        schema_identity=schema_identity,
        locale=locale,
        baseline=baseline,
        contributors=contributors,
    )


def _assemble_graded_projection(
    *,
    snapshot: RegistrySnapshot,
    resolved_target: ModeloWorkspaceResolvedTargetV1,
    calculation_revision: CalculationRevision,
    review: ModeloWorkReview,
    readiness: ProjectionModeloReadiness,
    required_grade: RegistryAuthorityGrade,
    output_language: OutputLanguage,
    page_size: int,
    cursor: ModeloWorkspaceCursorV1 | None,
    schema_identity: ModeloWorkspaceSchemaIdentityV1,
    locale: ModeloWorkspaceLocaleSummaryV1,
    baseline: ModeloWorkspaceBaselineV1,
    contributors: tuple[ModeloWorkspaceContributorIdentityV1, ...],
) -> ModeloWorkspaceResultV1:
    schema_facet = paginate_modelo_workspace_facet(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1],
        graded_snapshot_schema_records(snapshot, resolved_target, output_language=output_language),
        facet=ModeloWorkspaceFacetName.SCHEMA,
        cursor=facet_cursor(cursor, ModeloWorkspaceFacetName.SCHEMA),
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
        cursor=facet_cursor(cursor, ModeloWorkspaceFacetName.MATERIALIZATION),
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
        cursor=facet_cursor(cursor, ModeloWorkspaceFacetName.PROVENANCE),
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
        work_review=ModeloWorkspaceWorkReviewFacetV1(
            disposition=ModeloWorkspaceCapabilityDisposition.AVAILABLE,
            review=review,
        ),
        readiness=readiness,
        capabilities=graded_snapshot_modelo_workspace_capabilities(
            snapshot,
            resolved_target,
            calculation_revision=calculation_revision,
            review=review,
            readiness=readiness,
        ),
    )
    return ModeloWorkspaceGradedSnapshotResultV1(projection=projection)


def _missing_work_refusal(
    target: ModeloWorkspaceTargetV1,
    resolved_modelo: ModeloCode,
    resolved_period: Period,
) -> ModeloWorkspaceResultV1:
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


def _authority_refusal(
    target: ModeloWorkspaceTargetV1,
    required_grade: RegistryAuthorityGrade,
    work_unit_id: WorkUnitId,
) -> ModeloWorkspaceResultV1:
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
            work_unit_id=work_unit_id,
        ),
    )


def _calculation_refusal(
    target: ModeloWorkspaceTargetV1,
    resolved_target: ModeloWorkspaceResolvedTargetV1,
    snapshot: RegistrySnapshot,
    work_unit_id: WorkUnitId,
) -> ModeloWorkspaceResultV1:
    return graded_snapshot_refusal(
        ModeloWorkspaceRefusalCode.CALCULATION_UNAVAILABLE,
        requested_target=target,
        selected_target=resolved_target,
        capability=ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION,
        reconsideration_condition="calculate this work unit, then request a graded snapshot again",
        facts=(
            ModeloWorkspaceEvidenceFactV1(
                name="work_unit_id",
                value=ModeloWorkspaceTextFactValueV1(value=work_unit_id),
            ),
        ),
        evidence=schema_family_evidence(
            WORKSPACE_CAPABILITY_SOURCE_FAMILIES[ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION],
            declarations=snapshot.revision.family_dispositions,
        ),
        source_disposition=schema_family_disposition(
            WORKSPACE_CAPABILITY_SOURCE_FAMILIES[ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION],
            declarations=snapshot.revision.family_dispositions,
            declared_member_count=len(snapshot.revision.formulas),
        ),
        recovery_action=modelo_workspace_recovery_action(
            "operator.modelo.work.calculate",
            work_unit_id=resolved_target.work_unit_id,
        ),
    )
