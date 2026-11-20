"""Composition of the consent ledger as the grant store of ledger classification jobs.

A person's grant of off-host classification reads is a consent-ledger entry
bound to the open profile, the lane (provider, transport and model) and the
classification task kind. A grant for the agent session names the profile
session it was given in by a digest of that session's identity, so a new
sign-in starts a session no earlier grant covers. Every standing bar is read
when a grant is recorded and again when each read mints its consent: the gestor
bar, the deployment opt-in and the profile's own eligibility.
"""

from __future__ import annotations

import secrets
from typing import Final

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.model_runs import ModelRunTaskKind

from ..adapters.outbound.llm.consent import off_host_evidence_read_askable
from ..adapters.persistence.llm.consent_ledger import EvidenceConsentLedger
from ..adapters.persistence.storage.master_key.active_session import current_active_bucket_session
from ..application.ledger.classification_job_consent import off_host_consent_refused
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.user_profile.capabilities import cloud_evidence_upload_eligible_for_active_profile
from ..core.config import load_settings
from ..core.hashing import sha256_hex
from ..core.identity.bucket import canonical_bucket_id
from ..domain.evidence_consent.grant import (
    ConsentGrantLane,
    ConsentGrantStanding,
    consent_grant_standing,
    standing_consent_grant,
)
from ..domain.evidence_consent.record import EvidenceConsentGrantTerms, EvidenceConsentRecordKind
from ..domain.transactions.classification_job import (
    ClassificationConsentScope,
    ClassificationJobConsent,
    ClassificationJobLane,
)

__all__ = ["LedgerClassificationConsentGrants", "profile_session_reference"]

_TASK_KIND: Final = ModelRunTaskKind.CLASSIFICATION.value


def profile_session_reference(bucket_id: str) -> str | None:
    """Return a digest naming the profile session open now for ``bucket_id``, or ``None`` when none is.

    A resumed session keeps the opening instant of the sign-in it resumes, so
    the reference lasts exactly as long as that sign-in.
    """
    session = current_active_bucket_session()
    if session is None or canonical_bucket_id(session.bucket_id) != canonical_bucket_id(bucket_id):
        return None
    return sha256_hex(f"{canonical_bucket_id(session.bucket_id)}|{session.opened_at.isoformat()}".encode())


def _grant_lane(lane: ClassificationJobLane) -> ConsentGrantLane:
    return ConsentGrantLane(provider=lane.provider_id, transport=lane.transport, model=lane.model, task_kind=_TASK_KIND)


def _require_open_profile(bucket_id: str) -> None:
    session = current_active_bucket_session()
    if session is None or canonical_bucket_id(session.bucket_id) != canonical_bucket_id(bucket_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def classification_reads_askable() -> bool:
    """Whether the standing bars let this profile grant off-host reads at all."""
    settings = load_settings()
    return off_host_evidence_read_askable(
        settings, profile_eligible=cloud_evidence_upload_eligible_for_active_profile(settings=settings)
    )


class LedgerClassificationConsentGrants:
    """Record, find, check and revoke classification grants in the open profile's consent ledger."""

    def __init__(self, ledger: EvidenceConsentLedger | None = None) -> None:
        """Bind the consent ledger; the production one when none is given."""
        self._ledger = ledger or EvidenceConsentLedger()

    def grant(
        self,
        *,
        bucket_id: str,
        lane: ClassificationJobLane,
        scope: ClassificationConsentScope,
        job_id: str,
        surface: str,
    ) -> ClassificationJobConsent:
        """Record the person's grant, or refuse with both remedies when a standing bar forbids off-host reads."""
        _require_open_profile(bucket_id)
        session_reference = profile_session_reference(bucket_id)
        if not classification_reads_askable() or (
            scope is ClassificationConsentScope.AGENT_SESSION and session_reference is None
        ):
            raise off_host_consent_refused(consent_present=False)
        terms = EvidenceConsentGrantTerms(
            grant_id=secrets.token_hex(32),
            scope=scope,
            task_kind=_TASK_KIND,
            transport=lane.transport,
            job_id=job_id if scope is ClassificationConsentScope.ONCE else None,
            session_reference=session_reference if scope is ClassificationConsentScope.AGENT_SESSION else None,
        )
        entry = self._ledger.append_grant(provider=lane.provider_id, model=lane.model, surface=surface, grant=terms)
        return ClassificationJobConsent(scope=scope, consent_reference=terms.grant_id, granted_at=entry.recorded_at)

    def standing_grant(self, *, bucket_id: str, lane: ClassificationJobLane) -> ClassificationJobConsent | None:
        """Return the newest remembered grant, or grant for the agent session open now, that covers ``lane``."""
        _require_open_profile(bucket_id)
        if not classification_reads_askable():
            return None
        entry = standing_consent_grant(
            self._ledger.load_entries(),
            profile_bucket_id=canonical_bucket_id(bucket_id),
            lane=_grant_lane(lane),
            session_reference=profile_session_reference(bucket_id),
        )
        if entry is None or entry.grant is None:
            return None
        return ClassificationJobConsent(
            scope=entry.grant.scope, consent_reference=entry.grant.grant_id, granted_at=entry.recorded_at
        )

    def standing(
        self, *, bucket_id: str, lane: ClassificationJobLane, consent: ClassificationJobConsent, job_id: str
    ) -> ConsentGrantStanding:
        """Return whether the grant ``consent`` names covers a read by ``job_id`` on ``lane`` now."""
        _require_open_profile(bucket_id)
        return consent_grant_standing(
            self._ledger.load_entries(),
            grant_id=consent.consent_reference,
            profile_bucket_id=canonical_bucket_id(bucket_id),
            lane=_grant_lane(lane),
            job_id=job_id,
            session_reference=profile_session_reference(bucket_id),
        )

    def revoke(self, *, bucket_id: str, consent: ClassificationJobConsent, surface: str) -> bool:
        """Withdraw the grant ``consent`` names; ``False`` when the ledger holds no such grant or it was revoked."""
        _require_open_profile(bucket_id)
        profile = canonical_bucket_id(bucket_id)
        entries = self._ledger.load_entries()
        revoked = {
            entry.revoked_grant_id
            for entry in entries
            if entry.profile_bucket_id == profile and entry.record_kind is EvidenceConsentRecordKind.REVOCATION
        }
        granted = next(
            (
                entry
                for entry in entries
                if entry.profile_bucket_id == profile
                and entry.grant is not None
                and entry.grant.grant_id == consent.consent_reference
            ),
            None,
        )
        if granted is None or consent.consent_reference in revoked:
            return False
        self._ledger.append_revocation(granted=granted, surface=surface)
        return True
