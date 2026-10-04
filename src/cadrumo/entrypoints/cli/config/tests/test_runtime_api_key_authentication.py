"""Installed CLI API-key admission uses the enrolled profile's scoped runtime."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime import runtime_credentials
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.user_profile.view_operation import PROFILE_VIEW_OPERATION_DEFINITION_ID
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections

from .....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "cli-api-key-test-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _view_scope(destination_id: UUID) -> AccessScope:
    return AccessScope(
        operations=frozenset({PROFILE_VIEW_OPERATION_DEFINITION_ID}),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.COMMIT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=destination_id,
                    projection_id=f"{PROFILE_VIEW_OPERATION_DEFINITION_ID}.result",
                    category=DisclosureCategory.PROFILE_VALUES,
                ),
                DisclosurePermission(
                    destination_id=destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            }
        ),
        periods=frozenset(),
        allow_period_independent=True,
        allow_delegation=False,
    )


def _invoke_api(*, profile_id: UUID, secret: str, command: tuple[str, ...]):
    return invoke_cached_cli(
        (
            "--format",
            "json",
            "--profile",
            str(profile_id),
            "--profile-auth-method",
            "api-key",
            "--profile-secrets-stdin",
            *command,
        ),
        input=json.dumps({"api_key": secret}),
    )


def _invoke_reference(*, profile_id: UUID, reference: UUID, command: tuple[str, ...]):
    return invoke_cached_cli(
        (
            "--format",
            "json",
            "--profile",
            str(profile_id),
            "--profile-auth-method",
            "api-key",
            "--profile-credential-ref",
            str(reference),
            *command,
        )
    )


def test_enrolled_api_key_and_reference_read_only_their_profile_and_cannot_become_human(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
        subject.owner.requesting = requester
        subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
            requester=requester, secrets_store=subject.client_native
        )
        scope = _view_scope(requester.client_id)
        facts = subject.owner.current
        assert facts.session is not None
        subject.owner.current = changed(
            facts,
            profile=changed(facts.profile, scope=scope),
            session=changed(facts.session, scope=scope),
        )
        proposal = changed(subject.proposal, scope=scope)
        request_id = uuid4()
        subject.service.request(request_id, proposal)
        completed = subject.approve(request_id)
        assert completed.credential_reference is not None
        record = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
        credential = subject.owner.delivery.endpoint.possession(record)
        assert credential is not None and completed.key_id is not None
        secret = credential.get_secret_value().decode("ascii")
        reference = completed.credential_reference
        profile_id = subject.store.binding.profile_id

        close_active_bucket_session()
        create, decode = profile_authority_contexts()
        foreign = register_profile_with_credentials(
            label="Foreign profile",
            passphrase=PROFILE_INPUT,
            profile_create_context=create,
            profile_decode_context=decode,
        )
        foreign_id = UUID(foreign.profile_id)
        close_active_bucket_session()

        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        monkeypatch.setattr(runtime_credentials, "installed_automation_secret_store", lambda: subject.client_native)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with override_settings(cadrumo_local_storage_root=root, cadrumo_output_language="en"):
                    shown = _invoke_api(profile_id=profile_id, secret=secret, command=("config", "profile", "view"))
                    assert shown.exit_code == 0, shown.output
                    document = json.loads(shown.stdout)
                    assert document["command"] == "config.profile.view"
                    assert document["result"]["display_name"] == "Enrollment tests"
                    assert document["result"]["profile_id"] == "<profile-id>"

                    by_reference = _invoke_reference(
                        profile_id=profile_id, reference=reference, command=("config", "profile", "view")
                    )
                    assert by_reference.exit_code == 0, by_reference.output
                    assert json.loads(by_reference.stdout)["result"] == document["result"]

                    reference_admin = _invoke_reference(
                        profile_id=profile_id, reference=reference, command=("config", "profile", "sessions")
                    )
                    assert reference_admin.exit_code == 2
                    missing_reference = _invoke_reference(
                        profile_id=profile_id, reference=uuid4(), command=("config", "profile", "view")
                    )
                    assert missing_reference.exit_code == 2
                    foreign_reference = _invoke_reference(
                        profile_id=foreign_id, reference=reference, command=("config", "profile", "view")
                    )
                    assert foreign_reference.exit_code == 2

                    human_only = _invoke_api(
                        profile_id=profile_id, secret=secret, command=("config", "profile", "sessions")
                    )
                    assert human_only.exit_code == 2

                    prefix, key_id, random_part = secret.split(".")
                    wrong_part = ("A" if random_part[0] != "A" else "B") + random_part[1:]
                    wrong_secret = ".".join((prefix, key_id, wrong_part))
                    bad_key = _invoke_api(
                        profile_id=profile_id, secret=wrong_secret, command=("config", "profile", "view")
                    )
                    assert bad_key.exit_code == 2

                    wrong_profile = _invoke_api(
                        profile_id=foreign_id, secret=secret, command=("config", "profile", "view")
                    )
                    assert wrong_profile.exit_code == 2

                for result in (
                    shown,
                    by_reference,
                    reference_admin,
                    missing_reference,
                    foreign_reference,
                    human_only,
                    bad_key,
                    wrong_profile,
                ):
                    assert secret not in result.output
                    assert wrong_secret not in result.output
                    assert str(reference) not in result.output
                for result in (
                    reference_admin,
                    missing_reference,
                    foreign_reference,
                    human_only,
                    bad_key,
                    wrong_profile,
                ):
                    assert '"facts"' not in result.output
                    assert '"result"' not in result.output
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    running.result(timeout=20)
                except Exception:
                    if primary is None:
                        raise
                finally:
                    endpoint.close()
