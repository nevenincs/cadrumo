"""Synthetic encrypted profiles shared by native worker acceptance tests."""

from __future__ import annotations

import base64
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.master_key.active_session import (
    close_active_bucket_session,
    current_active_bucket_session,
)
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    AccessSession,
    ProfileAccessBinding,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.time.clock import now

PROFILE_INPUT = "synthetic-worker-password"


def changed[T: BaseModel](model: T, **values: object) -> T:
    return model.__class__.model_validate(
        {**{name: getattr(model, name) for name in model.__class__.model_fields}, **values}
    )


def owner_id() -> str:
    import win32api
    import win32security

    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), 8)
    try:
        sid, _ = win32security.GetTokenInformation(token, win32security.TokenUser)
        return win32security.ConvertSidToStringSid(sid)
    finally:
        win32api.CloseHandle(token)


@contextmanager
def worker_profiles(tmp_path: Path) -> Iterator[tuple[Path, tuple[tuple[ProfileWorkerIdentity, bytes], ...]]]:
    create, decode = profile_authority_contexts()
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        targets: list[tuple[ProfileWorkerIdentity, bytes]] = []
        boot, installation = uuid4(), uuid4()
        try:
            for index in range(2):
                result = register_profile_with_credentials(
                    label=f"Worker profile {index}",
                    passphrase=PROFILE_INPUT,
                    profile_create_context=create,
                    profile_decode_context=decode,
                )
                material = load_committed_profile_password_material(UUID(result.profile_id), root=root)
                session = current_active_bucket_session()
                assert session is not None
                targets.append(
                    (
                        ProfileWorkerIdentity(
                            worker_id=uuid4(),
                            runtime_boot_id=boot,
                            binding=ProfileAccessBinding(
                                profile_id=UUID(result.profile_id),
                                installation_id=installation,
                                os_owner_id=owner_id(),
                                custody_generation=material.envelope.password_generation,
                                dek_epoch=UUID(bytes=base64.b64decode(material.envelope.dek_epoch)),
                            ),
                        ),
                        session.dek,
                    )
                )
                close_active_bucket_session()
            yield root, tuple(targets)
        finally:
            close_active_bucket_session()


def lease(identity: ProfileWorkerIdentity, *, seconds: float = 120) -> AccessSession:
    instant = now()
    return AccessSession(
        session_id=uuid4(),
        binding=identity.binding,
        runtime_boot_id=identity.runtime_boot_id,
        profile_lock_generation=0,
        connection_id=uuid4(),
        client_id=uuid4(),
        kind=SessionKind.API_KEY,
        state=SessionState.ACTIVE,
        scope=AccessScope(
            operations=frozenset({"user-profile.field-mutation"}),
            actions=frozenset(AccessAction),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        grant_id=uuid4(),
        grant_generation=1,
        key_id=uuid4(),
        key_generation=1,
        issued_at=instant,
        issued_monotonic=time.monotonic(),
        expires_at=instant + timedelta(seconds=seconds),
    )
