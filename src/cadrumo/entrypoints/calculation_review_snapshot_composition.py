"""Compose the same selected saved baseline for native and local review exports."""

from __future__ import annotations

from uuid import UUID

from ..application.export.review_snapshot import CalculationReviewSelection, ReviewSnapshot
from ..application.export.review_snapshot_loader import build_calculation_review_snapshot
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.hashing import content_hash_hex
from ..core.hex import Hex64Str
from ..core.identity.hex_ids import CalculationRevisionId
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .adapter_composition import build_verification_repository_bundle


def load_calculation_review_snapshot(
    revision_id: CalculationRevisionId,
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    filing_record_id: Hex64Str | None = None,
) -> ReviewSnapshot:
    """Read retained selected values and filing records without consulting current transactions."""
    profile = str(profile_id)
    bundle = build_verification_repository_bundle(profile, operation=operation)
    if any(repository.bucket_id != profile for repository in (bundle.calculation, bundle.work_unit, bundle.filing)):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    revision = bundle.calculation.load(operation=operation).get(revision_id)
    if revision is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    unit = bundle.work_unit.load().get(revision.work_unit_id)
    if unit is None or unit.bucket_id != profile:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    reference = revision.registry_snapshot_ref
    rendering = revision.rendering_snapshot
    selection = CalculationReviewSelection(
        profile_id=profile_id,
        work_unit_id=revision.work_unit_id,
        calculation_revision_id=revision.calculation_revision_id,
        modelo=reference.modelo,
        filing_year=reference.modelo_year,
        period=reference.period,
        registry_snapshot_ref=reference,
        authority_generation=rendering.authority_generation
        if rendering is not None
        else operation.generation.logical_generation,
        # A legacy coordinate digest identifies only retained coordinates. It
        # neither resolves today's template nor claims original schema custody.
        registry_digest=rendering.registry_digest
        if rendering is not None
        else content_hash_hex(reference.model_dump(mode="json")),
    )
    records = tuple(
        record
        for record in bundle.filing.load().records.values()
        if record.calculation_revision_id == revision.calculation_revision_id
        and record.work_unit_id == unit.work_unit_id
        and (filing_record_id is None or record.filing_record_id == filing_record_id)
    )
    # A group/member filing needs an explicit member selection. Never silently
    # choose one member's confirmation or current record as the whole review's.
    if len(records) > 1 or (filing_record_id is not None and not records):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return build_calculation_review_snapshot(
        selection=selection,
        revision=revision,
        work_unit=unit,
        filing_record=records[0] if records else None,
    )
