"""Seed suffered-withholding payer records through the real write port, for tests.

A record is written exactly as an operator's certificate would be: the active
bucket's encrypted store computes the keyed payer reference, and the pinned
authority's write refusals (own tax id, unsupported ejercicio, undeclared
family) all apply. All identifiers and amounts a caller passes are synthetic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from .....application.aggregation.retencion_soportada_absence_repository import (
    RetencionSoportadaAbsenceWritePorts,
    attest_retencion_soportada_absence,
)
from .....application.aggregation.retencion_soportada_repository import (
    PinnedRetencionSoportadaWriteAuthority,
    record_retencion_soportada,
)
from .....core.bucket_pointer import require_active_bucket_id
from .....core.identity.bucket import canonical_bucket_id
from .....core.retencion_soportada import RetencionSoportadaClase
from .....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from .....domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence
from ...storage.attachment import AttachmentStore
from ...storage.runtime_repository import secure_object_repository_for_active_bucket
from ..retencion_soportada_evidence_custody import RetencionSoportadaEvidenceCustodyAdapter
from ..retencion_soportada_records import (
    RetencionSoportadaAbsenceRepositoryAdapter,
    RetencionSoportadaRecordRepositoryAdapter,
)

_YEAR = filing_year_envelope().horizon

__all__ = ["active_bucket_custody", "keep_certificate", "seed_absence_attestation", "seed_payer_certificate"]

_CAPTURED_AT = datetime(_YEAR, 4, 2, 9, 0, tzinfo=UTC)


def active_bucket_custody() -> RetencionSoportadaEvidenceCustodyAdapter:
    """Return the active bucket's real attachment custody, as the certificate operations compose it."""
    bucket_id = canonical_bucket_id(require_active_bucket_id())
    return RetencionSoportadaEvidenceCustodyAdapter(
        store=AttachmentStore(bucket_id=bucket_id, objects=secure_object_repository_for_active_bucket()),
        bucket_id=bucket_id,
    )


def keep_certificate(data: bytes) -> str:
    """Keep synthetic certificate bytes in the active bucket's custody and return their sha256."""
    return active_bucket_custody().ingest(
        source_path=Path("synthetic-certificate.pdf"),
        data=data,
        mime_type="application/pdf",
        captured_at=_CAPTURED_AT,
    )


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
        # The sha256 of a synthetic certificate's bytes, kept in custody: one certificate per payer, class and ejercicio.
        evidence_fingerprint=keep_certificate(
            f"synthetic certificate {payer_tax_id} {income_class.value} {ejercicio}".encode(),
        ),
        captured_at=_CAPTURED_AT,
    )
    record_retencion_soportada(
        record,
        repository=repository,
        authority=PinnedRetencionSoportadaWriteAuthority(operation),
        custody=active_bucket_custody(),
        taxpayer_tax_id=taxpayer_tax_id,
        expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
    )
    return record


def seed_absence_attestation(
    *,
    operation: PinnedAuthorityOperation,
    ejercicio: int,
    income_class: RetencionSoportadaClase,
) -> RetencionSoportadaAbsence:
    """Attest in the active bucket that no payer withheld on one income class, and return the attestation."""
    objects = secure_object_repository_for_active_bucket()
    attestation = RetencionSoportadaAbsence(
        ejercicio=ejercicio,
        income_class=income_class,
        note="Synthetic note: no payer withheld on this income.",
        attested_at=_CAPTURED_AT,
    )
    attest_retencion_soportada_absence(
        attestation,
        ports=RetencionSoportadaAbsenceWritePorts(
            attestations=RetencionSoportadaAbsenceRepositoryAdapter(objects=objects),
            records=RetencionSoportadaRecordRepositoryAdapter(objects=objects),
            authority=PinnedRetencionSoportadaWriteAuthority(operation),
        ),
        expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
    )
    return attestation
