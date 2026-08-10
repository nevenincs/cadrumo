"""Locale-neutral precondition identities for modelo application verbs."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ..operator_actions import (
    ActionArgumentBinding,
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
    lookup_action,
)
from ..operator_surface import ManifestActionProfile

_NAMESPACED_ID_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"


class ModeloPreconditionFailure(BaseModel):
    """One application-owned failed condition at a canonical modelo leaf."""

    model_config = STRICT_FROZEN_CONFIG

    subject_leaf_key: str = Field(pattern=_NAMESPACED_ID_PATTERN, min_length=3, max_length=160)
    scenario_id: str = Field(pattern=_NAMESPACED_ID_PATTERN, min_length=3, max_length=160)
    verdict: PreconditionVerdict

    @property
    def identity(self) -> tuple[str, str, str]:
        """Return the exact leaf, condition, and scenario identity."""
        return (self.subject_leaf_key, self.verdict.failed_condition_id, self.scenario_id)

    @model_validator(mode="after")
    def _match_declared_profile(self) -> ModeloPreconditionFailure:
        profile = _PROFILE_BY_IDENTITY.get(self.identity)
        if profile is None:
            raise ValueError("modelo precondition failure identity is not declared")
        if profile.action != self.verdict.action:
            raise ValueError("modelo precondition failure action contradicts its declaration")
        if profile.no_recovery_outcome != self.verdict.no_recovery_outcome:
            raise ValueError("modelo precondition failure no-recovery outcome contradicts its declaration")
        return self


def _profile(
    subject_leaf_key: str,
    condition_id: str,
    scenario_id: str,
    *,
    action_id: str | None = None,
) -> ManifestActionProfile:
    return ManifestActionProfile(
        subject_leaf_key=subject_leaf_key,
        condition_id=condition_id,
        scenario_id=scenario_id,
        action=ActionReference(action_id=action_id) if action_id is not None else None,
        no_recovery_outcome=(None if action_id is not None else NoRecoveryOutcome.OPERATOR_DECISION),
    )


MODELO_PRECONDITION_PROFILES: tuple[ManifestActionProfile, ...] = (
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.borrador_snapshot.active",
        "modelo.work.calculate.borrador_snapshot.load_failed",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.borrador_snapshot.active",
        "modelo.work.calculate.borrador_snapshot.inactive",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.source_inputs.unowned",
        "modelo.work.calculate.source_inputs.binding_override_rejected",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.source_inputs.unowned",
        "modelo.work.calculate.source_inputs.casilla_override_rejected",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.lifecycle_path.required",
        "modelo.work.verify.lifecycle_path.direct_cross_period_promotion_refused",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.m390.reconciliation.complete",
        "modelo.work.calculate.m390.reconciliation.clean_m303_observations_missing",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.ledger_preflight.ready",
        "modelo.work.calculate.ledger_preflight.blocked",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.m200.accounting_result.present",
        "modelo.work.calculate.m200.accounting_result.ledger_rows_without_accounting_result",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.m349.operator_rows.present",
        "modelo.work.calculate.m349.operator_rows.intracom_ledger_without_operator_rows",
    ),
    *(
        _profile(
            leaf,
            "modelo.work.required_bindings.resolved",
            f"{leaf}.required_bindings_missing",
            action_id="operator.modelo.bindings.list",
        )
        for leaf in ("modelo.work.calculate", "modelo.work.verify", "modelo.work.file")
    ),
    _profile(
        "modelo.work.file",
        "modelo.work.file.deductible_vat_evidence.present",
        "modelo.work.file.deductible_vat_evidence.missing",
    ),
    _profile(
        "modelo.export",
        "modelo.export.deductible_vat_evidence.present",
        "modelo.export.deductible_vat_evidence.missing",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.registry_snapshot.available",
        "modelo.work.verify.registry_snapshot.unavailable",
        action_id="operator.registry.verify",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.required_casillas.complete",
        "modelo.work.verify.required_casillas.missing",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.registry_predicate.satisfied",
        "modelo.work.verify.registry_predicate.failed",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.deductible_vat_evidence.present",
        "modelo.work.verify.deductible_vat_evidence.missing",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.ledger_row.taxable_base_present",
        "modelo.work.verify.ledger_row.cuota_less_base_missing",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.oss_source.routed",
        "modelo.work.verify.oss_source.unrouted",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.oss_evidence.present",
        "modelo.work.verify.oss_evidence.missing",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.ledger_snapshot.current",
        "modelo.work.verify.ledger_snapshot.drift_detected",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.m210.agrupacion.valid",
        "modelo.work.verify.m210.agrupacion.invalid",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.m210.rate.resolved",
        "modelo.work.verify.m210.rate.unresolved",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.m202.modality.complete",
        "modelo.work.verify.m202.modality.incomplete",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.cross_period_dependency.clean",
        "modelo.work.verify.cross_period_dependency.unclean",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.activity_start_date.present",
        "modelo.work.verify.activity_start_date.missing_for_first_filer_adjudication",
    ),
)

_PROFILE_BY_IDENTITY = {profile.identity: profile for profile in MODELO_PRECONDITION_PROFILES}
if len(_PROFILE_BY_IDENTITY) != len(MODELO_PRECONDITION_PROFILES):
    raise ValueError("modelo precondition profile identities must be unique")


def build_modelo_precondition_failure(
    *,
    subject_leaf_key: str,
    condition_id: str,
    scenario_id: str,
    evidence_id: str,
    evidence_values: Mapping[str, str | int | bool | Decimal],
    provenance: ActionEvidenceProvenance,
    action_id: str | None = None,
    action_argument_values: Mapping[str, str | int | bool | Decimal] | None = None,
) -> ModeloPreconditionFailure:
    """Build one declared verdict and fail closed on catalogue disagreement."""
    evidence = ConditionEvidence(
        condition_id=condition_id,
        evidence_id=evidence_id,
        provenance=provenance,
        values=evidence_values,
    )
    bindings: tuple[ActionArgumentBinding, ...] = ()
    if action_id is not None:
        declaration = lookup_action(action_id)
        values = action_argument_values or {}
        declared_names = {item.argument_name for item in declaration.argument_specifications}
        if set(values) != declared_names:
            raise ValueError("modelo action argument values must exactly match the catalogue declaration")
        bindings = tuple(
            ActionArgumentBinding(
                argument_name=name,
                status=ActionArgumentStatus.RESOLVED,
                value=value,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key=name,
            )
            for name, value in values.items()
        )
    verdict = PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(evidence,),
        action=ActionReference(action_id=action_id) if action_id is not None else None,
        argument_bindings=bindings,
        conditionality=(
            ActionConditionality.IMMEDIATE if declared_action_id is not None else ActionConditionality.NOT_APPLICABLE
        ),
        no_recovery_outcome=profile.no_recovery_outcome,
    )
    return ModeloPreconditionFailure(
        subject_leaf_key=subject_leaf_key,
        scenario_id=scenario_id,
        verdict=verdict,
    )


__all__ = [
    "MODELO_PRECONDITION_PROFILES",
    "ModeloPreconditionFailure",
    "build_modelo_precondition_failure",
]
