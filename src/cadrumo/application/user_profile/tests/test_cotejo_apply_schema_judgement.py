"""The cotejo censal write door judges adopted certificate values against the schema.

Three doors write profile facts: registration's initial record, the wizard's
fact patch, and this one, which adopts values read off a Certificado de
Situacion Censal. The first two refused through the shared schema authority and
this one did not, so an official artefact could place a value at a path the
schema never declared, or in a shape it never types, and the record took it
without complaint.

The ruling pinned here is that an official ORIGIN is not evidence about either
question. AEAT certifies what the taxpayer's censal situation is; it does not
certify that a value belongs at one of this application's declared paths, or
that it arrives in the shape that path is typed. Those are the profile's own
contract, so the adopting door satisfies it exactly as an operator edit does.
Provenance is not weakened by that: each adopted fact keeps its
``censo_artefact_g313`` source token, which the schema itself declares, so a
reader still distinguishes a certified value from a typed one.

The third test is the one that keeps the ruling honest. The cotejo runs DURING
setup, against a profile legitimately still missing the fields filing depends
on, so a door demanding completeness would refuse the very reconciliation meant
to help supply them. Hardening without that test passes every refusal case
above while breaking the only case that actually happens.

Assertions read the ISSUE CODE off the refusal rather than merely observing
that something was raised: a door refusing for an unrelated reason, a missing
session or an unreadable record, would otherwise satisfy a bare
``pytest.raises`` and report the defect as fixed.
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
from ....core.config import override_settings
from ....core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT
from ....domain.user_profile import (
    ProfileSchemaValidationError,
    ProfileSetupState,
    UserProfileFact,
    load_user_profile_schema,
)
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import complete_profile_facts
from cadrumo.application.workflow.state_models import WorkflowState
from cadrumo.application.user_profile.capsule_record import ProfileRecordSession
from cadrumo.application.user_profile.cotejo_apply import CensoDivergence, apply_cotejo
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository, bound_profile_record_session
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.user_profile.validation import DATE_VALUE_ISSUE_CODE, UNKNOWN_FIELD_ISSUE_CODE

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSPHRASE = "cotejo-apply-schema-judgement-passphrase"  # noqa: S105 - synthetic test credential
_UNDECLARED_CENSO_PATH = "censo.filed_on"
_TYPED_CENSO_PATH = "censo.activity_start_date"


@contextmanager
def _cotejo_subject(tmp_path: Path, *, facts: tuple[UserProfileFact, ...] | None = None) -> Generator[tuple[Path, str]]:
    """Register a real capsule, bind its record session, and route the active profile."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Cotejo apply subject",
            passphrase=_PASSPHRASE,
            facts=facts if facts is not None else (UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        )
        material = load_committed_profile_password_material(UUID(outcome.profile_id), root=storage_root)
        unlocked = unlock_profile_custody(material.envelope, _PASSPHRASE, sentinel=material.sentinel)
        session = ProfileRecordSession.from_envelope(envelope=material.envelope, dek=unlocked.dek)
        try:
            with bound_profile_record_session(session), override_settings(cadrumo_active_profile=outcome.profile_id):
                yield storage_root, outcome.profile_id
        finally:
            session.close()


def _record_revision(profile_id: str, storage_root: Path) -> int:
    return ProfileRecordRepository.for_current_session(profile_id, root=storage_root).load(profile_id).record_revision


def test_apply_cotejo_refuses_an_adopted_value_at_a_path_the_schema_never_declared(tmp_path: Path) -> None:
    """The exact instance the schema-as-contract ruling named: an undeclared censo path."""
    with _cotejo_subject(tmp_path) as (storage_root, profile_id):
        before = _record_revision(profile_id, storage_root)

        with pytest.raises(ProfileSchemaValidationError) as refusal:
            apply_cotejo(
                WorkflowState(),
                adopted=(
                    UserProfileFact(
                        path=_UNDECLARED_CENSO_PATH,
                        value="2024-03-01",
                        source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
                    ),
                ),
                divergences=(),
            )

        context = refusal.value.context or {}
        assert UNKNOWN_FIELD_ISSUE_CODE in context["issue_codes"]
        assert _UNDECLARED_CENSO_PATH in context["issue_paths"]
        assert _record_revision(profile_id, storage_root) == before, (
            "the refusal must land before the record command, leaving the revision untouched"
        )


