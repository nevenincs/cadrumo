"""Installation acts over the durable reset of every profile.

Each handler calls the application function the matching ``config reset``
command calls, and each reply carries the document the command prints. A
command beside a running runtime sends these acts; the runtime hosts profile
workers that hold the stores a reset deletes. So a start or a resume first
fences every profile it will touch against new admission and drains the ones
this runtime hosts, and keeps them fenced until the reset settles. A reset
that is interrupted leaves its own journal, which a resume continues; nothing
here keeps state of its own.
"""

from __future__ import annotations

from uuid import UUID

from ...adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from ...adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ...adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from ...application.config_reset import (
    config_reset_status,
    latest_incomplete_config_reset_id,
    normalise_retention_override,
    require_config_reset_confirmation,
    resume_config_reset,
    start_config_reset,
)
from ...application.config_reset_documents import ConfigResetOperationPayload
from ...application.config_reset_models import ConfigResetOperation, ConfigResetOperationStatus
from ...application.runtime.installation_requests import (
    RuntimeResetResumeReply,
    RuntimeResetResumeRequest,
    RuntimeResetStartReply,
    RuntimeResetStartRequest,
    RuntimeResetStatusReply,
    RuntimeResetStatusRequest,
)
from ...application.workflow.profile_bucket_scan import list_profile_buckets
from ...core.errors.hierarchy import CadrumoError
from .installation_composition import InstallationActRegistry
from .installation_door import InstallationActExchange


def _profiles_to_fence(exchange: InstallationActExchange, *, journalled: tuple[str, ...] = ()) -> frozenset[UUID]:
    """Name every profile a reset can reach or this runtime hosts, so none is admitted mid-reset."""
    named = {*list_profile_buckets(root=exchange.storage_root), *journalled}
    fenced = set(exchange.hosted_profile_ids())
    for identifier in named:
        try:
            fenced.add(UUID(identifier))
        except ValueError:
            # A name that is no profile identifier cannot be hosted or admitted.
            continue
    return frozenset(fenced)


def _serve_start(request: RuntimeResetStartRequest, exchange: InstallationActExchange) -> RuntimeResetStartReply:
    require_config_reset_confirmation(request.confirmed)
    override = normalise_retention_override(
        acknowledge_retention_override=request.acknowledge_retention_override,
        retention_override_reason=request.retention_override_reason,
    )
    with (
        composed_profile_persistence_ports(automation_secrets_store=exchange.secret_store()) as ports,
        # Listing the profiles reads their capsules, which needs the ports bound first.
        exchange.reserve_profiles(_profiles_to_fence(exchange)) as reservation,
    ):
        reservation.retire_hosted()
        exchange.require_login()
        operation = start_config_reset(
            certificate_secret_backend_factory=build_certificate_secret_backend,
            operator_scope_ports=build_operator_scope_ports(),
            bucket_storage=ports.bucket_storage(),
            confirmed=True,
            acknowledge_retention_override=override.acknowledged,
            retention_override_reason=override.reason,
        )
    return exchange.reply(RuntimeResetStartReply, operation=ConfigResetOperationPayload.from_operation(operation))


def _serve_status(request: RuntimeResetStatusRequest, exchange: InstallationActExchange) -> RuntimeResetStatusReply:
    journal = config_reset_status(request.operation_id)
    return exchange.reply(
        RuntimeResetStatusReply,
        operation=None if journal is None else ConfigResetOperationPayload.from_operation(journal),
    )


def _readable_journal(operation_id: str) -> ConfigResetOperation | None:
    """Read the named journal, or nothing when it cannot be read: the resume itself reports why."""
    try:
        return config_reset_status(operation_id)
    except CadrumoError:
        return None


def _serve_resume(request: RuntimeResetResumeRequest, exchange: InstallationActExchange) -> RuntimeResetResumeReply:
    require_config_reset_confirmation(request.confirmed)
    override = normalise_retention_override(
        acknowledge_retention_override=request.acknowledge_retention_override,
        retention_override_reason=request.retention_override_reason,
    )
    operation_id = request.operation_id or latest_incomplete_config_reset_id()
    journal = _readable_journal(operation_id)
    # A journal that is already complete is returned as it stands; no profile is touched, so none is drained.
    settled = journal is not None and journal.status is ConfigResetOperationStatus.COMPLETE
    journalled = () if journal is None else tuple(target.bucket_id for target in journal.targets)
    with composed_profile_persistence_ports(automation_secrets_store=exchange.secret_store()) as ports:
        fenced = frozenset[UUID]() if settled else _profiles_to_fence(exchange, journalled=journalled)
        with exchange.reserve_profiles(fenced) as reservation:
            reservation.retire_hosted()
            exchange.require_login()
            operation = resume_config_reset(
                operation_id,
                certificate_secret_backend_factory=build_certificate_secret_backend,
                operator_scope_ports=build_operator_scope_ports(),
                bucket_storage=ports.bucket_storage(),
                confirmed=True,
                acknowledge_retention_override=override.acknowledged,
                retention_override_reason=override.reason,
            )
    return exchange.reply(RuntimeResetResumeReply, operation=ConfigResetOperationPayload.from_operation(operation))


def register_reset_acts(registry: InstallationActRegistry) -> None:
    """Serve the three reset acts on ``registry``."""
    registry.register(RuntimeResetStartRequest, _serve_start)
    registry.register(RuntimeResetStatusRequest, _serve_status)
    registry.register(RuntimeResetResumeRequest, _serve_resume)
