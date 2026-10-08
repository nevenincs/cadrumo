"""Canonical public registered operations for active user-profile maintenance."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, SecretStr

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import (
    OperationEffect,
)
from ...core.operations import profile_operation_subject as _profile_subject
from ...core.time.clock import now
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from .bundle_export import export_profile_bundle
from .bundle_export_contracts import (
    ProfileBundleExportRequest,
    ProfileBundleExportTransport,
)
from .descendant_rows import replace_profile_descendants
from .fact_write import apply_manager_profile_field_mutation
from .plantilla_media_rows import PlantillaMediaWriteSurface, remove_plantilla_media_year, set_plantilla_media_year
from .profile_operation_contracts import (
    PROFILE_BUNDLE_EXPORT_PHASES,
    PROFILE_COMPLETE_SETUP_PHASES,
    PROFILE_DESCENDANTS_PHASES,
    PROFILE_FIELD_MUTATION_PHASES,
    PROFILE_PATCH_PHASES,
    PROFILE_PLANTILLA_MEDIA_PHASES,
    PROFILE_REPEATABLE_ROW_MUTATION_PHASES,
    PROFILE_REPEATABLE_ROW_REMOVE_PHASES,
    PROFILE_REPEATABLE_ROW_UPDATE_PHASES,
    ProfileBundleExportOperationRequest,
    ProfileCompleteSetupOperationRequest,
    ProfileCompleteSetupOperationResult,
    ProfileDescendantsOperationRequest,
    ProfileDescendantsOperationResult,
    ProfileFieldMutationOperationRequest,
    ProfileMutationOperationResult,
    ProfilePatchOperationRequest,
    ProfilePatchOperationResult,
    ProfilePlantillaMediaOperationRequest,
    ProfilePlantillaMediaOperationResult,
    ProfilePlantillaMediaSet,
    ProfileRepeatableRowChangeOperationResult,
    ProfileRepeatableRowMutationOperationRequest,
    ProfileRepeatableRowMutationOperationResult,
    ProfileRepeatableRowRemoveOperationRequest,
    ProfileRepeatableRowUpdateOperationRequest,
)
from .profile_record_repository import ProfileRecordRepository
from .section_rows import (
    ProfileRepeatableRowChangeOutcome,
    add_profile_repeatable_section_row,
    remove_profile_repeatable_section_row,
    update_profile_repeatable_section_row,
)
from .view_operation import (
    PROFILE_VIEW_PHASES,
    ProfileViewOperationRequest,
)
from .view_reader import read_profile_view_page

__all__: list[str] = []


def _require_active_profile_subject[PayloadT: BaseModel](request: OperationRequest[PayloadT], profile_id: UUID) -> None:
    """Bind every active-profile authority to exactly its secure operation subject."""
    if request.subject_ref != _profile_subject(str(profile_id)):
        raise ValueError("user-profile operation subject does not match its exact profile")
    if require_active_bucket_id() != str(profile_id):
        raise ValueError("user-profile operation requires its profile to be active")


async def _result_reference(result: BaseModel, context: OperationExecutorContext) -> str:
    """Persist a post-mutation result through the supervisor's encrypted operand store."""
    return await context.operands.put(result, written_at=now())


async def _repeatable_row_change_reference(
    profile_id: UUID, mutation: ProfileRepeatableRowChangeOutcome, context: OperationExecutorContext
) -> str:
    """Persist the result of one exact-row update or removal."""
    result = ProfileRepeatableRowChangeOperationResult(
        profile_id=profile_id,
        record_revision=mutation.record.record_revision,
        content_digest=mutation.record.content_digest,
        section_key=mutation.section_key,
        row_key=mutation.row_key,
        changed=mutation.changed,
    )
    return await _result_reference(result, context)


