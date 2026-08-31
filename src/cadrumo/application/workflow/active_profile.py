"""Canonical active-profile selection and record-resolution contracts.

Workflow state is an encrypted record and must not become a second import
surface for the process-wide active-profile selector.  This module owns the
translation from that core selector to a committed capsule and its authenticated
profile record.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.config import override_settings
from ...core.errors.hierarchy import NoActiveProfileError
from ...core.logging import get_logger
from ...core.profile_session import ProfileRecordUnavailability
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from .profile_bucket_scan import resolve_profile_bucket

if TYPE_CHECKING:
    from ...domain.user_profile.values import UserProfileRecord

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ActiveProfileRecordResolution:
    """One active-profile record read, together with why it produced nothing.

    Exactly one of :attr:`record` and :attr:`unavailability` is populated.
    The dataclass never crosses a serialization boundary, so it deliberately
    avoids eagerly importing the domain profile model at module import time.
    """

    record: UserProfileRecord | None = None
    unavailability: ProfileRecordUnavailability | None = None

    def __post_init__(self) -> None:
        """Require exactly one resolved record or unavailability reason."""
        if (self.record is None) == (self.unavailability is None):
            raise ValueError("an active-profile record resolution carries either a record or one reason, never both")


def active_profile_selection() -> tuple[str | None, str | None]:
    """Return the raw active selector and its canonical live bucket UUID."""
    identifier = resolve_active_bucket_id()
    if identifier is None:
        return None, None
    pointer = resolve_profile_bucket(identifier)
    return identifier, pointer.bucket_id if pointer is not None else None


def require_active_profile_bucket_id() -> str:
    """Return the selected committed bucket or raise the canonical refusal."""
    _identifier, bucket_id = active_profile_selection()
    if bucket_id is None:
        raise NoActiveProfileError(translated_message="application.workflow.errors.no_active_profile_bucket")
    return bucket_id


def resolve_active_profile_record() -> ActiveProfileRecordResolution:
    """Read the active profile record and name the reason when it is absent."""
    from ...domain.user_profile.errors import ProfileNotFoundError
    from ..user_profile.profile_record_repository import (
        ProfileRecordRepository,
        profile_record_session_if_authenticated,
    )

    identifier, bucket_id = active_profile_selection()
    if bucket_id is None:
        if identifier is not None:
            _log.debug("active profile record resolution found no live bucket for the selected profile")
        return ActiveProfileRecordResolution(unavailability=ProfileRecordUnavailability.NO_LIVE_CAPSULE)

    with override_settings(cadrumo_active_profile=bucket_id):
        session = profile_record_session_if_authenticated(bucket_id)
        if session is None:
            _log.debug("active profile record resolution found no authenticated session for the committed capsule")
            return ActiveProfileRecordResolution(unavailability=ProfileRecordUnavailability.SESSION_REQUIRED)
        try:
            record = ProfileRecordRepository(session=session).load(bucket_id)
        except ProfileNotFoundError as exc:
            _log.debug("active profile record resolution hit a mis-addressed session: %s", type(exc).__name__)
            return ActiveProfileRecordResolution(
                unavailability=ProfileRecordUnavailability.SESSION_IDENTITY_MISMATCH,
            )
    return ActiveProfileRecordResolution(record=record)


def active_transaction_catalogue_repository[RepositoryT: TransactionCatalogueRepositoryProtocol](
    *,
    repository_factory: Callable[[str], RepositoryT],
) -> RepositoryT:
    """Compose the active bucket's transaction catalogue through an outward factory."""
    from ...domain.transactions.errors import LedgerNoActiveBucketError

    try:
        bucket_id = require_active_profile_bucket_id()
    except NoActiveProfileError as exc:
        raise LedgerNoActiveBucketError(
            translated_message="application.workflow.errors.no_active_profile_bucket",
            context={"repository": "transaction_catalogue", "operation": "resolve_active_bucket"},
        ) from exc
    return repository_factory(bucket_id)


__all__ = [
    "ActiveProfileRecordResolution",
    "active_profile_selection",
    "active_transaction_catalogue_repository",
    "require_active_profile_bucket_id",
    "resolve_active_profile_record",
]
