"""Shared Modelo Workspace target capture and currentness checks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.errors.hierarchy import CadrumoError, InternalInvariantError
from ...core.external_constants import OutputLanguage
from ...core.identity.hex_ids import WorkUnitId
from ...core.period import Period
from ...core.schema_family_disposition import RegistrySchemaFamilyDisposition
from ...domain.calculations.registry.modelo_localization import (
    revision_locale_key,
)
from ...domain.calculations.registry.schema_overrides import SchemaFamilyDispositionDeclaration
from ...domain.calculations.registry.static_inspection import RegistryRevisionInspection
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from ..operator_actions.models import ActionReference
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
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceCapabilityV1,
    ModeloWorkspaceDomainRefusalV1,
    ModeloWorkspaceEvidenceFactV1,
    ModeloWorkspaceEvidenceReferenceV1,
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceLegalEvidenceReferenceV1,
    ModeloWorkspaceLocaleDisposition,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceRefusalCode,
    ModeloWorkspaceRefusedResultV1,
    ModeloWorkspaceResolvedTargetV1,
    ModeloWorkspaceRevisionAssertionDisposition,
    ModeloWorkspaceRevisionAssertionSource,
    ModeloWorkspaceRevisionAssertionV1,
    ModeloWorkspaceSourceEvidenceReferenceV1,
    ModeloWorkspaceTargetV1,
    ModeloWorkspaceTextFactValueV1,
    ModeloWorkspaceWorkReviewFacetV1,
)

if TYPE_CHECKING:
    pass

from .workspace_producers import (
    MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1,
    MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1,
    ModeloWorkspaceContributingProjectionV1,
    ModeloWorkspaceCurrentEpochPortV1,
    ModeloWorkspaceEpochV1,
    ModeloWorkspaceLocaleCatalogueBatchPortV1,
    ModeloWorkspaceProducerContractV1,
    ModeloWorkspaceRegistryPortV1,
    ModeloWorkspaceRegistryProjectionV1,
    ModeloWorkspaceWorkPortV1,
    RegistryAuthorityCapturePort,
)

WORKSPACE_RESPONSIBLE_OWNER = "modelo.workspace"


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
    resolved_modelo, resolved_filing_year, resolved_period = resolved_obligation(resolution)

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
    ((summary, value),) = resolve_locale_summaries_and_values((key,), output_language=output_language)
    return summary, value


def resolve_locale_summaries_and_values(
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


WORKSPACE_CAPABILITY_SOURCE_FAMILIES: Final[dict[ModeloWorkspaceCapabilityName, str]] = {
    ModeloWorkspaceCapabilityName.SCHEMA_INSPECTION: "casillas",
    ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION: "formulas",
    ModeloWorkspaceCapabilityName.VERIFICATION_READINESS: "verification_expectations",
    ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS: "export_layouts",
}


MODELO_WORKSPACE_RECOVERY_ACTION_IDS: Final[frozenset[str]] = frozenset(
    {
        "operator.modelo.work.calculate",
        "operator.modelo.work.create",
        "operator.modelo.work.status",
        "operator.modelo.work.verify",
    }
)


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
    if action_id not in MODELO_WORKSPACE_RECOVERY_ACTION_IDS:
        raise InternalInvariantError(f"{action_id} is not a declared workspace recovery action")
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


def schema_family_disposition(
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


def schema_family_evidence(
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
    family = WORKSPACE_CAPABILITY_SOURCE_FAMILIES[capability]
    disposition = schema_family_disposition(
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
        evidence=schema_family_evidence(family, declarations=declarations),
        recovery_action=modelo_workspace_recovery_action(
            _WORKSPACE_CAPABILITY_RECOVERY_ACTIONS[capability],
            work_unit_id=work_unit_id,
        ),
    )


def capability_row(
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
        capability_row(
            capability,
            disposition=disposition,
            contract=contract,
            resolved_target=resolved_target,
            declarations=inspection.family_dispositions,
            declared_member_count=counts.get(WORKSPACE_CAPABILITY_SOURCE_FAMILIES[capability]),
        )
        for capability, contract, disposition in _STATIC_INSPECTION_CAPABILITY_DISPOSITIONS
    )


def resolved_obligation(resolution: ModeloWorkResolution) -> tuple[ModeloCode, int, Period]:
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


def contributors_still_current(
    reads: Sequence[tuple[ModeloWorkspaceCurrentEpochPortV1, ModeloWorkspaceEpochV1]],
) -> bool:
    """Whether every contributor still stands where its capture found it.

    The second pass of an admission. Each capture is internally stable, but the
    captures are taken one after another, so a write landing between two of
    them would mint a baseline from contributors describing different states.
    Every owner re-reads its current coordinate after the last capture, and a
    baseline is minted only when all of them still match.
    """
    for port, captured in reads:
        try:
            captured.require_current(port.read_current_epoch())
        except ValueError:
            return False
    return True


def workspace_changed_refusal(
    requested_target: ModeloWorkspaceTargetV1,
    selected_target: ModeloWorkspaceResolvedTargetV1 | None,
) -> ModeloWorkspaceRefusedResultV1:
    """Refuse an admission whose contributors moved before its second pass.

    Nothing about the taxpayer's data is wrong; it changed while it was being
    read, so the remedy is to read it again. A caller may do that a bounded
    number of times and must say so when the data will not hold still.
    """
    return ModeloWorkspaceRefusedResultV1(
        refusal=ModeloWorkspaceDomainRefusalV1(
            code=ModeloWorkspaceRefusalCode.WORKSPACE_CHANGED,
            boundary="admission",
            capability=None,
            requested_target=requested_target,
            selected_target=selected_target,
            facts=(),
            evidence=(),
            responsible_owner=WORKSPACE_RESPONSIBLE_OWNER,
            reconsideration_condition="read the declaration again; its stored data changed while it was being read",
            source_disposition=None,
            recovery_action=None,
        )
    )