class ProfileFieldMutationOperationExecutor:
    """Delegate one scalar replacement to the canonical profile-fact write door."""

    async def execute(
        self,
        request: OperationRequest[ProfileFieldMutationOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(PROFILE_FIELD_MUTATION_PHASES[0])
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(PROFILE_FIELD_MUTATION_PHASES[1])
        async with context.cancellation.irreversible_section():
            record = await await_cancellation_complete(
                asyncio.to_thread(
                    apply_manager_profile_field_mutation,
                    profile_id=str(payload.profile_id),
                    path=payload.path,
                    value=payload.value,
                    expected_revision=payload.expected_revision,
                    expected_content_digest=payload.expected_content_digest,
                    profile_decode_context=context.authority_operation.profile_decode_context(),
                ),
                task_name="profile-field-mutation",
            )
            result = ProfileMutationOperationResult(
                profile_id=payload.profile_id,
                record_revision=record.record_revision,
                content_digest=record.content_digest,
            )
            result_ref = await _result_reference(result, context)
        await context.events.effect(
            OperationEffect.UPDATED if record.record_revision != payload.expected_revision else OperationEffect.NONE
        )
        await context.events.phase(PROFILE_FIELD_MUTATION_PHASES[2])
        return result_ref


class ProfilePatchOperationExecutor:
    """Validate and commit every supplied wizard answer as one profile change."""

    async def execute(
        self,
        request: OperationRequest[ProfilePatchOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        from ..wizard.catalogue import build_setup_flow
        from ..wizard.patch_edit import apply_profile_patch

        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(PROFILE_PATCH_PHASES[0])
        flow = build_setup_flow(context.authority_operation)
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(PROFILE_PATCH_PHASES[1])
        async with context.cancellation.irreversible_section():
            record = await await_cancellation_complete(
                asyncio.to_thread(
                    apply_profile_patch,
                    flow=flow,
                    profile_id=str(payload.profile_id),
                    expected_revision=payload.expected_revision,
                    expected_content_digest=payload.expected_content_digest,
                    supplied={item.question_id: item.value for item in payload.values},
                    colegio_concertado=payload.colegio_concertado,
                    operation=context.authority_operation,
                ),
                task_name="profile-atomic-patch",
            )
            result = ProfilePatchOperationResult(
                profile_id=payload.profile_id,
                record_revision=record.record_revision,
                content_digest=record.content_digest,
                changed=record.record_revision != payload.expected_revision,
            )
            result_ref = await _result_reference(result, context)
        await context.events.effect(OperationEffect.UPDATED if result.changed else OperationEffect.NONE)
        await context.events.phase(PROFILE_PATCH_PHASES[2])
        return result_ref


class ProfilePlantillaMediaOperationExecutor:
    """Own the canonical year's publication and result through cancellation."""

    async def execute(
        self,
        request: OperationRequest[ProfilePlantillaMediaOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Persist the actual year mutation witness inside its commit guard."""
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(PROFILE_PLANTILLA_MEDIA_PHASES[0])
        decode = context.authority_operation.profile_decode_context()
        await context.events.phase(PROFILE_PLANTILLA_MEDIA_PHASES[1])

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                if isinstance(payload.change, ProfilePlantillaMediaSet):
                    mutation = await asyncio.to_thread(
                        set_plantilla_media_year,
                        profile_id=str(payload.profile_id),
                        year=payload.year,
                        average_workforce=Decimal(payload.change.average_workforce),
                        state=payload.change.state,
                        surface=PlantillaMediaWriteSurface.MANAGER,
                        expected_revision=payload.expected_revision,
                        expected_content_digest=payload.expected_content_digest,
                        profile_decode_context=decode,
                    )
                else:
                    mutation = await asyncio.to_thread(
                        remove_plantilla_media_year,
                        profile_id=str(payload.profile_id),
                        year=payload.year,
                        surface=PlantillaMediaWriteSurface.MANAGER,
                        expected_revision=payload.expected_revision,
                        expected_content_digest=payload.expected_content_digest,
                        profile_decode_context=decode,
                    )
                result_ref = await _result_reference(
                    ProfilePlantillaMediaOperationResult(
                        profile_id=payload.profile_id,
                        record_revision=mutation.record.record_revision,
                        content_digest=mutation.record.content_digest,
                        year=payload.year,
                        changed=mutation.changed,
                    ),
                    context,
                )
                await context.events.effect(OperationEffect.UPDATED if mutation.changed else OperationEffect.NONE)
                return result_ref

        result_ref = await await_cancellation_complete(publish(), task_name="profile-plantilla-media-publication")
        await context.events.phase(PROFILE_PLANTILLA_MEDIA_PHASES[2])
        return result_ref


class ProfileDescendantsOperationExecutor:
    """Retain one atomic family publication through cancellation and settlement."""

    async def execute(
        self,
        request: OperationRequest[ProfileDescendantsOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Publish count, canonical rows and orphan clears through one guarded CAS."""
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(PROFILE_DESCENDANTS_PHASES[0])
        await context.events.phase(PROFILE_DESCENDANTS_PHASES[1])

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                mutation = await asyncio.to_thread(
                    replace_profile_descendants,
                    profile_id=str(payload.profile_id),
                    descendants=payload.descendants,
                    expected_revision=payload.expected_revision,
                    expected_content_digest=payload.expected_content_digest,
                    operation=context.authority_operation,
                )
                result_ref = await _result_reference(
                    ProfileDescendantsOperationResult(
                        profile_id=payload.profile_id,
                        record_revision=mutation.record.record_revision,
                        content_digest=mutation.record.content_digest,
                        total=mutation.total,
                        changed=mutation.changed,
                    ),
                    context,
                )
                await context.events.effect(OperationEffect.UPDATED if mutation.changed else OperationEffect.NONE)
                return result_ref

        result_ref = await await_cancellation_complete(publish(), task_name="profile-descendants-publication")
        await context.events.phase(PROFILE_DESCENDANTS_PHASES[2])
        return result_ref


class ProfileRepeatableRowMutationOperationExecutor:
    """Delegate one whole repeatable row to the shared schema and fact-write authorities."""

    async def execute(
        self,
        request: OperationRequest[ProfileRepeatableRowMutationOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(PROFILE_REPEATABLE_ROW_MUTATION_PHASES[0])
        values = {item.field_key: item.value for item in payload.values}
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(PROFILE_REPEATABLE_ROW_MUTATION_PHASES[1])
        async with context.cancellation.irreversible_section():
            mutation = await await_cancellation_complete(
                asyncio.to_thread(
                    add_profile_repeatable_section_row,
                    profile_id=str(payload.profile_id),
                    section_key=payload.section_key,
                    values=values,
                    expected_revision=payload.expected_revision,
                    expected_content_digest=payload.expected_content_digest,
                    schema=context.authority_operation.profile_schema(),
                    profile_decode_context=context.authority_operation.profile_decode_context(),
                ),
                task_name="profile-repeatable-row-mutation",
            )
            result = ProfileRepeatableRowMutationOperationResult(
                profile_id=payload.profile_id,
                record_revision=mutation.record.record_revision,
                content_digest=mutation.record.content_digest,
                section_key=mutation.section_key,
                row_index=mutation.row_index,
            )
            result_ref = await _result_reference(result, context)
        await context.events.effect(OperationEffect.UPDATED)
        await context.events.phase(PROFILE_REPEATABLE_ROW_MUTATION_PHASES[2])
        return result_ref


class ProfileRepeatableRowUpdateOperationExecutor:
    """Apply one exact-row patch through the canonical schema/fact writer."""

    async def execute(
        self,
        request: OperationRequest[ProfileRepeatableRowUpdateOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(PROFILE_REPEATABLE_ROW_UPDATE_PHASES[0])
        values = {item.field_key: item.value for item in payload.values}
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(PROFILE_REPEATABLE_ROW_UPDATE_PHASES[1])
        async with context.cancellation.irreversible_section():
            mutation = await await_cancellation_complete(
                asyncio.to_thread(
                    update_profile_repeatable_section_row,
                    profile_id=str(payload.profile_id),
                    section_key=payload.section_key,
                    row_key=payload.row_key,
                    values=values,
                    clear_fields=payload.clear_fields,
                    expected_revision=payload.expected_revision,
                    expected_content_digest=payload.expected_content_digest,
                    schema=context.authority_operation.profile_schema(),
                    profile_decode_context=context.authority_operation.profile_decode_context(),
                ),
                task_name="profile-repeatable-row-update",
            )
            result_ref = await _repeatable_row_change_reference(payload.profile_id, mutation, context)
        await context.events.effect(OperationEffect.UPDATED if mutation.changed else OperationEffect.NONE)
        await context.events.phase(PROFILE_REPEATABLE_ROW_UPDATE_PHASES[2])
        return result_ref


class ProfileRepeatableRowRemoveOperationExecutor:
    """Remove one exact row through the canonical schema/tombstone writer."""

    async def execute(
        self,
        request: OperationRequest[ProfileRepeatableRowRemoveOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(PROFILE_REPEATABLE_ROW_REMOVE_PHASES[0])
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(PROFILE_REPEATABLE_ROW_REMOVE_PHASES[1])
        async with context.cancellation.irreversible_section():
            mutation = await await_cancellation_complete(
                asyncio.to_thread(
                    remove_profile_repeatable_section_row,
                    profile_id=str(payload.profile_id),
                    section_key=payload.section_key,
                    row_key=payload.row_key,
                    expected_revision=payload.expected_revision,
                    expected_content_digest=payload.expected_content_digest,
                    schema=context.authority_operation.profile_schema(),
                    profile_decode_context=context.authority_operation.profile_decode_context(),
                ),
                task_name="profile-repeatable-row-remove",
            )
            result_ref = await _repeatable_row_change_reference(payload.profile_id, mutation, context)
        await context.events.effect(OperationEffect.UPDATED if mutation.changed else OperationEffect.NONE)
        await context.events.phase(PROFILE_REPEATABLE_ROW_REMOVE_PHASES[2])
        return result_ref


class ProfileCompleteSetupOperationExecutor:
    """Promote one complete profile through the canonical CAS lifecycle."""

    async def execute(
        self,
        request: OperationRequest[ProfileCompleteSetupOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(PROFILE_COMPLETE_SETUP_PHASES[0])
        await context.events.effect(OperationEffect.UNKNOWN)
        await context.events.phase(PROFILE_COMPLETE_SETUP_PHASES[1])
        async with context.cancellation.irreversible_section():
            record = await await_cancellation_complete(
                asyncio.to_thread(
                    lambda: ProfileRecordRepository.for_current_session(
                        payload.profile_id,
                        profile_decode_context=context.authority_operation.profile_decode_context(),
                    ).complete_setup(
                        payload.profile_id,
                        expected_revision=payload.expected_revision,
                        expected_content_digest=payload.expected_content_digest,
                    )
                ),
                task_name="profile-complete-setup",
            )
            already_complete = record.record_revision == payload.expected_revision
            result = ProfileCompleteSetupOperationResult(
                profile_id=payload.profile_id,
                record_revision=record.record_revision,
                content_digest=record.content_digest,
                already_complete=already_complete,
            )
            result_ref = await _result_reference(result, context)
        await context.events.effect(OperationEffect.NONE if already_complete else OperationEffect.UPDATED)
        await context.events.phase(PROFILE_COMPLETE_SETUP_PHASES[2])
        return result_ref


class ProfileBundleExportOperationExecutor:
    """Publish through the existing crash-reconcilable bundle export authority."""

    async def execute(
        self,
        request: OperationRequest[ProfileBundleExportOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(PROFILE_BUNDLE_EXPORT_PHASES[0])
        await context.events.phase(PROFILE_BUNDLE_EXPORT_PHASES[1])
        async with context.ephemeral_secret.consume() as secret:
            passphrase = bytes(secret).decode("utf-8")
            try:
                await context.events.effect(OperationEffect.UNKNOWN)
                await context.events.phase(PROFILE_BUNDLE_EXPORT_PHASES[2])
                async with context.cancellation.irreversible_section():
                    result = await await_cancellation_complete(
                        asyncio.to_thread(
                            export_profile_bundle,
                            ProfileBundleExportRequest(
                                profile_name=None,
                                destination=payload.destination,
                                purpose=payload.purpose,
                                transport=ProfileBundleExportTransport.PASSPHRASE_ENCRYPTED,
                                passphrase=SecretStr(passphrase),
                            ),
                            authority_operation=context.authority_operation,
                            profile_decode_context=context.authority_operation.profile_decode_context(),
                            authorized_profile_id=str(payload.profile_id),
                        ),
                        task_name="profile-bundle-export",
                    )
                    result_ref = await _result_reference(result, context)
            finally:
                passphrase = ""
        await context.events.effect(OperationEffect.UPDATED)
        await context.events.phase(PROFILE_BUNDLE_EXPORT_PHASES[3])
        return result_ref


class ProfileViewOperationExecutor:
    """Read one pinned page through the canonical encrypted profile record owner."""

    async def execute(
        self,
        request: OperationRequest[ProfileViewOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        payload = request.payload
        _require_active_profile_subject(request, payload.profile_id)
        await context.events.phase(PROFILE_VIEW_PHASES[0])
        result = await await_cancellation_complete(
            asyncio.to_thread(
                read_profile_view_page,
                payload,
                authority_operation=context.authority_operation,
            ),
            task_name="profile-view-page",
        )
        await context.events.phase(PROFILE_VIEW_PHASES[1])
        result_ref = await _result_reference(result, context)
        await context.events.effect(OperationEffect.NONE)
        return result_ref
