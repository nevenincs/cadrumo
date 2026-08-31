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
:class:`~cadrumo.domain.user_profile.values.UserProfileFact` rows for the cotejo's
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

from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT
from ...core.identity import validate_spanish_tax_id
from ...core.models import STRICT_FROZEN_CONFIG
from ..user_profile.values import UserProfileFact


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
    """The six axes AEAT states a G313 censal certificate certifies.

    This is the model's scope, not an inventory of the document. AEAT's
    "¿Qué certifica?" enumerates what the certificate ATTESTS; whether the
    issued artefact also carries an issue date, a CSV or header furniture
    is unestablished, because no issued-certificate specimen exists in this
    tree. Read the absence of a temporal field as unmeasured, never as
    evidence the document has none -- and in particular do not derive an
    obligation start year from that absence.
    """

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

    Returns :class:`~cadrumo.domain.user_profile.values.UserProfileFact` rows
    stamped with the artefact provenance token. Axes without an unambiguous
    profile counterpart are deliberately absent (display-only evidence on
    the cotejo page); see the module docstring for the per-axis rationale.

    Every certified ``actividad`` is projected, not only the first. The
    ``activities`` section is schema-declared ``repeatable``, and
    :func:`~cadrumo.application.user_profile.profile_section_rows` already
    treats a repeatable fact written WITHOUT an index as the implicit first
    row -- the shape every other single-activity producer in this codebase
    writes -- so the primary activity keeps that unindexed address for
    compatibility, and every activity after it is projected at its own
    numeric index (``activities.1.description``, ``activities.2.description``,
    ...), which is the addressing scheme the manager and status surfaces
    already read repeatable rows through. A taxpayer with a second local or
    a second IAE epígrafe on the certificate used to lose it here silently:
    ``actividades[0]`` with no loop, no warning, and a cotejo that still
    reported success.
    """
    facts: list[UserProfileFact] = [
        UserProfileFact(
            path="contact.fiscal_address",
            value=certificado.domicilio_fiscal,
            source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
        ),
    ]
    for index, actividad in enumerate(certificado.actividades):
        prefix = "activities" if index == 0 else f"activities.{index}"
        facts.append(
            UserProfileFact(
                path=f"{prefix}.description",
                value=actividad.descripcion,
                source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
            ),
        )
        if actividad.epigrafe_iae:
            facts.append(
                UserProfileFact(
                    path=f"{prefix}.iae_epigraph",
                    value=actividad.epigrafe_iae,
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
