"""Shared size refusal for operation results that must fit a registered byte bound."""

from __future__ import annotations

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.hashing import canonical_json_bytes
from ..user_profile.access_errors import ProfileAccessRefusedError


def refuse_oversized_result(result: BaseModel, limit: int) -> None:
    """Refuse a result whose canonical JSON exceeds *limit* bytes rather than omit content from it."""
    if len(canonical_json_bytes(result.model_dump(mode="json"))) > limit:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