def test_apply_cotejo_refuses_an_adopted_certificate_value_in_the_wrong_shape(tmp_path: Path) -> None:
    """A declared path is not enough; the certified value must also arrive typed.

    The path here IS declared and IS one a censal certificate legitimately
    supplies, so this refuses for a different reason than the test above and
    cannot pass on the same branch.
    """
    with _cotejo_subject(tmp_path) as (storage_root, profile_id):
        before = _record_revision(profile_id, storage_root)

        with pytest.raises(ProfileSchemaValidationError) as refusal:
            apply_cotejo(
                WorkflowState(),
                adopted=(
                    UserProfileFact(
                        path=_TYPED_CENSO_PATH,
                        value="01/03/2024",
                        source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
                    ),
                ),
                divergences=(),
            )

        context = refusal.value.context or {}
        assert DATE_VALUE_ISSUE_CODE in context["issue_codes"]
        assert _record_revision(profile_id, storage_root) == before


def test_apply_cotejo_still_commits_a_valid_reconciliation_on_an_incomplete_profile(tmp_path: Path) -> None:
    """The door must not demand completeness of a profile still in setup.

    The cotejo is a setup-phase reconciliation, so the subject is legitimately
    missing required fields. A door asserting complete-profile validation would
    refuse this while passing every refusal test above, which is why this case
    decides whether the hardening is correct rather than merely strict.
    """
    with _cotejo_subject(tmp_path) as (storage_root, profile_id):
        before = _record_revision(profile_id, storage_root)

        apply_cotejo(
            WorkflowState(),
            adopted=(
                UserProfileFact(
                    path=_TYPED_CENSO_PATH,
                    value="2024-03-01",
                    source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
                ),
            ),
            divergences=(
                CensoDivergence(axis="censo.certificado.situacion_tributaria.0", artefact_value="ALTA EN EL CENSO"),
            ),
        )

        record = ProfileRecordRepository.for_current_session(profile_id, root=storage_root).load(profile_id)
        assert record.record_revision == before + 1
        values = {fact.path: fact.value for fact in record.facts}
        assert str(values[_TYPED_CENSO_PATH]) == "2024-03-01"
        assert values["censo.divergencia.0.artefact_value"] == "ALTA EN EL CENSO"
        adopted_fact = next(fact for fact in record.facts if fact.path == _TYPED_CENSO_PATH)
        assert adopted_fact.source == PROVENANCE_SOURCE_CENSO_ARTEFACT, (
            "judging the value must not strip the provenance that marks it non-official"
        )


def test_apply_cotejo_records_divergences_on_a_profile_past_setup(tmp_path: Path) -> None:
    """A completed profile still takes a divergence-only cotejo.

    Past setup the door judges under the COMPLETE contract, so this run holds
    the whole stored fact set to the required-field rules the incomplete case
    defers. It is the shape the profile-read surface exercises when it proves
    the open-divergence notice, and it is the case a completeness rule applied
    to the wrong side of the setup boundary would break.

    The subject is completed by SUPPLYING the required fields, derived from
    the schema itself, not by flipping the state flag over a record still
    missing them. Building it the second way would test a record no finished
    setup can produce, and would fail for the promotion door's reasons rather
    than this one's.
    """
    with _cotejo_subject(tmp_path, facts=complete_profile_facts(load_user_profile_schema())) as (
        storage_root,
        profile_id,
    ):
        repository = ProfileRecordRepository.for_current_session(profile_id, root=storage_root)
        seeded = repository.load(profile_id)
        completed = repository.complete_setup(
            profile_id,
            expected_revision=seeded.record_revision,
            expected_content_digest=seeded.content_digest,
        )
        assert completed.setup_state is ProfileSetupState.COMPLETE

        apply_cotejo(
            WorkflowState(),
            adopted=(),
            divergences=(CensoDivergence(axis="activities.description", artefact_value="Consultoria informatica"),),
        )

        record = ProfileRecordRepository.for_current_session(profile_id, root=storage_root).load(profile_id)
        assert record.setup_state is ProfileSetupState.COMPLETE
        values = {fact.path: fact.value for fact in record.facts}
        assert values["censo.divergencia.0.axis"] == "activities.description"
