"""Record a Modelo 100 work income the way an operator does: as the payer's certificate.

The casillas of the gross, in-kind, reduction and expense figures of work income are bound to the
stored payer records of income class ``trabajo``, so a caller cannot type them. A scenario that
needs them seeds one certificate through the production write port. Four more boxes, the
employer's contributions and the protected-estate contribution, are in no certificate: the filer
states each, here as a typed zero.
"""

from __future__ import annotations

from decimal import Decimal

from ....adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.ids import BindingId

__all__ = ["UNSTATED_WORK_INCOME_AS_ZERO", "record_work_income"]

#: The four income boxes no payer certificate states (0008, 0009, 0010, 0024), each typed as zero.
UNSTATED_WORK_INCOME_AS_ZERO: dict[BindingId, Decimal] = {
    "renta-trabajo-contribucion-empresarial-prevision": Decimal("0"),
    "renta-trabajo-contribucion-empresarial-seguro-dependencia": Decimal("0"),
    "renta-trabajo-aportacion-patrimonio-protegido": Decimal("0"),
    "renta-trabajo-aportacion-empresa-decision-trabajador": Decimal("0"),
}


def record_work_income(
    *,
    operation: PinnedAuthorityOperation,
    taxpayer_tax_id: str,
    filing_year: int,
    gross: Decimal,
    retencion: Decimal = Decimal("0.00"),
    in_kind: Decimal = Decimal("0.00"),
    ingreso_a_cuenta: Decimal = Decimal("0.00"),
    ingreso_a_cuenta_repercutido: Decimal = Decimal("0.00"),
    reductions: Decimal = Decimal("0.00"),
    expenses: Decimal = Decimal("0.00"),
    payer_tax_id: str = "B00000001",
) -> None:
    """Store one synthetic payer certificate of work income in the active bucket."""
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id=taxpayer_tax_id,
        ejercicio=filing_year,
        payer_tax_id=payer_tax_id,
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=retencion,
        importe_integro_dinerario=gross,
        valoracion_especie=in_kind,
        ingreso_a_cuenta=ingreso_a_cuenta,
        ingreso_a_cuenta_repercutido=ingreso_a_cuenta_repercutido,
        reducciones_aplicables=reductions,
        gastos_deducibles=expenses,
    )
