"""Shared G313 certificate builder preserving all six certified axes."""

from __future__ import annotations

from typing import TypedDict, Unpack

from ..certificado import ActividadLocalCertificada, CertificadoSituacionCensal


class _CertificadoFields(TypedDict):
    domicilio_fiscal: str
    condicion_residencia: str
    representantes_nif: tuple[str, ...]
    situacion_tributaria: tuple[str, ...]
    actividades: tuple[ActividadLocalCertificada, ...]
    obligaciones_periodicas: tuple[str, ...]


class _CertificadoOverrides(TypedDict, total=False):
    domicilio_fiscal: str
    condicion_residencia: str
    representantes_nif: tuple[str, ...]
    situacion_tributaria: tuple[str, ...]
    actividades: tuple[ActividadLocalCertificada, ...]
    obligaciones_periodicas: tuple[str, ...]


def build_certificado(**overrides: Unpack[_CertificadoOverrides]) -> CertificadoSituacionCensal:
    """Build the shared typed certificate with optional per-axis overrides."""
    payload: _CertificadoFields = {
        "domicilio_fiscal": "Calle Mayor 1, 28001 Madrid",
        "condicion_residencia": "Residente",
        "representantes_nif": ("12345678Z",),
        "situacion_tributaria": ("Alta en el censo de empresarios",),
        "actividades": (
            ActividadLocalCertificada(
                descripcion="Programación informática",
                epigrafe_iae="763",
                local="Calle Mayor 1",
            ),
        ),
        "obligaciones_periodicas": ("303 trimestral", "130 trimestral"),
    }
    payload.update(overrides)
    return CertificadoSituacionCensal(**payload)
