"""Bind the local quickfile chain to one worker profile and retained authority pin."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from ..adapters.persistence.storage.attachment import AttachmentStore
from ..adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from ..adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ..application.modelo.action_errors import ModeloProfileReadinessError
from ..application.modelo.profile_readiness_gate import load_modelo_work_profile
from ..application.modelo.quickfile_operation_ports import QuickfileOperationPorts
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.wizard.status import taxpayer_profile_from_record
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from .adapter_composition import (
    build_calculation_action_ports,
    build_diagnostics_ports,
    build_modelo_export_ports,
    build_operator_probe_ports,
    build_state_projection_read_ports,
    build_verification_repository_bundle,
)


def build_quickfile_operation_ports(
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    mutation_writer: Callable[[Callable[[], None]], None],
) -> QuickfileOperationPorts:
    """Supply configured repositories without nesting authority or borrowing another profile."""
    bucket_id = str(profile_id)
    if require_active_bucket_id() != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    base = secure_object_repository_for_bucket(bucket_id)
    objects = SecureObjectRepository(
        engine=base.engine,
        namespace_registry=base.namespace_registry,
        active_session_bucket_id=bucket_id,
        require_secure_active_session=True,
        mutation_writer=mutation_writer,
    )
    profile = load_modelo_work_profile(bucket_id=bucket_id, profile_decode_context=operation.profile_decode_context())
    if profile is None:
        raise ModeloProfileReadinessError(
            translated_message="application.modelo.errors.profile_readiness_profile_missing",
            context={"bucket_id": bucket_id},
        )
    if str(profile.record.profile_id) != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    workflow_profile = taxpayer_profile_from_record(profile.record, schema=operation.profile_schema())
    return QuickfileOperationPorts(
        profile_id=profile_id,
        operation=operation,
        profile=profile,
        workflow_profile=workflow_profile,
        calculation=build_calculation_action_ports(
            bucket_id=bucket_id,
            operation=operation,
            profile_record=profile.record,
            objects=objects,
        ),
        verification=build_verification_repository_bundle(bucket_id, operation=operation, objects=objects),
        export=build_modelo_export_ports(
            bucket_id=bucket_id,
            m303_rectificativa_taxpayer_tax_id=workflow_profile.tax_id,
            operation=operation,
            objects=objects,
        ),
        read=build_state_projection_read_ports(
            diagnostics_ports=build_diagnostics_ports(bucket_id=bucket_id),
            operation=operation,
            objects=objects,
            bucket_id=bucket_id,
        ),
        certificate_secret_backend_factory=build_certificate_secret_backend,
        operator_probe_ports=build_operator_probe_ports(),
        operator_scope_ports=build_operator_scope_ports(),
        attachments=AttachmentStore(objects=objects),
    )
