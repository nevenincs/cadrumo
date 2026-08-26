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

from ...domain.modelos import ModeloCode
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from .work_addressing import (
    ModeloExactWorkUnitTarget,
    ModeloVisibleFilingTarget,
    ModeloWorkResolution,
    ModeloWorkSelectionMode,
    ModeloWorkSelectorRequest,
    assert_work_target_revision,
)
from .workspace_models import (
    ModeloWorkspaceExactWorkUnitTargetV1,
    ModeloWorkspaceRevisionAssertionDisposition,
    ModeloWorkspaceRevisionAssertionSource,
    ModeloWorkspaceRevisionAssertionV1,
    ModeloWorkspaceTargetV1,
)
from .workspace_producers import (
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
    the two axes against what the caller already captured, through the sole
    pure :func:`assert_work_target_revision`.

    A mismatch on either axis is NOT swallowed into a boolean: the raised
    :class:`ModeloWorkRegistryYearMismatchError` names which axis diverged in
    ``err.args[0]`` prose only, so the caller wanting per-axis dispositions
    recomputes membership by re-checking each axis against the same law
    revision id below, once per axis, never trusting the exception's shape.
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

    if mismatched:
        # Reuse the sole pure assertion to raise the canonical, translated
        # refusal text -- assert_work_target_revision remains the single place
        # the mismatch wording and the "why" prose are authored, even though
        # the per-axis disposition below is what the caller actually persists.
        # comparison_domain/generation are irrelevant to the pure check itself
        # (only .projection.revision_id is read), so a same-process sentinel
        # coordinate is sufficient here -- no second REGISTRY read occurs.
        from ...domain.calculations.registry.authority import RegistryAuthorityCapture

        raw_projection = (
            registry_projection.inspection
            if registry_projection.inspection is not None
            else registry_projection.snapshot
        )
        assert raw_projection is not None
        assert_work_target_revision(
            RegistryAuthorityCapture(projection=raw_projection, comparison_domain=law_revision_id, generation=1),
            requested_revision_id=requested_revision_id,
            stored_revision_id=stored_revision_id,
        )

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


__all__ = [
    "ModeloWorkspaceRevisionAxes",
    "capture_modelo_workspace_target_axes",
    "modelo_work_selector_request_for_target",
    "resolve_modelo_workspace_revision_axes",
]
