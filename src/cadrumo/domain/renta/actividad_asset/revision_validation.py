"""Validation of an immutable activity-asset revision's facts."""

from __future__ import annotations

from .disposal import ActivityAssetDisposal
from .election import ACQUIRED_CONDITION_FACTS
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
        raise ActividadAssetValidationError(
            context={"field": "supersedes_revision_id"},
            translated_message="ledger.actividad_asset.errors.revision_first_cannot_supersede",
        )
    if revision.revision_number > 1 and revision.supersedes_revision_id is None:
        raise ActividadAssetValidationError(
            context={"field": "supersedes_revision_id"},
            translated_message="ledger.actividad_asset.errors.revision_requires_superseded",
        )


def _validate_primary_purchase(revision: ActivityAssetRevision) -> None:
    if revision.acquisition_shape is AcquisitionShape.FINANCIAL_LEASE_UNEXERCISED:
        raise ActividadAssetUnsupportedError(
            translated_message="ledger.actividad_asset.errors.financial_lease_unexercised",
            context={"legal_reference": "LIS art. 106"},
        )
    if revision.acquisition_shape not in REGISTERABLE_ACQUISITION_SHAPES:
        raise ActividadAssetValidationError(
            context={"field": "acquisition_shape"},
            translated_message="ledger.actividad_asset.errors.acquisition_shape_not_registerable",
        )
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
        raise ActividadAssetValidationError(
            context={"field": "acquisition"},
            translated_message="ledger.actividad_asset.errors.primary_purchase_lineage_shape",
        )


def _validate_acquired_outside_ledger(revision: ActivityAssetRevision) -> None:
    lineage = revision.acquisition
    if (
        lineage.observed_transaction_id is not None
        or lineage.observed_lineage_event_id is not None
        or lineage.evidence_fingerprint is not None
    ):
        raise ActividadAssetValidationError(
            context={"field": "acquisition"},
            translated_message="ledger.actividad_asset.errors.outside_ledger_names_no_row",
        )
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
                "declared_acquisition_date": declared,
                "in_service_date": revision.in_service_date,
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
                "later_affectation_on": affected,
                "in_service_date": revision.in_service_date,
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
        raise ActividadAssetValidationError(
            context={"field": "residual_value"},
            translated_message="ledger.actividad_asset.errors.residual_value_not_below_basis",
        )


def _validate_building_construction_date(revision: ActivityAssetRevision) -> None:
    if revision.building_construction_date is not None:
        if "building_construction_date" not in ACQUIRED_CONDITION_FACTS[revision.acquired_condition]:
            raise ActividadAssetValidationError(
                context={"field": "building_construction_date"},
                translated_message="ledger.actividad_asset.errors.building_construction_date_requires_used_asset",
            )
        if revision.building_construction_date > revision.in_service_date:
            raise ActividadAssetValidationError(
                context={"field": "building_construction_date"},
                translated_message="ledger.actividad_asset.errors.building_construction_date_after_service",
            )


def _validate_vehicle_affectation(revision: ActivityAssetRevision) -> None:
    if revision.vehicle_affectation is not None and revision.asset_kind is not AssetKind.MATERIAL:
        raise ActividadAssetValidationError(
            context={"field": "vehicle_affectation"},
            translated_message="ledger.actividad_asset.errors.vehicle_affectation_requires_material",
        )
