"""The worker identity bound to a published test profile capsule."""

from __future__ import annotations

import base64
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

from cadrumo.application.user_profile.access_contracts import (
    AccessSession,
    ProfileAccessBinding,
    SessionKind,
    SessionState,
)
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity

from ...custody.capsule import load_committed_profile_password_material


def published_capsule_identity(profile_id: UUID, root: Path) -> ProfileWorkerIdentity:
    """A fresh worker identity bound to the custody generation and DEK epoch the published capsule carries."""
    envelope = load_committed_profile_password_material(profile_id, root=root).envelope
    return ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=profile_id,
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=envelope.password_generation,
            dek_epoch=UUID(bytes=base64.b64decode(envelope.dek_epoch)),
        ),
    )


def worker_lease(
    identity: ProfileWorkerIdentity,
    *,
    kind: SessionKind = SessionKind.HUMAN,
    minutes: int = 15,
    issued_monotonic: float = 0.0,
) -> AccessSession:
    """An active all-action session on ``identity``; an API-key session also carries its grant and key."""
    human = kind is SessionKind.HUMAN
    issued = now()
    return AccessSession(
        session_id=uuid4(),
        binding=identity.binding,
        runtime_boot_id=identity.runtime_boot_id,
        profile_lock_generation=0,
        connection_id=uuid4(),
        client_id=uuid4(),
        kind=kind,
        originating_login_id="synthetic-os-login" if human else None,
        state=SessionState.ACTIVE,
        scope=AccessScope(
            operations=frozenset(),
            actions=frozenset(AccessAction),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        grant_id=None if human else uuid4(),
        grant_generation=None if human else 1,
        key_id=None if human else uuid4(),
        key_generation=None if human else 1,
        issued_at=issued,
        issued_monotonic=issued_monotonic,
        expires_at=issued + timedelta(minutes=minutes),
    )
