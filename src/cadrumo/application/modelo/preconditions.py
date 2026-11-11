"""Locale-neutral precondition identities for modelo application verbs."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identifier_grammar import NamespacedId
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ...domain.modelos.work_unit import WorkUnit
from ..operator_actions.catalogue import lookup_action
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from ..operator_surface.models import ManifestActionProfile


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
    @pydantic_validation_boundary
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
    "local_calculation_redeme_unstated",
    "local_calculation_refund_undecided",
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
    "local_calculation_only",
    "not_seeded",
    "registry_snapshot_unavailable",
    "revision_amount_missing",
    "selected_amount_missing",
    "target_mismatch",
)


IVA_WALLET_OPENING_BALANCE_SCENARIOS: Final[frozenset[str]] = frozenset(
    {
        "first_period_zero_ungrounded",
        "local_evidence_unreadable",
        "no_usable_authority",
        "not_seeded",
    },
)
"""The wallet refusals the period's opening balance is the way out of.

Each says the period's carry has no usable recorded authority, which is exactly
what declaring the opening balance supplies. A stale wallet, a divergence, or a
correction names a different wallet entry, so it keeps no action here rather
than naming a command that would not settle it. The wallet gate's served step
and these profiles' action read this one set.
"""

IVA_WALLET_OPENING_BALANCE_ACTION_ID: Final[str] = "operator.modelo.iva_wallet.seed"
"""The catalogue action that declares the opening balance of a period's carry."""

IVA_WALLET_OVERRIDE_SCENARIOS: Final[frozenset[str]] = frozenset(
    {
        "filed_history_requires_override",
        "local_recurrence_requires_override",
        "stale_wallet_local_recurrence_requires_override",
    },
)
"""The wallet refusals an explicit taxpayer override of the period's carry is the way out of.

Each says the carry rests on the taxpayer's own records alone, with no current
AEAT wallet behind it, so it is carried only once the taxpayer states the amount
and the evidence for it. The amount those records give is known, so the action
names it; the reason and the evidence are the taxpayer's to supply.
"""

IVA_WALLET_OVERRIDE_ACTION_ID: Final[str] = "operator.modelo.iva_wallet.override"
"""The catalogue action that records an explicit taxpayer override of a period's carry."""


def _iva_wallet_action_id(scenario_code: str) -> str | None:
    """Name the catalogue action that settles one wallet refusal, or None when none does."""
    if scenario_code in IVA_WALLET_OPENING_BALANCE_SCENARIOS:
        return IVA_WALLET_OPENING_BALANCE_ACTION_ID
    if scenario_code in IVA_WALLET_OVERRIDE_SCENARIOS:
        return IVA_WALLET_OVERRIDE_ACTION_ID
    return None


def _iva_wallet_profiles(
    subject_leaf_key: str,
    scenario_codes: tuple[str, ...],
) -> tuple[ManifestActionProfile, ...]:
    return tuple(
        _profile(
            subject_leaf_key,
            f"{subject_leaf_key}.iva_wallet.ready",
            f"{subject_leaf_key}.iva_wallet.{scenario_code}",
            action_id=_iva_wallet_action_id(scenario_code),
        )
        for scenario_code in scenario_codes
    )


# Where an earlier declaration stands names the work that moves it on.
_SOURCE_STANDING_DOORS: tuple[tuple[str, str], ...] = (
    ("source_absent", "operator.modelo.work.create"),
    ("source_uncalculated", "operator.modelo.work.calculate"),
    ("source_unverified", "operator.modelo.work.verify"),
    ("source_unfiled", "operator.modelo.work.file"),
)


