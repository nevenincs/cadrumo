"""Typed JSON payloads for the commands that accept, revoke and list disputed Modelo figures."""

from __future__ import annotations

from ...core.identity.bucket import BucketId
from ...core.json_contract import OutputSchema


class DisagreementSourcePayload(OutputSchema):
    """One source of a disagreement and what it stated."""

    role: str
    source_family: str
    value: str


class DisagreementResolutionPayload(OutputSchema):
    """One stored resolution of a source disagreement: the operator's acceptance of the value in use."""

    finding_id: str
    key: str
    reached_casillas: list[str]
    sources: list[DisagreementSourcePayload]
    accepted_role: str
    reason: str
    state: str
    resolved_at: str
    resolved_by_session: str
    revoked_at: str | None = None
    revoked_by_session: str | None = None
    revision_id: str
    applies: bool


class WorkAcceptDisagreementResult(OutputSchema):
    """JSON envelope for ``aeat app modelo work accept-disagreement``."""

    bucket_id: BucketId
    calculation_revision_id: str
    resolution: DisagreementResolutionPayload


class WorkRevokeDisagreementResult(OutputSchema):
    """JSON envelope for ``aeat app modelo work revoke-disagreement``."""

    bucket_id: BucketId
    calculation_revision_id: str
    resolution: DisagreementResolutionPayload


class WorkDisagreementsResult(OutputSchema):
    """JSON envelope for ``aeat app modelo work disagreements``."""

    bucket_id: BucketId
    calculation_revision_id: str
    resolutions: list[DisagreementResolutionPayload]
    count: int


__all__ = [
    "DisagreementResolutionPayload",
    "DisagreementSourcePayload",
    "WorkAcceptDisagreementResult",
    "WorkDisagreementsResult",
    "WorkRevokeDisagreementResult",
]
