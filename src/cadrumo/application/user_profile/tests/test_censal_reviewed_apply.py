"""Real repository proofs for exact reviewed-censal apply."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

import pytest
from pydantic import ValidationError

from cadrumo.application.user_profile.capsule_record import (
    ProfileRecordConflictError,
    ProfileRecordSession,
    ProfileRecordStore,
)
from cadrumo.application.user_profile.censal_observation import (
    CensalObservation,
    CensalObservationAddress,
    CensalObservationIdentity,
)
from cadrumo.application.user_profile.censal_operation import (
    CensalFieldIntent,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
    CensalReviewedOperand,
)
from cadrumo.application.user_profile.cotejo_apply import apply_cotejo
from cadrumo.application.user_profile.profile_record_repository import (
    ProfileRecordRepository,
    bound_profile_record_session,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.workflow.state_models import WorkflowState

from ....adapters.persistence.storage.custody import load_committed_profile_password_material, unlock_profile_custody
from ....core.config import override_settings
from ....domain.buckets import BucketEventType
from ....domain.user_profile import UserProfileFact
from ....tests.aeat_literal_fixtures import aeat_url
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSPHRASE = "censal-reviewed-apply-passphrase"  # noqa: S105 - synthetic fixture
_NOW = datetime(2026, 8, 24, 16, tzinfo=UTC)


@contextmanager
def _subject(tmp_path: Path) -> Generator[tuple[str, ProfileRecordSession]]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Reviewed censal apply",
            passphrase=_PASSPHRASE,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        )
        material = load_committed_profile_password_material(UUID(outcome.profile_id), root=root)
        unlocked = unlock_profile_custody(material.envelope, _PASSPHRASE, sentinel=material.sentinel)
        session = ProfileRecordSession.from_envelope(envelope=material.envelope, dek=unlocked.dek)
        try:
            with bound_profile_record_session(session), override_settings(cadrumo_active_profile=outcome.profile_id):
                yield outcome.profile_id, session
        finally:
            session.close()


def _proposal(record: object) -> CensalReviewedOperand:
    from ....domain.user_profile import UserProfileRecord

    assert isinstance(record, UserProfileRecord)
    return CensalReviewedOperand(
        observation=CensalObservation(
            identity=CensalObservationIdentity(nif="12345678Z"),
            domicilio_fiscal=CensalObservationAddress(
                tipo_via="CALLE",
                nombre_via="Mayor",
                numero_casa="7",
                codigo_postal="28013",
                referencia_catastral="1234567VK4713C0001AB",
            ),
            domicilio_notificacion=CensalObservationAddress(),
            captured_at=_NOW,
            source_url=aeat_url("sede", "/censo/consulta"),
        ),
        baseline=CensalProfileBaseline.from_record(record),
        field_intents=(
            CensalReviewedFieldIntent(path="contact.fiscal_address", intent=CensalFieldIntent.ADOPT),
            CensalReviewedFieldIntent(path="contact.postcode", intent=CensalFieldIntent.PRESERVE),
            CensalReviewedFieldIntent(
                path="contact.fiscal_address_cadastral_reference",
                intent=CensalFieldIntent.ADOPT,
            ),
        ),
    )


def test_reviewed_proposal_applies_exact_effects_and_one_event(tmp_path: Path) -> None:
    with _subject(tmp_path) as (profile_id, session):
        repository = ProfileRecordRepository.for_current_session(profile_id)
        before = repository.load(profile_id)
        history_before = ProfileRecordStore(session=session).history()

        apply_cotejo(WorkflowState(), reviewed_proposal=_proposal(before))

        after = repository.load(profile_id)
        values = {fact.path: fact.value for fact in after.facts}
        assert after.record_revision == before.record_revision + 1
        assert values["contact.fiscal_address"] == "CALLE Mayor 7, 28013"
        assert values["contact.fiscal_address_cadastral_reference"] == "1234567VK4713C0001AB"
        assert values["censo.divergencia.0.axis"] == "contact.postcode"
        history = ProfileRecordStore(session=session).history()
        assert len(history) == len(history_before) + 1
        assert history[-1].event_type is BucketEventType.CENSO_APPLIED
        assert history[-1].payload["adopted_count"] == "2"
        assert history[-1].payload["divergence_count"] == "1"


@pytest.mark.parametrize("stale_axis", ["revision", "digest"])
def test_reviewed_proposal_refuses_stale_baseline_without_effect(tmp_path: Path, stale_axis: str) -> None:
    with _subject(tmp_path) as (profile_id, session):
        repository = ProfileRecordRepository.for_current_session(profile_id)
        before = repository.load(profile_id)
        proposal = _proposal(before)
        baseline_update = (
            {"record_revision": before.record_revision + 1}
            if stale_axis == "revision"
            else {"content_digest": "f" * 64}
        )
        stale_payload = proposal.model_dump(mode="python")
        stale_payload["baseline"] = proposal.baseline.model_copy(update=baseline_update)
        stale_payload["proposed_effect_digest"] = ""
        stale = CensalReviewedOperand.model_validate(stale_payload, strict=True)
        history_before = ProfileRecordStore(session=session).history()

        with pytest.raises(ProfileRecordConflictError, match="baseline is stale"):
            apply_cotejo(WorkflowState(), reviewed_proposal=stale)

        assert repository.load(profile_id) == before
        assert ProfileRecordStore(session=session).history() == history_before


def test_reviewed_proposal_refuses_tampered_intent_before_effect(tmp_path: Path) -> None:
    with _subject(tmp_path) as (profile_id, session):
        repository = ProfileRecordRepository.for_current_session(profile_id)
        before = repository.load(profile_id)
        proposal = _proposal(before)
        tampered = proposal.model_copy(
            update={
                "field_intents": (
                    proposal.field_intents[0].model_copy(update={"intent": CensalFieldIntent.PRESERVE}),
                    *proposal.field_intents[1:],
                )
            }
        )
        history_before = ProfileRecordStore(session=session).history()

        with pytest.raises(ValidationError, match="proposed-effect digest"):
            apply_cotejo(WorkflowState(), reviewed_proposal=tampered)

        assert repository.load(profile_id) == before
        assert ProfileRecordStore(session=session).history() == history_before


def test_reviewed_proposal_refuses_foreign_profile_baseline_without_effect(tmp_path: Path) -> None:
    with _subject(tmp_path) as (profile_id, session):
        repository = ProfileRecordRepository.for_current_session(profile_id)
        before = repository.load(profile_id)
        proposal = _proposal(before)
        payload = proposal.model_dump(mode="python")
        payload["baseline"] = proposal.baseline.model_copy(
            update={"profile_id": "22222222-2222-4222-8222-222222222222"}
        )
        payload["proposed_effect_digest"] = ""
        foreign = CensalReviewedOperand.model_validate(payload, strict=True)
        history_before = ProfileRecordStore(session=session).history()

        with pytest.raises(ProfileRecordConflictError, match="baseline is stale"):
            apply_cotejo(WorkflowState(), reviewed_proposal=foreign)

        assert repository.load(profile_id) == before
        assert ProfileRecordStore(session=session).history() == history_before


@pytest.mark.parametrize(
    ("missing_effect", "message"),
    [
        ("adopted", "requires both adopted facts and divergences"),
        ("divergences", "requires both adopted facts and divergences"),
        ("none", "requires both adopted facts and divergences"),
    ],
)
def test_incomplete_direct_mode_refuses_before_publication(
    tmp_path: Path,
    missing_effect: Literal["adopted", "divergences", "none"],
    message: str,
) -> None:
    with _subject(tmp_path) as (profile_id, session):
        repository = ProfileRecordRepository.for_current_session(profile_id)
        before = repository.load(profile_id)
        history_before = ProfileRecordStore(session=session).history()

        with pytest.raises(ValueError, match=message):
            if missing_effect == "adopted":
                apply_cotejo(WorkflowState(), adopted=())
            elif missing_effect == "divergences":
                apply_cotejo(WorkflowState(), divergences=())
            else:
                apply_cotejo(WorkflowState())

        assert repository.load(profile_id) == before
        assert ProfileRecordStore(session=session).history() == history_before


@pytest.mark.parametrize("direct_effect", ["adopted", "divergences"])
def test_reviewed_and_direct_mixed_mode_refuses_before_publication(
    tmp_path: Path,
    direct_effect: Literal["adopted", "divergences"],
) -> None:
    with _subject(tmp_path) as (profile_id, session):
        repository = ProfileRecordRepository.for_current_session(profile_id)
        before = repository.load(profile_id)
        history_before = ProfileRecordStore(session=session).history()
        proposal = _proposal(before)

        with pytest.raises(ValueError, match="cannot be combined with direct cotejo effects"):
            if direct_effect == "adopted":
                apply_cotejo(WorkflowState(), reviewed_proposal=proposal, adopted=())
            else:
                apply_cotejo(WorkflowState(), reviewed_proposal=proposal, divergences=())

        assert repository.load(profile_id) == before
        assert ProfileRecordStore(session=session).history() == history_before
