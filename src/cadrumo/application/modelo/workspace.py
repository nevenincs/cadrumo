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

from ...core import OutputLanguage
from ...domain.calculations.registry.modelo_localization import revision_locale_key
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
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceCapabilityV1,
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceLocaleDisposition,
    ModeloWorkspaceLocaleSummaryV1,
    ModeloWorkspaceResolvedTargetV1,
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
    MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1,
    ModeloWorkspaceLocaleCataloguePortV1,
    ModeloWorkspaceProducerContractV1,
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


def capture_modelo_workspace_target_axes(
    target: ModeloWorkspaceTargetV1,
    *,
    bucket_id: str,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
    authority: ValidatedRegistryAuthority,
) -> tuple[ModeloWorkResolution, ModeloWorkspaceRegistryProjectionV1, ModeloWorkspaceRevisionAxes]:
    """Capture WORK exactly once, then REGISTRY exactly once from its coordinates.

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
    return resolution, registry_projection, axes


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

    Spanish is the source language for every catalogue entry
    (``aeat-locales-cli``), so a requested language whose own key is absent
    falls back to Spanish rather than to an arbitrary third language; Spanish
    absent as well is the suppressed floor, never a missing key propagated as
    an exception.
    """
    key = revision_locale_key(resolved_target.modelo, resolved_target.law_selected_revision_id)
    requested = ModeloWorkspaceLocaleCataloguePortV1(
        translation_key=key,
        locale=output_language.value,
    ).capture_projection_with_epoch()
    if requested.projection.value is not None:
        return ModeloWorkspaceLocaleSummaryV1(
            requested_language=output_language,
            resolved_language=output_language,
            disposition=ModeloWorkspaceLocaleDisposition.EXACT,
            catalogue_digest=requested.projection.catalogue_digest,
        )
    if output_language is OutputLanguage.ES:
        return ModeloWorkspaceLocaleSummaryV1(
            requested_language=output_language,
            resolved_language=OutputLanguage.ES,
            disposition=ModeloWorkspaceLocaleDisposition.SUPPRESSED,
            catalogue_digest=requested.projection.catalogue_digest,
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
    return ModeloWorkspaceLocaleSummaryV1(
        requested_language=output_language,
        resolved_language=OutputLanguage.ES,
        disposition=disposition,
        catalogue_digest=spanish.projection.catalogue_digest,
    )


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
# SCHEMA_INSPECTION is provisionally UNMEASURED too, by the identical rule:
# field_manifest is the capability's canonical producer, and whether
# field_manifest can produce a valid manifest for a STATIC_INSPECTION target
# at all is the open W03.P20.S278 question. Flip this one row to AVAILABLE
# once S278 supplies a field manifest static inspection can actually capture.
_STATIC_INSPECTION_CAPABILITY_PRODUCERS: tuple[
    tuple[ModeloWorkspaceCapabilityName, ModeloWorkspaceProducerContractV1], ...
] = (
    (ModeloWorkspaceCapabilityName.SCHEMA_INSPECTION, MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1),
    (ModeloWorkspaceCapabilityName.CALCULATION_MATERIALIZATION, MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1),
    (ModeloWorkspaceCapabilityName.VERIFICATION_READINESS, MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1),
    (ModeloWorkspaceCapabilityName.FILING_DRAFT_READINESS, MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1),
    (ModeloWorkspaceCapabilityName.FILING_EXPORT_READINESS, MODELO_WORKSPACE_CLOSURE_PRODUCER_CONTRACT_V1),
)


def static_inspection_modelo_workspace_capabilities(
    resolved_target: ModeloWorkspaceResolvedTargetV1,
) -> tuple[ModeloWorkspaceCapabilityV1, ...]:
    """Return the complete STATIC_INSPECTION capability denominator, all UNMEASURED.

    Every row cites the capability's own canonical producer contributor per
    the S279 ADR amendment; see the module-level comment above this function.
    All five are ``UNMEASURED`` for STATIC_INSPECTION today: the four
    non-schema producers are contributors this admission structurally never
    reads, and ``schema_inspection`` waits on W03.P20.S278. GRADED_SNAPSHOT's
    dispositions are a distinct, not-yet-answered question and MUST NOT be
    derived from this table.
    """
    return tuple(
        ModeloWorkspaceCapabilityV1(
            capability=capability,
            disposition=ModeloWorkspaceCapabilityDisposition.UNMEASURED,
            target=resolved_target,
            selected_revision_id=resolved_target.law_selected_revision_id,
            producer_owner=contract.contributor.owner,
            producer=contract.contributor.producer,
        )
        for capability, contract in _STATIC_INSPECTION_CAPABILITY_PRODUCERS
    )


__all__ = [
    "ModeloWorkspaceRevisionAxes",
    "capture_modelo_workspace_locale_summary",
    "capture_modelo_workspace_target_axes",
    "modelo_work_selector_request_for_target",
    "resolve_modelo_workspace_revision_axes",
    "resolve_modelo_workspace_target",
    "static_inspection_modelo_workspace_capabilities",
]
