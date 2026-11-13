"""Pension contribution certificate operations through the real supervisor matrix."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

from ...application.aggregation.prevision_social_contribution_repository import (
    record_prevision_social_contribution,
)
from ...application.operations.public_scalar import PublicDecimal
from ...application.prevision_social_contribution.contracts import (
    PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID,
)
from ...application.prevision_social_contribution.ports import PrevisionSocialPorts
from ...application.prevision_social_contribution.requests import (
    PrevisionSocialListRequest,
    PrevisionSocialRecordRequest,
    PrevisionSocialRemoveRequest,
)
from ...application.prevision_social_contribution.results import (
    PrevisionSocialListProjection,
    PrevisionSocialMutationProjection,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.prevision_social import PrevisionSocialBeneficiario, PrevisionSocialClave, PrevisionSocialSubclave
from ...core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ...domain.renta.prevision_social_contribution import PrevisionSocialContribution
from ..prevision_social_contribution_composition import build_prevision_social_contribution_ports
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_CERTIFICATE_BYTES = b"%PDF-1.4 synthetic pension contribution certificate"
_ISSUER = "V00010082"
_PLAN = "V00010090"


def _seed(
    context: ConformanceFamilyContext, ports: PrevisionSocialPorts, ejercicio: int
) -> tuple[PrevisionSocialContribution, str]:
    repository = ports.repository
    captured_at = datetime.now(UTC)
    record = PrevisionSocialContribution(
        ejercicio=ejercicio,
        issuer_tax_id=_ISSUER,
        issuer_ref=repository.issuer_reference(_ISSUER),
        plan_tax_id=_PLAN,
        plan_ref=repository.plan_reference(_PLAN),
        clave=PrevisionSocialClave.CLAVE_A,
        subclave=PrevisionSocialSubclave.SUBCLAVE_01,
        amount=Decimal("1000.00"),
        beneficiary=PrevisionSocialBeneficiario.TAXPAYER,
        evidence_fingerprint=ports.custody.ingest(
            source_path=context.input_root / "certificate.pdf",
            data=_CERTIFICATE_BYTES,
            mime_type="application/pdf",
            captured_at=captured_at,
        ),
        captured_at=captured_at,
    )
    record_prevision_social_contribution(
        record,
        repository=repository,
        authority=ports.authority,
        custody=ports.custody,
        expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
    )
    return record, repository.load_revisioned(record.identity)[1]


def _prepare_list(
    context: ConformanceFamilyContext, ports: PrevisionSocialPorts, ejercicio: int
) -> ConformancePreparation:
    seeded, revision_id = _seed(context, ports, ejercicio)

    def verify_list(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(PrevisionSocialListProjection)
        assert result.profile_id == context.profile_id
        (row,) = result.rows
        assert row.issuer_ref == seeded.issuer_ref
        assert row.revision_id == revision_id
        assert row.casilla_id is not None
        assert result.ejercicios == tuple(sorted(context.operation.supported_filing_years().years))

    return ConformancePreparation(
        profile_operation_subject(str(context.profile_id)),
        PrevisionSocialListRequest(profile_id=context.profile_id, ejercicio=ejercicio),
        verify=verify_list,
    )


def _prepare_record(
    context: ConformanceFamilyContext, ports: PrevisionSocialPorts, ejercicio: int
) -> ConformancePreparation:
    # The certificate is a file the worker reads and keeps in custody; its sha256 is the stored fingerprint.
    (context.input_root / "certificate.pdf").write_bytes(_CERTIFICATE_BYTES)

    def verify_record(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(PrevisionSocialMutationProjection)
        assert result.outcome == "recorded"
        assert result.count == 1
        assert result.row is not None
        ((stored, revision_id),) = ports.repository.list_revisioned(ejercicio)
        assert stored.amount == Decimal("1000.00")
        assert stored.evidence_fingerprint == sha256(_CERTIFICATE_BYTES).hexdigest()
        assert ports.custody.holds(stored.evidence_fingerprint)
        assert result.row.revision_id == revision_id

    return ConformancePreparation(
        profile_operation_subject(str(context.profile_id)),
        PrevisionSocialRecordRequest(
            profile_id=context.profile_id,
            ejercicio=ejercicio,
            issuer_tax_id=_ISSUER,
            plan_tax_id=_PLAN,
            clave=PrevisionSocialClave.CLAVE_A,
            subclave=PrevisionSocialSubclave.SUBCLAVE_01,
            amount=PublicDecimal(decimal="1000.00"),
            source_path="certificate.pdf",
            source_directory=str(context.input_root),
        ),
        verify=verify_record,
    )


def _prepare_remove(
    context: ConformanceFamilyContext, ports: PrevisionSocialPorts, ejercicio: int
) -> ConformancePreparation:
    seeded, revision_id = _seed(context, ports, ejercicio)

    def verify_remove(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(PrevisionSocialMutationProjection)
        assert result.outcome == "removed"
        assert result.count == 0
        assert ports.repository.list_revisioned(ejercicio) == ()

    return ConformancePreparation(
        profile_operation_subject(str(context.profile_id)),
        PrevisionSocialRemoveRequest(
            profile_id=context.profile_id,
            ejercicio=ejercicio,
            issuer_ref=seeded.issuer_ref,
            plan_ref=seeded.plan_ref,
            clave=seeded.clave,
            subclave=seeded.subclave,
            expected_revision_id=revision_id,
        ),
        verify=verify_remove,
    )


_PREPARERS = {
    PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID: _prepare_list,
    PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID: _prepare_record,
    PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID: _prepare_remove,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    ports = build_prevision_social_contribution_ports(profile_id=context.profile_id, operation=context.operation)
    ejercicio = min(context.operation.supported_filing_years().years)
    return _PREPARERS[context.definition.definition_id](context, ports, ejercicio)


PREVISION_SOCIAL_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
        ),
        RegisteredExecutorConformanceCase(
            PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
        ),
        RegisteredExecutorConformanceCase(
            PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
        ),
    ),
    prepare=_prepare,
)
