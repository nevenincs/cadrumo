"""Protected lifecycle controls over the existing profile authority and custody."""

from __future__ import annotations

import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from pydantic import SecretBytes

from ...adapters.local_runtime.framing import read_secret, write_document
from ...adapters.persistence.storage.profile_custody import build_profile_custody_port
from ...application.runtime.access_management import (
    RuntimeAccessManagementRequest,
    RuntimeAutomationDenied,
    RuntimeAutomationDeny,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileRecoveryPrepared,
    RuntimeProfileResume,
    RuntimeProfileResumed,
    RuntimeSessionInventoryReply,
)
from ...application.runtime.contracts import RuntimeByteChannel
from ...application.runtime.profile_access import RuntimeAccessRefusal, RuntimeSecretReady
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.automation_enrollment import AdministrationFacts
from ...application.user_profile.automation_lifecycle import AutomationDenial
from ...application.user_profile.automation_lifecycle_service import AutomationLifecycleService, AutomationResumeRequest
from ...application.user_profile.custody_ports import bind_profile_custody_port
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
            [RuntimeConnectionContext, RuntimeByteChannel, RuntimeAccessManagementRequest],
            tuple[ProfileConnection, RuntimeProfileHost],
        ],
        validate: Callable[[ProfileConnection, RuntimeProfileHost], None],
        lock_changed: Callable[[UUID], None],
        synchronize: Callable[[RuntimeProfileHost], None],
    ) -> None:
        """Receive exact current connection composition and existing lifecycle owners."""
        self._resolve, self._validate = resolve, validate
        self._lock_changed, self._synchronize = lock_changed, synchronize

    def handle(
        self, context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeAccessManagementRequest
    ) -> None:
        """Require human authority or a separately bound fresh-password journey."""
        try:
            connection, host = self._resolve(context, channel, request)
            owner = RuntimeLifecycleOwner(host, connection, self._validate, self._lock_changed)
            service = AutomationLifecycleService(
                custody=host.store, owner=owner, sessions=host.authority, storage_root=host.store.root
            )
            if isinstance(request, RuntimeProfileRecoveryPrepare):
                with owner.administration_guard():
                    lock = host.profile_lock_state()
                    connection.recovery_generation = lock.generation
                    result = RuntimeProfileRecoveryPrepared(
                        request_id=request.request_id,
                        runtime_boot_id=context.runtime_boot_id,
                        connection_id=context.connection_id,
                        profile_id=request.profile_id,
                        lock_generation=lock.generation,
                        globally_locked=lock.globally_locked,
                    )
            elif isinstance(request, RuntimeAutomationDeny):
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
                result = RuntimeAutomationDenied(
                    request_id=request.request_id,
                    runtime_boot_id=context.runtime_boot_id,
                    connection_id=context.connection_id,
                    receipt=receipt,
                )
            elif isinstance(request, RuntimeProfileResume):
                with owner.administration_guard():
                    facts = owner.facts()
                    if request.lock_generation != facts.profile.lock_generation:
                        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                write_document(
                    channel,
                    RuntimeSecretReady(
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
                    resumed = service.resume(
                        AutomationResumeRequest(
                            request_id=request.request_id,
                            profile_id=request.profile_id,
                            lock_generation=request.lock_generation,
                            grants=request.grants,
                        ),
                        password=SecretBytes(bytes(secret)),
                    )
                result = RuntimeProfileResumed(
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
                    write_document(
                        channel,
                        RuntimeSessionInventoryReply(
                            request_id=request.request_id,
                            runtime_boot_id=context.runtime_boot_id,
                            connection_id=context.connection_id,
                            sessions=sessions,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                return
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            result = RuntimeAccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=context.runtime_boot_id,
                connection_id=context.connection_id,
                code=error.reason,
            )
        # A successful global lock intentionally ends its caller's lease. This
        # exact nonsecret effect acknowledgement cannot require surviving access.
        write_document(channel, result, deadline=time.monotonic() + 5)
