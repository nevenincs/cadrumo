"""Whether a recorded classification grant covers a read, decided from the consent ledger's entries alone."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ....core.hashing import sha256_hex
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...transactions.classification_job import ClassificationConsentScope
from ..grant import ConsentGrantLane, ConsentGrantStanding, consent_grant_standing, standing_consent_grant
from ..record import (
    EvidenceConsentGrantTerms,
    EvidenceConsentLedgerEntry,
    EvidenceConsentRecordKind,
    evidence_consent_grant_address,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PROFILE = "3c5e7a9b-1d2f-4a6b-8c0d-2e4f6a8b0c1d"
_OTHER_PROFILE = "5e7a9b1d-2f4a-4b6c-8d0e-4f6a8b0c1d2e"
_JOB = sha256_hex(b"synthetic job")
_SESSION = sha256_hex(b"synthetic session")
_LANE = ConsentGrantLane(provider="example", transport="api", model="example-model-1", task_kind="classification")
_AT = datetime(filing_year_envelope().horizon, 3, 1, 9, 0, tzinfo=UTC)


def _granted(
    scope: ClassificationConsentScope,
    *,
    label: str = "grant",
    profile: str = _PROFILE,
    model: str = "example-model-1",
    task_kind: str = "classification",
    minutes: int = 0,
) -> EvidenceConsentLedgerEntry:
    terms = EvidenceConsentGrantTerms(
        grant_id=sha256_hex(label.encode()),
        scope=scope,
        task_kind=task_kind,
        transport="api",
        job_id=_JOB if scope is ClassificationConsentScope.ONCE else None,
        session_reference=_SESSION if scope is ClassificationConsentScope.AGENT_SESSION else None,
    )
    return EvidenceConsentLedgerEntry(
        entry_id=sha256_hex(f"entry {label}".encode()),
        profile_bucket_id=profile,
        evidence_content_address=evidence_consent_grant_address(
            profile_bucket_id=profile, provider="example", model=model, grant=terms
        ),
        provider="example",
        model=model,
        surface="synthetic-surface",
        recorded_at=_AT + timedelta(minutes=minutes),
        record_kind=EvidenceConsentRecordKind.GRANT,
        grant=terms,
    )


def _revocation(granted: EvidenceConsentLedgerEntry, *, profile: str = _PROFILE) -> EvidenceConsentLedgerEntry:
    assert granted.grant is not None
    return EvidenceConsentLedgerEntry(
        entry_id=sha256_hex(f"revoke {granted.entry_id}".encode()),
        profile_bucket_id=profile,
        evidence_content_address=granted.evidence_content_address,
        provider=granted.provider,
        model=granted.model,
        surface="synthetic-surface",
        recorded_at=granted.recorded_at + timedelta(hours=1),
        record_kind=EvidenceConsentRecordKind.REVOCATION,
        revoked_grant_id=granted.grant.grant_id,
    )


def _standing(
    entries: tuple[EvidenceConsentLedgerEntry, ...],
    granted: EvidenceConsentLedgerEntry,
    *,
    job_id: str = _JOB,
    session_reference: str | None = _SESSION,
    lane: ConsentGrantLane = _LANE,
) -> ConsentGrantStanding:
    assert granted.grant is not None
    return consent_grant_standing(
        entries,
        grant_id=granted.grant.grant_id,
        profile_bucket_id=_PROFILE,
        lane=lane,
        job_id=job_id,
        session_reference=session_reference,
    )


@pytest.mark.parametrize("scope", list(ClassificationConsentScope))
def test_a_recorded_grant_covers_its_own_lane_job_and_session(scope: ClassificationConsentScope) -> None:
    granted = _granted(scope)

    assert _standing((granted,), granted) is ConsentGrantStanding.VALID


def test_a_grant_the_ledger_does_not_hold_or_another_profile_holds_covers_nothing() -> None:
    granted = _granted(ClassificationConsentScope.REMEMBERED, profile=_OTHER_PROFILE)

    assert _standing((), granted) is ConsentGrantStanding.MISSING
    assert _standing((granted,), granted) is ConsentGrantStanding.MISSING


def test_a_revoked_grant_covers_nothing_and_only_its_own_profiles_revocation_revokes_it() -> None:
    granted = _granted(ClassificationConsentScope.REMEMBERED)

    assert _standing((granted, _revocation(granted)), granted) is ConsentGrantStanding.REVOKED
    assert _standing((granted, _revocation(granted, profile=_OTHER_PROFILE)), granted) is ConsentGrantStanding.VALID


def test_a_grant_for_another_model_or_task_kind_does_not_cover_the_read() -> None:
    other_model = _granted(ClassificationConsentScope.REMEMBERED, model="example-model-2")
    other_task = _granted(ClassificationConsentScope.REMEMBERED, label="task", task_kind="extraction")

    assert _standing((other_model,), other_model) is ConsentGrantStanding.LANE_MISMATCH
    assert _standing((other_task,), other_task) is ConsentGrantStanding.LANE_MISMATCH


def test_a_once_grant_covers_only_the_job_it_was_given_for() -> None:
    granted = _granted(ClassificationConsentScope.ONCE)

    assert _standing((granted,), granted, job_id=sha256_hex(b"another job")) is ConsentGrantStanding.MISSING


@pytest.mark.parametrize("session_reference", [sha256_hex(b"a later sign-in"), None])
def test_a_session_grant_expires_with_the_session_it_was_given_in(session_reference: str | None) -> None:
    granted = _granted(ClassificationConsentScope.AGENT_SESSION)

    assert _standing((granted,), granted, session_reference=session_reference) is ConsentGrantStanding.EXPIRED


def test_the_standing_grant_is_the_newest_unrevoked_remembered_or_current_session_grant_for_the_lane() -> None:
    once = _granted(ClassificationConsentScope.ONCE, label="once", minutes=5)
    remembered = _granted(ClassificationConsentScope.REMEMBERED, label="remembered", minutes=1)
    session = _granted(ClassificationConsentScope.AGENT_SESSION, label="session", minutes=2)
    revoked = _granted(ClassificationConsentScope.REMEMBERED, label="revoked", minutes=3)
    entries = (remembered, session, revoked, _revocation(revoked), once)

    newest = standing_consent_grant(entries, profile_bucket_id=_PROFILE, lane=_LANE, session_reference=_SESSION)
    after_sign_in = standing_consent_grant(
        entries, profile_bucket_id=_PROFILE, lane=_LANE, session_reference=sha256_hex(b"a later sign-in")
    )

    assert newest == session
    assert after_sign_in == remembered
    assert standing_consent_grant((once,), profile_bucket_id=_PROFILE, lane=_LANE, session_reference=_SESSION) is None


@pytest.mark.parametrize(
    ("scope", "job_id", "session_reference"),
    [
        (ClassificationConsentScope.ONCE, None, None),
        (ClassificationConsentScope.AGENT_SESSION, None, None),
        (ClassificationConsentScope.REMEMBERED, _JOB, None),
        (ClassificationConsentScope.REMEMBERED, None, _SESSION),
    ],
)
def test_grant_terms_name_a_job_only_once_and_a_session_only_for_the_session(
    scope: ClassificationConsentScope, job_id: str | None, session_reference: str | None
) -> None:
    with pytest.raises(ValidationError):
        EvidenceConsentGrantTerms(
            grant_id=sha256_hex(b"terms"),
            scope=scope,
            task_kind="classification",
            transport="api",
            job_id=job_id,
            session_reference=session_reference,
        )


def test_a_grant_entry_carries_its_terms_and_a_dispatch_entry_carries_none() -> None:
    granted = _granted(ClassificationConsentScope.REMEMBERED)

    with pytest.raises(ValidationError):
        EvidenceConsentLedgerEntry.model_validate({**granted.model_dump(), "grant": None})
    with pytest.raises(ValidationError):
        EvidenceConsentLedgerEntry.model_validate(
            {**granted.model_dump(), "record_kind": EvidenceConsentRecordKind.DISPATCH}
        )
