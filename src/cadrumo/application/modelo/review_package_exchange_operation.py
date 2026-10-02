"""Registered human review-package exchange using canonical crypto and custody.

Only explicit final operator artifacts are written to the filesystem. Transient
private keys, decrypted bytes and envelope contents never enter generic operation
facts or result schemas. Canonical audit/replay ordering is retained.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hex import Hex64Str
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ..ledger.commit_fence import LedgerCommitAttemptTracker, run_with_ledger_commit_fence
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .recipient_encryption import RecipientEncryptedPackage
from .review_package import ReviewPackageActor
from .review_package_collab_audit import (
    emit_collab_feedback_countersign_attached_event,
    emit_collab_package_counter_signed_event,
    emit_collab_package_decrypted_event,
    emit_collab_package_encrypted_event,
)
from .review_package_counter_sign import (
    CounterSignedReceipt,
    ReviewPackageCounterSigningError,
    counter_sign_review_package,
)
from .review_package_exchange_operation_ports import (
    ReviewPackageExchangeOperationPorts,
    ReviewPackageExchangeOperationPortsFactory,
)
from .review_package_feedback import (
    build_feedback_package,
    encrypt_feedback_package_for_originator,
    import_feedback_package,
)
from .review_package_recipient_encryption import (
    RecipientEncryptionError,
    decrypt_review_package_for_recipient,
    encrypt_review_package_for_recipient,
    ensure_recipient_encryption_keypair,
)
from .review_package_recipient_registry import get_recipient_fingerprint
from .review_package_signing import (
    ReviewPackageSigningError,
    SignedReviewPackage,
    ensure_review_package_signing_keypair,
    sign_review_package,
)
from .review_package_text import ReviewFeedbackNote, ReviewPackageNote

MODELO_REVIEW_PACKAGE_SIGN_OPERATION_DEFINITION_ID = "modelo.review_package.sign"
MODELO_REVIEW_PACKAGE_COUNTER_SIGN_OPERATION_DEFINITION_ID = "modelo.review_package.counter_sign"
MODELO_REVIEW_PACKAGE_ENCRYPT_FOR_RECIPIENT_OPERATION_DEFINITION_ID = "modelo.review_package.encrypt_for_recipient"
MODELO_REVIEW_PACKAGE_DECRYPT_OPERATION_DEFINITION_ID = "modelo.review_package.decrypt"
MODELO_REVIEW_PACKAGE_ENCRYPT_FEEDBACK_OPERATION_DEFINITION_ID = "modelo.review_package.encrypt_feedback"
MODELO_REVIEW_PACKAGE_IMPORT_FEEDBACK_OPERATION_DEFINITION_ID = "modelo.review_package.import_feedback"
_FRONTENDS = frozenset({OperationFrontendProjection.CLI})
_ACTIONS = frozenset(
    {
        AccessAction.SUBMIT,
        AccessAction.START,
        AccessAction.RESUME,
        AccessAction.OBSERVE,
        AccessAction.RESULT,
        AccessAction.COMMIT,
    }
)


class _Request(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID


class ModeloReviewPackageSignRequest(_Request):
    """Explicit package and final signature paths; no signing private key."""

    package: Path
    output: Path


class ModeloReviewPackageCounterSignRequest(_Request):
    """Original signature input and human receipt output, retaining the existing note."""

    package: Path
    signature: Path
    output: Path
    note: ReviewPackageNote = ""


class ModeloReviewPackageEncryptForRecipientRequest(_Request):
    """One trusted recipient and the existing review-only/expiry choices."""

    package: Path
    recipient_id: Annotated[str, Field(min_length=1, max_length=200)]
    output: Path
    review_only: bool = False
    valid_for_days: Annotated[int, Field(gt=0)] | None = None


class ModeloReviewPackageDecryptRequest(_Request):
    """Local encrypted envelope and explicit final human plaintext package."""

    envelope_path: Path
    output: Path


class ModeloReviewPackageEncryptFeedbackRequest(_Request):
    """Canonical feedback fields, protected as one human request."""

    originator_id: Annotated[str, Field(min_length=1, max_length=200)]
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    submitted_by: ReviewPackageActor
    output: Path
    note: ReviewFeedbackNote = ""
    receipt: Path | None = None


class ModeloReviewPackageImportFeedbackRequest(_Request):
    """Existing local feedback/package inputs and explicit signature trust anchors."""

    envelope_path: Path
    package: Path
    operator_public_key_hex: Hex64Str
    counter_signer_public_key_hex: Hex64Str | None = None


class _Projection(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    effect: OperationEffect


class ModeloReviewPackageSignProjection(_Projection):
    """Complete existing signature receipt without private material."""

    package_path: str
    signature_path: str
    bucket_id: BucketId
    calculation_revision_id: CalculationRevisionId
    manifest_sha256: Hex64Str
    signer_public_key_hex: Hex64Str
    signed_at: datetime


class ModeloReviewPackageCounterSignProjection(_Projection):
    """Complete protected human counter-sign receipt metadata."""

    package_path: str
    signature_path: str
    receipt_path: str
    bucket_id: BucketId
    note: ReviewPackageNote
    counter_signer_public_key_hex: Hex64Str
    counter_signed_at: datetime


class ModeloReviewPackageEncryptForRecipientProjection(_Projection):
    """Existing recipient output and disposition, without ciphertext."""

    package_path: str
    output_path: str
    recipient_id: str
    recipient_public_key_hex: Hex64Str
    review_only: bool
    issued_at: datetime
    valid_until: datetime | None


class ModeloReviewPackageDecryptProjection(_Projection):
    """Existing human final plaintext output receipt, never recovered bytes."""

    envelope_path: str
    output_path: str
    bucket_id: BucketId
    review_only: bool


class ModeloReviewPackageEncryptFeedbackProjection(_Projection):
    """Existing return-envelope receipt without raw feedback or ciphertext."""

    output_path: str
    originator_id: str
    originator_public_key_hex: Hex64Str
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    has_counter_sign: bool
    issued_at: datetime
    valid_until: datetime | None


class ModeloReviewPackageImportFeedbackProjection(_Projection):
    """Full existing human verified feedback metadata in protected result custody."""

    envelope_path: str
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    note: ReviewFeedbackNote
    submitted_by: ReviewPackageActor
    counter_signature_verified: bool | None
    attached_to_journal: bool


type ReviewPackageExchangeProjection = (
    ModeloReviewPackageSignProjection
    | ModeloReviewPackageCounterSignProjection
    | ModeloReviewPackageEncryptForRecipientProjection
    | ModeloReviewPackageDecryptProjection
    | ModeloReviewPackageEncryptFeedbackProjection
    | ModeloReviewPackageImportFeedbackProjection
)


class ReviewPackageExchangeExecutionResult(BaseModel):
    """One complete typed human receipt retained outside generic journals."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: ReviewPackageExchangeProjection


