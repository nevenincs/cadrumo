"""Finite binding inspection fixture over actual receipt storage and custody kernels.

The production resume readers verify the login and sign-in generation. This
additional test probe inspects those coordinates and exercises refused-receipt
deletion without opening a DEK; it is not a product status API.
"""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ......core.logging import get_logger
from ......core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...errors import KeyringUnavailableError, StorageValidationError
from .. import acceleration_receipt_crypto as _crypto
from ..acceleration_receipt import (
    PROFILE_SESSION_RECORD_MAX_BYTES,
    ReceiptDeletion,
    _clear_captured_receipt,
    _current_record,
    _decode_receipt,
    _delete_refused_receipt,
    _ensure_profile_session_directory,
    _profile_session_lock_path,
    _receipt_binding_refusal,
    _recover_pending_retirement,
    profile_session_path,
)
from ..errors import ProfileCustodyRecordError
from ..filesystem import (
    profile_custody_local_lock,
    profile_custody_root_lock,
    read_optional_profile_custody_local_record,
)
from ..sign_in_generation import SignInGenerationCustody, SignInGenerationObservation

_log = get_logger(__name__)


class ReceiptBindingVerdict(StrEnum):
    """Whether a receipt still belongs to the expected sign-in; only ``BOUND`` admits."""

    BOUND = "bound"
    """The receipt names this profile, the expected login and the current generation."""

    ABSENT = "absent"
    """No receipt exists; nothing to refuse or delete."""

    MALFORMED = "malformed"
    """The receipt bytes are not a canonical receipt of any schema."""

    SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"
    """The receipt was minted by another build's schema, before the binding existed."""

    PROFILE_MISMATCH = "profile_mismatch"
    """The receipt at this profile's path names another profile."""

    GENERATION_MISSING = "generation_missing"
    """No generation record exists, so no receipt can be current."""

    GENERATION_UNREADABLE = "generation_unreadable"
    """The generation record exists but cannot be read."""

    GENERATION_BINDING_MISMATCH = "generation_binding_mismatch"
    """The generation record fences other custody of this profile."""

    GENERATION_CHANGED = "generation_changed"
    """The receipt carries a generation that has since been advanced or replaced."""

    LOGIN_MISMATCH = "login_mismatch"
    """The receipt was minted for another OS login."""


class ReceiptBindingCheck(BaseModel):
    """Typed outcome of checking a receipt against the expected sign-in."""

    model_config = _STRICT_FROZEN

    verdict: ReceiptBindingVerdict
    deletion: ReceiptDeletion
    record: _crypto.PersistedProfileSession | None = None


def classify_profile_session_binding(
    *,
    record: _crypto.PersistedProfileSession,
    profile_id: UUID,
    login_id: str,
    generation: SignInGenerationObservation,
) -> ReceiptBindingVerdict:
    """Decide whether ``record`` belongs to the expected sign-in, with no I/O.

    It reads no file and no keychain, so a status probe may call it with its
    own generation observation. The generation fence is checked before the
    login: it is the revocation authority, and a fenced receipt is refused
    whichever login it names.
    """
    if record.profile_id != profile_id:
        return ReceiptBindingVerdict.PROFILE_MISMATCH
    refused = _receipt_binding_refusal(record=record, login_id=login_id, generation=generation)
    return ReceiptBindingVerdict.BOUND if refused is None else ReceiptBindingVerdict(refused.value)


def verify_profile_session_binding(*, sign_in: SignInGenerationCustody, login_id: str) -> ReceiptBindingCheck:
    """Check the profile's receipt against ``login_id`` and the current generation.

    The profile, storage root and custody come from ``sign_in``. The check
    runs under the custody root lock, which every generation write also
    holds, so an advance cannot interleave with it. Any verdict other than
    ``BOUND`` or ``ABSENT`` deletes the receipt and reports how far deletion
    got. This neither unwraps the DEK nor checks deadlines or custody; the
    resume readers keep those checks.

    Raises:
        ProfileCustodyRecordError: When the custody locks cannot be held.
    """
    storage_root = sign_in.root
    profile_id = sign_in.binding.profile_id
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    with profile_custody_root_lock(storage_root):
        generation = sign_in.observe()
        _ensure_profile_session_directory(path)
        with profile_custody_local_lock(_profile_session_lock_path(path)):
            try:
                _recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
            except (
                KeyringUnavailableError,
                ProfileCustodyRecordError,
                StorageValidationError,
                ValueError,
                ValidationError,
            ) as exc:
                # The journal concerns keys of other sessions; the receipt
                # read below still decides this check.
                _log.debug("profile-session retirement recovery deferred error_type=%s", type(exc).__name__)
            payload = read_optional_profile_custody_local_record(path, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES)
            if payload is None:
                return ReceiptBindingCheck(verdict=ReceiptBindingVerdict.ABSENT, deletion=ReceiptDeletion.NOT_REQUIRED)
            try:
                decoded = _decode_receipt(payload)
            except (ValueError, ValidationError):
                cleared = _clear_captured_receipt(path, payload=payload, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES)
                return ReceiptBindingCheck(
                    verdict=ReceiptBindingVerdict.MALFORMED,
                    deletion=ReceiptDeletion.DELETED if cleared else ReceiptDeletion.RECEIPT_RETAINED,
                )
            record = _current_record(decoded)
            if record is None:
                verdict = ReceiptBindingVerdict.SCHEMA_VERSION_MISMATCH
            else:
                verdict = classify_profile_session_binding(
                    record=record,
                    profile_id=profile_id,
                    login_id=login_id,
                    generation=generation,
                )
                if verdict is ReceiptBindingVerdict.BOUND:
                    return ReceiptBindingCheck(verdict=verdict, deletion=ReceiptDeletion.NOT_REQUIRED, record=record)
            return ReceiptBindingCheck(
                verdict=verdict,
                deletion=_delete_refused_receipt(path=path, payload=payload, decoded=decoded),
                record=record,
            )