def _cross_period_door_profiles(subject_leaf_key: str) -> tuple[ManifestActionProfile, ...]:
    """An unclean source routed by its first blocker: its own work, or its capture once filed."""
    return tuple(
        _profile(
            subject_leaf_key,
            f"{subject_leaf_key}.cross_period_dependency.clean",
            f"{subject_leaf_key}.cross_period_dependency.{scenario}",
            action_id=action_id,
        )
        for scenario, action_id in (
            *_SOURCE_STANDING_DOORS,
            ("filed_evidence_missing", "operator.live.filed.pull"),
        )
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
        "modelo.work.create",
        "modelo.work.create.censo.work_unit_allowed",
        "modelo.work.create.censo.modelo_superseded",
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
    # An account page the export needs is written from an own account the
    # register holds; adding one is the way to give the export what it asks for.
    *(
        _profile(
            "modelo.export",
            f"modelo.export.{role}_account.registered",
            f"modelo.export.{role}_account.missing",
            action_id="operator.ledger.account.add",
        )
        for role in ("charge", "refund")
    ),
    # A split in two instalments the export cannot write is a choice about the
    # export that no catalogued action states.
    _profile(
        "modelo.export",
        "modelo.export.instalment_election.admitted",
        "modelo.export.instalment_election.refused",
    ),
    _profile(
        "modelo.export",
        "modelo.export.period.maps_to_filing_period",
        "modelo.export.period.unmappable",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    *(
        _profile(
            leaf,
            f"{leaf}.external_evidence.present",
            f"{leaf}.external_evidence.missing",
            action_id="operator.modelo.filing_record.import",
        )
        for leaf in ("modelo.work.amend", "modelo.work.amend_wizard")
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
    *(
        _profile(
            leaf,
            f"{leaf}.source_inputs.unowned",
            f"{leaf}.source_inputs.{kind}_override_rejected",
        )
        for leaf in ("modelo.work.calculate", "modelo.project")
        for kind in ("binding", "casilla")
    ),
    _profile(
        "modelo.project",
        "modelo.project.m130_quarters.present",
        "modelo.project.m130_quarters.no_work_units",
        action_id="operator.modelo.work.create",
    ),
    _profile(
        "modelo.project",
        "modelo.project.m130_quarters.calculated",
        "modelo.project.m130_quarters.no_calculation",
        action_id="operator.modelo.work.calculate",
    ),
    # No action: the region is a fact of the profile's tax residence, and which
    # one it is belongs to the filer.
    _profile(
        "modelo.project",
        "modelo.project.region.stated",
        "modelo.project.region.unstated",
    ),
    # No action: which revision the registry's declaration names is the registry's,
    # and the filer cannot change it.
    _profile(
        "modelo.project",
        "modelo.project.projection_mapping.names_revision",
        "modelo.project.projection_mapping.revision_unnamed",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.caller_overrides.binding_declared",
        "modelo.work.calculate.caller_overrides.binding_unknown",
        action_id="operator.modelo.bindings.list",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.caller_overrides.casilla_declared",
        "modelo.work.calculate.caller_overrides.casilla_unknown",
        action_id="operator.modelo.casillas",
    ),
    # No action: a row field's values arrive on the detail rows that carry it,
    # and which rows those are is the operator's to supply, not a refusal's.
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.caller_overrides.casilla_scalar",
        "modelo.work.calculate.caller_overrides.row_field_casilla_refused",
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
    *(
        _profile(
            leaf,
            f"{leaf}.m123_count_authority.resolved",
            f"{leaf}.m123_count_authority.unresolved",
        )
        for leaf in ("modelo.work.calculate", "modelo.work.verify", "modelo.work.file", "modelo.export")
    ),
    # No action: a settled prior-accrual Modelo 193 row needs an official
    # source for its payment-year amounts, which only the operator can obtain.
    *(
        _profile(
            leaf,
            f"{leaf}.m193_settled_row_amount_authority.resolved",
            f"{leaf}.m193_settled_row_amount_authority.unresolved",
        )
        for leaf in ("modelo.work.file", "modelo.export")
    ),
    # A ledger row that holds the calculation is reclassified, the row named;
    # an issue about the whole period is re-checked over that period.
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.ledger_preflight.ready",
        "modelo.work.calculate.ledger_preflight.blocked",
        action_id="operator.ledger.classify.movement",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.ledger_preflight.ready",
        "modelo.work.calculate.ledger_preflight.period_blocked",
        action_id="operator.ledger.preflight",
    ),
    # The statement that no earlier-ejercicio carry is pending is the edit the
    # declaration's form serves; the command line stages the same edit.
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.prior_carries.stated",
        "modelo.work.calculate.prior_carries.renta_negative_general_bases_pending_unstated",
        action_id="operator.modelo.work.attest_prior_carries",
    ),
    # An input no source supplied is stated on the calculation itself; the
    # binding listing names it and the work unit's form takes the value.
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.input.supplied",
        "modelo.work.calculate.input.binding_unanswered",
        action_id="operator.modelo.bindings.list",
    ),
    # An input whose value the operator may state over its source is answered
    # by that statement: the door is the override bound to the input.
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.input.supplied",
        "modelo.work.calculate.input.override_unanswered",
        action_id="operator.modelo.work.override",
    ),
    # A carry from an earlier period of the same ejercicio is read from that
    # period's filed return; where that return stands names the work that
    # moves it on.
    *(
        _profile(
            "modelo.work.calculate",
            "modelo.work.calculate.prior_filing.sources_filed",
            f"modelo.work.calculate.prior_filing.{scenario}",
            action_id=action_id,
        )
        for scenario, action_id in _SOURCE_STANDING_DOORS
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
        "modelo.work.calculate.m303_filing_evidence.joint_return_unanswered",
        action_id="operator.modelo.work.calculate_joint_return",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.period_mismatch",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.exonerado_390_attestation_outside_last_period",
    ),
    _profile(
        "modelo.work.calculate",
        "modelo.work.calculate.m303_filing_evidence.valid",
        "modelo.work.calculate.m303_filing_evidence.period_outside_filing_schedule",
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
    *_cross_period_door_profiles("modelo.work.file"),
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
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    # No action, and TERMINAL rather than OPERATOR_DECISION: a revision that
    # declares less than filing authority is not something the operator can
    # decide their way out of. Re-running verify produces the identical refusal,
    # The bundled registry is shipped product data, not operator-configurable
    # state. A missing snapshot is likewise terminal: the release must be
    # repaired and re-issued; the operator has no local recovery action.
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
        "modelo.work.verify.invoice_source_document.present",
        "modelo.work.verify.invoice_source_document.missing",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.iva_selected_scope_evidence.complete",
        "modelo.work.verify.iva_selected_scope_evidence.unresolved",
    ),
    # TERMINAL: these deductions rest on a document no ledger write can record,
    # so nothing the operator does inside the product lets the same declaration
    # pass. It is filed another way.
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.iva_selected_scope_evidence.complete",
        "modelo.work.verify.iva_selected_scope_evidence.import_document_unrecordable",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.iva_selected_scope_evidence.complete",
        "modelo.work.verify.iva_selected_scope_evidence.reagp_document_unrecordable",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.iva_selected_scope_evidence.complete",
        "modelo.work.verify.iva_selected_scope_evidence.rectification_document_unrecordable",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.iva_selected_scope_evidence.complete",
        "modelo.work.verify.iva_selected_scope_evidence.cuota_disagrees_with_rate",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.iva_compensation_annual_source_evidence.complete",
        "modelo.work.verify.iva_compensation_annual_source_evidence.unresolved",
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
        "modelo.work.verify.scheme_period.matches",
        "modelo.work.verify.scheme_period.contradicted",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.oss_no_activity.consistent",
        "modelo.work.verify.oss_no_activity.contradicted",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.oss_evidence.present",
        "modelo.work.verify.oss_evidence.missing",
    ),
    # Two scenarios, one condition: an annual withholding summary whose
    # per-perceptor detail is empty is refused either because nothing proves the
    # absence, or because the ledger contradicts the attestation that would. The
    # operator's next step differs (attest, versus reconcile the invoices), so a
    # single scenario would hide which refusal they met.
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.withholding_detail.proven",
        "modelo.work.verify.withholding_detail.unproven",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.withholding_detail.proven",
        "modelo.work.verify.withholding_detail.contradicted",
    ),
    # A periodic box counting more persons than the annual summary names at all.
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.withholding_count.reconciled",
        "modelo.work.verify.withholding_count.exceeded",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.ledger_snapshot.current",
        "modelo.work.verify.ledger_snapshot.drift_detected",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.ledger_snapshot.current",
        "modelo.work.verify.ledger_snapshot.membership_unavailable",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.invoice_fingerprint.current",
        "modelo.work.verify.invoice_fingerprint.drift_detected",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.invoice_fingerprint.current",
        "modelo.work.verify.invoice_fingerprint.catalogue_unavailable",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.invoice_fingerprint.current",
        "modelo.work.verify.invoice_fingerprint.scope_narrower",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.shared_casilla_cells.adjudicated",
        "modelo.work.verify.shared_casilla_cells.unadjudicated",
    ),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.xml_return_content.accepted",
        "modelo.work.verify.xml_return_content.refused",
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
    *_cross_period_door_profiles("modelo.work.verify"),
    _profile(
        "modelo.work.verify",
        "modelo.work.verify.activity_start_date.present",
        "modelo.work.verify.activity_start_date.missing_for_first_filer_adjudication",
    ),
    *_iva_wallet_profiles("modelo.work.calculate", _IVA_WALLET_CALCULATE_SCENARIOS),
    *_iva_wallet_profiles("modelo.work.verify", _IVA_WALLET_REVISION_SCENARIOS),
    *_iva_wallet_profiles("modelo.work.file", _IVA_WALLET_REVISION_SCENARIOS),
    *_iva_wallet_profiles("modelo.export", _IVA_WALLET_REVISION_SCENARIOS),
    # A calculation the note gate withholds an action from. A stale screen is
    # put right by calculating again; a blocking note is read on the
    # declaration's status; a filing recorded before screens existed has no
    # action that clears it, so it is the operator's decision.
    *(
        profile
        for leaf in ("modelo.work.verify", "modelo.work.file", "modelo.export", "modelo.work.report")
        for profile in (
            _profile(
                leaf,
                f"{leaf}.calculation_notes.clear",
                f"{leaf}.calculation_notes.screen_outdated",
                action_id="operator.modelo.work.calculate",
            ),
            _profile(
                leaf,
                f"{leaf}.calculation_notes.clear",
                f"{leaf}.calculation_notes.blocking_note",
                action_id="operator.modelo.work.status",
            ),
            _profile(
                leaf,
                f"{leaf}.calculation_notes.clear",
                f"{leaf}.calculation_notes.filed_before_grade_cap",
            ),
        )
    ),
    # An operator's Modelo 390 applicability attestation the application refuses
    # to record or to rely on. Evidence that is unusable or observed at a time
    # its period does not allow is replaced by recording a new attestation; the
    # other causes lie in what the request names, which the operator decides,
    # or in what this path cannot record at all.
    *(
        _profile(
            "modelo.work.attest_m303_exonerado_390",
            "modelo.work.attest_m303_exonerado_390.evidence.admissible",
            f"modelo.work.attest_m303_exonerado_390.evidence.{scenario_code}",
            action_id="operator.modelo.work.attest_m303_exonerado_390",
        )
        for scenario_code in ("observation_timing", "evidence_unusable")
    ),
    _profile(
        "modelo.work.attest_m303_exonerado_390",
        "modelo.work.attest_m303_exonerado_390.evidence.admissible",
        "modelo.work.attest_m303_exonerado_390.evidence.profile_not_current",
        action_id="operator.profile.status",
    ),
    *(
        _profile(
            "modelo.work.attest_m303_exonerado_390",
            "modelo.work.attest_m303_exonerado_390.evidence.admissible",
            f"modelo.work.attest_m303_exonerado_390.evidence.{scenario_code}",
        )
        for scenario_code in ("identity_unusable", "target_wrong", "conflicting_assertions")
    ),
    _profile(
        "modelo.work.attest_m303_exonerado_390",
        "modelo.work.attest_m303_exonerado_390.evidence.admissible",
        "modelo.work.attest_m303_exonerado_390.evidence.request_unsupported",
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    ),
)

