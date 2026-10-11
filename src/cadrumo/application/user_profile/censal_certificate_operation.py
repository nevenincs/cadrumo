"""Preview or enrol the facts a censal certificate file certifies, reading the file in the operation.

``config profile censo import`` parses the certificate in its own process and
submits the facts it derived. A client that only submits operations has no
process to parse in, so this operation takes the file itself: it reads the
named file through one verified handle, parses those bytes, and either reports
what the certificate certifies or enrols its facts through the one cotejo apply
authority the fact-carrying operation uses.

Its public result has the members that command reports, with their real
values. The command applies its own output redaction when it prints.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.path_confinement import HostPathRefusal, opened_confined_file
from ...core.time.clock import now
from ...domain.censo.certificado import (
    CertificadoCensalParseError,
    CertificadoSituacionCensal,
    censo_facts_from_certificado,
)
from ...domain.user_profile.values import UserProfileFact
from ..operations.access_resolution import (
    COMMITTING_OPERATION_LIFECYCLE_ACTIONS,
    OPERATION_LIFECYCLE_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
)
from ..operations.capabilities import RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_terminal_receipt_match
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1, OperationReconciliationPolicy
from ..operations.subject_reference import OperationSubjectReferenceV1
from .access_contracts import AccessDenialCode, Availability
from .access_errors import ProfileAccessRefusedError
from .censal_access import bind_whole_profile_censal_access
from .censal_file_import_operation import (
    CensalFileImportFact,
    CensalFileImportOperationRequest,
    CensalFileImportProvenance,
    apply_censal_file_facts,
)

CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID = "user-profile.censo-certificate-import"
CENSAL_CERTIFICATE_PHASE_READ = "user-profile.censo-certificate-import.read"
CENSAL_CERTIFICATE_PHASE_APPLY = "user-profile.censo-certificate-import.apply"
CENSAL_CERTIFICATE_PHASE_RESULT = "user-profile.censo-certificate-import.result"

#: Largest certificate file the operation reads. An issued certificate is a
#: few pages; the ceiling only stops a mistaken path from being read whole.
MAX_CENSAL_CERTIFICATE_BYTES: Final[int] = 16 * 1024 * 1024

type CensalCertificateParser = Callable[[bytes], CertificadoSituacionCensal]
"""Parse certificate bytes, or raise ``CertificadoCensalParseError``."""


class CensalCertificateFactRow(BaseModel):
    """One fact a certificate projects onto, with its value in the text a command prints."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    path: str
    value: str
    source: str


class CensalCertificateIngest(BaseModel):
    """What one certificate certifies, the facts it projects onto, and whether they were enrolled."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    applied: bool
    certificate: CertificadoSituacionCensal
    facts: tuple[CensalCertificateFactRow, ...] = ()


@dataclass(frozen=True, slots=True)
class CensalCertificateReading:
    """One parsed certificate and the profile facts it projects onto."""

    certificate: CertificadoSituacionCensal
    profile_facts: tuple[UserProfileFact, ...]

    @property
    def facts(self) -> tuple[CensalCertificateFactRow, ...]:
        """Return the projected facts as rows.

        A projected fact holds its value in the profile's typed form, which
        for an epigraph is a number. A row carries the text form, and the
        profile restores the type when it adopts the fact.
        """
        return tuple(
            CensalCertificateFactRow(path=fact.path, value=str(fact.value), source=fact.source)
            for fact in self.profile_facts
        )

    def ingest(self, *, applied: bool) -> CensalCertificateIngest:
        """Return what a preview or an enrollment of this certificate answers with."""
        return CensalCertificateIngest(applied=applied, certificate=self.certificate, facts=self.facts)


def read_censal_certificate(data: bytes, *, parse: CensalCertificateParser) -> CensalCertificateReading:
    """Parse certificate bytes and project the facts a profile can adopt from them.

    Raises:
        CertificadoCensalParseError: The bytes are not a certificate the
            parser reads.
    """
    certificate = parse(data)
    return CensalCertificateReading(certificate=certificate, profile_facts=censo_facts_from_certificado(certificate))


class CensalCertificateOperationRequest(BaseModel):
    """The exact profile and the certificate file to read; ``preview`` enrolls nothing.

    ``certificate_path`` is absolute: the process that reads the file is not
    the one that named it.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    certificate_path: Path
    preview: bool = False


