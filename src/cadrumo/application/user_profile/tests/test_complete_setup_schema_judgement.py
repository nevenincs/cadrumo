"""Promoting a profile out of setup judges it against the contract COMPLETE claims.

A profile is born SETUP_INCOMPLETE and is allowed to be missing the fields
filing depends on, because demanding them in order to build an unfinished
profile is a contradiction. The validator defers exactly those issues and its
own prose says they come due in full at the promotion. They did not: the
promotion flipped the state after a compare-and-swap and nothing else, so a
record missing required residence and IVA-regime answers became COMPLETE
without complaint.

That is worse than an unjudged fact write, which is what makes it a stricter
door rather than the same one copied. An invalid record that merely exists is
contained; an invalid record wearing COMPLETE is TRUSTED -- setup state is what
downstream surfaces read to decide a profile is ready, so the promotion is the
moment the claim becomes load-bearing. COMPLETE is not a label for a record
that stopped being edited, it is the claim that nothing required is missing, so
this door judges with the completeness rules switched ON while the fact-writing
doors leave them deferred.

The refusal tests fail for two different reasons on purpose -- one an
unconditional required field, one a conditional block opened by an answer -- so
neither can pass on the other's branch, and a door that only re-applied half
the completeness rules would still red.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody import (
    load_committed_profile_password_material,
    unlock_profile_custody,
)
from ....domain.user_profile.errors import ProfileSchemaValidationError
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import complete_profile_facts
from ..capsule_record import ProfileRecordSession
from ..profile_record_repository import ProfileRecordRepository, bound_profile_record_session
from ..registration import register_profile_with_credentials
from ..validation import CONDITIONAL_REQUIRED_FIELD_MISSING_CODE, REQUIRED_FIELD_MISSING_CODE

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSPHRASE = "complete-setup-schema-judgement-passphrase"  # noqa: S105 - synthetic test credential


@contextmanager
def _setup_subject(tmp_path: Path, *, facts: tuple[UserProfileFact, ...]) -> Generator[tuple[Path, str]]:
    """Register a real INCOMPLETE capsule carrying ``facts`` and bind its session."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Promotion subject",
            passphrase=_PASSPHRASE,
            facts=facts,
        )
        material = load_committed_profile_password_material(UUID(outcome.profile_id), root=storage_root)
        unlocked = unlock_profile_custody(material.envelope, _PASSPHRASE, sentinel=material.sentinel)
        session = ProfileRecordSession.from_envelope(envelope=material.envelope, dek=unlocked.dek)
        try:
            with bound_profile_record_session(session):
                yield storage_root, outcome.profile_id
        finally:
            session.close()


def _promote(profile_id: str, storage_root: Path):
    """Attempt the promotion using the record's own current CAS coordinates."""
    repository = ProfileRecordRepository.for_current_session(profile_id, root=storage_root)
    current = repository.load(profile_id)
    return repository.complete_setup(
        profile_id,
        expected_revision=current.record_revision,
        expected_content_digest=current.content_digest,
    )


def test_complete_setup_refuses_a_record_missing_an_unconditional_required_field(tmp_path: Path) -> None:
    """The literal defect: a record short of required answers became COMPLETE."""
    with _setup_subject(
        tmp_path,
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    ) as (storage_root, profile_id):
        with pytest.raises(ProfileSchemaValidationError) as refusal:
            _promote(profile_id, storage_root)

        context = refusal.value.context or {}
        issue_codes = context["issue_codes"]
        issue_paths = context["issue_paths"]
        assert isinstance(issue_codes, tuple)
        assert isinstance(issue_paths, tuple)
        assert REQUIRED_FIELD_MISSING_CODE in issue_codes
        assert "tax_residence.jurisdiction_scope" in issue_paths

        record = ProfileRecordRepository.for_current_session(profile_id, root=storage_root).load(profile_id)
        assert record.setup_state is ProfileSetupState.INCOMPLETE, (
            "a refused promotion must leave the record honestly incomplete"
        )


def test_complete_setup_refuses_a_record_whose_conditional_block_is_unanswered(tmp_path: Path) -> None:
    """Answering one field can open a block, and promotion re-applies those too.

    This subject satisfies every UNCONDITIONAL requirement, so it fails on a
    different rule than the test above and cannot pass on that test's branch. A
    door that re-applied only the unconditional half would go green there and
    red here.
    """
    schema = load_user_profile_schema()
    unconditional_only = tuple(
        fact
        for fact in complete_profile_facts(schema)
        if fact.path in {"identity.tax_id", "tax_residence.jurisdiction_scope", "iva.regime"}
    )
    with _setup_subject(tmp_path, facts=unconditional_only) as (storage_root, profile_id):
        with pytest.raises(ProfileSchemaValidationError) as refusal:
            _promote(profile_id, storage_root)

        context = refusal.value.context or {}
        issue_codes = context["issue_codes"]
        assert isinstance(issue_codes, tuple)
        assert CONDITIONAL_REQUIRED_FIELD_MISSING_CODE in issue_codes

        record = ProfileRecordRepository.for_current_session(profile_id, root=storage_root).load(profile_id)
        assert record.setup_state is ProfileSetupState.INCOMPLETE


def test_complete_setup_promotes_a_record_that_satisfies_the_contract(tmp_path: Path) -> None:
    """The door must still promote a genuinely finished profile.

    Without this the refusals above are satisfied by a door that refuses
    everything, which would strand every operator at the end of setup.
    """
    with _setup_subject(tmp_path, facts=complete_profile_facts(load_user_profile_schema())) as (
        storage_root,
        profile_id,
    ):
        repository = ProfileRecordRepository.for_current_session(profile_id, root=storage_root)
        before = repository.load(profile_id)
        assert before.setup_state is ProfileSetupState.INCOMPLETE

        promoted = _promote(profile_id, storage_root)

        assert promoted.setup_state is ProfileSetupState.COMPLETE
        assert promoted.record_revision == before.record_revision + 1
        reloaded = ProfileRecordRepository.for_current_session(profile_id, root=storage_root).load(profile_id)
        assert reloaded.setup_state is ProfileSetupState.COMPLETE


def test_complete_setup_is_a_no_op_on_an_already_complete_record(tmp_path: Path) -> None:
    """Re-promoting publishes nothing and does not re-judge.

    The already-COMPLETE early return sits ahead of the judgement deliberately:
    it changes no state, so holding it to a contract a stored record may
    predate would refuse a caller that writes nothing. This pins that ordering
    -- a second call returns the same revision rather than advancing or
    raising.
    """
    with _setup_subject(tmp_path, facts=complete_profile_facts(load_user_profile_schema())) as (
        storage_root,
        profile_id,
    ):
        promoted = _promote(profile_id, storage_root)
        again = _promote(profile_id, storage_root)

        assert again.setup_state is ProfileSetupState.COMPLETE
        assert again.record_revision == promoted.record_revision, "a re-promotion must not advance the revision"
