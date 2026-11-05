"""A complete natural-person profile seeded for work-unit suites, stated by the autonomo-fontanero persona.

The identity, activity and tax-axis facts are the persona's own answers, read
through the core persona reader and stored under the profile paths the production setup flow assigns.
"""

from __future__ import annotations

from datetime import datetime

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileFactValue
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from cadrumo.tests.personas import IdentityRef, Persona, YearEnvelope, read_persona

_PERSONA_ID = "autonomo-fontanero"

_ANSWER_IDS: tuple[str, ...] = (
    "tax-id",
    "name",
    "surnames",
    "tax-residence-ccaa",
    "tax-residence-jurisdiction-scope",
    "iva-regime",
    "iva-m303-regime-composition",
    "iva-redeme-enrolled",
    "iva-cash-accounting-regime-enrolled",
    "iva-voluntary-sii-enrolled",
    "iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
    "entity-type",
    "irpf-income-categories",
    "irpf-estimation-regime",
)
"""The persona answers a ready profile carries; the setup flow owns the profile path each is stored under."""


def _persona_and_paths() -> tuple[Persona, dict[str, str]]:
    with bundled_indexed_authority().operation() as operation:
        support = operation.supported_filing_years()
        persona = read_persona(_PERSONA_ID, envelope=YearEnvelope(floor=support.floor, horizon=support.horizon))
        flow = build_setup_flow(operation)
    paths = {
        question.id: question.profile_key
        for section in flow.sections
        for question in section.questions
        if question.profile_key is not None
    }
    return persona, paths


def _stated(persona: Persona, answer_id: str) -> UserProfileFactValue:
    value = next(answer.value for answer in persona.profile if answer.question_id == answer_id)
    if isinstance(value, bool | str):
        return value
    if isinstance(value, IdentityRef):
        return persona.identity(value)
    if isinstance(value, tuple):
        return ",".join(value)
    raise TypeError(f"persona answer {answer_id} is not a plain profile value")


def _ready_profile_facts() -> tuple[UserProfileFact, ...]:
    persona, paths = _persona_and_paths()
    return (
        *(UserProfileFact(path=paths[answer_id], value=_stated(persona, answer_id)) for answer_id in _ANSWER_IDS),
        UserProfileFact(path="activities.description", value=dict(persona.activities[0].values)["description"]),
        UserProfileFact(path="provenance.source", value="manual_cli"),
        # Modelo 111 refuses a defaulted colegio-concertado declaration; the persona
        # leaves this header attestation outside its answers, and a natural-person
        # filer truthfully states False.
        UserProfileFact(path="withholding.colegio_concertado", value=False),
    )


def seed_ready_profile(*, bucket_id: str, at: datetime) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=_ready_profile_facts(),
            created_at=at,
            updated_at=at,
            context=_profile_creation_context_for_test(),
        ),
    )
