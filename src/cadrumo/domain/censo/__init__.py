"""Censo domain records: the G313 certificate target shape and its fact projection.

Public facade for the Certificado de Situación Censal domain surface:
the strict :class:`CertificadoSituacionCensal` record (the six officially
certified fields), its per-row :class:`ActividadLocalCertificada`, the
typed failure family, and :func:`censo_facts_from_certificado`, which
projects a parsed certificate onto candidate
:class:`~cadrumo.domain.user_profile.values.UserProfileFact` rows for the setup
flow's cotejo reconciliation.
"""

from __future__ import annotations

from ._certificado import (
    ActividadLocalCertificada,
    CertificadoCensalError,
    CertificadoCensalParseError,
    CertificadoSituacionCensal,
    censo_facts_from_certificado,
)

__all__ = [
    "ActividadLocalCertificada",
    "CertificadoCensalError",
    "CertificadoCensalParseError",
    "CertificadoSituacionCensal",
    "censo_facts_from_certificado",
]
