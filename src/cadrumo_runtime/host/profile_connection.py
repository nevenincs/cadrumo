"""Host-owned state for one runtime profile connection."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from cadrumo.application.user_profile.proof_cancellation import ProfileProofCancellation
from cadrumo_client.contracts.access_vocabulary import AccessScope
from cadrumo_client.contracts.login import LoginEvidence
from cadrumo_client.contracts.transport import ConnectionContext


@dataclass
class ProfileConnection:
    """Host-owned connection state, excluded from all wire and persisted documents."""

    context: ConnectionContext
    login: LoginEvidence
    client_id: UUID
    profile_id: UUID
    frontend: OperationFrontendProjection
    session_id: UUID | None = None
    method: str = "password"
    human_secret: bytearray | None = field(default=None, repr=False)
    persist_human_receipt: bool = False
    recovery_generation: int | None = None
    bootstrap_digest: str | None = None
    requested_scope: AccessScope | None = None
    owner_scope: tuple[OperationPublicContractSetV1, UUID, AccessScope] | None = field(
        default=None, repr=False, compare=False
    )
    disconnecting: bool = False
    human_admission_deadline: float | None = None
    human_proof_attempt_id: UUID | None = None
    human_proof_cancellation: ProfileProofCancellation | None = field(default=None, repr=False)
