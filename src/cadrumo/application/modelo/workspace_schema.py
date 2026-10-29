"""Static Modelo Workspace schema inspection and pagination."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.hashing import content_hash_hex
from ...core.identity.continuidad import ContinuidadId
from ...core.schema_family_disposition import RegistrySchemaFamilyDisposition
from ...domain.calculations.registry.ids import BindingId, ExportFieldId
from ...domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
    modelo_localization_source,
    revision_locale_key,
)
from ...domain.calculations.registry.relation_prefill_bindings import RelationPrefillProvider
from ...domain.calculations.registry.schema import (
    BindingDefinition,
    FormulaDefinition,
)
from ...domain.calculations.registry.schema_formula import FormulaExpression, ParameterDefinition
from ...domain.calculations.registry.schema_overrides import SchemaFamilyDispositionDeclaration
from ...domain.calculations.registry.static_inspection import RegistryRevisionInspection
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from .work_selection import (
    ModeloWorkSelectionMode,
)
from .workspace_baseline import resolve_workspace_baseline
from .workspace_models import (
    ModeloWorkspaceBaselineV1,
    ModeloWorkspaceBindingReferenceV1,
    ModeloWorkspaceBoundedFacetV1,
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCasillaReferenceV1,
    ModeloWorkspaceContinuityReferenceV1,
    ModeloWorkspaceContributorIdentityV1,
    ModeloWorkspaceCursorV1,
    ModeloWorkspaceEvidenceHorizonV1,
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
    ModeloWorkspaceLocalizedTextV1,
    ModeloWorkspaceParameterReferenceV1,
    ModeloWorkspaceProjectionV1,
    ModeloWorkspaceRefusedResultV1,
    ModeloWorkspaceRelationSourceEndpointReferenceV1,
    ModeloWorkspaceRelationTargetEndpointReferenceV1,
    ModeloWorkspaceResolvedTargetV1,
    ModeloWorkspaceSchemaClassification,
    ModeloWorkspaceSchemaIdentityV1,
    ModeloWorkspaceSchemaRecordV1,
    ModeloWorkspaceStaticInspectionResultV1,
    ModeloWorkspaceStaticInspectionScopeV1,
    ModeloWorkspaceTargetV1,
    ModeloWorkspaceTechnicalLabelV1,
)

if TYPE_CHECKING:
    pass

from .workspace import (
    STATIC_INSPECTION_WORK_REVIEW_FACET,
    ModeloWorkspaceAbsentRegistryProjectionError,
    capture_modelo_workspace_locale_summary,
    capture_modelo_workspace_target_captures,
    contributors_still_current,
    modelo_work_selector_request_for_target,
    resolve_locale_summaries_and_values,
    resolved_obligation,
    static_inspection_modelo_workspace_capabilities,
    workspace_changed_refusal,
)
from .workspace_producers import (
    MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_LOCALE_CATALOGUE_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_REGISTRY_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_WORK_PRODUCER_CONTRACT_V1,
    ModeloWorkspaceFieldManifestPortV1,
    ModeloWorkspaceLocaleCataloguePortV1,
    ModeloWorkspaceRegistryPortV1,
    ModeloWorkspaceWorkPortV1,
    RegistryAuthorityCapturePort,
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
        if provider.source_modelo == source_modelo
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
    labels = resolve_locale_summaries_and_values(keys, output_language=output_language)
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


def facet_cursor(
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


def not_applicable_family_dispositions(
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

    See :func:`not_applicable_family_dispositions` for the shared logic;
    the inspection carries no data for most schema families (it strips
    everything but casilla/binding/formula/relation/parameter/projection-endpoint/
    workbook-parity/live-cross-reference identifiers).
    """
    return not_applicable_family_dispositions(inspection.family_dispositions)


def resolve_static_inspection_result(
    target: ModeloWorkspaceTargetV1,
    *,
    bucket_id: str,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
    authority: RegistryAuthorityCapturePort,
    output_language: OutputLanguage,
    page_size: int = 200,
    cursor: ModeloWorkspaceCursorV1 | None = None,
) -> ModeloWorkspaceStaticInspectionResultV1 | ModeloWorkspaceRefusedResultV1:
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
    registry or work capture occurs anywhere in this function; the one second
    read is the currentness pass, which re-reads each contributor's coordinate
    and refuses as ``WORKSPACE_CHANGED`` when any of them moved.
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
    resolved_modelo, resolved_filing_year, resolved_period = resolved_obligation(resolution)
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
    locale_port = ModeloWorkspaceLocaleCataloguePortV1(
        translation_key=locale_key,
        locale=output_language.value,
    )
    locale_capture = locale_port.capture_projection_with_epoch()
    field_manifest_port = ModeloWorkspaceFieldManifestPortV1(authority=inspection)
    field_manifest_capture = field_manifest_port.capture_projection_with_epoch()

    # The work and registry ports are rebuilt from the same inputs the capture
    # helper used; only their current-coordinate reads are exercised here.
    work_port = ModeloWorkspaceWorkPortV1(
        request=modelo_work_selector_request_for_target(target, bucket_id=bucket_id),
        catalogue_repository=catalogue_repository,
        mode=ModeloWorkSelectionMode.VISIBLE_OR_EXACT,
    )
    registry_port = ModeloWorkspaceRegistryPortV1(
        authority=authority,
        modelo_id=resolved_modelo,
        filing_year=resolved_filing_year,
        period=resolved_period.registry_token,
    )
    if not contributors_still_current(
        (
            (work_port, work_capture.epoch),
            (registry_port, registry_capture.epoch),
            (locale_port, locale_capture.epoch),
            (field_manifest_port, field_manifest_capture.epoch),
        )
    ):
        return workspace_changed_refusal(target, resolved_target)

    baseline = resolve_workspace_baseline(
        resolved_target,
        schema_identity=schema_identity,
        locale=locale,
        stamps=(work_capture.stamp, registry_capture.stamp, locale_capture.stamp, field_manifest_capture.stamp),
        epochs=(work_capture.epoch, registry_capture.epoch, locale_capture.epoch, field_manifest_capture.epoch),
    )
    contributors = static_inspection_contributors()

    records = static_inspection_schema_records(inspection, resolved_target, output_language=output_language)
    schema_facet = paginate_modelo_workspace_facet(
        ModeloWorkspaceBoundedFacetV1[ModeloWorkspaceSchemaRecordV1],
        records,
        facet=ModeloWorkspaceFacetName.SCHEMA,
        cursor=facet_cursor(cursor, ModeloWorkspaceFacetName.SCHEMA),
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
