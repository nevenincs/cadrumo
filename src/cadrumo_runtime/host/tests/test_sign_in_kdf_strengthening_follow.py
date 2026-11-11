"""A password sign-in that replaced its own profile's custody is proved again on the successor and admitted.

The worker re-wraps a fallback envelope at a stronger point inside a password
proof and then refuses that proof as custody changed. These tests commit a real
strengthening replacement at exactly that point of the real proof, through the
same application door the worker uses, and then let the real runtime decide:
it retires the replaced incarnation, launches a worker bound to the committed
generation, proves the same password there and admits the sign-in. An attempt
cancelled meanwhile is not followed, and the replacement it committed stands.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.custody_ports import (
    load_profile_custody_password_material,
    unlock_profile_custody_password,
)
from cadrumo.application.user_profile.kdf_strength import ProfileKdfStrength
from cadrumo.application.user_profile.passphrase_rotation import strengthen_profile_password_kdf
from cadrumo.core.operations import OperationFrontendProjection
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ...adapters.tests.profile_worker_support import PROFILE_INPUT
from ..session_owner import ProfileWorkerSessionOwner
from .served_runtime import connect_verified
from .test_service_records import ServiceRecordRuntime, service_record_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_STRONGER = ProfileKdfStrength(memory_mib=64, iterations=4, parallelism=1)


def _strengthen(root: Path, profile_id: UUID) -> None:
    material = load_profile_custody_password_material(profile_id, root=root)
    dek = unlock_profile_custody_password(material, password=PROFILE_INPUT).dek
    assert strengthen_profile_password_kdf(
        profile_id=profile_id,
        password=PROFILE_INPUT,
        dek=dek,
        proven_envelope_digest=material.envelope.self_digest,
        strength=_STRONGER,
        profile_decode_context=profile_authority_contexts()[1],
        root=root,
    )


def _replace_during_first_proof(
    monkeypatch: pytest.MonkeyPatch, profile_id: UUID, replace: Callable[[], None]
) -> list[int]:
    """Commit ``replace`` inside the first real proof of ``profile_id`` and refuse it as the worker does.

    Returns the custody generation of each worker that proved the password.
    """
    original = ProfileWorkerSessionOwner.authenticate_human
    proved: list[int] = []

    @contextmanager
    def replacing(owner: ProfileWorkerSessionOwner, connection_id: UUID) -> Generator[object]:
        with original(owner, connection_id) as authenticated:
            if owner.identity.binding.profile_id == profile_id:
                proved.append(owner.identity.binding.custody_generation)
                if len(proved) == 1:
                    # The login thread composes no adapters; the worker that strengthens does.
                    with profile_adapter_composition():
                        replace()
                    raise ProfileAccessRefusedError(AccessDenialCode.CUSTODY_CHANGED)
            yield authenticated

    monkeypatch.setattr(ProfileWorkerSessionOwner, "authenticate_human", replacing)
    return proved


def _client(runtime: ServiceRecordRuntime) -> FrontendClient:
    connection = connect_verified(runtime.endpoint)
    runtime.clients.append(connection)
    return FrontendClient(connection, profile_id=runtime.other_profile_id, frontend=OperationFrontendProjection.CLI)


def test_the_attempt_follows_its_own_replacement_onto_the_successor_and_is_admitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        root, profile_id = runtime.root, runtime.other_profile_id
        before = load_committed_profile_password_material(profile_id, root=root).envelope
        proved = _replace_during_first_proof(monkeypatch, profile_id, lambda: _strengthen(root, profile_id))

        admitted = _client(runtime).login_password(bytearray(PROFILE_INPUT.encode()))

        assert admitted.status.denial is None and admitted.status.session_id is not None
        assert proved == [before.password_generation, before.password_generation + 1]
        after = load_committed_profile_password_material(profile_id, root=root).envelope
        assert (after.kdf.memory_mib, after.kdf.iterations, after.kdf.parallelism) == (64, 4, 1)
        assert runtime.profiles._profiles[profile_id].store.binding.custody_generation == after.password_generation


def test_a_cancelled_attempt_is_not_followed_and_its_replacement_stands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        root, profile_id = runtime.root, runtime.other_profile_id
        before = load_committed_profile_password_material(profile_id, root=root).envelope

        def strengthen_then_cancel() -> None:
            _strengthen(root, profile_id)
            (attempt,) = (
                pending
                for pending in runtime.profiles._pending_logins.values()
                if pending.request.profile_id == profile_id
            )
            attempt.control.cancel()

        proved = _replace_during_first_proof(monkeypatch, profile_id, strengthen_then_cancel)

        with pytest.raises(FrontendRefusedError) as refused:
            _client(runtime).login_password(bytearray(PROFILE_INPUT.encode()))

        assert refused.value.reason == AccessDenialCode.CUSTODY_CHANGED.value
        assert proved == [before.password_generation]
        after = load_committed_profile_password_material(profile_id, root=root).envelope
        assert after.password_generation == before.password_generation + 1