_MODELS: dict[str, tuple[type[_Request], type[_Projection]]] = {
    MODELO_REVIEW_PACKAGE_SIGN_OPERATION_DEFINITION_ID: (
        ModeloReviewPackageSignRequest,
        ModeloReviewPackageSignProjection,
    ),
    MODELO_REVIEW_PACKAGE_COUNTER_SIGN_OPERATION_DEFINITION_ID: (
        ModeloReviewPackageCounterSignRequest,
        ModeloReviewPackageCounterSignProjection,
    ),
    MODELO_REVIEW_PACKAGE_ENCRYPT_FOR_RECIPIENT_OPERATION_DEFINITION_ID: (
        ModeloReviewPackageEncryptForRecipientRequest,
        ModeloReviewPackageEncryptForRecipientProjection,
    ),
    MODELO_REVIEW_PACKAGE_DECRYPT_OPERATION_DEFINITION_ID: (
        ModeloReviewPackageDecryptRequest,
        ModeloReviewPackageDecryptProjection,
    ),
    MODELO_REVIEW_PACKAGE_ENCRYPT_FEEDBACK_OPERATION_DEFINITION_ID: (
        ModeloReviewPackageEncryptFeedbackRequest,
        ModeloReviewPackageEncryptFeedbackProjection,
    ),
    MODELO_REVIEW_PACKAGE_IMPORT_FEEDBACK_OPERATION_DEFINITION_ID: (
        ModeloReviewPackageImportFeedbackRequest,
        ModeloReviewPackageImportFeedbackProjection,
    ),
}


