"""Validate the native claimant for a separate human review scope."""

from __future__ import annotations

from cadrumo.application.operations.person_acts import is_persons_frontend
from cadrumo.application.user_profile.access_contracts import AccessSession, SessionKind
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_runtime.contracts.worker_authorization import RuntimeHumanReviewClaimAttestation


def require_review_attestation(proof: RuntimeHumanReviewClaimAttestation, worker: ProfileWorkerIdentity) -> None:
    """Require the exact worker incarnation and person frontend before custody access."""
    if (
        proof.worker_id != worker.worker_id
        or proof.runtime_boot_id != worker.runtime_boot_id
        or proof.profile_binding != worker.binding
        or not is_persons_frontend(proof.frontend)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)


def require_review_claimant(claimant: AccessSession, proof: RuntimeHumanReviewClaimAttestation) -> None:
    """Match the current human lease to the native attestation."""
    if (
        claimant.kind is not SessionKind.HUMAN
        or claimant.connection_id != proof.connection_id
        or claimant.originating_login_id != proof.source_ref
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.HUMAN_AUTHORITY_REQUIRED)
