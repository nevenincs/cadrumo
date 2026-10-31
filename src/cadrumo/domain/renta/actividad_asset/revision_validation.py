"""Validation of an immutable activity-asset revision's facts."""

from __future__ import annotations

from .disposal import ActivityAssetDisposal
from .election import AcquiredCondition
from .errors import ActividadAssetUnsupportedError, ActividadAssetValidationError
from .lifecycle import REGISTERABLE_ACQUISITION_SHAPES, AcquisitionShape, ActivityAssetRevision, AssetKind


def validate_revision(revision: ActivityAssetRevision) -> None:
    """Validate the shape and cross-fact relationships of a revision."""
    _validate_revision_lineage(revision)
    _validate_primary_purchase(revision)
    _validate_further_acquisitions(revision)
    _validate_service_dates(revision)
    _validate_opening_year(revision)
    _validate_residual_basis(revision)
    _validate_building_construction_date(revision)
    _validate_vehicle_affectation(revision)


def _validate_revision_lineage(revision: ActivityAssetRevision) -> None:
    if revision.revision_number == 1 and revision.supersedes_revision_id is not None:
        raise ValueError("first asset revision cannot supersede another revision")
    if revision.revision_number > 1 and revision.supersedes_revision_id is None:
        raise ValueError("later asset revisions require supersedes_revision_id")


def _validate_primary_purchase(revision: ActivityAssetRevision) -> None:
    if revision.acquisition_shape is AcquisitionShape.FINANCIAL_LEASE_UNEXERCISED:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.financial_lease_unexercised",
            context={"legal_reference": "LIS art. 106"},
        )
    if revision.acquisition_shape not in REGISTERABLE_ACQUISITION_SHAPES:
        raise ValueError("an element is registered as a primary purchase or as acquired outside the ledger")
    if not revision.acquisition.invoice_evidence_id.strip():
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.acquisition_evidence_reference_required",
        )
    if revision.acquisition_shape is AcquisitionShape.ACQUIRED_OUTSIDE_LEDGER:
        _validate_acquired_outside_ledger(revision)
    elif (
        revision.acquisition.observed_transaction_id is None
        or revision.acquisition.evidence_fingerprint is None
        or revision.declared_acquisition_date is not None
        or revision.declared_activity is not None
    ):
        raise ValueError(
            "a primary purchase names its ledger row and evidence fingerprint and declares no date or activity"
        )


def _validate_acquired_outside_ledger(revision: ActivityAssetRevision) -> None:
    lineage = revision.acquisition
    if (
        lineage.observed_transaction_id is not None
        or lineage.observed_lineage_event_id is not None
        or lineage.evidence_fingerprint is not None
    ):
        raise ValueError("an element acquired outside the ledger names no ledger row as its primary acquisition")
    declared = revision.declared_acquisition_date
    if declared is None:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.declared_acquisition_date_required",
        )
    if revision.declared_activity is None:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.declared_activity_required",
        )
    if declared > revision.in_service_date:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.declared_acquisition_after_service",
            context={
                "declared_acquisition_date": declared.isoformat(),
                "in_service_date": revision.in_service_date.isoformat(),
            },
        )


def _validate_further_acquisitions(revision: ActivityAssetRevision) -> None:
    owned = revision.acquisition_transaction_ids
    if len(set(owned)) != len(owned):
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.acquisition_row_named_twice",
        )


def _validate_service_dates(revision: ActivityAssetRevision) -> None:
    disposal = revision.disposal
    if disposal is None:
        if revision.out_of_service_date is not None:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.out_of_service_date_without_disposal",
            )
        return
    if disposal.disposal_date < revision.in_service_date:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.disposal_before_service",
        )
    if revision.out_of_service_date != disposal.boundary:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.out_of_service_date_not_the_boundary",
        )
    require_later_affectation_in_order(revision, disposal)


def require_later_affectation_in_order(revision: ActivityAssetRevision, disposal: ActivityAssetDisposal) -> None:
    """Refuse an affectation after the element entered service, whose charge starts with it.

    A baja never predates entry into service, so this also keeps the affectation before the baja.
    """
    affected = disposal.later_affectation_on
    if affected is not None and affected > revision.in_service_date:
        raise ActividadAssetValidationError(
            context={
                "later_affectation_on": affected.isoformat(),
                "in_service_date": revision.in_service_date.isoformat(),
            },
            translated_message="ledger.actividad_asset.errors.later_affectation_out_of_order",
        )


def _validate_opening_year(revision: ActivityAssetRevision) -> None:
    covered_through = revision.opening_history.covered_through_tax_year
    if covered_through is not None and covered_through < revision.in_service_date.year:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.opening_year_before_in_service",
            context={
                "opening_tax_year": covered_through,
                "in_service_tax_year": revision.in_service_date.year,
            },
        )


def _validate_residual_basis(revision: ActivityAssetRevision) -> None:
    if revision.residual_value >= revision.basis.deductible_basis():
        raise ValueError("residual_value must be below allocated depreciation basis")


def _validate_building_construction_date(revision: ActivityAssetRevision) -> None:
    if revision.building_construction_date is not None:
        if revision.acquired_condition is not AcquiredCondition.USED:
            raise ValueError("building_construction_date is only a fact of a used asset")
        if revision.building_construction_date > revision.in_service_date:
            raise ValueError("building_construction_date cannot follow in_service_date")


def _validate_vehicle_affectation(revision: ActivityAssetRevision) -> None:
    if revision.vehicle_affectation is not None and revision.asset_kind is not AssetKind.MATERIAL:
        raise ValueError("vehicle_affectation is only a fact of a material asset")
