"""Protected lifecycle controls over the existing profile authority and custody."""

from __future__ import annotations

import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import ReceiptDeletion
from cadrumo.adapters.persistence.storage.profile_custody import build_profile_custody_port
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import AdministrationFacts
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenial
from cadrumo.application.user_profile.custody_ports import bind_profile_custody_port
from cadrumo.application.user_profile.session_retirement import SessionRetirementKind
from cadrumo_client.contracts.access_management import (
    AccessManagementRequest,
    AutomationDenied,
    AutomationDeny,
    ProfileRecoveryPrepare,
    ProfileRecoveryPrepared,
    ProfileResume,
    ProfileResumed,
    SessionInventoryReply,
)
from cadrumo_client.contracts.contracts import ByteChannel
from cadrumo_client.contracts.profile_access import AccessRefusal, SecretReady
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frame_io import read_secret, write_document, write_session_inventory

from ..application.automation_lifecycle_service import (
    AutomationLifecycleService,
    AutomationResumeRequest,
    HumanSignInRevocationResult,
)
from .profile_host import ProfileConnection, RuntimeProfileHost


@dataclass(frozen=True)
class RuntimeLifecycleOwner:
    """Fresh profile and native-login observations with the shared denial fence."""

    host: RuntimeProfileHost
    connection: ProfileConnection
    validate: Callable[[ProfileConnection, RuntimeProfileHost], None]
    lock_changed: Callable[[UUID], None]

    @contextmanager
    def administration_guard(self) -> Generator[None]:
        """Keep current authority and publication serialized with private effects."""
        with self.host.guard:
            self.validate(self.connection, self.host)
            yield

    def facts(self) -> AdministrationFacts:
        """Fresh password recovery has no lease; denial requires an existing human."""
        self.validate(self.connection, self.host)
        connection = self.connection
        if connection.session_id is not None:
            return self.host.authority.human_administration_facts(
                connection_id=connection.context.connection_id, session_id=connection.session_id
            )
        if connection.method != "management":
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        facts = self.host.facts(connection.context.connection_id)
        return AdministrationFacts(
            profile=facts.profile,
            context=facts.context,
            originating_login_id=connection.login.login_id,
            session=None,
        )

    def revoke_human_sign_in(self) -> HumanSignInRevocationResult:
        """Use the runtime's generation-first retirement after fresh recovery proof."""
        deletion, _ = self.host.revoke_human_sign_in(kind=SessionRetirementKind.REVOKED)
        return HumanSignInRevocationResult(
            receipt_removed=deletion is not ReceiptDeletion.RECEIPT_RETAINED,
            keychain_removed=deletion in {ReceiptDeletion.DELETED, ReceiptDeletion.NOT_REQUIRED},
        )

    def set_profile_lock(self, *, generation: int, locked: bool) -> None:
        """Fence memory before fallible durable denial, using the exact host."""
        self.host.set_profile_lock(generation=generation, locked=locked)
        if locked:
            self.lock_changed(self.host.store.binding.profile_id)


class RuntimeAccessManagement:
    """Transport projection of canonical security administration, not domain execution."""

    def __init__(
        self,
        *,
        resolve: Callable[
            [ConnectionContext, ByteChannel, AccessManagementRequest],
            tuple[ProfileConnection, RuntimeProfileHost],
        ],
        validate: Callable[[ProfileConnection, RuntimeProfileHost], None],
        lock_changed: Callable[[UUID], None],
        synchronize: Callable[[RuntimeProfileHost], None],
    ) -> None:
        """Receive exact current connection composition and existing lifecycle owners."""
        self._resolve, self._validate = resolve, validate
        self._lock_changed, self._synchronize = lock_changed, synchronize

    def handle(self, context: ConnectionContext, channel: ByteChannel, request: AccessManagementRequest) -> None:
        """Require human authority or a separately bound fresh-password journey."""
        try:
            connection, host = self._resolve(context, channel, request)
            owner = RuntimeLifecycleOwner(host, connection, self._validate, self._lock_changed)
            service = AutomationLifecycleService(
                custody=host.store, owner=owner, sessions=host.authority, storage_root=host.store.root
            )
            if isinstance(request, ProfileRecoveryPrepare):
                with owner.administration_guard():
                    lock = host.profile_lock_state()
                    connection.recovery_generation = lock.generation
                    result = ProfileRecoveryPrepared(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                        profile_id=request.profile_id,
                        lock_generation=lock.generation,
                        globally_locked=lock.globally_locked,
                    )
            elif isinstance(request, AutomationDeny):
                try:
                    receipt = service.deny(
                        AutomationDenial(
                            request_id=request.request_id,
                            binding=host.store.binding,
                            kind=request.kind,
                            target_id=request.target_id,
                        )
                    )
                finally:
                    self._synchronize(host)
                result = AutomationDenied(
                    request_id=request.request_id,
                    runtime_boot_id=context.runtime_boot_id,
                    connection_id=context.connection_id,
                    receipt=receipt,
                )
            elif isinstance(request, ProfileResume):
                with owner.administration_guard():
                    facts = owner.facts()
                    if request.lock_generation != facts.profile.lock_generation:
                        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                write_document(
                    channel,
                    SecretReady(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                    ),
                    deadline=time.monotonic() + 5,
                )
                with (
                    read_secret(channel, deadline=time.monotonic() + 10) as secret,
                    bind_profile_custody_port(build_profile_custody_port()),
                ):
                    try:
                        resumed = service.resume(
                            AutomationResumeRequest(
                                request_id=request.request_id,
                                profile_id=request.profile_id,
                                lock_generation=request.lock_generation,
                                grants=request.grants,
                            ),
                            password=SecretBytes(bytes(secret)),
                        )
                    finally:
                        self._synchronize(host)
                result = ProfileResumed(
                    request_id=request.request_id,
                    runtime_boot_id=context.runtime_boot_id,
                    connection_id=context.connection_id,
                    receipt=resumed,
                )
            else:
                with owner.administration_guard():
                    sessions = host.authority.session_inventory(
                        connection_id=context.connection_id, session_id=request.session_id
                    )
                    write_session_inventory(
                        channel,
                        SessionInventoryReply(
                            request_id=request.request_id,
                            runtime_boot_id=context.runtime_boot_id,
                            connection_id=context.connection_id,
                            sessions=sessions,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                return
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            result = AccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=context.runtime_boot_id,
                connection_id=context.connection_id,
                code=error.reason,
                sign_in=error.sign_in if isinstance(error, ProfileAccessRefusedError) else None,
            )
        # A successful global lock intentionally ends its caller's lease. This
        # exact nonsecret effect acknowledgement cannot require surviving access.
        write_document(channel, result, deadline=time.monotonic() + 5)