MODELO_PRECONDITION_PROFILE_REGISTRY: Mapping[tuple[str, str, str], ManifestActionProfile] = MappingProxyType(
    {profile.identity: profile for profile in MODELO_PRECONDITION_PROFILES}
)
if len(MODELO_PRECONDITION_PROFILE_REGISTRY) != len(MODELO_PRECONDITION_PROFILES):
    raise ValueError("modelo precondition profile identities must be unique")


def _action_argument_bindings(
    declared_action_id: str | None,
    action_argument_values: Mapping[str, str | int | bool | Decimal] | None,
    missing_action_arguments: tuple[str, ...],
) -> tuple[ActionArgumentBinding, ...]:
    """Bind resolved and missing arguments, requiring exact coverage of the catalogue declaration."""
    if declared_action_id is None:
        if missing_action_arguments:
            raise ValueError("modelo precondition failure without an action cannot name missing arguments")
        return ()
    declaration = lookup_action(declared_action_id)
    values = action_argument_values or {}
    missing = set(missing_action_arguments)
    declared_names = {item.argument_name for item in declaration.argument_specifications}
    if (
        len(missing) != len(missing_action_arguments)
        or missing & set(values)
        or set(values) | missing != declared_names
    ):
        raise ValueError("modelo action argument values must exactly match the catalogue declaration")
    return (
        *(
            ActionArgumentBinding(
                argument_name=name,
                status=ActionArgumentStatus.RESOLVED,
                value=value,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key=name,
            )
            for name, value in values.items()
        ),
        *(
            ActionArgumentBinding(argument_name=name, status=ActionArgumentStatus.MISSING)
            for name in missing_action_arguments
        ),
    )


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
    missing_action_arguments: tuple[str, ...] = (),
) -> ModeloPreconditionFailure:
    """Build one declared verdict and fail closed on catalogue disagreement.

    ``missing_action_arguments`` names the declared arguments only the operator
    can supply, such as an answer the refused request did not carry; together
    with the resolved ``action_argument_values`` they must cover the catalogue
    declaration exactly.
    """
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
    bindings = _action_argument_bindings(declared_action_id, action_argument_values, missing_action_arguments)
    if declared_action_id is None:
        conditionality = ActionConditionality.NOT_APPLICABLE
    elif missing_action_arguments:
        conditionality = ActionConditionality.REQUIRES_ARGUMENTS
    else:
        conditionality = ActionConditionality.IMMEDIATE
    verdict = PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(evidence,),
        action=profile.action,
        argument_bindings=bindings,
        missing_argument_names=missing_action_arguments,
        conditionality=conditionality,
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
    missing_action_arguments: tuple[str, ...] = (),
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
        missing_action_arguments=missing_action_arguments,
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
    "IVA_WALLET_OPENING_BALANCE_ACTION_ID",
    "IVA_WALLET_OPENING_BALANCE_SCENARIOS",
    "IVA_WALLET_OVERRIDE_ACTION_ID",
    "IVA_WALLET_OVERRIDE_SCENARIOS",
    "MODELO_PRECONDITION_PROFILES",
    "MODELO_PRECONDITION_PROFILE_REGISTRY",
    "ModeloPreconditionFailure",
    "build_modelo_precondition_failure",
    "build_modelo_precondition_failure_for_scenario",
    "build_modelo_work_file_unverified_revision_failure",
]
