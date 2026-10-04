"""Canonical isolated profile-storage fixtures for CLI config tests."""

import json
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from click.testing import Result
from pydantic import TypeAdapter

from .....adapters.local_runtime.installation import runtime_installation
from .....adapters.local_runtime.tests.profile_worker_support import owner_id
from .....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from .....adapters.local_runtime.windows import WindowsRuntimeEndpoint
from .....adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from .....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from .....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from .....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .....application.user_profile.access_contracts import Availability, LoginEligibility, OsLockState, OsLoginContext
from .....application.user_profile.profile_record_repository import (
    ProfileRecordRepository,
    active_profile_record_session,
)
from .....core.config import override_settings
from .....domain.user_profile.values import UserProfileRecord
from ....runtime.profile_connections import RuntimeProfileConnections
from ...tests.cli_runner import invoke_cached_cli

#: The passphrase every profile these fixtures create is protected by.
CREDENTIAL_INPUT = "a-sufficiently-long-operator-passphrase"
_JSON_OBJECT: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])

#: Every flag a natural person with activity income needs before
#: ``complete-setup`` accepts the record.
COMPLETE_NATURAL_PERSON_FLAGS = (
    "--entity-type",
    "natural_person",
    "--tax-id",
    "12345678Z",
    "--name",
    "Ana",
    "--surnames",
    "Gil Ruiz",
    "--fiscal-residency",
    "resident_irpf",
    "--tax-residence-jurisdiction-scope",
    "common_regime",
    "--tax-residence-ccaa",
    "madrid",
    "--irpf-income-categories",
    "actividad_economica",
    "--activity",
    "Consultoria",
    "--iva-regime",
    "GENERAL",
    "--iva-m303-regime-composition",
    "general",
    "--no-iva-redeme-enrolled",
    "--no-iva-cash-accounting-regime-enrolled",
    "--no-iva-voluntary-sii-enrolled",
    "--no-iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
)


@pytest.fixture
def config_check_backend(tmp_path: Path) -> Iterator[None]:
    """Isolated storage/locale backend for the ``config check`` suites."""

    with (
        override_settings(cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
    ):
        yield


@pytest.fixture(name="_isolated_backend", autouse=True)
def config_check_isolated_backend(config_check_backend: None) -> None:
    """Autouse variant of :func:`config_check_backend` for the ``config check`` suites."""

    return config_check_backend


@pytest.fixture
def live_cli_profile(tmp_path: Path) -> Iterator[None]:
    """Create one incomplete profile through the real ``create`` verb.

    ``create`` leaves the new profile's session live in this process, so every
    later command in the test authenticates exactly as the operator's own
    session would, and reads records under the same pinned authority the CLI
    uses. Registering through a test-only authority instead binds the record to
    a different generation, which the CLI then refuses to read.
    """
    overrides = {
        "cadrumo_local_storage_root": tmp_path / "cadrumo-storage",
        "cadrumo_secret_passphrase": CREDENTIAL_INPUT,
    }
    with override_settings(**overrides):
        created = invoke_cached_cli(
            ("--format", "json", "config", "profile", "create", "Editor", "--quiet", "--secrets-stdin"),
            input=json.dumps({"passphrase": CREDENTIAL_INPUT, "passphrase_confirmation": CREDENTIAL_INPUT}),
        )
        assert created.exit_code == 0, created.output
        try:
            yield
        finally:
            close_active_bucket_session()


class _NativeLogin:
    login_id = "cli-config-test-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


@contextmanager
def native_profile_view_server(storage_root: Path, *, allow_unavailable_shutdown: bool = False) -> Iterator[None]:
    """Host real native profile workers for explicit password-backed CLI reads."""
    if sys.platform != "win32":
        pytest.skip("requires native Windows profile workers")
    endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
    runtime_installation(storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
    stop, boot, native = Event(), uuid4(), MemoryNativePort()
    profiles = RuntimeProfileConnections(
        storage_root=storage_root,
        storage_identity=endpoint.storage_identity,
        runtime_boot_id=boot,
        stop=stop,
        capture_login=lambda _channel: _NativeLogin(),
        secret_store=lambda: native,
    )
    profiles.prepare_registry()
    server = RetainedRuntimeTransportServer(
        endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(server.serve)
        try:
            assert server.ready.wait(3)
            yield
        finally:
            stop.set()
            try:
                try:
                    running.result(timeout=15)
                except RuntimeRefusalError as error:
                    if not allow_unavailable_shutdown or error.reason is not RuntimeRefusalCode.UNAVAILABLE:
                        raise
            finally:
                endpoint.close()


@pytest.fixture
def native_cli_profile_view(live_cli_profile: None, tmp_path: Path) -> Iterator[None]:
    """Opt-in native authority for tests whose assertion is the CLI view itself."""
    with native_profile_view_server(tmp_path / "cadrumo-storage"):
        yield


def profile_cli(*args: str) -> Result:
    """Run one ``config profile`` verb in JSON mode against the live profile."""
    if args == ("view",) or (args and args[0] in {"edit", "complete-setup"}):
        # Registration mints no receipt. This password is consumed only on
        # the verified secret frame for the explicit profile.
        return invoke_cached_cli(
            (
                "--format",
                "json",
                "--profile",
                "Editor",
                "--profile-secrets-stdin",
                "config",
                "profile",
                *args,
            ),
            input=json.dumps({"profile_passphrase": CREDENTIAL_INPUT}),
        )
    return invoke_cached_cli(("--format", "json", "config", "profile", *args))


def profile_view_document() -> dict[str, object]:
    """Return the parsed ``config profile view`` envelope, whatever its exit code."""
    return _JSON_OBJECT.validate_python(json.loads(profile_cli("view").stdout))


def profile_persisted_record() -> UserProfileRecord:
    """Read actual encrypted state for mutation tests without claiming runtime view."""
    session = active_profile_record_session()
    assert session is not None
    return ProfileRecordRepository.for_current_session(
        session.profile_id, profile_decode_context=session.profile_decode_context
    ).load(session.profile_id)


def profile_persisted_facts() -> dict[str, str]:
    """Return the live encrypted record's facts as path/value test evidence."""
    from .....application.user_profile.projections import record_to_path_values

    return record_to_path_values(profile_persisted_record())


def profile_event_count(event_type: str) -> int:
    """Count the live profile's history events of one type."""
    listed = profile_cli("history")
    assert listed.exit_code == 0, listed.output
    events = json.loads(listed.stdout)["result"]["events"]
    return sum(1 for event in events if event["event_type"] == event_type)


__all__ = [
    "COMPLETE_NATURAL_PERSON_FLAGS",
    "CREDENTIAL_INPUT",
    "config_check_backend",
    "config_check_isolated_backend",
    "live_cli_profile",
    "native_cli_profile_view",
    "native_profile_view_server",
    "profile_cli",
    "profile_event_count",
    "profile_persisted_facts",
    "profile_persisted_record",
    "profile_view_document",
]
