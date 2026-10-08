"""Typed ``--json`` payload schemas for the ``app modelo m360`` solicitud commands.

A solicitud appears by its filing year, destination, holder and account kind;
an own account by its opaque ``own_account_id`` and a representante account by
its mask. No IBAN, BIC, name, address or tax identifier appears in any output.

Core types: :class:`~cadrumo.core.json_contract.OutputSchema`.
"""

from __future__ import annotations

from ...application.modelo.m360_solicitud_operation import Modelo360SolicitudProjection
from ...core.json_contract import OutputSchema
from ...core.text_bounds import NonEmptyStr


class Modelo360SolicitudPayload(OutputSchema):
    """Masked view of one declared solicitud."""

    filing_year: int
    pais_destino: NonEmptyStr
    causa_presentacion: NonEmptyStr
    titular_en_calidad_de: NonEmptyStr
    has_representante: bool
    account_kind: str | None = None
    own_account_id: str | None = None
    masked_iban: str | None = None

    @classmethod
    def from_projection(cls, solicitud: Modelo360SolicitudProjection) -> Modelo360SolicitudPayload:
        """Copy the worker's masked projection onto the wire shape."""
        return cls(
            filing_year=solicitud.filing_year,
            pais_destino=solicitud.pais_destino,
            causa_presentacion=solicitud.causa_presentacion.value,
            titular_en_calidad_de=solicitud.titular_en_calidad_de.value,
            has_representante=solicitud.has_representante,
            account_kind=solicitud.account_kind,
            own_account_id=solicitud.own_account_id,
            masked_iban=solicitud.masked_iban,
        )


class Modelo360SolicitudListResult(OutputSchema):
    """Every declared solicitud."""

    solicitudes: tuple[Modelo360SolicitudPayload, ...]


class Modelo360SolicitudChangeResult(OutputSchema):
    """The outcome of one declaration or removal; ``changed`` is ``False`` when nothing differed."""

    filing_year: int
    changed: bool
    solicitudes: tuple[Modelo360SolicitudPayload, ...]


__all__ = ["Modelo360SolicitudChangeResult", "Modelo360SolicitudListResult", "Modelo360SolicitudPayload"]
