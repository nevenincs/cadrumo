"""Registered operations for the operator's resolutions of disputed Modelo figures.

The operator accepts a source disagreement by the finding id a refusal or the
form showed, takes the acceptance back, or lists what a declaration holds. Every
write goes through the one guarded write path of
:mod:`~cadrumo.application.modelo.credit_resolution_repository`; this module adds
the exact-profile operation surface around it.

An id is matched against the findings the declaration's *current* persisted
calculation holds. A resolution that matched nothing, or a calculation that has
since been replaced, is refused with a typed reason before anything is stored: an
operator who believes a figure was accepted when it was not would file on it.
Every refusal is decided from persisted facts before anything is written, and
settles with effect ``NONE`` after the ``UNKNOWN`` declared on entry to the
irreversible section;
:class:`CalculationRevision`, the saved calculation revision.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Final

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...core.time.clock import now
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionCatalogue
from ...domain.modelos.work_unit import WorkUnit
from ..operations.access_port import OperationAccessResolver
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
)
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    refused_receipt_references_hold,
    require_succeeded_terminal_receipt,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .calculation_note_gate import SOURCE_DISAGREEMENT_FINDING_ID_LENGTH
from .credit_resolution import (
    credit_resolution_for_finding,
    find_finding,
    revoke_refusal_for,
    stored_resolution_for,
)
from .credit_resolution_contracts import (
    MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
    MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID,
    MODELO_CREDIT_RESOLUTION_REFUSAL_CODE,
    MODELO_CREDIT_RESOLUTION_REFUSAL_CODES,
    MODELO_CREDIT_RESOLUTION_REVISION_REFUSAL_CODE,
    MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID,
    CreditResolutionAcceptRequest,
    CreditResolutionExecutionResult,
    CreditResolutionListProjection,
    CreditResolutionListRequest,
    CreditResolutionMutationProjection,
    CreditResolutionOperationId,
    CreditResolutionOperationRefusalReason,
    CreditResolutionRefusalProjection,
    CreditResolutionRequest,
    CreditResolutionRevokeRequest,
    CreditResolutionRowProjection,
)
from .credit_resolution_repository import (
    CreditResolutionRefusedError,
    CreditResolutionRepository,
    CreditResolutionRevisionConflictError,
    revoke_credit_resolution,
    revoke_refusal_reason,
    store_credit_resolution,
)
from .credit_resolution_words import served_credit_resolution_refusal_words
from .verification_repository_ports import VerificationRepositoryBundleFactory

__all__ = [
    "UNIDENTIFIED_SESSION_LABEL",
    "CreditResolutionExecutor",
    "build_credit_resolution_accept_definition",
    "build_credit_resolution_list_definition",
    "build_credit_resolution_list_registration",
    "build_credit_resolution_mutation_registration",
    "build_credit_resolution_revoke_definition",
    "project_credit_resolution_list_result",
    "project_credit_resolution_result",
]

_REQUEST_TYPES: Final[dict[str, type[CreditResolutionRequest]]] = {
    MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID: CreditResolutionAcceptRequest,
    MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID: CreditResolutionRevokeRequest,
    MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID: CreditResolutionListRequest,
}
_OPERATION_IDS: Final[dict[str, CreditResolutionOperationId]] = {
    MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID: "accept",
    MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID: "revoke",
    MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID: "list",
}
_MUTATING_DEFINITIONS: Final = {
    "accept": MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID,
    "revoke": MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID,
}
_MESSAGE: Final = "credit resolution result contradicts its terminal receipt"
UNIDENTIFIED_SESSION_LABEL: Final = "session.unidentified"
"""The label an acceptance is recorded under where no session host says which session admitted it."""


class _Declaration:
    """The persisted calculation revision a request addresses, with its work unit and the profile's stores."""

    def __init__(
        self,
        revision: CalculationRevision,
        work_unit: WorkUnit,
        resolutions: CreditResolutionRepository,
        current_finding_keys: frozenset[str],
    ) -> None:
        self.revision = revision
        self.work_unit = work_unit
        self.resolutions = resolutions
        self.current_finding_keys = current_finding_keys
        """The finding keys of the disagreements the work unit's current calculation holds."""

    @property
    def coordinates(self) -> tuple[str, int, str]:
        """The modelo, filing year and period token every resolution of this declaration is stored under."""
        unit = self.work_unit
        return str(unit.modelo), unit.filing_year, unit.period.registry_token


def _current_finding_keys(unit: WorkUnit, revisions: CalculationRevisionCatalogue) -> frozenset[str]:
    """The finding keys of the disagreements the unit's current calculation revision states."""
    current_id = unit.current_calculation_revision_id
    current = None if current_id is None else revisions.get(current_id)
    return frozenset(
        issue.disagreement.finding_key
        for issue in (() if current is None else current.source_issues)
        if issue.disagreement is not None
    )


