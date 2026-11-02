"""Certificates recorded through the registered executor feed the real suffered-withholding source mesh.

The executor runs against the real encrypted repository, the real write port and
the pinned authority; only the operation host's event and operand plumbing is a
minimal stand-in. All identifiers and amounts are synthetic.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.profile.retencion_soportada_certificado import (
    RetencionSoportadaCertificadoRepositoryAdapter,
)
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.retencion_soportada_repository import (
    PinnedRetencionSoportadaWriteAuthority,
    RetencionSoportadaPorts,
)
from cadrumo.application.aggregation.retencion_soportada_source import RetencionSoportadaSourceResolver
from cadrumo.application.aggregation.source_mesh import CalculationSourceContext
from cadrumo.application.aggregation.source_resolution_operations import merge_source_resolutions
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.refusal_evidence import OperationRefusalEvidence
from cadrumo.application.retencion_soportada_certificado.contracts import (
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
)
from cadrumo.application.retencion_soportada_certificado.executor import RetencionSoportadaCertificadoExecutor
from cadrumo.application.retencion_soportada_certificado.ports import RetencionSoportadaCertificadoPorts
from cadrumo.application.retencion_soportada_certificado.requests import RetencionSoportadaRecordRequest
from cadrumo.application.tests.operation_host_fakes import RecordingEvents
from cadrumo.core.operations import profile_operation_subject
from cadrumo.core.period import Period
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector
from cadrumo.domain.renta.retencion_soportada import RetencionSoportadaOrigen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_PROFILE = "3f1c8b2e-5d4a-4e6b-9c7d-0a1b2c3d4e5f"
_TAXPAYER = "00000000T"
_EJERCICIO = 2025
_BINDING = "renta-retencion-soportada-trabajo"
_LEGAL_REFS = ("ley-35-2006:art-99", "rd-439-2007:art-108")
_SOURCE_REFS = ("aeat-modelo-100-instructions-2025",)


class _Cancellation:
    def __init__(self) -> None:
        self.inside = False

    @asynccontextmanager
    async def irreversible_section(self):
        self.inside = True
        try:
            yield
        finally:
            self.inside = False


class _Operands:
    def __init__(self, cancellation: _Cancellation) -> None:
        self._cancellation = cancellation
        self.value: BaseModel | None = None

    async def put(self, value: BaseModel, *, written_at: object) -> str:
        del written_at
        assert self._cancellation.inside
        self.value = value
        return "d" * 64


class _Context:
    def __init__(self, authority_operation: PinnedAuthorityOperation) -> None:
        self.identity = OperationIdentity(
            operation_id="c" * 64,
            definition_id=RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(_PROFILE),
        )
        self.authority_operation = authority_operation
        self.events = RecordingEvents()
        self.cancellation = _Cancellation()
        self.operands = _Operands(self.cancellation)


def _ports_factory(*, profile_id: UUID, operation: PinnedAuthorityOperation) -> RetencionSoportadaCertificadoPorts:
    del profile_id
    return RetencionSoportadaCertificadoPorts(
        repository=RetencionSoportadaCertificadoRepositoryAdapter(objects=secure_object_repository_for_active_bucket()),
        authority=PinnedRetencionSoportadaWriteAuthority(operation),
        taxpayer_tax_id=lambda: _TAXPAYER,
    )


def _request(
    payer: str, *, retencion: str, ingreso: str = "0.00", repercutido: str = "0.00"
) -> OperationRequest[BaseModel]:
    return OperationRequest(
        definition_id=RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(_PROFILE),
        payload=RetencionSoportadaRecordRequest(
            profile_id=UUID(_PROFILE),
            ejercicio=_EJERCICIO,
            income_class=RetencionSoportadaClase.TRABAJO,
            payer_tax_id=payer,
            importe_integro_dinerario=PublicDecimal(decimal="20000.00"),
            valoracion_especie=PublicDecimal(decimal="0.00"),
            retencion=PublicDecimal(decimal=retencion),
            ingreso_a_cuenta=PublicDecimal(decimal=ingreso),
            ingreso_a_cuenta_repercutido=PublicDecimal(decimal=repercutido),
            origin=RetencionSoportadaOrigen.PAYER_CERTIFICATE,
            evidence_fingerprint="a" * 64,
        ),
    )


def _run(authority_operation: PinnedAuthorityOperation, request: OperationRequest[BaseModel]) -> object:
    context = _Context(authority_operation)
    executor = RetencionSoportadaCertificadoExecutor(
        _ports_factory, definition_id=RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID
    )
    return asyncio.run(executor.execute(request, cast(OperationExecutorContext, context)))


def test_recorded_certificates_resolve_to_the_hand_summed_class_credit(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE):
        # Payer A: 1.200,00 retención + 300,00 ingreso a cuenta (repercutido, still credited); payer B: 450,00.
        for request in (
            _request("B00000001", retencion="1200.00", ingreso="300.00", repercutido="300.00"),
            _request("B00000002", retencion="450.00"),
        ):
            assert not isinstance(_run(operation, request), OperationRefusalEvidence)
        own = _run(operation, _request(_TAXPAYER, retencion="10.00"))
        assert isinstance(own, OperationRefusalEvidence)

        revision = ModeloRevision(
            id="2025-retencion-soportada-test",
            localization_key="test.schema.revision.2025-retencion-soportada-test.label",
            valid_from=date(2025, 1, 1),
            period_selector=PeriodSelector(years=(_EJERCICIO,), periods=("0A",)),
            legal_refs=_LEGAL_REFS,
            source_refs=_SOURCE_REFS,
            bindings=(
                BindingDefinition(
                    id=_BINDING,
                    provider={"kind": "retencion_soportada", "income_class": "trabajo", "quantity": "pago_a_cuenta"},
                    value={"data_type": "money", "channel": "decimal"},
                    legal_refs=_LEGAL_REFS,
                    source_refs=_SOURCE_REFS,
                ),
            ),
        )
        repository = RetencionSoportadaCertificadoRepositoryAdapter(
            objects=secure_object_repository_for_active_bucket()
        )
        resolver = RetencionSoportadaSourceResolver(ports=RetencionSoportadaPorts(repository=repository))
        resolution = merge_source_resolutions(
            (
                resolver.resolve(
                    CalculationSourceContext(
                        bucket_id="operator",
                        modelo="100",
                        filing_year=_EJERCICIO,
                        period=Period.from_year_and_code(_EJERCICIO, "0A"),
                        revision=revision,
                    )
                ),
            )
        )
        stored = repository.list_revisioned(_EJERCICIO)

    assert resolution.binding_values == {_BINDING: Decimal("1950.00")}
    assert len(stored) == 2
    assert all(revision_id != ABSENT_SECURE_OBJECT_REVISION_ID for _record, revision_id in stored)
