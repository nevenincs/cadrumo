"""Encrypted admission intent retained independently of expiring session leases."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, model_validator

from ...core.hashing import content_hash_hex
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..user_profile.access_contracts import AccessAction, AccessScope, OperationAccessRequest, ProfileAccessBinding
from .models import OperationIdentity, OperationRequest


class OperationAdmissionProvenance(BaseModel):
    """Original authority ceiling and publication, never a reusable credential.

    The complete record belongs in the existing encrypted operand store. The
    ordinary journal retains only its digest. Input revisions and domain record
    coordinates remain in the exact typed request bound by this fingerprint.
    Reader incarnation is deliberately absent: reopening the same immutable
    publication in another process does not change its logical generation.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    schema_version: Literal[2] = 2
    identity: OperationIdentity
    profile_binding: ProfileAccessBinding
    approved_scope: AccessScope
    admitted_request: OperationAccessRequest
    authority_generation: ContentDigest
    request_fingerprint: ContentDigest

    @model_validator(mode="after")
    def _bind_admitted_request(self) -> Self:
        """Keep resolved output coordinates attached to this exact original admission."""
        if (
            self.admitted_request.action is not AccessAction.SUBMIT
            or self.admitted_request.profile_id != self.profile_binding.profile_id
            or self.admitted_request.definition_id != self.identity.definition_id
        ):
            raise ValueError("admitted access must describe this invocation's profile and definition")
        return self

    def require_invocation[Payload: BaseModel](
        self, identity: OperationIdentity, request: OperationRequest[Payload]
    ) -> None:
        """Refuse provenance substituted from a different invocation or operand."""
        if (
            self.identity != identity
            or identity.definition_id != request.definition_id
            or identity.subject_ref != request.subject_ref
            or self.request_fingerprint != content_hash_hex(request.payload.model_dump(mode="json"))
        ):
            raise ValueError("operation admission provenance does not match stored invocation")
