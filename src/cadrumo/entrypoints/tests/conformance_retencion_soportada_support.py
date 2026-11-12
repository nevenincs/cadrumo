"""Suffered-withholding certificate operations through the real supervisor matrix."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

from ...application.aggregation.retencion_soportada_repository import record_retencion_soportada
from ...application.operations.public_scalar import PublicDecimal
from ...application.retencion_soportada_certificado.contracts import (
    RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID,
)
from ...application.retencion_soportada_certificado.requests import (
    RetencionSoportadaListRequest,
    RetencionSoportadaRecordRequest,
    RetencionSoportadaRemoveRequest,
)
from ...application.retencion_soportada_certificado.results import (
    RetencionSoportadaListProjection,
    RetencionSoportadaMutationProjection,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.retencion_soportada import RetencionSoportadaClase
from ...core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ...domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from ..retencion_soportada_certificado_composition import build_retencion_soportada_certificado_ports
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_EJERCICIO = 2025
_CERTIFICATE_BYTES = b"%PDF-1.4 synthetic payer certificate"
_CAPTURED_AT = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_PAYER = "B00010090"
_SEEDING_TAXPAYER = "00000000T"


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    definition_id = context.definition.definition_id
    subject = profile_operation_subject(str(context.profile_id))
    ports = build_retencion_soportada_certificado_ports(profile_id=context.profile_id, operation=context.operation)
    repository = ports.repository

    def seed() -> tuple[RetencionSoportadaRecord, str]:
        record = RetencionSoportadaRecord(
            ejercicio=_EJERCICIO,
            payer_tax_id=_PAYER,
            payer_ref=repository.payer_reference(_PAYER),
            income_class=RetencionSoportadaClase.TRABAJO,
            importe_integro_dinerario=Decimal("20000.00"),
            valoracion_especie=Decimal("0.00"),
            retencion=Decimal("1200.00"),
            ingreso_a_cuenta=Decimal("300.00"),
            ingreso_a_cuenta_repercutido=Decimal("300.00"),
            reducciones_aplicables=Decimal("0.00"),
            gastos_deducibles=Decimal("0.00"),
            origin=RetencionSoportadaOrigen.PAYER_CERTIFICATE,
            evidence_fingerprint=ports.custody.ingest(
                source_path=context.input_root / "certificate.pdf",
                data=_CERTIFICATE_BYTES,
                mime_type="application/pdf",
                captured_at=_CAPTURED_AT,
            ),
            captured_at=_CAPTURED_AT,
        )
        record_retencion_soportada(
            record,
            repository=repository,
            authority=ports.authority,
            custody=ports.custody,
            taxpayer_tax_id=_SEEDING_TAXPAYER,
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
        return record, repository.load_revisioned(record.identity)[1]

    if definition_id == RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID:
        seeded, revision_id = seed()

        def verify_list(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(RetencionSoportadaListProjection)
            assert result.profile_id == context.profile_id
            (row,) = result.rows
            assert row.payer_ref == seeded.payer_ref
            assert row.revision_id == revision_id
            assert row.income_class_label.strip()
            assert row.pago_a_cuenta.decimal == "1500.00"
            assert row.origin_label.strip()
            assert row.payer_display_name.strip()
            assert result.ejercicios == tuple(sorted(context.operation.supported_filing_years().years))
            assert [column.field.value for column in result.amount_columns][-1] == "pago_a_cuenta"
            assert repository.list_revisioned(_EJERCICIO) == ((seeded, revision_id),)

        return ConformancePreparation(
            subject,
            RetencionSoportadaListRequest(profile_id=context.profile_id, ejercicio=_EJERCICIO),
            verify=verify_list,
        )

    if definition_id == RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID:
        # The certificate is a file the worker reads and keeps in custody; its sha256 is the stored fingerprint.
        (context.input_root / "certificate.pdf").write_bytes(_CERTIFICATE_BYTES)

        def verify_record(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(RetencionSoportadaMutationProjection)
            assert result.outcome == "recorded"
            assert result.count == 1
            assert result.row is not None
            ((stored, revision_id),) = repository.list_revisioned(_EJERCICIO)
            assert stored.pago_a_cuenta == Decimal("1500.00")
            assert stored.evidence_fingerprint == sha256(_CERTIFICATE_BYTES).hexdigest()
            assert ports.custody.holds(stored.evidence_fingerprint)
            assert result.row.revision_id == revision_id
            assert result.row.payer_ref == stored.payer_ref

        return ConformancePreparation(
            subject,
            RetencionSoportadaRecordRequest(
                profile_id=context.profile_id,
                ejercicio=_EJERCICIO,
                income_class=RetencionSoportadaClase.TRABAJO,
                payer_tax_id=_PAYER,
                importe_integro_dinerario=PublicDecimal(decimal="20000.00"),
                valoracion_especie=PublicDecimal(decimal="0.00"),
                retencion=PublicDecimal(decimal="1200.00"),
                ingreso_a_cuenta=PublicDecimal(decimal="300.00"),
                ingreso_a_cuenta_repercutido=PublicDecimal(decimal="300.00"),
                # A work-income certificate states the reductions and deductible expenses the payer applied.
                reducciones_aplicables=PublicDecimal(decimal="0.00"),
                gastos_deducibles=PublicDecimal(decimal="0.00"),
                origin=RetencionSoportadaOrigen.PAYER_CERTIFICATE,
                source_path="certificate.pdf",
                source_directory=str(context.input_root),
            ),
            verify=verify_record,
        )

    if definition_id == RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID:
        seeded, revision_id = seed()

        def verify_remove(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(RetencionSoportadaMutationProjection)
            assert result.outcome == "removed"
            assert result.count == 0
            assert result.row is None
            assert repository.list_revisioned(_EJERCICIO) == ()

        return ConformancePreparation(
            subject,
            RetencionSoportadaRemoveRequest(
                profile_id=context.profile_id,
                ejercicio=_EJERCICIO,
                income_class=seeded.income_class,
                payer_ref=seeded.payer_ref,
                expected_revision_id=revision_id,
            ),
            verify=verify_remove,
        )

    raise AssertionError(f"unsupported suffered-withholding conformance definition: {definition_id}")


RETENCION_SOPORTADA_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
        ),
        RegisteredExecutorConformanceCase(
            RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
        ),
        RegisteredExecutorConformanceCase(
            RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
        ),
    ),
    prepare=_prepare,
)
