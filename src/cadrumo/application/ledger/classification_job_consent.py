"""The lane and consent checks every ledger classification job operation shares.

A job is bound to the lane the agent read with when it was enqueued or last
authorised. A job on a lane that reads off this computer holds a person's
grant, recorded in the consent ledger. Before a run reads anything, the agent's
lane must still be the job's lane, and the grant must still cover the job:
recorded, not revoked, in scope, and for that lane and the classification task
kind. Otherwise the run refuses with the typed cause; it never reads on another
lane, and never on a grant the ledger no longer holds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from ...core.model_roles import ModelRole
from ...domain.evidence_consent.grant import ConsentGrantStanding
from ...domain.transactions.classification_job import ClassificationItemFailureCause, ClassificationJobLane
from .classification_job_errors import ClassificationJobConsentNotNeededError, ClassificationJobLaneChangedError
from .off_host_consent_refusal import off_host_consent_required
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

if TYPE_CHECKING:
    from cadrumo_client.contracts.model_runs import ModelRunLane

    from .classification_job_contracts import LedgerClassifyJobConsentGrant
    from .evidence_errors import LedgerOffHostConsentRequiredError

__all__ = [
    "CONSENT_FAILURE_CAUSES",
    "classification_job_lane",
    "granted_lane",
    "lane_changed",
    "off_host_consent_refused",
    "reads_with",
    "standing_failure_cause",
]

CONSENT_FAILURE_CAUSES: Final = frozenset(
    {
        ClassificationItemFailureCause.CONSENT_REQUIRED,
        ClassificationItemFailureCause.CONSENT_REVOKED,
        ClassificationItemFailureCause.CONSENT_EXPIRED,
        ClassificationItemFailureCause.LANE_CHANGED,
    }
)
"""The causes a new grant puts right: the movements that failed with them are asked again under it."""

_STANDING_CAUSES: Final = {
    ConsentGrantStanding.MISSING: ClassificationItemFailureCause.CONSENT_REQUIRED,
    ConsentGrantStanding.REVOKED: ClassificationItemFailureCause.CONSENT_REVOKED,
    ConsentGrantStanding.EXPIRED: ClassificationItemFailureCause.CONSENT_EXPIRED,
    ConsentGrantStanding.LANE_MISMATCH: ClassificationItemFailureCause.CONSENT_REQUIRED,
}


def classification_job_lane(lane: ModelRunLane) -> ClassificationJobLane:
    """Return the job lane the agent's resolved ``lane`` names."""
    return ClassificationJobLane(
        provider_id=lane.provider_id,
        transport=lane.transport,
        model=lane.model,
        reads_off_host=lane.reads_off_host,
    )


def reads_with(job_lane: ClassificationJobLane, lane: ModelRunLane) -> bool:
    """Whether the agent's resolved ``lane`` is the lane the job is bound to."""
    return (job_lane.provider_id, job_lane.transport, job_lane.model, job_lane.reads_off_host) == (
        lane.provider_id,
        lane.transport,
        lane.model,
        lane.reads_off_host,
    )


def lane_changed(lane: ModelRunLane) -> ClassificationJobLaneChangedError:
    """The refusal naming the lane the agent reads with now."""
    return ClassificationJobLaneChangedError(
        provider_id=lane.provider_id, transport=lane.transport, model=lane.model, reads_off_host=lane.reads_off_host
    )


def granted_lane(grant: LedgerClassifyJobConsentGrant, lane: ModelRunLane) -> ClassificationJobLane:
    """Return the lane the person's ``grant`` covers, which must be the lane the agent reads with.

    Raises:
        ClassificationJobLaneChangedError: The person consented to another lane
            than the one the agent reads with.
        ClassificationJobConsentNotNeededError: The lane reads on this computer.
    """
    if (grant.provider_id, grant.connection, grant.model) != (lane.provider_id, lane.transport, lane.model):
        raise lane_changed(lane)
    if not lane.reads_off_host:
        raise ClassificationJobConsentNotNeededError
    return classification_job_lane(lane)


def standing_failure_cause(standing: ConsentGrantStanding) -> ClassificationItemFailureCause:
    """Return the item cause of a grant that no longer covers the job."""
    return _STANDING_CAUSES[standing]


def off_host_consent_refused(
    *, consent_present: bool, standing: ConsentGrantStanding | None = None
) -> LedgerOffHostConsentRequiredError:
    """The ledger's off-host consent refusal, with both remedies, stating why no grant covers the read."""
    facts: dict[str, str | bool] = {
        "model_run_refusal": ModelRunRefusalCode.CONSENT_MISSING.value,
        "model_role": ModelRole.TEXT_EXTRACTION.value,
        "consent_token_present": consent_present,
    }
    if standing is not None:
        facts["consent_standing"] = standing.value
    return off_host_consent_required(
        ledger_no_recovery_verdict(LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE, facts=facts)
    )