class CreditResolutionExecutor:
    """Run the resolution write path under exact-profile worker custody."""

    def __init__(
        self,
        bundle_factory: VerificationRepositoryBundleFactory,
        *,
        definition_id: str,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the exact-profile repository composition and the public operation id."""
        self._bundle_factory = bundle_factory
        self._definition_id = definition_id
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self, request: OperationRequest[BaseModel], context: OperationExecutorContext
    ) -> str | OperationRefusalEvidence:
        """Run one acceptance, revocation or listing and retain its receipt-correlated outcome."""
        payload = self._validate_request(request, context)
        await context.events.phase(self._definition_id)
        operation_id = _OPERATION_IDS[self._definition_id]
        if isinstance(payload, CreditResolutionListRequest):
            return await self._list(context, payload)
        if not isinstance(payload, (CreditResolutionAcceptRequest, CreditResolutionRevokeRequest)):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        actor = self._session_label(context)
        declaration = await asyncio.to_thread(self._declaration, context, payload)

        def work() -> CreditResolutionRowProjection:
            return self._prepare(declaration, payload)(actor)

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    row = await asyncio.to_thread(work)
                except CreditResolutionRevisionConflictError:
                    return await self._persist_refusal(context, payload, declaration, operation_id, "stale_revision")
                except CreditResolutionRefusedError as refused:
                    return await self._persist_refusal(context, payload, declaration, operation_id, refused.reason)
                result = CreditResolutionExecutionResult(
                    operation_id=operation_id,
                    outcome="success",
                    profile_id=payload.profile_id,
                    work_unit_id=declaration.work_unit.work_unit_id,
                    calculation_revision_id=payload.calculation_revision_id,
                    resolution=row,
                )
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(commit(), task_name=f"credit-resolution-{operation_id}")

    def _session_label(self, context: OperationExecutorContext) -> str:
        """Name the session that admitted this execution, as the record of who answered.

        A person's frontends are named by frontend, session kind and client; an
        automation is named by its own session label. Without a session host
        nothing identifies the session, which the label says.
        """
        reader = self._execution_caller_reader
        if reader is None:
            return UNIDENTIFIED_SESSION_LABEL
        caller = reader(context.identity)
        return execution_actor_label(
            reader, context, supplied=f"{caller.frontend.value}.{caller.session_kind.value}.{caller.client_id}"
        )

    def _validate_request(
        self, request: OperationRequest[BaseModel], context: OperationExecutorContext
    ) -> CreditResolutionRequest:
        request_type = _REQUEST_TYPES.get(self._definition_id)
        payload = request.payload
        if request_type is None or type(payload) is not request_type:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if request.definition_id != self._definition_id or context.identity.subject_ref != request.subject_ref:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        if not isinstance(payload, CreditResolutionRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return payload

    def _declaration(self, context: OperationExecutorContext, payload: CreditResolutionRequest) -> _Declaration:
        profile_id = str(payload.profile_id)
        operation = context.authority_operation
        bundle = self._bundle_factory(profile_id, operation=operation)
        if bundle.calculation.bucket_id != profile_id or bundle.work_unit.bucket_id != profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        revisions = bundle.calculation.load(operation=operation)
        revision = revisions.get(payload.calculation_revision_id)
        if revision is None or revision.work_unit_id != context.identity.subject_ref:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        unit = bundle.work_unit.load().get(revision.work_unit_id)
        if unit is None or unit.bucket_id != profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return _Declaration(
            revision,
            unit,
            bundle.credit_resolution,
            _current_finding_keys(unit, revisions),
        )

    def _prepare(
        self, declaration: _Declaration, payload: CreditResolutionRequest
    ) -> Callable[[str], CreditResolutionRowProjection]:
        """Decide every refusal that persisted facts settle, and return the write that remains."""
        if isinstance(payload, CreditResolutionAcceptRequest):
            return self._prepare_accept(declaration, payload)
        if isinstance(payload, CreditResolutionRevokeRequest):
            return self._prepare_revoke(declaration, payload)
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def _prepare_accept(
        self, declaration: _Declaration, payload: CreditResolutionAcceptRequest
    ) -> Callable[[str], CreditResolutionRowProjection]:
        if declaration.work_unit.current_calculation_revision_id != declaration.revision.calculation_revision_id:
            raise CreditResolutionRefusedError("calculation_not_current")
        issue = find_finding(declaration.revision, payload.finding_id)
        repository = declaration.resolutions
        fact = issue.disagreement
        if fact is None:
            raise CreditResolutionRefusedError("unknown_finding")
        stored, expected_revision_id = repository.load_revisioned(
            (fact.modelo, fact.filing_year, fact.period, fact.finding_key)
        )
        if stored is not None and stored.active:
            raise CreditResolutionRefusedError("already_resolved")

        def write(actor: str) -> CreditResolutionRowProjection:
            record = credit_resolution_for_finding(issue, reason=payload.reason, at=now(), by_session=actor)
            revision_id = store_credit_resolution(
                record, repository=repository, expected_revision_id=expected_revision_id
            )
            return CreditResolutionRowProjection.of(
                record,
                revision_id=revision_id,
                applies=True,
                current=record.finding_key in declaration.current_finding_keys,
                revoke_refusal=revoke_refusal_reason(record),
                language=payload.output_language,
            )

        return write

    def _prepare_revoke(
        self, declaration: _Declaration, payload: CreditResolutionRevokeRequest
    ) -> Callable[[str], CreditResolutionRowProjection]:
        modelo, filing_year, period = declaration.coordinates
        stored = declaration.resolutions.list_revisioned(modelo=modelo, filing_year=filing_year, period=period)
        identity = stored_resolution_for((record for record, _revision_id in stored), payload.finding_id).identity
        repository = declaration.resolutions
        current = {issue.disagreement.finding_key for issue in declaration.revision.source_issues if issue.disagreement}

        def write(actor: str) -> CreditResolutionRowProjection:
            revoked, revision_id = revoke_credit_resolution(
                identity,
                at=now(),
                by_session=actor,
                repository=repository,
                expected_revision_id=payload.expected_revision_id,
            )
            return CreditResolutionRowProjection.of(
                revoked,
                revision_id=revision_id,
                applies=revoked.finding_key in current,
                current=revoked.finding_key in declaration.current_finding_keys,
                revoke_refusal=revoke_refusal_reason(revoked),
                language=payload.output_language,
            )

        return write

    async def _list(self, context: OperationExecutorContext, payload: CreditResolutionListRequest) -> str:
        async def read() -> str:
            def work() -> CreditResolutionExecutionResult:
                declaration = self._declaration(context, payload)
                modelo, filing_year, period = declaration.coordinates
                persisted = {
                    issue.disagreement.finding_key
                    for issue in declaration.revision.source_issues
                    if issue.disagreement is not None
                }
                stored = declaration.resolutions.list_revisioned(modelo=modelo, filing_year=filing_year, period=period)
                records = tuple(record for record, _revision_id in stored)
                rows = tuple(
                    CreditResolutionRowProjection.of(
                        record,
                        revision_id=revision_id,
                        applies=record.finding_key in persisted,
                        current=record.finding_key in declaration.current_finding_keys,
                        revoke_refusal=revoke_refusal_for(
                            records, record.finding_key[:SOURCE_DISAGREEMENT_FINDING_ID_LENGTH]
                        ),
                        language=payload.output_language,
                    )
                    for record, revision_id in stored
                )
                return CreditResolutionExecutionResult(
                    operation_id="list",
                    outcome="success",
                    profile_id=payload.profile_id,
                    work_unit_id=declaration.work_unit.work_unit_id,
                    calculation_revision_id=payload.calculation_revision_id,
                    resolutions=rows,
                )

            result = await asyncio.to_thread(work)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(read(), task_name="credit-resolution-list")

    async def _persist_refusal(
        self,
        context: OperationExecutorContext,
        payload: CreditResolutionRequest,
        declaration: _Declaration,
        operation_id: CreditResolutionOperationId,
        reason: CreditResolutionOperationRefusalReason,
    ) -> OperationRefusalEvidence:
        code = (
            MODELO_CREDIT_RESOLUTION_REVISION_REFUSAL_CODE
            if reason == "stale_revision"
            else MODELO_CREDIT_RESOLUTION_REFUSAL_CODE
        )
        finding_id = getattr(payload, "finding_id", None)
        if not isinstance(finding_id, str) or len(finding_id) != SOURCE_DISAGREEMENT_FINDING_ID_LENGTH:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        words, words_language = served_credit_resolution_refusal_words(reason, error_code=code)
        refusal = CreditResolutionRefusalProjection.model_validate(
            {
                "code": code,
                "reason": reason,
                "finding_id": finding_id,
                "refusal_words": words,
                "refusal_words_language": words_language,
            }
        )
        result = CreditResolutionExecutionResult(
            operation_id=operation_id,
            outcome="refused",
            profile_id=payload.profile_id,
            work_unit_id=declaration.work_unit.work_unit_id,
            calculation_revision_id=payload.calculation_revision_id,
            refusal=refusal,
        )
        detail_ref = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return OperationRefusalEvidence(refusal_code=code, detail_ref=detail_ref)


def _definition(
    definition_id: str,
    bundle_factory: VerificationRepositoryBundleFactory,
    execution_caller_reader: OperationExecutionCallerReader | None,
) -> OperationDefinition:
    is_list = definition_id == MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=_REQUEST_TYPES[definition_id],
        subject_reference=OperationSubjectReferenceV1.stored_work_unit("calculation_revision_id"),
        result_type=CreditResolutionExecutionResult,
        executor_type=CreditResolutionExecutor,
        build=lambda: CreditResolutionExecutor(
            bundle_factory, definition_id=definition_id, execution_caller_reader=execution_caller_reader
        ),
        capabilities=(
            RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
            if is_list
            else RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
        ),
        refusal_detail_codes=frozenset() if is_list else MODELO_CREDIT_RESOLUTION_REFUSAL_CODES,
    )


def build_credit_resolution_accept_definition(
    bundle_factory: VerificationRepositoryBundleFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Build the definition that accepts one disagreement of a persisted calculation by its finding id."""
    return _definition(MODELO_CREDIT_RESOLUTION_ACCEPT_OPERATION_DEFINITION_ID, bundle_factory, execution_caller_reader)


def build_credit_resolution_revoke_definition(
    bundle_factory: VerificationRepositoryBundleFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Build the revision-guarded definition that takes an acceptance back."""
    return _definition(MODELO_CREDIT_RESOLUTION_REVOKE_OPERATION_DEFINITION_ID, bundle_factory, execution_caller_reader)


def build_credit_resolution_list_definition(
    bundle_factory: VerificationRepositoryBundleFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Build the definition that lists the acceptances one declaration holds."""
    return _definition(MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID, bundle_factory, execution_caller_reader)


def _refusal_receipt_matches(receipt: OperationTerminalReceipt, code: str) -> bool:
    return (
        receipt.condition is OperationTerminalCondition.REFUSED
        and receipt.effect is OperationEffect.NONE
        and receipt.refusal_ref == code
        and receipt.refusal_detail_ref is not None
        and refused_receipt_references_hold(receipt)
        and receipt.diagnostic_ref is None
        and code in MODELO_CREDIT_RESOLUTION_REFUSAL_CODES
    )


def project_credit_resolution_list_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CreditResolutionListProjection:
    """Release the stored resolutions of one declaration only against a read-only receipt."""
    if type(result) is not CreditResolutionExecutionResult:
        raise ValueError(_MESSAGE)
    private = CreditResolutionExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    if (
        receipt.identity.definition_id != MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID
        or private.operation_id != "list"
        or private.outcome != "success"
        or private.resolutions is None
    ):
        raise ValueError(_MESSAGE)
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=MODELO_CREDIT_RESOLUTION_LIST_OPERATION_DEFINITION_ID,
        subject_ref=private.work_unit_id,
        effect=OperationEffect.NONE,
        message=_MESSAGE,
    )
    return CreditResolutionListProjection(
        profile_id=private.profile_id,
        calculation_revision_id=private.calculation_revision_id,
        resolutions=private.resolutions,
    )


def project_credit_resolution_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CreditResolutionMutationProjection:
    """Release one accepted or revoked outcome, or its typed refusal that stored nothing."""
    if type(result) is not CreditResolutionExecutionResult:
        raise ValueError(_MESSAGE)
    private = CreditResolutionExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    definition_id = _MUTATING_DEFINITIONS.get(private.operation_id)
    if definition_id is None or receipt.identity.definition_id != definition_id:
        raise ValueError(_MESSAGE)
    if receipt.identity.subject_ref != private.work_unit_id:
        raise ValueError(_MESSAGE)
    if private.outcome == "refused":
        refusal = private.refusal
        if refusal is None or not _refusal_receipt_matches(receipt, refusal.code):
            raise ValueError(_MESSAGE)
        return CreditResolutionMutationProjection(
            outcome="refused",
            profile_id=private.profile_id,
            calculation_revision_id=private.calculation_revision_id,
            refusal=refusal,
        )
    resolution = private.resolution
    if resolution is None:
        raise ValueError(_MESSAGE)
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=definition_id,
        subject_ref=private.work_unit_id,
        effect=OperationEffect.UPDATED,
        message=_MESSAGE,
    )
    return CreditResolutionMutationProjection(
        outcome="accepted" if private.operation_id == "accept" else "revoked",
        profile_id=private.profile_id,
        calculation_revision_id=private.calculation_revision_id,
        resolution=resolution,
    )


def build_credit_resolution_mutation_registration(
    definition: OperationDefinition, *, access_resolver: OperationAccessResolver
) -> OperationPublicDefinitionRegistrationV1:
    """Bind an acceptance or revocation projection and its typed refusal contract."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=CreditResolutionMutationProjection,
        result_projector=project_credit_resolution_result,
        access_resolver=access_resolver,
    )


def build_credit_resolution_list_registration(
    definition: OperationDefinition, *, access_resolver: OperationAccessResolver
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the list projection to its disclosure guard."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=CreditResolutionListProjection,
        result_projector=project_credit_resolution_list_result,
        access_resolver=access_resolver,
    )
