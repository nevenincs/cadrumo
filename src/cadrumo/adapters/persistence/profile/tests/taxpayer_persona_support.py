"""Seed the canonical estimación directa normal persona as a Modelo-ready profile."""

from __future__ import annotations

from datetime import datetime

from cadrumo.application.user_profile.tests.persona_profile_facts import (
    COLEGIO_CONCERTADO_ATTESTATION,
    DIRECTA_NORMAL_PERSONA,
)
from cadrumo.domain.user_profile.values import UserProfileFact

from .ready_profile_support import seed_persona_profile


def seed_modelo_ready_profile(
    *, bucket_id: str, at: datetime, tax_id: str | None = None, facts: tuple[UserProfileFact, ...] = ()
) -> None:
    """Seed the canonical directa normal persona as a complete profile that passes the Modelo readiness gate.

    ``tax_id`` replaces the persona's identifier for a suite whose operation
    binds the taxpayer to a source record, and ``facts`` adds the enrolment a
    modelo's applicability gate asks of the filer.
    """
    seed_persona_profile(
        DIRECTA_NORMAL_PERSONA,
        bucket_id=bucket_id,
        at=at,
        facts=(
            COLEGIO_CONCERTADO_ATTESTATION,
            *(() if tax_id is None else (UserProfileFact(path="identity.tax_id", value=tax_id),)),
            *facts,
        ),
    )
