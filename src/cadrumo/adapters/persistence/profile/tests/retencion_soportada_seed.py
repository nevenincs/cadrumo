"""Seed suffered-withholding payer records through the real write port, for tests.

A record is written exactly as an operator's certificate would be: the active
bucket's encrypted store computes the keyed payer reference, and the pinned
authority's write refusals (own tax id, unsupported ejercicio, undeclared
family) all apply. All identifiers and amounts a caller passes are synthetic.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from .....application.aggregation.retencion_soportada_repository import (
    PinnedRetencionSoportadaWriteAuthority,
    record_retencion_soportada,
)
from .....core.retencion_soportada import RetencionSoportadaClase
from .....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from ...storage.runtime_repository import secure_object_repository_for_active_bucket
from ..retencion_soportada_records import RetencionSoportadaRecordRepositoryAdapter

__all__ = ["seed_payer_certificate"]

_CAPTURED_AT = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)


def seed_payer_certificate(
    *,
    operation: PinnedAuthorityOperation,
    taxpayer_tax_id: str,
    ejercicio: int,
    payer_tax_id: str,
    income_class: RetencionSoportadaClase,
    retencion: Decimal,
    ingreso_a_cuenta: Decimal = Decimal("0.00"),
    ingreso_a_cuenta_repercutido: Decimal = Decimal("0.00"),
    importe_integro_dinerario: Decimal = Decimal("0.00"),
    valoracion_especie: Decimal = Decimal("0.00"),
) -> RetencionSoportadaRecord:
    """Store one payer certificate record in the active bucket and return it."""
    repository = RetencionSoportadaRecordRepositoryAdapter(objects=secure_object_repository_for_active_bucket())
    payer_ref = repository.payer_reference(payer_tax_id)
    record = RetencionSoportadaRecord(
        ejercicio=ejercicio,
        payer_tax_id=payer_tax_id,
        payer_legal_name="Pagador Sintetico SL",
        payer_ref=payer_ref,
        income_class=income_class,
        importe_integro_dinerario=importe_integro_dinerario,
        valoracion_especie=valoracion_especie,
        retencion=retencion,
        ingreso_a_cuenta=ingreso_a_cuenta,
        ingreso_a_cuenta_repercutido=ingreso_a_cuenta_repercutido,
        origin=RetencionSoportadaOrigen.PAYER_CERTIFICATE,
        # The sha256 of a synthetic certificate's bytes, one certificate per payer, class and ejercicio.
        evidence_fingerprint=hashlib.sha256(
            f"synthetic certificate {payer_tax_id} {income_class.value} {ejercicio}".encode(),
        ).hexdigest(),
        captured_at=_CAPTURED_AT,
    )
    record_retencion_soportada(
        record,
        repository=repository,
        authority=PinnedRetencionSoportadaWriteAuthority(operation),
        taxpayer_tax_id=taxpayer_tax_id,
        expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
    )
    return record
