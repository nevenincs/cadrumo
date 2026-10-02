"""Exact invocation coordinates for transient runtime approval custody."""

from uuid import UUID

from pydantic import BaseModel

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.models import OperationId
from ..user_profile.access_contracts import ProfileAccessBinding


class RuntimeApprovalBinding(BaseModel):
    """One owned invocation, never a bearer supplied by a frontend."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    worker_id: UUID
    runtime_boot_id: UUID
    profile_binding: ProfileAccessBinding
    connection_id: UUID
    session_id: UUID
    operation_id: OperationId
    enrollment_request_id: UUID
    review_digest: ContentDigest
