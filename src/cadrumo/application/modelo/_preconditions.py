"""Locale-neutral precondition identities for modelo application verbs."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType

from pydantic import BaseModel, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ...core.identifier_grammar import NamespacedId
from ...core.identity import CalculationRevisionId
from ...domain.modelos import WorkUnit
from ..operator_actions import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
    lookup_action,
)
from ..operator_surface import ManifestActionProfile


class ModeloPreconditionFailure(BaseModel):
    """One application-owned failed condition at a canonical modelo leaf."""

    model_config = STRICT_FROZEN_CONFIG

    subject_leaf_key: NamespacedId
    scenario_id: NamespacedId
    verdict: PreconditionVerdict

    @property
    def identity(self) -> tuple[str, str, str]:
        """Return the exact leaf, condition, and scenario identity."""
        return (self.subject_leaf_key, self.verdict.failed_condition_id, self.scenario_id)

    @model_validator(mode="after")
    def _match_declared_profile(self) -> ModeloPreconditionFailure:
        profile = MODELO_PRECONDITION_PROFILE_REGISTRY.get(self.identity)
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
    no_recovery_outcome: NoRecoveryOutcome = NoRecoveryOutcome.OPERATOR_DECISION,
) -> ManifestActionProfile:
    return ManifestActionProfile(
        subject_leaf_key=subject_leaf_key,
        condition_id=condition_id,
        scenario_id=scenario_id,
        action=ActionReference(action_id=action_id) if action_id is not None else None,
        no_recovery_outcome=(None if action_id is not None else no_recovery_outcome),
    )


_IVA_WALLET_BLOCKED_DECISION_SCENARIOS = (
    "filed_history_requires_override",
    "local_evidence_unreadable",
    "local_recurrence_requires_override",
    "no_usable_authority",
    "stale_wallet_local_recurrence_requires_override",
    "stale_wallet_no_local_recurrence",
    "wallet_local_recurrence_divergence",
)

_IVA_WALLET_CALCULATE_SCENARIOS = (
    "backend_casilla_conflict",
    *_IVA_WALLET_BLOCKED_DECISION_SCENARIOS,
    "caller_binding_conflict",
    "caller_casilla_conflict",
    "first_period_zero_ungrounded",
    "not_seeded",
    "registry_snapshot_unavailable",
    "selected_amount_missing",
    "supplied_decision_mismatch",
    "target_mismatch",
    "taxpayer_identity_missing",
    "taxpayer_mismatch",
    "unsupported_decision_type",
)

_IVA_WALLET_REVISION_SCENARIOS = (
    "amount_mismatch",
    *_IVA_WALLET_BLOCKED_DECISION_SCENARIOS,
    "first_period_zero_ungrounded",
    "not_seeded",
    "registry_snapshot_unavailable",
    "revision_amount_missing",
    "selected_amount_missing",
    "target_mismatch",
)


def _iva_wallet_profiles(
    subject_leaf_key: str,
    scenario_codes: tuple[str, ...],
) -> tuple[ManifestActionProfile, ...]:
    return tuple(
        _profile(
            subject_leaf_key,
            f"{subject_leaf_key}.iva_wallet.ready",
            f"{subject_leaf_key}.iva_wallet.{scenario_code}",
        )
        for scenario_code in scenario_codes
    )


MODELO_PRECONDITION_PROFILES: tuple[ManifestActionProfile, ...] = (
    _profile(
        "modelo.work.create",
        "modelo.work.create.period.filing_year.matches",
        "modelo.work.create.period.filing_year.mismatch",
    ),
    _profile(
        "modelo.work.create",
        "modelo.work.create.lifecycle.target_available",
        "modelo.work.create.lifecycle.target_discarded",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    _profile(
        "modelo.work.rename",
        "modelo.work.rename.lifecycle.mutable",
        "modelo.work.rename.lifecycle.discarded",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    _profile(
        "modelo.work.discard",
        "modelo.work.discard.lifecycle.not_already_discarded",
        "modelo.work.discard.lifecycle.already_discarded",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.lifecycle.active",
        "modelo.work.calculate.lifecycle.discarded",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    _profile(
        "modelo.filing_record.import",
        "modelo.filing_record.import.lifecycle.active",
        "modelo.filing_record.import.lifecycle.discarded",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    _profile(
        "modelo.readiness",
        "modelo.readiness.export_layout.renderable",
        "modelo.readiness.export_layout.unrenderable",
        action_id="operator.modelo.describe",
    ),
    _profile(
        "modelo.work.amend_wizard",
        "modelo.work.amend_wizard.external_evidence.present",
        "modelo.work.amend_wizard.external_evidence.missing",
    ),
    _profile(
        "modelo.work.wizard",
        "modelo.work.wizard.inputs.resolved",
        "modelo.work.wizard.inputs.retry_exhausted",
    ),
    *(
        _profile(
            leaf,
            "modelo.iva_wallet.taxpayer.identity_available",
            f"{leaf}.taxpayer_identity_missing",
        )
        for leaf in ("modelo.iva_wallet.seed", "modelo.iva_wallet.correct", "modelo.iva_wallet.override")
    ),
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
    *(
        _profile(
            leaf,
            f"{leaf}.calculation_revision.addresses_calculation",
            f"{leaf}.calculation_revision.work_unit_target",
            action_id="operator.modelo.work.calculate",
        )
        for leaf in ("modelo.work.verify", "modelo.work.file")
    ),
    *(
        _profile(
            leaf,
            f"{leaf}.calculation_revision.addresses_calculation",
            f"{leaf}.calculation_revision.work_unit_target_discarded",
            no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
        )
        for leaf in ("modelo.work.verify", "modelo.work.file")
    ),
    *(
        _profile(
            leaf,
            f"{leaf}.work_address.resolved",
            f"{leaf}.work_address.natural_target_absent",
        )
        for leaf in ("modelo.work.verify", "modelo.work.file")
    ),
    *(
        _profile(
            leaf,
            f"{leaf}.work_address.resolved",
            f"{leaf}.work_address.exact_work_unit_absent",
        )
        for leaf in ("modelo.work.verify", "modelo.work.file")
    ),
    _profile(
        "modelo.work.file",
        "modelo.work.file.calculation_revision.verified",
        "modelo.work.file.calculation_revision.unverified",
        action_id="operator.modelo.work.verify",
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
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.unsupported_modelo",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.missing",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.period_mismatch",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.regimen_snapshot_mismatch",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.regimen_scope_profile_divergence",
    ),
    *(
        _profile(
            "modelo.work.calculate",
            "modelo.work.calculate.m303_profile_readiness.ready",
            f"modelo.work.calculate.m303_profile_readiness.{scenario_code}",
        )
        for scenario_code in (
            "iva_composition_missing",
            "iva_composition_unknown",
            "profile_absent",
            "profile_inactive",
        )
    ),
    *(
        _profile(
            "modelo.work.calculate",
            "modelo.work.calculate.m303_filing_evidence.valid",
            f"modelo.work.calculate.m303_filing_evidence.{scenario_code}",
        )
        for scenario_code in (
            "exonerado_390_endpoint_coverage_incomplete",
            "exonerado_390_endpoints_on_non_applicable",
            "exonerado_390_not_final_period",
            "exonerado_390_observation_value_divergence",
            "exonerado_390_revision_value_divergence",
            "simplified_calculation_result_divergence",
        )
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
        "modelo.work.file.deductible_iva_evidence.present",
        "modelo.work.file.deductible_iva_evidence.missing",
    ),
    _profile(
        "modelo.work.file",
        "modelo.work.file.m202.modality.complete",
        "modelo.work.file.m202.modality.incomplete",
    ),
    _profile(
        "modelo.work.file",
        "modelo.work.file.cross_period_dependency.clean",
        "modelo.work.file.cross_period_dependency.unclean",
    ),
    _profile(
        "modelo.work.file",
        "modelo.work.file.activity_start_date.present",
        "modelo.work.file.activity_start_date.missing_for_first_filer_adjudication",
    ),
    _profile(
        "modelo.export",
        "modelo.export.deductible_iva_evidence.present",
        "modelo.export.deductible_iva_evidence.missing",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.registry_snapshot.available",
        "modelo.work.verify.registry_snapshot.unavailable",
        action_id="operator.registry.verify",
    ),
    # No action, and TERMINAL rather than OPERATOR_DECISION: a revision that
    # declares less than filing authority is not something the operator can
    # decide their way out of. Re-running verify produces the identical refusal,
    # so pointing at ``operator.registry.verify`` here -- as the sibling above
    # legitimately does for an UNRESOLVED snapshot -- would hand out a next step
    # that cannot resolve the finding. The revision has to be split and attested
    # first, and that is not operator work.
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.registry_snapshot.filing_authority",
        "modelo.work.verify.registry_snapshot.authority_grade_insufficient",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
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
        "modelo.work.verify.deductible_iva_evidence.present",
        "modelo.work.verify.deductible_iva_evidence.missing",
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
    *_iva_wallet_profiles("modelo.work.calculate", _IVA_WALLET_CALCULATE_SCENARIOS),
    *_iva_wallet_profiles("modelo.work.verify", _IVA_WALLET_REVISION_SCENARIOS),
    *_iva_wallet_profiles("modelo.work.file", _IVA_WALLET_REVISION_SCENARIOS),
    *_iva_wallet_profiles("modelo.export", _IVA_WALLET_REVISION_SCENARIOS),
)

MODELO_PRECONDITION_PROFILE_REGISTRY: Mapping[tuple[str, str, str], ManifestActionProfile] = MappingProxyType(
    {profile.identity: profile for profile in MODELO_PRECONDITION_PROFILES}
)
if len(MODELO_PRECONDITION_PROFILE_REGISTRY) != len(MODELO_PRECONDITION_PROFILES):
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
    identity = (subject_leaf_key, condition_id, scenario_id)
    profile = MODELO_PRECONDITION_PROFILE_REGISTRY.get(identity)
    if profile is None:
        raise ValueError("modelo precondition failure identity is not declared")
    declared_action_id = profile.action.action_id if profile.action is not None else None
    if action_id != declared_action_id:
        raise ValueError("modelo precondition failure action contradicts its declaration")
    evidence = ConditionEvidence(
        condition_id=condition_id,
        evidence_id=evidence_id,
        provenance=provenance,
        values=evidence_values,
    )
    bindings: tuple[ActionArgumentBinding, ...] = ()
    if declared_action_id is not None:
        declaration = lookup_action(declared_action_id)
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
        action=profile.action,
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


def build_modelo_precondition_failure_for_scenario(
    *,
    subject_leaf_key: str,
    scenario_id: str,
    evidence_id: str,
    evidence_values: Mapping[str, str | int | bool | Decimal],
    provenance: ActionEvidenceProvenance,
    action_argument_values: Mapping[str, str | int | bool | Decimal] | None = None,
) -> ModeloPreconditionFailure:
    """Build a failure from its declared leaf/scenario profile without re-declaring its condition."""
    profiles = tuple(
        profile
        for profile in MODELO_PRECONDITION_PROFILES
        if profile.subject_leaf_key == subject_leaf_key and profile.scenario_id == scenario_id
    )
    if len(profiles) != 1:
        raise ValueError("modelo precondition scenario must resolve to exactly one declared profile")
    profile = profiles[0]
    return build_modelo_precondition_failure(
        subject_leaf_key=subject_leaf_key,
        condition_id=profile.condition_id,
        scenario_id=scenario_id,
        evidence_id=evidence_id,
        evidence_values=evidence_values,
        provenance=provenance,
        action_id=None if profile.action is None else profile.action.action_id,
        action_argument_values=action_argument_values,
    )


def build_modelo_work_file_unverified_revision_failure(
    *,
    calculation_revision_id: CalculationRevisionId,
    state: str,
    work_unit: WorkUnit,
) -> ModeloPreconditionFailure:
    """Build the one declared filing-admission refusal for an unverified revision.

    Both the operator-addressing facade and the direct filing operation enforce
    this same persisted lifecycle condition.  Keeping its evidence and action
    binding here prevents either entry path from independently re-declaring the
    recovery contract.
    """
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.work.file",
        scenario_id="modelo.work.file.calculation_revision.unverified",
        evidence_id="modelo.work.file.calculation_revision.state",
        evidence_values={
            "calculation_revision_id": calculation_revision_id,
            "work_unit_id": work_unit.work_unit_id,
            "modelo": str(work_unit.modelo),
            "year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "state": state,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values={"work_unit_id": work_unit.work_unit_id},
    )


__all__ = [
    "MODELO_PRECONDITION_PROFILES",
    "MODELO_PRECONDITION_PROFILE_REGISTRY",
    "ModeloPreconditionFailure",
    "build_modelo_precondition_failure",
    "build_modelo_precondition_failure_for_scenario",
    "build_modelo_work_file_unverified_revision_failure",
]
