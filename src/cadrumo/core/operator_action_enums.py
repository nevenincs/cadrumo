"""Closed value axes shared by operator-action policy and wire projection."""

from __future__ import annotations

from enum import StrEnum


class ActionEvidenceProvenance(StrEnum):
    """Authority that observed one failed-condition fact."""

    APPLICATION_STATE = "application_state"
    DOMAIN_EVALUATION = "domain_evaluation"
    PERSISTED_STATE = "persisted_state"
    REGISTRY_RECORD = "registry_record"
    RUNTIME_OBSERVATION = "runtime_observation"


class ActionArgumentSource(StrEnum):
    """Provenance of a projected recovery-action argument value."""

    VERDICT_CONTEXT = "operator_action.verdict_context"
    CONDITION_EVIDENCE = "operator_action.condition_evidence"
    REQUEST_CONTEXT = "operator_action.request_context"


class ActionArgumentStatus(StrEnum):
    """Whether a recovery-action argument has a concrete projected value."""

    RESOLVED = "resolved"
    MISSING = "missing"


class ActionConditionality(StrEnum):
    """Whether a projected recovery action is currently materialisable."""

    IMMEDIATE = "immediate"
    REQUIRES_ARGUMENTS = "requires_arguments"
    NOT_APPLICABLE = "not_applicable"


class NoRecoveryOutcome(StrEnum):
    """Closed reasons a refusal deliberately has no recovery action."""

    TERMINAL = "terminal"
    SAFETY = "safety"
    OPERATOR_DECISION = "operator_decision"


class OperatorActionAxis(StrEnum):
    """Operator action classes shared by blocker-vocabulary projections."""

    SUPPLY_MANUAL_INPUT = "supply_manual_input"
    IMPORT_LEDGER_DATA = "import_ledger_data"
    SET_PROFILE_FACT = "set_profile_fact"
    FILE_PRIOR_PERIOD = "file_prior_period"
    CAPTURE_EXTERNAL_EVIDENCE = "capture_external_evidence"
    RESOLVE_VALUE_DIVERGENCE = "resolve_value_divergence"
    RE_VERIFY = "re_verify"
    RESOLVE_REVISION_MISMATCH = "resolve_revision_mismatch"
    CONFIRM_GROUP_MEMBERSHIP = "confirm_group_membership"
    RESOLVE_IDENTITY = "resolve_identity"
    COMPLETE_DOCUMENT_EVIDENCE = "complete_document_evidence"
    REVIEW_ADVISORY = "review_advisory"


__all__ = [
    "ActionArgumentSource",
    "ActionArgumentStatus",
    "ActionConditionality",
    "ActionEvidenceProvenance",
    "NoRecoveryOutcome",
    "OperatorActionAxis",
]
