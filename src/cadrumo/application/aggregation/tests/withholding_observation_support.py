"""Withholding observation shared by the percepciones and resolver suites."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cadrumo.tests.withholding_zero_blocks import zeroed_withholding_blocks

from ....core.aggregation import (
    RetencionClave,
)
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation


def perceptor_observation(nif: str, clave: RetencionClave) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=f"row-{nif}-{clave}",
        perceptor_tax_id=nif,
        transaction_date=date(filing_year_envelope().horizon, 6, 1),
        clave=clave,
        percibido_dinerario=Decimal("1000"),
        retencion_practicada=Decimal("190"),
        **zeroed_withholding_blocks(),
        base_retenciones=Decimal("0"),
    )
