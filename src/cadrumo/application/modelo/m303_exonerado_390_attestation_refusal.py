"""Refusals of an operator's Modelo 390 applicability attestation, with served words and the door that leads on.

The attestation is the operator's statement that the Modelo 390 does not apply
to a Modelo 303 period. Recording it and relying on it are both refused for a
fixed set of causes. Each cause is a refusal of the operator's request or of
the evidence the request names, never a fault of the stored data, so each has
its own catalogue sentence and a verdict that either names the action which
puts it right or says honestly that none does.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period
from .action_errors import M303Exonerado390AttestationUnadmissibleError
from .preconditions import build_modelo_precondition_failure_for_scenario

_LEAF: Final[str] = "modelo.work.attest_m303_exonerado_390"
_SCENARIO_ROOT: Final[str] = f"{_LEAF}.evidence"
_REFUSAL_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "observation_timing": "application.modelo.errors.exonerado_390_attestation_observation_timing",
    "stored_observation_timing": "application.modelo.errors.exonerado_390_attestation_stored_observation_timing",
    "coordinate_unsupported": "application.modelo.errors.exonerado_390_attestation_coordinate_unsupported",
    "applicable_unsupported": "application.modelo.errors.exonerado_390_attestation_applicable_unsupported",
    "evidence_other_profile": "application.modelo.errors.exonerado_390_attestation_evidence_other_profile",
    "evidence_not_attestation": "application.modelo.errors.exonerado_390_attestation_evidence_not_attestation",
    "evidence_reference_invalid": "application.modelo.errors.exonerado_390_attestation_evidence_reference_invalid",
    "evidence_coordinate_mismatch": (
        "application.modelo.errors.exonerado_390_attestation_evidence_coordinate_mismatch"
    ),
    "conflicting_assertions": "application.modelo.errors.exonerado_390_attestation_conflicting_assertions",
    "unknown_attachment": "application.modelo.errors.exonerado_390_attestation_unknown_attachment",
    "evidence_unusable": "application.modelo.errors.exonerado_390_attestation_evidence_unusable",
    "malformed_identity": "application.modelo.errors.exonerado_390_attestation_malformed_identity",
    "incomplete_identity": "application.modelo.errors.exonerado_390_attestation_incomplete_identity",
    "not_modelo_303_work_unit": "application.modelo.errors.exonerado_390_attestation_not_modelo_303_work_unit",
    "profile_bucket_invalid": "application.modelo.errors.exonerado_390_attestation_profile_bucket_invalid",
    "profile_not_current": "application.modelo.errors.exonerado_390_attestation_profile_not_current",
}
"""The catalogue sentence each cause is served as."""


class PeriodAttestationRefusal(StrEnum):
    """Causes that concern one Modelo 303 period, so their words and door name it."""

    OBSERVATION_TIMING = "observation_timing"
    STORED_OBSERVATION_TIMING = "stored_observation_timing"
    COORDINATE_UNSUPPORTED = "coordinate_unsupported"
    APPLICABLE_UNSUPPORTED = "applicable_unsupported"
    EVIDENCE_OTHER_PROFILE = "evidence_other_profile"
    EVIDENCE_NOT_ATTESTATION = "evidence_not_attestation"
    EVIDENCE_REFERENCE_INVALID = "evidence_reference_invalid"
    EVIDENCE_COORDINATE_MISMATCH = "evidence_coordinate_mismatch"
    CONFLICTING_ASSERTIONS = "conflicting_assertions"
    UNKNOWN_ATTACHMENT = "unknown_attachment"
    EVIDENCE_UNUSABLE = "evidence_unusable"


class RequestAttestationRefusal(StrEnum):
    """Causes found before any period is known, in what the request names."""

    MALFORMED_IDENTITY = "malformed_identity"
    INCOMPLETE_IDENTITY = "incomplete_identity"
    NOT_MODELO_303_WORK_UNIT = "not_modelo_303_work_unit"
    PROFILE_BUCKET_INVALID = "profile_bucket_invalid"
    PROFILE_NOT_CURRENT = "profile_not_current"


_PERIOD_SCENARIOS: Final[dict[PeriodAttestationRefusal, str]] = {
    PeriodAttestationRefusal.OBSERVATION_TIMING: "observation_timing",
    PeriodAttestationRefusal.STORED_OBSERVATION_TIMING: "observation_timing",
    PeriodAttestationRefusal.COORDINATE_UNSUPPORTED: "request_unsupported",
    PeriodAttestationRefusal.APPLICABLE_UNSUPPORTED: "request_unsupported",
    PeriodAttestationRefusal.EVIDENCE_OTHER_PROFILE: "evidence_unusable",
    PeriodAttestationRefusal.EVIDENCE_NOT_ATTESTATION: "evidence_unusable",
    PeriodAttestationRefusal.EVIDENCE_REFERENCE_INVALID: "evidence_unusable",
    PeriodAttestationRefusal.EVIDENCE_COORDINATE_MISMATCH: "evidence_unusable",
    PeriodAttestationRefusal.CONFLICTING_ASSERTIONS: "conflicting_assertions",
    PeriodAttestationRefusal.UNKNOWN_ATTACHMENT: "evidence_unusable",
    PeriodAttestationRefusal.EVIDENCE_UNUSABLE: "evidence_unusable",
}

_REQUEST_SCENARIOS: Final[dict[RequestAttestationRefusal, str]] = {
    RequestAttestationRefusal.MALFORMED_IDENTITY: "identity_unusable",
    RequestAttestationRefusal.INCOMPLETE_IDENTITY: "identity_unusable",
    RequestAttestationRefusal.NOT_MODELO_303_WORK_UNIT: "target_wrong",
    RequestAttestationRefusal.PROFILE_BUCKET_INVALID: "target_wrong",
    RequestAttestationRefusal.PROFILE_NOT_CURRENT: "profile_not_current",
}

_REPLACEABLE_SCENARIOS: Final[frozenset[str]] = frozenset({"observation_timing", "evidence_unusable"})
"""The scenarios whose door is recording a new attestation, which takes the period and an observation time."""


def _refusal(
    reason: str,
    scenario: str,
    *,
    evidence: dict[str, str | int | bool],
    context: dict[str, object],
    action_argument_values: dict[str, str | int] | None,
    missing_action_arguments: tuple[str, ...],
) -> M303Exonerado390AttestationUnadmissibleError:
    scenario_id = f"{_SCENARIO_ROOT}.{scenario}"
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=_LEAF,
        scenario_id=scenario_id,
        evidence_id=f"{scenario_id}.observation",
        evidence_values={"reason": reason, "admissible": False, **evidence},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        action_argument_values=action_argument_values,
        missing_action_arguments=missing_action_arguments,
    )
    return M303Exonerado390AttestationUnadmissibleError(
        translated_message=_REFUSAL_LOCALE_KEYS[reason],
        context={"reason": reason, **context},
        precondition_failure=failure,
    )


def period_attestation_unadmissible(
    reason: PeriodAttestationRefusal, period: Period
) -> M303Exonerado390AttestationUnadmissibleError:
    """Refuse the attestation of ``period`` for ``reason``, naming the period in its words.

    Where recording a new attestation puts the cause right, the verdict names
    that action with the year and period bound; the observation time is the
    operator's to state.
    """
    scenario = _PERIOD_SCENARIOS[reason]
    replaceable = scenario in _REPLACEABLE_SCENARIOS
    return _refusal(
        reason.value,
        scenario,
        evidence={"period": period.registry_token, "filing_year": period.filing_year},
        context={"period": period.registry_token, "filing_year": period.filing_year},
        action_argument_values={"year": period.filing_year, "period": period.registry_token} if replaceable else None,
        missing_action_arguments=("observed_at",) if replaceable else (),
    )


def request_attestation_unadmissible(
    reason: RequestAttestationRefusal, *, work_unit_id: str | None = None
) -> M303Exonerado390AttestationUnadmissibleError:
    """Refuse an attestation request for ``reason`` found in what the request names.

    ``work_unit_id`` names the declaration a request addressed, where the cause
    is that it is not a Modelo 303.
    """
    scenario = _REQUEST_SCENARIOS[reason]
    facts: dict[str, str | int | bool] = {} if work_unit_id is None else {"work_unit_id": work_unit_id}
    return _refusal(
        reason.value,
        scenario,
        evidence=facts,
        context=dict(facts),
        action_argument_values=None,
        missing_action_arguments=(),
    )


__all__ = [
    "PeriodAttestationRefusal",
    "RequestAttestationRefusal",
    "period_attestation_unadmissible",
    "request_attestation_unadmissible",
]
