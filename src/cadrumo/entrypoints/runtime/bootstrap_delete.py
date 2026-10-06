"""Runtime hosting for the existing confirmed single-target custody journal."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from ...adapters.local_runtime.runtime_frame_io import write_document
from ...adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from ...application.bucket_maintenance.contracts import AssessBucketDeletionCommand
from ...application.bucket_maintenance.service import BucketMaintenanceService
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.bootstrap_delete import (
    RuntimeProfileDelete,
    RuntimeProfileDeleted,
    RuntimeProfileDeletePrepare,
    RuntimeProfileDeletePrepared,
    RuntimeProfileDeleteRefused,
)
from ...application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeShutdownIncompleteError,
)
from ...application.runtime.profile_access import RuntimeAccessRefusal
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_contracts import Availability
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.custody_repository import ProfileCustodyTransactionRepository
from ...application.user_profile.custody_transactions import (
    ProfileCustodyTransactionConflictError,
    ProfileCustodyTransactionError,
    ProfileCustodyTransactionOperation,
)
from ...application.user_profile.lifecycle import ProfileCapsuleLifecycle
from ...application.user_profile.profile_pointer import active_profile_pointer_transaction
from ...core.errors.hierarchy import CadrumoError
from .profile_host import ProfileConnection

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


class RuntimeBootstrapDeleteMixin:
    """Keep journal execution owned after client loss and outside client locks."""

    def bootstrap_delete(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileDeletePrepare | RuntimeProfileDelete,
    ) -> None:
        """Serialize containment with polling and shutdown; never wait inside root."""
        if not self._drain_guard.acquire(blocking=False):
            write_document(
                channel,
                RuntimeAccessRefusal(
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
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimeProfileDeletePrepare | RuntimeProfileDelete,
    ) -> None:
        coordinates = dict(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            profile_id=request.profile_id,
        )
        transaction_id: UUID | None = None
        reserved = False
        try:
            if (
                context.runtime_boot_id != self.boot
                or context.peer != channel.peer
                or request.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            with self._guard:
                prior = self._connections.get(context.connection_id)
                if prior is not None and (
                    prior.context != context
                    or prior.profile_id != request.profile_id
                    or prior.frontend != request.frontend
                    or prior.method != "bootstrap-delete"
                ):
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            connection = prior or ProfileConnection(
                context,
                self._capture(channel),
                uuid4(),
                request.profile_id,
                request.frontend,
                method="bootstrap-delete",
            )

            def require_login() -> None:
                observed = connection.login.observe(credential_facilities=Availability.UNAVAILABLE)
                if not self._admitting():
                    raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
                if not observed.active or not observed.unlocked or observed.os_owner_id != context.peer.os_owner_id:
                    raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)

            require_login()
            with self._guard:
                if request.profile_id in self._custody_mutations:
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                self._custody_mutations.add(request.profile_id)
                reserved = True
                self._connections[context.connection_id] = connection
                self._logins[connection.login.login_id] = connection.login
                host = self._profiles.get(request.profile_id)
            with composed_profile_persistence_ports(automation_secrets_store=self._secret_store()) as ports:
                lifecycle = ProfileCapsuleLifecycle(root=self.root)
                if isinstance(request, RuntimeProfileDeletePrepare):
                    with active_profile_pointer_transaction(self.root) as pointer:
                        require_login()
                        if pointer.read().bucket_id == str(request.profile_id):
                            result = RuntimeProfileDeleteRefused.model_validate(
                                {**coordinates, "code": "selected_profile"}
                            )
                        else:
                            assessment = BucketMaintenanceService(
                                bucket_storage=ports.bucket_storage(),
                                root=self.root,
                            ).assess_deletion(AssessBucketDeletionCommand(bucket_id=str(request.profile_id)))
                            if not assessment.exists or assessment.fingerprint != request.fingerprint:
                                raise ProfileCustodyTransactionConflictError("deletion preflight changed")
                            # The lifecycle owner checks current retention/holds and
                            # records the exact inventory before any destructive step.
                            journal = lifecycle.prepare_delete(
                                profile_id=request.profile_id,
                                requires_inactive_target=True,
                            )
                            transaction_id = journal.transaction_id
                            result = RuntimeProfileDeletePrepared.model_validate(
                                {
                                    **coordinates,
                                    "confirmation": lifecycle.confirm_delete(journal),
                                }
                            )
                else:
                    transaction_id = request.confirmation.transaction_id
                    repository = ProfileCustodyTransactionRepository(root=self.root)
                    journal = repository.load_journal(transaction_id)
                    if (
                        journal.operation is not ProfileCustodyTransactionOperation.DELETE
                        or not journal.requires_inactive_target
                        or journal.retention_override is not None
                        or lifecycle.confirm_delete(journal) != request.confirmation
                    ):
                        raise ProfileCustodyTransactionConflictError("deletion confirmation changed")
                    # This check is repeated by execute_delete under its root lock.
                    # No root/profile guard is retained while native workers settle.
                    with active_profile_pointer_transaction(self.root) as pointer:
                        if repository.load_receipt(transaction_id) is None and pointer.read().bucket_id == str(
                            request.profile_id
                        ):
                            raise ProfileCustodyTransactionConflictError("deletion target is selected")
                    require_login()
                    if host is not None:
                        with host.guard:
                            worker = host.owner.begin_drain()
                        deadline = time.monotonic() + 15
                        if worker is not None:
                            worker.drain(deadline=deadline)
                        if not host.owner.wait_construction(deadline=deadline):
                            raise RuntimeShutdownIncompleteError()
                        host.close()
                        self._remove_retired_host(host)
                    # Unknown lock evidence is never authorization for cleanup.
                    # Once execution starts, the serving owner finishes its journal
                    # even if the client disconnects before receiving the receipt.
                    with active_profile_pointer_transaction(self.root):
                        require_login()
                        receipt = lifecycle.delete(request.confirmation)
                    result = RuntimeProfileDeleted.model_validate({**coordinates, "receipt": receipt})
        except ProfileCustodyTransactionConflictError:
            result = RuntimeProfileDeleteRefused.model_validate(
                {
                    **coordinates,
                    "code": "custody_changed",
                    "transaction_id": transaction_id,
                }
            )
        except ProfileCustodyTransactionError:
            result = RuntimeProfileDeleteRefused.model_validate(
                {
                    **coordinates,
                    "code": "custody_refused",
                    "transaction_id": transaction_id,
                }
            )
        except (AutomationCustodyError, RuntimeRefusalError) as error:
            result = RuntimeAccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                code=error.reason,
            )
        except (OSError, CadrumoError, RuntimeShutdownIncompleteError, ExceptionGroup):
            result = RuntimeProfileDeleteRefused.model_validate(
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
