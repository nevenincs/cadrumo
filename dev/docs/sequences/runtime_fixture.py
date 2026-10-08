"""Editable docs runtime host and its isolated, recorded profile-worker script.

This fixture uses native transport and real encrypted profile workers. Its
explicit login observation and unavailable automation secret store are test
controls. The three sign-out journeys additionally use synthetic shared receipt
custody; none establish native credential-store or installed-wheel acceptance.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import override
from uuid import UUID, uuid4

import keyring
import keyring.backends.null
import keyring.core
import pytest
from pydantic import BaseModel, Field, field_validator

from cadrumo.adapters.local_runtime.posix_endpoint import PosixRuntimeEndpoint
from cadrumo.adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
from cadrumo.application.exchange_rate_provider import bind_exchange_rate_provider_factory
from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
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
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.time.clock import frozen_clock
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.domain.filing import software_identity
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.runtime.worker import run
from cadrumo.tests.authority_run_snapshot import freeze_authority_root

# The native worker runs this trusted fixture as a bare script with ``-I``.
# Isolated mode omits the checkout root, so its dev-only sibling needs the
# same explicit bootstrap as the other standalone development entrypoints.
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dev.docs.sequences.receipt_fixture import RECEIPT_FIXTURE_DIRECTORY, SequenceReceiptKeyring

SANDBOX_INSTANT: datetime = datetime(2026, 4, 1, 9, 0, 0, tzinfo=UTC)
"""The canonical frozen instant for docs sequences and their profile workers."""


class _SequenceRuntimeTransportServer(RetainedRuntimeTransportServer):
    """Pin the fixture clock in the host's separate connection threads too."""

    @override
    def _connection(self, channel: RuntimeByteChannel) -> None:
        with frozen_clock(SANDBOX_INSTANT):
            super()._connection(channel)


_EXPORT_VERSION_FILE = "docs-export-version.json"
_EXPORT_VERSION_BYTES = 256
_WORKER_SCRIPT: ContextVar[Path | None] = ContextVar("sequence_worker_script", default=None)


@contextmanager
def sequence_worker_script(script: Path) -> Generator[None]:
    """Select a trusted instrumented copy for this developer sequence scope."""
    token = _WORKER_SCRIPT.set(script.resolve(strict=True))
    try:
        yield
    finally:
        _WORKER_SCRIPT.reset(token)


class _RecordedExportVersion(BaseModel):
    """A public export control for this trusted fixture, never installed metadata."""

    model_config = STRICT_FROZEN_CONFIG
    package_version: str = Field(min_length=1, max_length=32)

    @field_validator("package_version")
    @classmethod
    def _canonical_aux_version(cls, value: str) -> str:
        with pytest.MonkeyPatch.context() as selected:
            selected.setattr(software_identity, "PACKAGE_VERSION", value)
            software_identity.aeat_aux_version()
        return value


def _publish_export_version(sandbox_root: Path) -> None:
    recorded = _RecordedExportVersion(package_version=software_identity.PACKAGE_VERSION)
    with (sandbox_root / _EXPORT_VERSION_FILE).open("x", encoding="utf-8") as destination:
        destination.write(recorded.model_dump_json())


@contextmanager
def _recorded_export_version(sandbox_root: Path) -> Generator[None]:
    with (sandbox_root / _EXPORT_VERSION_FILE).open("rb") as source:
        raw = source.read(_EXPORT_VERSION_BYTES + 1)
    if len(raw) > _EXPORT_VERSION_BYTES:
        raise ValueError("recorded documentation export version exceeds its finite limit")
    recorded = _RecordedExportVersion.model_validate_json(raw)
    with pytest.MonkeyPatch.context() as selected:
        selected.setattr(software_identity, "PACKAGE_VERSION", recorded.package_version)
        yield


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
    receipt_root = root / RECEIPT_FIXTURE_DIRECTORY
    keyring.set_keyring(
        SequenceReceiptKeyring(receipt_root) if receipt_root.is_dir() else keyring.backends.null.Keyring()
    )
    try:
        with (
            _recorded_export_version(root.parent),
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
def sequence_runtime(root: Path, *, signed_in_profile: UUID | None = None) -> Generator[RetainedRuntimeTransportServer]:
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
    _publish_export_version(sandbox_root)
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
            worker_script=_WORKER_SCRIPT.get() or Path(__file__).resolve(),
            wall_clock=lambda: SANDBOX_INSTANT,
        )
        profiles.prepare_registry()
        server = _SequenceRuntimeTransportServer(
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
        # Poll terminal state without imposing an elapsed startup deadline.
        # A slow host can finish binding; a failed server still reports its
        # original exception instead of leaving the readiness wait parked.
        while not server.ready.wait(0.1):
            if running.done():
                running.result()
                raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_NOT_READY)
        if signed_in_profile is not None:
            _establish_synthetic_sign_in(signed_in_profile)
        yield server
    except BaseException as error:
        primary = error
        raise
    finally:
        owner.close_from_sync(task_name="docs-runtime-close", primary_error=primary)


def _establish_synthetic_sign_in(profile_id: UUID) -> None:
    """Mint real runtime-owned proof for the fixture's explicit sign-out scenario."""
    from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
    from cadrumo.application.operations.registry import OperationFrontendProjection

    client = asyncio.run(open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI))
    proof = bytearray(load_settings().cadrumo_dev_test_database_password.get_secret_value(), "utf-8")
    try:
        admitted = client.login_password(proof, persist_receipt=True)
        if admitted.human_login is None or not admitted.human_login.session_persisted:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    finally:
        proof[:] = bytes(len(proof))
        client.close()


if __name__ == "__main__":
    raise SystemExit(run(composition_factory=_worker_composition))
