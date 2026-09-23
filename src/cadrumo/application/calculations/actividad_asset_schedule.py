"""Application orchestration for registry-backed activity-asset forecasts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...core.operator_action_enums import ActionArgumentStatus, ActionConditionality, ActionEvidenceProvenance
from ...domain.calculations.registry.actividad_asset_bindings import resolve_activity_asset_schedule_authority
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.renta.actividad_asset.errors import ActividadAssetIncompleteError, VehicleAffectationRecovery
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduledAmortizationCharge,
    schedule_charge,
)
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict

VEHICLE_AFFECTATION_DECLARED_CONDITION = "actividad_asset.vehicle_affectation_declared"
"""Failed-condition identity: a vehicle-capable asset needs an affectation declaration."""

CORRECT_ASSET_REVISION_ACTION = "operator.ledger.actividad_asset.correct_revision"
"""Recovery action: append a correction that carries the missing declaration."""


def vehicle_affectation_verdict(recovery: VehicleAffectationRecovery) -> PreconditionVerdict:
    """Name the revision to correct; the operator supplies the corrected revision."""
    return PreconditionVerdict(
        failed_condition_id=VEHICLE_AFFECTATION_DECLARED_CONDITION,
        evidence=(
            ConditionEvidence(
                condition_id=VEHICLE_AFFECTATION_DECLARED_CONDITION,
                evidence_id="actividad_asset.current_revision",
                provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                values={
                    "asset_id": recovery.asset_id,
                    "revision_id": recovery.revision_id,
                    "authority_class_key": recovery.class_key,
                    "vehicle_affectation_declared": False,
                },
            ),
        ),
        action=ActionReference(action_id=CORRECT_ASSET_REVISION_ACTION),
        argument_bindings=(ActionArgumentBinding(argument_name="revision_json", status=ActionArgumentStatus.MISSING),),
        missing_argument_names=("revision_json",),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def forecast_activity_asset_charge(
    asset_revision: ActivityAssetRevision,
    *,
    modelo_100_revision: ModeloRevision,
    authority_generation: str,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None = None,
) -> ScheduledAmortizationCharge:
    """Forecast through published authority without creating a claim."""
    try:
        authority = resolve_activity_asset_schedule_authority(
            modelo_100_revision,
            tax_year=covered_from.year,
            asset_revision=asset_revision,
            authority_generation=authority_generation,
        )
    except ActividadAssetIncompleteError as exc:
        recovery = exc.vehicle_affectation_recovery
        if recovery is None or exc.terminal_precondition_verdict is not None:
            raise
        raise ActividadAssetIncompleteError(
            str(exc),
            precondition_verdict=vehicle_affectation_verdict(recovery),
            vehicle_affectation_recovery=recovery,
        ) from exc
    return schedule_charge(
        asset_revision,
        authority,
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


__all__ = [
    "CORRECT_ASSET_REVISION_ACTION",
    "VEHICLE_AFFECTATION_DECLARED_CONDITION",
    "forecast_activity_asset_charge",
    "vehicle_affectation_verdict",
]
