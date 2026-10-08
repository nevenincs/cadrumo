"""Real Windows bootstrap reset with synthetic login and optional-store evidence."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from typing import Never, override
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.bootstrap import RuntimePasswordReset
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileLogin
from cadrumo.application.user_profile import recovery_custody
from cadrumo.application.user_profile.access_contracts import Availability, OsLockState, OsLoginContext
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.application.user_profile.custody_ports import (
    ProfileCustodyRecoveryMaterialPort,
    ProfileCustodyRecoveryUnlockPort,
)
from cadrumo.application.user_profile.recovery_custody import ProfileRecoveryError, enroll_profile_recovery
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections

from .test_access_management import _connect, _LoginObservation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]


class _MutableLogin(_LoginObservation):
    locked = False

    @override
    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        observed = super().observe(credential_facilities=credential_facilities)
        return observed.model_copy(update={"lock_state": OsLockState.UNKNOWN}) if self.locked else observed


@pytest.mark.parametrize("case", ["wrong-proof", "reset-and-replay", "unknown-at-commit", "publication-failure"])
def test_runtime_bootstrap_reset_keeps_proof_and_replay_fences(
    tmp_path: Path,
    case: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid_proof = case != "wrong-proof"
    login = _MutableLogin()
    original_rewrap = recovery_custody.rewrap_profile_passphrase_under_lock
    if case == "publication-failure":

        def failed_publication(**_arguments: object) -> Never:
            raise OSError("synthetic publication failure")

        monkeypatch.setattr(recovery_custody, "rewrap_profile_passphrase_under_lock", failed_publication)
    if case == "unknown-at-commit":
        original_unlock = recovery_custody.unlock_profile_custody_recovery

        def lose_observation(
            material: ProfileCustodyRecoveryMaterialPort, *, recovery_secret: str
        ) -> ProfileCustodyRecoveryUnlockPort:
            proven = original_unlock(material, recovery_secret=recovery_secret)
            login.locked = True
            return proven

        monkeypatch.setattr(recovery_custody, "unlock_profile_custody_recovery", lose_observation)

    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    stop, boot = Event(), uuid4()
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        profile = subject.store.binding.profile_id
        handed: list[str] = []
        enroll_profile_recovery(
            profile_id=profile,
            current_passphrase=PROFILE_INPUT,
            root=root,
            recovery_handover=lambda enrollment: handed.append(enrollment.recovery_key.code) or handed[-1],
        )
        close_active_bucket_session()
        original = load_committed_profile_password_material(profile, root=root).envelope
        generation = SignInGenerationCustody(root=root, binding=subject.store.binding)
        before = generation.establish().current
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: login,
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                wire = _connect(endpoint)
                client = RuntimeFrontendClient(wire, profile_id=profile, frontend=OperationFrontendProjection.CLI)
                code = bytearray(handed[0].encode() if valid_proof else b"not-the-recovery-code")
                replacement = bytearray(b"replacement-bootstrap-password-for-test")
                confirmation = bytearray(replacement)
                try:
                    if case == "publication-failure":
                        with pytest.raises(RuntimeFrontendRefusedError) as refused:
                            client.reset_password(
                                recovery_code=code, new_passphrase=replacement, new_passphrase_confirmation=confirmation
                            )
                        assert refused.value.reason == "unavailable"
                        fenced = generation.observe().current
                        assert fenced is not None and fenced.generation > before.generation
                        assert load_committed_profile_password_material(profile, root=root).envelope == original
                        monkeypatch.setattr(recovery_custody, "rewrap_profile_passphrase_under_lock", original_rewrap)
                        retry = RuntimeFrontendClient(
                            _connect(endpoint), profile_id=profile, frontend=OperationFrontendProjection.CLI
                        )
                        try:
                            completed = retry.reset_password(
                                recovery_code=bytearray(handed[0].encode()),
                                new_passphrase=bytearray(b"retried-bootstrap-password-for-test"),
                                new_passphrase_confirmation=bytearray(b"retried-bootstrap-password-for-test"),
                            )
                            assert completed.outcome.password_generation == original.password_generation + 1
                            retried_generation = generation.observe().current
                            assert retried_generation is not None and retried_generation.generation > fenced.generation
                        finally:
                            retry.close()
                    elif case == "unknown-at-commit":
                        with pytest.raises(RuntimeFrontendRefusedError) as refusal:
                            client.reset_password(
                                recovery_code=code, new_passphrase=replacement, new_passphrase_confirmation=confirmation
                            )
                        assert refusal.value.reason == "needs_user"
                        assert generation.observe().current == before
                        assert load_committed_profile_password_material(profile, root=root).envelope == original
                    elif valid_proof:
                        result = client.reset_password(
                            recovery_code=code,
                            new_passphrase=replacement,
                            new_passphrase_confirmation=confirmation,
                        )
                        assert result.outcome.password_generation == original.password_generation + 1
                        assert result.outcome.dek_epoch_preserved
                        assert result.human_sign_in_revocation.receipt_removed
                        changed = generation.observe().current
                        assert changed is not None and changed.generation > before.generation
                        replay_secret = bytearray(b"this must not reach a secret frame")
                        replay = wire.password_reset(
                            RuntimePasswordReset(
                                request_id=uuid4(),
                                profile_id=profile,
                                envelope_digest=original.self_digest,
                            ),
                            replay_secret,
                            deadline=time.monotonic() + 5,
                        )
                        assert isinstance(replay, RuntimeAccessRefusal)
                        assert replay.code is AutomationCustodyCode.CONFLICT
                        assert generation.observe().current == changed
                        promotion = wire.login(
                            RuntimeProfileLogin(
                                request_id=uuid4(),
                                profile_id=profile,
                                frontend=OperationFrontendProjection.CLI,
                                method="password",
                            ),
                            bytearray(b"must-not-be-sent"),
                            deadline=time.monotonic() + 5,
                        )
                        assert isinstance(promotion, RuntimeAccessRefusal)
                        assert promotion.code is AutomationCustodyCode.CONFLICT
                    else:
                        with pytest.raises(ProfileRecoveryError):
                            client.reset_password(
                                recovery_code=code,
                                new_passphrase=replacement,
                                new_passphrase_confirmation=confirmation,
                            )
                        assert generation.observe().current == before
                        assert load_committed_profile_password_material(profile, root=root).envelope == original
                    assert not any(code) and not any(replacement) and not any(confirmation)
                    with pytest.raises(RuntimeFrontendRefusedError) as missing_session:
                        _ = client.session_id
                    assert missing_session.value.reason == "authentication_required"
                finally:
                    client.close()
            finally:
                stop.set()
                running.result(timeout=25)
