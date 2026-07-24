"""Typed record for the Certificado de Situación Censal (procedure G313).

The certificate is the operator-downloadable censal artefact the setup
flow's cotejo phase reconciles against. Its target shape is the SIX
officially certified fields (AEAT "¿Qué certifica?"): domicilio fiscal,
condición de residencia, NIF de los representantes, situación tributaria,
actividades y locales, and obligaciones periódicas. The shape is
primary-source grounded; the PDF layout extraction is deliberately
unpinned until a real issued-certificate specimen exists, so the inbound
adapter refuses loudly rather than guessing a layout.

``censo_facts_from_certificado`` projects the certificate onto candidate
:class:`~cadrumo.domain.user_profile.UserProfileFact` rows for the cotejo's
compare-select pages. Only axes with an unambiguous profile counterpart
produce a candidate fact; the rest are display-only certificate evidence:

* ``condicion_residencia`` — free-form certificate prose; mapping it onto
  the typed fiscal-residency enum needs the specimen's exact vocabulary.
* ``representantes_nif`` — the certificate certifies legal representatives,
  a DIFFERENT axis from the profile's IRNR ``representante_fiscal_nif``;
  auto-mapping would conflate the two.
* ``situacion_tributaria`` / ``obligaciones_periodicas`` — obligation
  surface, an input to the derived deadline schedule, not a static profile
  fact.

Every candidate fact carries the non-official artefact provenance token —
never an AEAT-verified stamp, so the calendar's ``censo.enrolment_unverified``
posture is unaffected.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from ...core import STRICT_FROZEN_CONFIG
from ...core.errors import CadrumoError
from ...core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT
from ...core.identity import validate_spanish_tax_id
from ..user_profile import UserProfileFact


class CertificadoCensalError(CadrumoError):
    """Base for every Certificado de Situación Censal failure."""


class CertificadoCensalParseError(CertificadoCensalError):
    """Raised when bytes cannot be parsed into a :class:`CertificadoSituacionCensal`."""


class ActividadLocalCertificada(BaseModel):
    """One certified actividad/local row on the certificate."""

    model_config = STRICT_FROZEN_CONFIG

    descripcion: str = Field(min_length=1)
    epigrafe_iae: str = ""
    local: str = ""


class CertificadoSituacionCensal(BaseModel):
    """The six certified fields of a G313 censal certificate."""

    model_config = STRICT_FROZEN_CONFIG

    domicilio_fiscal: str = Field(min_length=1)
    condicion_residencia: str = Field(min_length=1)
    representantes_nif: tuple[str, ...] = ()
    situacion_tributaria: tuple[str, ...] = ()
    actividades: tuple[ActividadLocalCertificada, ...] = ()
    obligaciones_periodicas: tuple[str, ...] = ()

    @field_validator("representantes_nif")
    @classmethod
    def _validate_representantes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Every certified representative NIF validates through the core identity authority."""
        return tuple(validate_spanish_tax_id(nif) for nif in value)


def censo_facts_from_certificado(certificado: CertificadoSituacionCensal) -> tuple[UserProfileFact, ...]:
    """Project the certificate onto candidate profile facts for the cotejo.

    Returns :class:`~cadrumo.domain.user_profile.UserProfileFact` rows
    stamped with the artefact provenance token. Axes without an unambiguous
    profile counterpart are deliberately absent (display-only evidence on
    the cotejo page); see the module docstring for the per-axis rationale.
    """
    facts: list[UserProfileFact] = [
        UserProfileFact(
            path="contact.fiscal_address",
            value=certificado.domicilio_fiscal,
            source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
        ),
    ]
    if certificado.actividades:
        primary = certificado.actividades[0]
        facts.append(
            UserProfileFact(
                path="activities.description",
                value=primary.descripcion,
                source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
            ),
        )
        if primary.epigrafe_iae:
            facts.append(
                UserProfileFact(
                    path="activities.iae_epigraph",
                    value=primary.epigrafe_iae,
                    source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
                ),
            )
    return tuple(facts)


__all__ = [
    "ActividadLocalCertificada",
    "CertificadoCensalError",
    "CertificadoCensalParseError",
    "CertificadoSituacionCensal",
    "censo_facts_from_certificado",
]
