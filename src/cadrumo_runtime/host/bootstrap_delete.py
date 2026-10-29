"""Runtime hosting for the existing confirmed single-target custody journal."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.application.bucket_maintenance.contracts import AssessBucketDeletionCommand
from cadrumo.application.bucket_maintenance.service import BucketMaintenanceService
from cadrumo.application.user_profile.custody_repository import ProfileCustodyTransactionRepository
from cadrumo.application.user_profile.custody_transactions import (
    ProfileCustodyTransactionConflictError,
    ProfileCustodyTransactionError,
    ProfileCustodyTransactionOperation,
)
from cadrumo.application.user_profile.profile_pointer import active_profile_pointer_transaction
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo_client.contracts.access_vocabulary import Availability
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.bootstrap_delete import (
    ProfileDelete,
    ProfileDeleted,
    ProfileDeletePrepare,
    ProfileDeletePrepared,
    ProfileDeleteRefused,
)
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError, ShutdownIncompleteError
from cadrumo_client.contracts.profile_access import AccessRefusal
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frame_io import write_document

from .profile_connection import ProfileConnection
from .profile_host import RuntimeProfileHost

if TYPE_CHECKING:
    from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle

    from .profile_connections import RuntimeProfileConnections


def delete_connection_matches(
    prior: ProfileConnection, context: ConnectionContext, request: ProfileDeletePrepare | ProfileDelete
) -> bool:
    """Retain only the exact existing bootstrap deletion connection."""
    return (
        prior.context == context
        and prior.profile_id == request.profile_id
        and prior.frontend == request.frontend
        and prior.method == "bootstrap-delete"
    )


def validate_delete_peer(context: ConnectionContext, channel: ByteChannel, boot: UUID) -> None:
    """Reject a connection whose boot or native peer does not match."""
    if context.runtime_boot_id != boot or context.peer != channel.peer:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)


def validate_delete_connection(
    prior: ProfileConnection | None, context: ConnectionContext, request: ProfileDeletePrepare | ProfileDelete
) -> None:
    """Reject a prior connection that cannot own this deletion."""
    if prior is not None and not delete_connection_matches(prior, context, request):
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)


def reserve_delete(mutations: set[UUID], profile_id: UUID) -> None:
    """Reserve deletion under the caller's existing custody guard."""
    if profile_id in mutations:
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    mutations.add(profile_id)


def require_delete_login(
    connection: ProfileConnection, context: ConnectionContext, admitting: Callable[[], bool]
) -> None:
    """Reobserve the deletion caller before each authority-sensitive phase."""
    observed = connection.login.observe(credential_facilities=Availability.UNAVAILABLE)
    if not admitting():
        raise RefusalError(RefusalCode.DRAINING)
    if not observed.active or not observed.unlocked or observed.os_owner_id != context.peer.os_owner_id:
        raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)


def drain_delete_host(host: RuntimeProfileHost, remove_host: Callable[[RuntimeProfileHost], None]) -> None:
    """Contain the existing worker before deleting its profile."""
    with host.guard:
        worker = host.owner.begin_drain()
    deadline = time.monotonic() + 15
    if worker is not None:
        worker.drain(deadline=deadline)
    if not host.owner.wait_construction(deadline=deadline):
        raise ShutdownIncompleteError()
    host.close()
    remove_host(host)


def execute_confirmed_delete(
    request: ProfileDelete,
    *,
    transaction_id: UUID,
    lifecycle: ProfileCapsuleLifecycle,
    root: Path,
    host: RuntimeProfileHost | None,
    coordinates: Mapping[str, UUID],
    require_login: Callable[[], None],
    remove_host: Callable[[RuntimeProfileHost], None],
    sign_in_changed: Callable[[], None],
) -> ProfileDeleted:
    """Recheck confirmation, contain the worker, then finish the owned journal."""
    repository = ProfileCustodyTransactionRepository(root=root)
    journal = repository.load_journal(transaction_id)
    if (
        journal.operation is not ProfileCustodyTransactionOperation.DELETE
        or journal.retention_override is not None
        or lifecycle.confirm_delete(journal) != request.confirmation
    ):
        raise ProfileCustodyTransactionConflictError("deletion confirmation changed")
    require_login()
    if host is not None:
        drain_delete_host(host, remove_host)
    # Unknown lock evidence is never authorization for cleanup.
    # Once execution starts, the serving owner finishes its journal
    # even if the client disconnects before receiving the receipt.
    with active_profile_pointer_transaction(root):
        require_login()
        receipt = lifecycle.delete(request.confirmation)
    sign_in_changed()
    return ProfileDeleted.model_validate({**coordinates, "receipt": receipt})


