"""Registered-executor conformance scenarios for recovery revocation and the censal certificate file.

The revocation proves the profile's own passphrase, which arrives on the
operation's one secret frame, and removes an enrollment the scenario made. The
certificate import runs the shipped parser, which refuses every document until
an issued specimen pins its layout, so its scenario is that refusal.
"""

from __future__ import annotations

from ...application.user_profile.censal_certificate_operation import (
    CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID,
    CENSAL_CERTIFICATE_PHASE_READ,
    CensalCertificateOperationRequest,
)
from ...application.user_profile.profile_record_repository import ProfileRecordRepository
from ...application.user_profile.recovery_custody import enroll_profile_recovery, profile_recovery_status
from ...application.user_profile.recovery_revoke_operation import (
    RECOVERY_REVOKE_OPERATION_DEFINITION_ID,
    RECOVERY_REVOKE_PHASE_CONSUME,
    RECOVERY_REVOKE_PHASE_EXECUTE,
    RECOVERY_REVOKE_PHASE_SETTLEMENT,
    RecoveryRevokeProjection,
    RecoveryRevokeRequest,
)
from ...core.errors.error_codes import get_registered_error_code
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.censo.certificado import CertificadoCensalParseError
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)


def _prepare_recovery_revoke(context: ConformanceFamilyContext) -> ConformancePreparation:
    enroll_profile_recovery(
        profile_id=context.profile_id,
        current_passphrase=context.profile_passphrase,
        recovery_handover=lambda enrollment: enrollment.recovery_key.code,
    )
    assert profile_recovery_status(profile_id=context.profile_id).enrolled is True

    def verify(outcome: ConformanceOutcome) -> None:
        assert profile_recovery_status(profile_id=outcome.profile_id).enrolled is False

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=RecoveryRevokeRequest(profile_id=context.profile_id),
        secret=context.profile_passphrase.encode("utf-8"),
        expected_result=RecoveryRevokeProjection(profile_id=context.profile_id, changed=True),
        verify=verify,
    )


def _prepare_censal_certificate(context: ConformanceFamilyContext) -> ConformancePreparation:
    certificate = context.input_root / "certificado-situacion-censal.pdf"
    certificate.write_bytes(b"%PDF-1.7 synthetic certificate no specimen pins")
    profile_id = str(context.profile_id)
    decode_context = context.operation.profile_decode_context()
    before = (
        ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode_context)
        .load(profile_id)
        .record_revision
    )

    def verify(outcome: ConformanceOutcome) -> None:
        parse_refusal = get_registered_error_code(CertificadoCensalParseError).code
        assert outcome.observed.projection.failure_error_code == parse_refusal
        after = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode_context).load(
            profile_id
        )
        assert after.record_revision == before

    return ConformancePreparation(
        subject_ref=profile_operation_subject(profile_id),
        request=CensalCertificateOperationRequest(profile_id=context.profile_id, certificate_path=certificate),
        verify=verify,
    )


_PREPARATIONS = {
    RECOVERY_REVOKE_OPERATION_DEFINITION_ID: _prepare_recovery_revoke,
    CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID: _prepare_censal_certificate,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    prepare = _PREPARATIONS.get(context.definition.definition_id)
    if prepare is None:
        raise AssertionError(f"no profile custody conformance scenario for {context.definition.definition_id}")
    return prepare(context)


PROFILE_CUSTODY_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            RECOVERY_REVOKE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (RECOVERY_REVOKE_PHASE_CONSUME, RECOVERY_REVOKE_PHASE_EXECUTE, RECOVERY_REVOKE_PHASE_SETTLEMENT),
        ),
        RegisteredExecutorConformanceCase(
            CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.FAILED,
            OperationEffect.NONE,
            (CENSAL_CERTIFICATE_PHASE_READ,),
        ),
    ),
    prepare=_prepare,
)
