"""Canonical application projection of one read-only AEAT censal observation."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

_STRICT_VALIDATED_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class CensalObservationIdentity(BaseModel):
    """Exact identity group observed on the censal consulta surface."""

    model_config = _STRICT_VALIDATED_FROZEN

    nif: str | None = Field(default=None, max_length=32)
    apellidos_y_nombre: str | None = Field(default=None, max_length=256)
    administracion_domicilio_fiscal: str | None = Field(default=None, max_length=128)
    lugar_nacimiento: str | None = Field(default=None, max_length=128)
    fecha_nacimiento: date | None = None
    pasaporte: str | None = Field(default=None, max_length=64)
    sexo: str | None = Field(default=None, max_length=32)
    nacionalidad: str | None = Field(default=None, max_length=64)
    estado_civil: str | None = Field(default=None, max_length=64)
    obligado_notificaciones_electronicas: bool | None = None
    suscrito_voluntariamente_notificaciones_electronicas: bool | None = None


class CensalObservationAddress(BaseModel):
    """Exact fiscal or notification address group in a censal observation."""

    model_config = _STRICT_VALIDATED_FROZEN

    tipo_via: str | None = Field(default=None, max_length=32)
    nombre_via: str | None = Field(default=None, max_length=128)
    tipo_numero: str | None = Field(default=None, max_length=32)
    numero_casa: str | None = Field(default=None, max_length=32)
    calificacion_numero: str | None = Field(default=None, max_length=32)
    bloque: str | None = Field(default=None, max_length=32)
    portal: str | None = Field(default=None, max_length=32)
    escalera: str | None = Field(default=None, max_length=32)
    planta: str | None = Field(default=None, max_length=32)
    puerta: str | None = Field(default=None, max_length=32)
    complemento: str | None = Field(default=None, max_length=128)
    localidad: str | None = Field(default=None, max_length=128)
    referencia_catastral: str | None = Field(default=None, max_length=32)
    indicador_referencia_catastral: str | None = Field(default=None, max_length=256)
    codigo_postal: str | None = Field(default=None, max_length=16)
    municipio: str | None = Field(default=None, max_length=128)
    provincia: str | None = Field(default=None, max_length=64)
    destinatario: str | None = Field(default=None, max_length=256)
    en_calidad_de: str | None = Field(default=None, max_length=128)


class CensalObservation(BaseModel):
    """One exact, immutable read of the taxpayer's censal consulta."""

    model_config = _STRICT_VALIDATED_FROZEN

    identity: CensalObservationIdentity
    domicilio_fiscal: CensalObservationAddress
    domicilio_notificacion: CensalObservationAddress
    captured_at: datetime
    source_url: AnyHttpUrl
    mode: Literal["read"] = "read"


__all__ = ["CensalObservation", "CensalObservationAddress", "CensalObservationIdentity"]