class CensalCertificateOperationResult(BaseModel):
    """The stored outcome: the exact profile and what was read from its certificate."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    ingest: CensalCertificateIngest


class CensalCertificateActivityProjection(BaseModel):
    """One certified activity row of a read certificate."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    descripcion: str
    epigrafe_iae: str
    local: str


class CensalCertificateProjection(BaseModel):
    """The six certified axes of a read certificate, as values a reader needs no authority to hold.

    The stored certificate checks its representatives' tax ids against the
    pinned authority. They were checked when the file was read, so the public
    form carries them as the text that was certified.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    domicilio_fiscal: str
    condicion_residencia: str
    representantes_nif: tuple[str, ...]
    situacion_tributaria: tuple[str, ...]
    actividades: tuple[CensalCertificateActivityProjection, ...]
    obligaciones_periodicas: tuple[str, ...]


class CensalCertificateOperationProjection(BaseModel):
    """The public outcome: the members ``config profile censo import`` reports, with their real values.

    The command hides what it hides when it prints. A result hides nothing.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    applied: bool
    certificate: CensalCertificateProjection
    facts: tuple[CensalCertificateFactRow, ...]


def _read_certificate_file(path: Path) -> bytes:
    """Read the named certificate through one verified handle, or refuse it by reason."""
    with opened_confined_file(path, max_bytes=MAX_CENSAL_CERTIFICATE_BYTES) as opened:
        content = opened if isinstance(opened, HostPathRefusal) else opened.read_bytes()
    if isinstance(content, HostPathRefusal):
        raise CertificadoCensalParseError(context={"reason": content.value})
    return content


def _enrollable_facts(reading: CensalCertificateReading, *, profile_id: UUID) -> tuple[CensalFileImportFact, ...]:
    """Hold the read facts to the contract facts supplied by a caller have to meet."""
    facts = tuple(
        CensalFileImportFact(path=row.path, value=row.value, source=CensalFileImportProvenance(row.source))
        for row in reading.facts
    )
    return CensalFileImportOperationRequest(profile_id=profile_id, facts=facts).facts


class CensalCertificateOperationExecutor:
    """Read the named certificate, then report its facts or commit them under COMMIT authority."""

    def __init__(self, parse_certificate: CensalCertificateParser) -> None:
        """Bind the certificate parser of the composing host."""
        self._parse_certificate = parse_certificate

    def _read(self, payload: CensalCertificateOperationRequest) -> CensalCertificateReading:
        reading = read_censal_certificate(
            _read_certificate_file(payload.certificate_path), parse=self._parse_certificate
        )
        _enrollable_facts(reading, profile_id=payload.profile_id)
        return reading

    async def execute(
        self, request: OperationRequest[CensalCertificateOperationRequest], context: OperationExecutorContext
    ) -> str:
        """Read the file, then store the preview or apply the facts and store the receipt."""
        payload = request.payload
        if (
            type(payload) is not CensalCertificateOperationRequest
            or request.definition_id != CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)

        await context.events.phase(CENSAL_CERTIFICATE_PHASE_READ)
        reading = await asyncio.to_thread(self._read, payload)

        if payload.preview:
            await context.events.effect(OperationEffect.NONE)
            await context.events.phase(CENSAL_CERTIFICATE_PHASE_RESULT)
            preview = CensalCertificateOperationResult(
                profile_id=payload.profile_id, ingest=reading.ingest(applied=False)
            )
            return await context.operands.put(preview, written_at=now())

        await context.events.phase(CENSAL_CERTIFICATE_PHASE_APPLY)
        profile_decode_context = context.authority_operation.profile_decode_context()
        facts = _enrollable_facts(reading, profile_id=payload.profile_id)

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                await asyncio.to_thread(
                    apply_censal_file_facts,
                    profile_id=str(payload.profile_id),
                    facts=facts,
                    profile_decode_context=profile_decode_context,
                )
                await context.events.effect(OperationEffect.UPDATED)
                await context.events.phase(CENSAL_CERTIFICATE_PHASE_RESULT)
                enrolled = CensalCertificateOperationResult(
                    profile_id=payload.profile_id, ingest=reading.ingest(applied=True)
                )
                return await context.operands.put(enrolled, written_at=now())

        return await await_cancellation_complete(commit(), task_name="censal-certificate-operation")


