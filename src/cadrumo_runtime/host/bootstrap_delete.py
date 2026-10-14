"""Runtime hosting for the existing confirmed single-target custody journal."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.application.bucket_maintenance.contracts import AssessBucketDeletionCommand
from cadrumo.application.bucket_maintenance.service import BucketMaintenanceService
from cadrumo.application.user_profile.access_contracts import Availability
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.custody_repository import ProfileCustodyTransactionRepository
from cadrumo.application.user_profile.custody_transactions import (
    ProfileCustodyTransactionConflictError,
    ProfileCustodyTransactionError,
    ProfileCustodyTransactionOperation,
)
from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle
from cadrumo.application.user_profile.profile_pointer import active_profile_pointer_transaction
from cadrumo.core.errors.hierarchy import CadrumoError
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

from .profile_host import ProfileConnection

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


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
        coordinates = dict(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            profile_id=request.profile_id,
        )
        transaction_id: UUID | None = None
        reserved = False
        try:
            if context.runtime_boot_id != self.boot or context.peer != channel.peer:
                raise RefusalError(RefusalCode.PEER_UNTRUSTED)
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
                    raise RefusalError(RefusalCode.DRAINING)
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
                if isinstance(request, ProfileDeletePrepare):
                    with active_profile_pointer_transaction(self.root) as pointer:
                        require_login()
                        if pointer.read().bucket_id == str(request.profile_id):
                            result = ProfileDeleteRefused.model_validate({**coordinates, "code": "selected_profile"})
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
                            result = ProfileDeletePrepared.model_validate(
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
                            raise ShutdownIncompleteError()
                        host.close()
                        self._remove_retired_host(host)
                    # Unknown lock evidence is never authorization for cleanup.
                    # Once execution starts, the serving owner finishes its journal
                    # even if the client disconnects before receiving the receipt.
                    with active_profile_pointer_transaction(self.root):
                        require_login()
                        receipt = lifecycle.delete(request.confirmation)
                    result = ProfileDeleted.model_validate({**coordinates, "receipt": receipt})
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