def _require_profile(
    request: OperationRequest[BaseModel], context: OperationExecutorContext, payload: _Request
) -> None:
    if (
        request.subject_ref != profile_operation_subject(str(payload.profile_id))
        or context.identity.definition_id != request.definition_id
        or context.identity.subject_ref != request.subject_ref
        or require_active_bucket_id() != str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _signed(path: Path, ports: ReviewPackageExchangeOperationPorts) -> SignedReviewPackage:
    try:
        return SignedReviewPackage.model_validate_json(ports.files.read_text(path))
    except ValueError as exc:
        raise ReviewPackageSigningError(str(exc)) from exc


def _receipt(path: Path, ports: ReviewPackageExchangeOperationPorts) -> CounterSignedReceipt:
    try:
        return CounterSignedReceipt.model_validate_json(ports.files.read_text(path))
    except ValueError as exc:
        raise ReviewPackageCounterSigningError(str(exc)) from exc


def _envelope(path: Path, ports: ReviewPackageExchangeOperationPorts) -> RecipientEncryptedPackage:
    try:
        return RecipientEncryptedPackage.model_validate_json(ports.files.read_text(path))
    except ValueError as exc:
        raise RecipientEncryptionError(str(exc)) from exc


def _exchange(payload: _Request, ports: ReviewPackageExchangeOperationPorts) -> ReviewPackageExchangeProjection:
    """Compose existing routines in their established order; do not duplicate crypto."""
    profile = str(payload.profile_id)
    if isinstance(payload, ModeloReviewPackageSignRequest):
        keypair = ensure_review_package_signing_keypair(bucket_id=profile, signing_keypair=ports.signing)
        signed = sign_review_package(payload.package, keypair=keypair, operation=ports.operation)
        ports.files.write_text(payload.output, signed.model_dump_json(indent=2))
        return ModeloReviewPackageSignProjection(
            profile_id=payload.profile_id,
            effect=OperationEffect.UPDATED,
            package_path=str(payload.package),
            signature_path=str(payload.output),
            bucket_id=profile,
            calculation_revision_id=signed.calculation_revision_id,
            manifest_sha256=signed.manifest_sha256,
            signer_public_key_hex=keypair.public_key_hex,
            signed_at=signed.signed_at,
        )
    if isinstance(payload, ModeloReviewPackageCounterSignRequest):
        signed = _signed(payload.signature, ports)
        keypair = ensure_review_package_signing_keypair(bucket_id=profile, signing_keypair=ports.signing)
        receipt = counter_sign_review_package(signed, counter_signer_keypair=keypair, note=payload.note)
        ports.files.write_text(payload.output, receipt.model_dump_json(indent=2))
        emit_collab_package_counter_signed_event(receipt, bucket_id=profile, repository=ports.history)
        return ModeloReviewPackageCounterSignProjection(
            profile_id=payload.profile_id,
            effect=OperationEffect.UPDATED,
            package_path=str(payload.package),
            signature_path=str(payload.signature),
            receipt_path=str(payload.output),
            bucket_id=profile,
            note=receipt.note,
            counter_signer_public_key_hex=keypair.public_key_hex,
            counter_signed_at=receipt.counter_signed_at,
        )
    if isinstance(payload, ModeloReviewPackageEncryptForRecipientRequest):
        ports.files.require_exists(payload.package)
        recipient = get_recipient_fingerprint(payload.recipient_id, ports=ports.recipients)
        package_bytes = ports.files.read_bytes(payload.package)
        envelope = encrypt_review_package_for_recipient(
            package_bytes,
            recipient_public_key_hex=recipient.public_key_hex,
            recipient_encryption=ports.encryption,
            review_only=payload.review_only,
            valid_for=timedelta(days=payload.valid_for_days) if payload.valid_for_days is not None else None,
        )
        ports.files.write_text(payload.output, envelope.model_dump_json(indent=2))
        emit_collab_package_encrypted_event(envelope, bucket_id=profile, repository=ports.history)
        return ModeloReviewPackageEncryptForRecipientProjection(
            profile_id=payload.profile_id,
            effect=OperationEffect.UPDATED,
            package_path=str(payload.package),
            output_path=str(payload.output),
            recipient_id=payload.recipient_id,
            recipient_public_key_hex=recipient.public_key_hex,
            review_only=envelope.review_only,
            issued_at=envelope.issued_at,
            valid_until=envelope.valid_until,
        )
    if isinstance(payload, ModeloReviewPackageDecryptRequest):
        envelope = _envelope(payload.envelope_path, ports)
        keypair = ensure_recipient_encryption_keypair(bucket_id=profile, recipient_encryption=ports.encryption)
        decrypted = decrypt_review_package_for_recipient(
            envelope, recipient_private_key_hex=keypair.private_key_hex, recipient_encryption=ports.encryption
        )
        emit_collab_package_decrypted_event(envelope, bucket_id=profile, repository=ports.history)
        ports.replay.mark_consumed(envelope.envelope_nonce_hex)
        ports.files.write_bytes(payload.output, decrypted.package_bytes)
        return ModeloReviewPackageDecryptProjection(
            profile_id=payload.profile_id,
            effect=OperationEffect.UPDATED,
            envelope_path=str(payload.envelope_path),
            output_path=str(payload.output),
            bucket_id=profile,
            review_only=decrypted.review_only,
        )
    if isinstance(payload, ModeloReviewPackageEncryptFeedbackRequest):
        originator = get_recipient_fingerprint(payload.originator_id, ports=ports.recipients)
        receipt = _receipt(payload.receipt, ports) if payload.receipt is not None else None
        feedback = build_feedback_package(
            bucket_id=originator.recipient_id,
            work_unit_id=payload.work_unit_id,
            calculation_revision_id=payload.calculation_revision_id,
            note=payload.note,
            counter_signed_receipt=receipt,
            submitted_by=payload.submitted_by,
        )
        envelope = encrypt_feedback_package_for_originator(
            feedback, originator_public_key_hex=originator.public_key_hex, recipient_encryption=ports.encryption
        )
        ports.files.write_text(payload.output, envelope.model_dump_json(indent=2))
        return ModeloReviewPackageEncryptFeedbackProjection(
            profile_id=payload.profile_id,
            effect=OperationEffect.UPDATED,
            output_path=str(payload.output),
            originator_id=payload.originator_id,
            originator_public_key_hex=originator.public_key_hex,
            work_unit_id=payload.work_unit_id,
            calculation_revision_id=payload.calculation_revision_id,
            has_counter_sign=receipt is not None,
            issued_at=envelope.issued_at,
            valid_until=envelope.valid_until,
        )
    if isinstance(payload, ModeloReviewPackageImportFeedbackRequest):
        ports.files.require_exists(payload.envelope_path)
        ports.files.require_exists(payload.package)
        envelope = _envelope(payload.envelope_path, ports)
        keypair = ensure_recipient_encryption_keypair(bucket_id=profile, recipient_encryption=ports.encryption)
        imported = import_feedback_package(
            envelope,
            originator_private_key_hex=keypair.private_key_hex,
            recipient_encryption=ports.encryption,
            reviewed_package_path=payload.package,
            operator_public_key_hex=payload.operator_public_key_hex,
            counter_signer_public_key_hex=payload.counter_signer_public_key_hex,
        )
        attached = imported.counter_signature_verified is True
        if attached:
            emit_collab_feedback_countersign_attached_event(imported, bucket_id=profile, repository=ports.history)
        return ModeloReviewPackageImportFeedbackProjection(
            profile_id=payload.profile_id,
            effect=OperationEffect.NONE,
            envelope_path=str(payload.envelope_path),
            bucket_id=profile,
            work_unit_id=imported.feedback.work_unit_id,
            calculation_revision_id=imported.feedback.calculation_revision_id,
            note=imported.feedback.note,
            submitted_by=imported.feedback.submitted_by,
            counter_signature_verified=imported.counter_signature_verified,
            attached_to_journal=attached,
        )
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


class ReviewPackageExchangeExecutor:
    """Settle each concrete key/artifact/audit/replay writer before result release."""

    def __init__(self, factory: ReviewPackageExchangeOperationPortsFactory) -> None:
        """Bind exact worker composition without retaining secrets or a registry pin."""
        self._factory = factory

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        """Execute the request-bound canonical human exchange and honest write effects."""
        models = _MODELS.get(request.definition_id)
        payload = request.payload
        if models is None or type(payload) is not models[0] or not isinstance(payload, _Request):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        _require_profile(request, context, payload)
        await context.events.phase(request.definition_id)

        async def settle() -> str:
            tracker = LedgerCommitAttemptTracker()

            def work() -> ReviewPackageExchangeProjection:
                _require_profile(request, context, payload)
                operation = context.authority_operation
                ports = self._factory(profile_id=payload.profile_id, operation=operation, write=tracker.call_writer)
                if ports.profile_id != payload.profile_id or ports.operation is not operation:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                return _exchange(payload, ports)

            try:
                projection = await run_with_ledger_commit_fence(
                    work, tracker=tracker, context=context, task_name=request.definition_id
                )
            except BaseException:
                effect = (
                    OperationEffect.UNKNOWN
                    if tracker.has_uncertain_write
                    else OperationEffect.PARTIAL
                    if tracker.confirmed_write
                    else OperationEffect.NONE
                )
                await context.events.effect(effect)
                raise
            if tracker.has_uncertain_write:
                await context.events.effect(OperationEffect.UNKNOWN)
                raise ValueError("review-package exchange writer outcome remained uncertain")
            effect = OperationEffect.UPDATED if tracker.confirmed_write else OperationEffect.NONE
            if type(payload) is not ModeloReviewPackageImportFeedbackRequest and effect is not OperationEffect.UPDATED:
                raise ValueError("review-package final artifact lacks a confirmed writer receipt")
            projection = type(projection).model_validate(projection.model_copy(update={"effect": effect}).model_dump())
            await context.events.effect(effect)
            return await context.operands.put(
                ReviewPackageExchangeExecutionResult(projection=projection), written_at=now()
            )

        return await await_cancellation_complete(settle(), task_name="review-package-exchange-settlement")


def resolve_review_package_exchange_operation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Exact human request/action/destination policy; no delegated signing/export purpose."""
    models = _MODELS.get(request.definition_id)
    payload = request.payload
    if models is None or type(payload) is not models[0] or not isinstance(payload, _Request):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if context.frontend not in _FRONTENDS:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    if context.action not in _ACTIONS:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    admitted = context.admitted_request
    if admitted is not None and context.action not in {AccessAction.SUBMIT, AccessAction.START, AccessAction.RESUME}:
        if (
            admitted.profile_id != payload.profile_id
            or admitted.definition_id != request.definition_id
            or admitted.destination_id != context.destination_id
            or admitted.frontend is not context.frontend
            or admitted.action is not AccessAction.SUBMIT
            or admitted.periods
            or not admitted.period_independent
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    elif context.authority_operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    disclosures = frozenset[DisclosurePermission]()
    if context.action is AccessAction.OBSERVE:
        disclosures = frozenset(
            (
                DisclosurePermission(
                    destination_id=context.destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            )
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None or schema.schema_id != request.definition_id + ".result":
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosures = frozenset(
            DisclosurePermission(
                destination_id=context.destination_id, projection_id=schema.schema_id, category=category
            )
            for category in (DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES)
        )
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=payload.profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=request.definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=_ACTIONS,
            disclosures=disclosures,
            periods=frozenset(),
            allow_period_independent=True,
            requires_all_periods=True,
            requires_human=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


def project_review_package_exchange_operation_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> BaseModel:
    """Release only the exact family purpose's complete and settled human receipt."""
    if type(result) is not ReviewPackageExchangeExecutionResult:
        raise ValueError("invalid review-package exchange result")
    projection = result.projection
    models = _MODELS.get(receipt.identity.definition_id)
    valid_effects = (
        {OperationEffect.NONE, OperationEffect.UPDATED}
        if type(projection) is ModeloReviewPackageImportFeedbackProjection
        else {OperationEffect.UPDATED}
    )
    if (
        models is None
        or type(projection) is not models[1]
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect not in valid_effects
        or receipt.effect is not projection.effect
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("review-package receipt differs from its exact purpose and writer outcome")
    if isinstance(
        projection,
        (
            ModeloReviewPackageSignProjection,
            ModeloReviewPackageCounterSignProjection,
            ModeloReviewPackageDecryptProjection,
            ModeloReviewPackageImportFeedbackProjection,
        ),
    ) and projection.bucket_id != str(projection.profile_id):
        raise ValueError("review-package human receipt differs from its worker profile")
    if isinstance(projection, ModeloReviewPackageImportFeedbackProjection):
        if projection.counter_signature_verified not in {None, True} or projection.attached_to_journal != (
            projection.counter_signature_verified is True
        ):
            raise ValueError("feedback receipt differs from its canonical verified attachment")
        if projection.attached_to_journal and projection.effect is not OperationEffect.UPDATED:
            raise ValueError("verified feedback attachment lacks a confirmed writer receipt")
    return type(projection).model_validate_json(projection.model_dump_json(), strict=True)


def build_review_package_exchange_operation_definitions(
    factory: ReviewPackageExchangeOperationPortsFactory,
) -> tuple[OperationDefinition, ...]:
    """Enroll the complete six-route family, retaining explicit human authority."""
    capabilities = OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset(
            {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.PARTIAL, OperationEffect.UNKNOWN}
        ),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )
    return tuple(
        OperationDefinition(
            definition_id=identifier,
            request_type=models[0],
            result_type=ReviewPackageExchangeExecutionResult,
            executor_factory=OperationExecutorFactory(
                request_type=models[0],
                executor_type=ReviewPackageExchangeExecutor,
                build=lambda: ReviewPackageExchangeExecutor(factory),
            ),
            phase_codes=(identifier,),
            interaction_kinds=frozenset(),
            capabilities=capabilities,
            reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
            permitted_frontends=_FRONTENDS,
        )
        for identifier, models in sorted(_MODELS.items())
    )


def build_review_package_exchange_operation_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind closed public metadata schemas; raw inputs/results stay in protected custody."""
    if len(definitions) != len(_MODELS) or {row.definition_id for row in definitions} != set(_MODELS):
        raise ValueError("incomplete review-package exchange operation family")
    return tuple(
        OperationPublicDefinitionRegistrationV1.compose(
            definition=definition,
            request_schema=OperationSchemaBindingV1.bind(
                schema_id=definition.definition_id + ".request",
                schema_version=1,
                model_type=_MODELS[definition.definition_id][0],
            ),
            result_schema=OperationSchemaBindingV1.bind(
                schema_id=definition.definition_id + ".result",
                schema_version=1,
                model_type=_MODELS[definition.definition_id][1],
            ),
            result_projector=project_review_package_exchange_operation_result,
            access_resolver=resolve_review_package_exchange_operation_access,
        )
        for definition in definitions
    )