def resolve_censal_certificate_operation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve whole-profile access: a preview reads, an enrollment declares its COMMIT action."""
    payload = require_access_request_profile_payload(
        request,
        definition_id=CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID,
        payload_type=CensalCertificateOperationRequest,
        access_profile_id=context.profile_id,
    )
    return bind_whole_profile_censal_access(
        request,
        context,
        actions=OPERATION_LIFECYCLE_ACTIONS if payload.preview else COMMITTING_OPERATION_LIFECYCLE_ACTIONS,
        provider=Availability.NOT_REQUIRED,
    )


def project_censal_certificate_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CensalCertificateOperationProjection:
    """Release the result only against the successful receipt of its own profile and effect."""
    message = "censal certificate result contradicts its terminal receipt"
    if type(result) is not CensalCertificateOperationResult:
        raise ValueError(message)
    require_terminal_receipt_match(
        receipt,
        definition_id=CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED if result.ingest.applied else OperationEffect.NONE,
        message=message,
    )
    return CensalCertificateOperationProjection.model_validate_json(result.ingest.model_dump_json(), strict=True)


def build_censal_certificate_operation_definition(parse_certificate: CensalCertificateParser) -> OperationDefinition:
    """Declare the secure-input, exact-profile certificate preview and enrollment."""
    return OperationDefinition(
        definition_id=CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID,
        request_type=CensalCertificateOperationRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=CensalCertificateOperationResult,
        executor_factory=OperationExecutorFactory(
            request_type=CensalCertificateOperationRequest,
            executor_type=CensalCertificateOperationExecutor,
            build=lambda: CensalCertificateOperationExecutor(parse_certificate),
        ),
        phase_codes=(
            CENSAL_CERTIFICATE_PHASE_READ,
            CENSAL_CERTIFICATE_PHASE_APPLY,
            CENSAL_CERTIFICATE_PHASE_RESULT,
        ),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        # A file that is no certificate, or whose layout cannot be read yet, is
        # refused with a reason the caller has to see to act on it.
        public_error_detail=True,
    )


def build_censal_certificate_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the request and result schemas, the projector and the access resolver."""
    if definition.definition_id != CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID:
        raise ValueError("unexpected censal certificate definition")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=CensalCertificateOperationProjection,
        result_projector=project_censal_certificate_result,
        access_resolver=resolve_censal_certificate_operation_access,
    )


def censal_certificate_operation(
    parse_certificate: CensalCertificateParser,
) -> tuple[OperationDefinition, OperationPublicDefinitionRegistrationV1]:
    """Compose the definition and its public registration for an operation registry."""
    definition = build_censal_certificate_operation_definition(parse_certificate)
    return definition, build_censal_certificate_operation_registration(definition)


__all__ = [
    "CENSAL_CERTIFICATE_OPERATION_DEFINITION_ID",
    "MAX_CENSAL_CERTIFICATE_BYTES",
    "CensalCertificateFactRow",
    "CensalCertificateIngest",
    "CensalCertificateOperationExecutor",
    "CensalCertificateOperationProjection",
    "CensalCertificateOperationRequest",
    "CensalCertificateOperationResult",
    "CensalCertificateParser",
    "CensalCertificateReading",
    "build_censal_certificate_operation_definition",
    "build_censal_certificate_operation_registration",
    "censal_certificate_operation",
    "project_censal_certificate_result",
    "read_censal_certificate",
    "resolve_censal_certificate_operation_access",
]
