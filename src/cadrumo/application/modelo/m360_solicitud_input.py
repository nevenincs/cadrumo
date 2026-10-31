"""Declarative public input for Modelo 360; governed codes resolve in the worker."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core.country_code import CountryCodeAlpha2
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..filing.producer_snapshot_m360 import (
    M360AmbitoEstablecimiento,
    Modelo360ApartadoCorreos,
    Modelo360DomicilioEspana,
    Modelo360ProfileFacts,
    Modelo360RepresentanteFacts,
)


class Modelo360SolicitudHeaderInput(BaseModel):
    """Entered header, with form codes checked against the pinned authority on use."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    nivel_calidad_datos: str = Field(min_length=1)
    pais_destino: CountryCodeAlpha2
    causa_presentacion: str = Field(min_length=1)
    numero_registro_declaracion_anterior: str | None = None
    comunicacion_prorrata_definitiva: bool | None = None
    presentacion_en_pruebas: bool | None = None


class Modelo360EstablecimientoInput(BaseModel):
    """Entered establishment and its optional governed territorial codes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    ambito: M360AmbitoEstablecimiento
    hacienda_foral: str | None = None
    delegacion_canarias_ceuta_melilla: str | None = None


class Modelo360SolicitanteInput(BaseModel):
    """Contact and establishment supplied for the solicitud."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    email: str
    establecimiento: Modelo360EstablecimientoInput
    phone: str | None = None
    domicilio: Modelo360DomicilioEspana | None = None
    apartado_correos: Modelo360ApartadoCorreos | None = None


class Modelo360CuentaTitularInput(BaseModel):
    """Entered holder facts; the governed holder code resolves on use."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    titular_nombre: str
    titular_en_calidad_de: str = Field(min_length=1)
    divisa: str


class Modelo360ProfileInput(BaseModel):
    """Public facts input, independent of authority-backed persistence serializers."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    solicitud: Modelo360SolicitudHeaderInput
    solicitante: Modelo360SolicitanteInput
    cuenta: Modelo360CuentaTitularInput
    representante: Modelo360RepresentanteFacts | None = None

    def to_facts(self) -> Modelo360ProfileFacts:
        """Validate every entered fact under the worker's retained authority scope."""
        return Modelo360ProfileFacts.model_validate(self.model_dump())


__all__ = [
    "Modelo360CuentaTitularInput",
    "Modelo360EstablecimientoInput",
    "Modelo360ProfileInput",
    "Modelo360SolicitanteInput",
    "Modelo360SolicitudHeaderInput",
]
