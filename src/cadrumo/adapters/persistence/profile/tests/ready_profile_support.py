"""A complete natural-person profile seeded for work-unit suites, stated by the autonomo-fontanero persona.

The identity, activity and tax-axis facts are the persona's own answers, read
through the core persona reader and placed on the profile paths the wizard
questions write to.
"""

from __future__ import annotations

from datetime import datetime

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileFactValue
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from cadrumo.tests.personas import IdentityRef, Persona, YearEnvelope, read_persona

_PERSONA_ID = "autonomo-fontanero"

_ANSWER_PATHS: tuple[tuple[str, str], ...] = (
    ("tax-id", "identity.tax_id"),
    ("name", "identity.name"),
    ("surnames", "identity.surnames"),
    ("tax-residence-ccaa", "tax_residence.ccaa"),
    ("tax-residence-jurisdiction-scope", "tax_residence.jurisdiction_scope"),
    ("iva-regime", "iva.regime"),
    ("iva-m303-regime-composition", "iva.m303_regime_composition"),
    ("iva-redeme-enrolled", "iva.redeme_enrolled"),
    ("iva-cash-accounting-regime-enrolled", "iva.cash_accounting_regime_enrolled"),
    ("iva-voluntary-sii-enrolled", "iva.voluntary_sii_enrolled"),
    (
        "iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
    ),
    ("entity-type", "taxpayer_type.entity_type"),
    ("irpf-income-categories", "taxpayer_type.irpf_income_categories"),
    ("irpf-estimation-regime", "irpf.estimation_regime"),
)
"""Persona wizard answer to the profile path it is stored under."""


def _persona() -> Persona:
    with bundled_indexed_authority().operation() as operation:
        support = operation.supported_filing_years()
        return read_persona(_PERSONA_ID, envelope=YearEnvelope(floor=support.floor, horizon=support.horizon))


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
    persona = _persona()
    return (
        *(UserProfileFact(path=path, value=_stated(persona, answer_id)) for answer_id, path in _ANSWER_PATHS),
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
