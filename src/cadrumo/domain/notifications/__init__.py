"""Canonical domain readings for notification documents.

The inbound notification adapter parses external document bytes, but the
typed reading is an application/domain fact that can be persisted and
consumed without depending on that adapter.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.identity import AeatCertificadoId, AeatClaveLiquidacion

_ZERO = Decimal("0.00")


class SancionLiquidacion(BaseModel):
    """The typed reading of one AEAT sanción / liquidación document.

    Every field is a figure printed on the document. Nothing here is derived,
    defaulted or inferred: an absent reducción is ``None``, never ``0``, so a
    reducción AEAT did not grant is distinguishable from one it granted at
    zero.
    """

    model_config = STRICT_FROZEN_CONFIG

    certificado_id: AeatCertificadoId
    clave_liquidacion: AeatClaveLiquidacion
    referencia: str = Field(min_length=1, max_length=64)
    nif: str = Field(min_length=8, max_length=16)
    objeto_tributario: Literal["sancion", "liquidacion"]
    base_sancion: Decimal
    porcentaje_minimo: Decimal
    sancion_resultante: Decimal
    reduccion_conformidad: Decimal | None = None
    reduccion_pronto_pago: Decimal | None = None
    diferencia: Decimal | None = None
    importe_a_ingresar: Decimal
    document_sha256: str = Field(min_length=64, max_length=64)
    mode: Literal["read"] = "read"

    @property
    def reducciones_total(self) -> Decimal:
        """Return the sum of every reducción the document actually printed."""
        return (self.reduccion_conformidad or _ZERO) + (self.reduccion_pronto_pago or _ZERO)


__all__ = ["SancionLiquidacion"]
