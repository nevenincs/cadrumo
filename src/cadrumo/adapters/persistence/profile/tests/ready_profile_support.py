"""Seed a canonical persona's profile for suites below the entrypoints, and the shared ready profile.

A persona's answers are read through the core persona reader. The production
setup flow assigns each answer its profile path, the profile patch judge
refuses what the patch operation would refuse, and the facts are stored
through the capsule writer the profile tests share. The entrypoints parity
suite holds the result equal to what replaying the persona's profile through
the production operations records.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Final

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_profile_facts
from cadrumo.application.user_profile.validation import reject_invalid_profile_facts
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.tests.personas import IdentityRef, Persona, YearEnvelope, read_persona

_PERSONA_ID = "autonomo-fontanero"

WITHHOLDING_PAYER_PERSONA: Final = "traductora-profesional"
"""The persona who withholds on a professional's fees, so she files Modelos 111 and 190; the ready profile pays none."""

INTRACOMMUNITY_OPERATOR_PERSONA: Final = "intracomunitario-desarrollador"
"""The persona enrolled in the ROI who trades with other Member States, so he files Modelo 349; the ready profile does not."""

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


def _stated(persona: Persona, answer_id: str) -> str | bool:
    value = next(answer.value for answer in persona.profile if answer.question_id == answer_id)
    if isinstance(value, bool | str):
        return value
    if isinstance(value, IdentityRef):
        return persona.identity(value)
    if isinstance(value, tuple):
        return ",".join(value)
    raise TypeError(f"persona answer {answer_id} is not a plain profile value")


_IDENTITY_ANSWER_IDS = frozenset({"tax-id", "name", "surnames"})


def ready_profile_fact_values() -> dict[str, str | bool]:
    """The ready profile's taxpayer facts keyed by profile path, without the persona's identity answers."""
    persona, paths = _persona_and_paths()
    return {
        paths[answer_id]: _stated(persona, answer_id)
        for answer_id in _ANSWER_IDS
        if answer_id not in _IDENTITY_ANSWER_IDS
    }


def seed_persona_profile(
    persona_id: str,
    *,
    bucket_id: str,
    at: datetime,
    facts: tuple[UserProfileFact, ...] = (),
    complete: bool = True,
    root: Path | None = None,
    label: str = "Test profile",
) -> None:
    """Store ``persona_id``'s profile in ``bucket_id``, with the extra ``facts`` a suite states beside it.

    The profile is complete when ``complete`` is true, and then it must pass the
    same complete-profile judgement the setup-completion operation applies, or
    the seed refuses. ``root`` and ``label`` name the storage root and the capsule label of a suite
    that keeps its profile outside the default root.
    """
    persona_facts = persona_profile_facts(persona_id)
    stated = {fact.path for fact in facts}
    merged = (*(fact for fact in persona_facts if fact.path not in stated), *facts)
    with bundled_indexed_authority().operation() as operation:
        if complete:
            reject_invalid_profile_facts(
                bucket_id,
                merged,
                require_complete=True,
                schema=operation.profile_decode_context().schema,
            )
        record = create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE if complete else ProfileSetupState.INCOMPLETE,
            profile_id=bucket_id,
            facts=merged,
            created_at=at,
            updated_at=at,
            context=operation.profile_create_context(),
        )
    seed_test_profile_record(record, root=root, label=label)


def seed_ready_profile(*, bucket_id: str, at: datetime, facts: tuple[UserProfileFact, ...] = ()) -> None:
    """Seed the shared ready profile: the autonomo-fontanero persona, with the colegio-concertado attestation.

    Modelo 111 refuses a defaulted colegio-concertado declaration; the persona
    leaves this header attestation outside its answers, and a natural-person
    filer truthfully states False. ``facts`` adds the enrolment a modelo's
    applicability gate asks of the filer.
    """
    seed_persona_profile(
        _PERSONA_ID,
        bucket_id=bucket_id,
        at=at,
        facts=(UserProfileFact(path="withholding.colegio_concertado", value=False), *facts),
    )


def persona_taxpayer_tax_id(persona_id: str) -> str:
    """Return the tax identifier ``persona_id``'s profile states for its taxpayer."""
    return next(str(fact.value) for fact in persona_profile_facts(persona_id) if fact.path == "identity.tax_id")
