"""Editable docs runtime host and its isolated, recorded profile-worker script.

This fixture uses native transport and real encrypted profile workers. Its
explicit login observation and unavailable secret store are test controls;
it does not establish native credential-store or installed-wheel acceptance.
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import copy_context
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import uuid4

import keyring
import keyring.backends.null
import keyring.core

from cadrumo.adapters.local_runtime.posix_endpoint import PosixRuntimeEndpoint
from cadrumo.adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
from cadrumo.application.exchange_rate_provider import bind_exchange_rate_provider_factory
from cadrumo.application.runtime.contracts import (
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    NativeSecretBackend,
)
from cadrumo.core.config import load_settings, override_settings
from cadrumo.core.time.clock import frozen_clock
from cadrumo.domain.calculations.registry.authority import bundled_authority_descriptor_path
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.runtime.worker import run
from cadrumo.tests.authority_run_snapshot import freeze_authority_root

SANDBOX_INSTANT: datetime = datetime(2026, 4, 1, 9, 0, 0, tzinfo=UTC)
"""The canonical frozen instant for docs sequences and their profile workers."""


class _UnavailableSecretStore:
    """Refuse every automation facility access without resolving a native provider."""

    @property
    def backend(self) -> NativeSecretBackend:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    def read(self, namespace: str, account: str) -> None:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    def replace(self, namespace: str, account: str, value: object) -> None:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)

    def delete(self, namespace: str, account: str) -> None:
        raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)


class _SequenceLoginObservation:
    """Explicit fixture login facts; native transport still verifies the peer."""

    def __init__(self, owner: str, login_id: str) -> None:
        self.owner, self.login_id = owner, login_id

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.owner,
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.INELIGIBLE,
            credential_facilities=credential_facilities,
        )


@contextmanager
def _worker_composition() -> Generator[None]:
    """Compose recorded dependencies after the canonical worker verifies its parent."""
    root = Path(load_settings().cadrumo_local_storage_root)
    previous_backend = keyring.core._keyring_backend
    keyring.set_keyring(keyring.backends.null.Keyring())
    try:
        with (
            override_settings(
                cadrumo_authority_root=root.parent / "docs-authority",
                cadrumo_output_language="en",
                cadrumo_live_tests_enabled="",
                cadrumo_live_tests_google="",
                cadrumo_log_dir=root / "logs" / "worker",
                cadrumo_llm_ollama_chat_url="http://127.0.0.1:1/api/chat",
            ),
            frozen_clock(SANDBOX_INSTANT),
            bind_exchange_rate_provider_factory(recorded_ecb_rate_provider),
            profile_adapter_composition(automation_secrets_store=_UnavailableSecretStore()),
        ):
            yield
    finally:
        keyring.core._keyring_backend = previous_backend


@contextmanager
def sequence_runtime(root: Path) -> Generator[RetainedRuntimeTransportServer]:
    """Serve the sandbox's exact endpoint before any installed frontend connects."""
    from cadrumo.adapters.local_runtime.tests.profile_worker_support import NativeRuntimeFixtureOwner

    # The parent carries a published authority in its Python settings context.
    # A fresh isolated child cannot inherit that context. Give the trusted
    # fixture script the same public generation through the existing snapshot
    # owner, without widening the native launch environment. Keep public bytes
    # beside private storage: Windows storage ACL propagation changes metadata
    # that the immutable authority reader correctly refuses after admission.
    selected = bundled_authority_descriptor_path().resolve(strict=True)
    staged = freeze_authority_root(selected.parent, root.parent / "docs-publication-stage")
    if staged is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    authority_root = root.parent / "docs-authority"
    sandbox_root = root.resolve(strict=True).parent
    if not staged.resolve(strict=True).is_relative_to(sandbox_root) or not authority_root.resolve().is_relative_to(
        sandbox_root
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    staged.rename(authority_root)
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=root)
    )
    stop, boot = Event(), uuid4()
    owner = NativeRuntimeFixtureOwner(endpoint, stop, timeout=25)
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="docs-runtime")
    owner.executor = pool
    primary: BaseException | None = None
    try:
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda channel: _SequenceLoginObservation(channel.peer.os_owner_id, str(boot)),
            secret_store=_UnavailableSecretStore,
            worker_script=Path(__file__).resolve(),
            wall_clock=lambda: SANDBOX_INSTANT,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint,
            product_version=version("cadrumo"),
            stop=stop,
            profiles=profiles,
            boot_id=boot,
        )
        context = copy_context()

        def serve() -> None:
            context.run(server.serve)

        running = pool.submit(serve)
        owner.running = running
        owner.server = server
        if not server.ready.wait(5):
            if running.done():
                running.result()
            raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_NOT_READY)
        yield server
    except BaseException as error:
        primary = error
        raise
    finally:
        owner.close_from_sync(task_name="docs-runtime-close", primary_error=primary)


if __name__ == "__main__":
    raise SystemExit(run(composition_factory=_worker_composition))
