"""Resolve the exact profile's own taxpayer number inside its live worker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.errors.hierarchy import CadrumoError
from ..user_profile.access_errors import ProfileAccessRefusedError
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ..user_profile.projections import fact_value
from .errors import LiveApplicationInputError

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_PROFILE_TAX_ID_PATH = "identity.tax_id"
_UNRESOLVED_KEY = "application.live.profile_taxpayer_number.errors.unresolved"


def resolve_profile_taxpayer_number(bucket_id: str, authority_operation: PinnedAuthorityOperation) -> str:
    """Return the recorded taxpayer number of the profile this worker serves.

    The record is read under the operation's pinned authority and the worker's
    own authenticated profile session, so no second custody route opens it.

    Raises:
        ProfileAccessRefusedError: When the session does not serve this profile.
        LiveApplicationInputError: When the record is unreadable or records no
            taxpayer number, so a check of "the profile's own number" has no
            subject and no remote read starts.
    """
    try:
        record = ProfileRecordRepository.for_current_session(
            bucket_id,
            profile_decode_context=authority_operation.profile_decode_context(),
        ).load(bucket_id)
    except ProfileAccessRefusedError:
        raise
    except (CadrumoError, OSError) as exc:
        raise LiveApplicationInputError(translated_message=_UNRESOLVED_KEY) from exc
    recorded = fact_value(record, _PROFILE_TAX_ID_PATH)
    if recorded is None or not recorded.strip():
        raise LiveApplicationInputError(translated_message=_UNRESOLVED_KEY)
    return recorded.strip()


__all__ = ["resolve_profile_taxpayer_number"]