class RuntimeBootstrapDeleteMixin:
    """Keep journal execution owned after client loss and outside client locks."""

    def bootstrap_delete(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ProfileDeletePrepare | ProfileDelete,
    ) -> None:
        """Serialize containment with polling and shutdown; never wait inside root."""
        if self._refused_as_persons_act(context, channel, request_id=request.request_id, frontend=request.frontend):
            return
        if not self._drain_guard.acquire_delete():
            write_document(
                channel,
                AccessRefusal(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                    code=AutomationCustodyCode.CONFLICT,
                ),
                deadline=time.monotonic() + 5,
            )
            return
        try:
            self._execute_bootstrap_delete(context, channel, request)
        finally:
            self._drain_guard.release()

    def _execute_bootstrap_delete(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ProfileDeletePrepare | ProfileDelete,
    ) -> None:
        # Deletion alone owns the capsule lifecycle and its SQL record graph.
        # Load it before reserving a profile or acquiring its pointer lock.
        from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle

        coordinates = dict(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            profile_id=request.profile_id,
        )
        transaction_id: UUID | None = None
        reserved = False
        try:
            validate_delete_peer(context, channel, self.boot)
            with self._guard:
                prior = self._connections.get(context.connection_id)
                validate_delete_connection(prior, context, request)
            connection = prior or ProfileConnection(
                context,
                self._capture(channel),
                uuid4(),
                request.profile_id,
                request.frontend,
                method="bootstrap-delete",
            )

            def require_login() -> None:
                require_delete_login(connection, context, self._admitting)

            require_login()
            with self._guard:
                reserve_delete(self._custody_mutations, request.profile_id)
                reserved = True
                self._connections[context.connection_id] = connection
                self._logins[connection.login.login_id] = connection.login
                host = self._profiles.get(request.profile_id)
            with composed_profile_persistence_ports(automation_secrets_store=self._secret_store()) as ports:
                lifecycle = ProfileCapsuleLifecycle(root=self.root)
                if isinstance(request, ProfileDeletePrepare):
                    with active_profile_pointer_transaction(self.root):
                        require_login()
                        assessment = BucketMaintenanceService(
                            bucket_storage=ports.bucket_storage(),
                            root=self.root,
                        ).assess_deletion(AssessBucketDeletionCommand(bucket_id=str(request.profile_id)))
                        if not assessment.exists or assessment.fingerprint != request.fingerprint:
                            raise ProfileCustodyTransactionConflictError("deletion preflight changed")
                        journal = lifecycle.prepare_delete(
                            profile_id=request.profile_id,
                            requires_inactive_target=False,
                        )
                        transaction_id = journal.transaction_id
                        result = ProfileDeletePrepared.model_validate(
                            {**coordinates, "confirmation": lifecycle.confirm_delete(journal)}
                        )
                else:
                    transaction_id = request.confirmation.transaction_id
                    result = execute_confirmed_delete(
                        request,
                        transaction_id=transaction_id,
                        lifecycle=lifecycle,
                        root=self.root,
                        host=host,
                        coordinates=coordinates,
                        require_login=require_login,
                        remove_host=self._remove_retired_host,
                        sign_in_changed=self._sign_in_changed,
                    )
        except ProfileCustodyTransactionConflictError:
            result = ProfileDeleteRefused.model_validate(
                {
                    **coordinates,
                    "code": "custody_changed",
                    "transaction_id": transaction_id,
                }
            )
        except ProfileCustodyTransactionError:
            result = ProfileDeleteRefused.model_validate(
                {
                    **coordinates,
                    "code": "custody_refused",
                    "transaction_id": transaction_id,
                }
            )
        except (AutomationCustodyError, RefusalError) as error:
            result = AccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                code=error.reason,
            )
        except (OSError, CadrumoError, ShutdownIncompleteError, ExceptionGroup):
            result = ProfileDeleteRefused.model_validate(
                {
                    **coordinates,
                    "code": "cleanup_incomplete",
                    "transaction_id": transaction_id,
                }
            )
        finally:
            if reserved:
                with self._guard:
                    self._custody_mutations.discard(request.profile_id)
        write_document(channel, result, deadline=time.monotonic() + 5)
