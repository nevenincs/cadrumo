"""The crash-recovery intent of one password-envelope replacement.

A password replacement changes two stores that no single write can cover: the
profile record row, whose header folds the envelope it was written under, and
the committed password envelope itself. The row is re-headed first and the
envelope swapped second, so a crash between them leaves a row naming an
envelope that was never published, and a profile that cannot read its own
record.

The intent closes that window. It is published, durably and exactly once,
before the re-head, and it carries everything a recovery needs without the
data key: the committed envelope it replaces, the replacement's exact bytes,
and the row header the record carries before and after the re-head. Those
headers are plaintext columns, so a recovery reads which side of the re-head
the record is on rather than guessing. It then rolls back (the re-head never
committed), rolls forward (the re-head committed and the swap did not) or
finishes (both did), and refuses every other combination.

The intent never holds a password or a data key. The proposed envelope is the
same public wrapper the capsule publishes, and it opens only under the new
password.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Final, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .....core.errors.hierarchy import pydantic_validation_boundary
from .....core.hashing import prefixed_digest, validate_prefixed_digest
from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_location
from .capsule import recognize_current_profile_capsule, replace_committed_profile_custody_envelope
from .digest_model import CustodyDigestModel
from .errors import ProfileCustodyRecordError
from .filesystem import (
    clear_profile_custody_local_record,
    read_optional_profile_custody_local_record,
    read_regular_file,
    write_profile_custody_local_record,
)
from .paths import profile_custody_path
from .records import (
    PROFILE_CUSTODY_ENVELOPE_FILENAME,
    PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
    parse_profile_custody_envelope,
)

if TYPE_CHECKING:
    from pathlib import Path

PROFILE_PASSWORD_REPLACEMENT_INTENT_MAX_BYTES: Final = 4096

_RECORD_NAMESPACE: Final = "cadrumo.application.user_profile.value"
"""The secure-object namespace of the one current profile record row."""

_DATABASE_RELATIVE_PATH: Final = storage_location(StorageCategory.BUCKET_DATABASE_FILE).subpath

_DATABASE_BUSY_TIMEOUT_SECONDS: Final = 30.0


class ProfilePasswordReplacementResolution(StrEnum):
    """What a recovery found and did for one profile's replacement intent."""

    NONE = "none"
    """No replacement was in flight."""

    ROLLED_BACK = "rolled_back"
    """The record was never re-headed; the committed envelope stands and the intent is discarded."""

    ROLLED_FORWARD = "rolled_forward"
    """The record was re-headed and the envelope was not; the replacement envelope is now published."""

    COMPLETED = "completed"
    """Both steps had committed; only the intent remained to discard."""


class ProfilePasswordReplacementIntent(CustodyDigestModel):
    """The durable, secret-free description of one in-flight password-envelope replacement."""

    _digest_maximum_bytes: ClassVar[int] = PROFILE_PASSWORD_REPLACEMENT_INTENT_MAX_BYTES
    _digest_subject: ClassVar[str] = "profile password replacement intent"
    _digest_mismatch_message: ClassVar[str] = "profile password replacement intent self_digest does not match"

    schema_version: Literal[1] = 1
    profile_id: UUID
    expected_envelope_sha256: str
    proposed_envelope: str = Field(min_length=1, max_length=PROFILE_CUSTODY_ENVELOPE_MAX_BYTES)
    previous_row_provenance: str = Field(min_length=1, max_length=255)
    rehead_row_provenance: str = Field(min_length=1, max_length=255)
    self_digest: str

    @field_validator("expected_envelope_sha256", "self_digest")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        return validate_prefixed_digest(value, field_name="password replacement digest")

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_replacement(self) -> ProfilePasswordReplacementIntent:
        envelope = parse_profile_custody_envelope(self.proposed_envelope_bytes)
        if envelope.profile_id != self.profile_id:
            raise ValueError("password replacement envelope names a different profile")
        if self.proposed_envelope_sha256 == self.expected_envelope_sha256:
            raise ValueError("password replacement envelope equals the envelope it replaces")
        if self.previous_row_provenance == self.rehead_row_provenance:
            raise ValueError("password replacement row headers do not differ")
        return self

    @property
    def proposed_envelope_bytes(self) -> bytes:
        """The exact canonical bytes the capsule publishes on completion."""
        return self.proposed_envelope.encode("utf-8")

    @property
    def proposed_envelope_sha256(self) -> str:
        """The compare-and-swap digest of the replacement envelope."""
        return prefixed_digest(self.proposed_envelope_bytes)

    @classmethod
    def create(
        cls,
        *,
        profile_id: UUID,
        expected_envelope: bytes,
        proposed_envelope: bytes,
        previous_row_provenance: str,
        rehead_row_provenance: str,
    ) -> ProfilePasswordReplacementIntent:
        """Describe replacing ``expected_envelope`` by ``proposed_envelope`` across one record re-head."""
        try:
            proposed_text = proposed_envelope.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProfileCustodyRecordError("password replacement envelope is not UTF-8") from exc
        return cls._create_with_self_digest(
            {
                "profile_id": profile_id,
                "expected_envelope_sha256": prefixed_digest(expected_envelope),
                "proposed_envelope": proposed_text,
                "previous_row_provenance": previous_row_provenance,
                "rehead_row_provenance": rehead_row_provenance,
            },
            "cannot construct profile password replacement intent",
        )


def profile_password_replacement_intent_path(profile_id: UUID, *, root: Path | None = None) -> Path:
    """The one intent path for ``profile_id``: a hidden sibling of its capsule, never a capsule member.

    Outside the capsule on purpose: the capsule's member set and inventory stay
    exactly what they are, and a backup of the capsule never carries an
    in-flight intent.
    """
    capsule_path = profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, root=root).parent
    return capsule_path.parent / f".{profile_id}.password-replacement.json"


def stage_profile_password_replacement_intent(intent: ProfilePasswordReplacementIntent, *, root: Path) -> None:
    """Publish ``intent`` durably and exactly once; an existing intent is refused, never overwritten.

    The caller holds the custody transaction lock and has resolved any earlier
    intent first, so an existing one here means a replacement this caller did
    not account for.
    """
    write_profile_custody_local_record(
        profile_password_replacement_intent_path(intent.profile_id, root=root),
        intent.canonical_json_bytes(),
        publish_once=True,
    )


def clear_profile_password_replacement_intent(profile_id: UUID, *, root: Path) -> None:
    """Discard the profile's settled intent; an absent intent is already settled."""
    clear_profile_custody_local_record(profile_password_replacement_intent_path(profile_id, root=root))


def _load_intent(profile_id: UUID, *, root: Path) -> ProfilePasswordReplacementIntent | None:
    payload = read_optional_profile_custody_local_record(
        profile_password_replacement_intent_path(profile_id, root=root),
        maximum_bytes=PROFILE_PASSWORD_REPLACEMENT_INTENT_MAX_BYTES,
    )
    if payload is None:
        return None
    try:
        intent = ProfilePasswordReplacementIntent.model_validate_json(payload)
    except ValueError as exc:
        raise ProfileCustodyRecordError("profile password replacement intent is malformed") from exc
    if intent.canonical_json_bytes() != payload or intent.profile_id != profile_id:
        raise ProfileCustodyRecordError("profile password replacement intent is not this profile's canonical record")
    return intent


def _record_database(capsule_path: Path) -> sqlite3.Connection:
    database_file = capsule_path / _DATABASE_RELATIVE_PATH
    if not database_file.is_file() or database_file.is_symlink():
        raise ProfileCustodyRecordError("profile capsule holds no regular record database")
    return sqlite3.connect(
        f"{database_file.as_uri()}?mode=rw", uri=True, timeout=_DATABASE_BUSY_TIMEOUT_SECONDS, isolation_level=None
    )


def profile_record_row_provenance(profile_id: UUID, *, root: Path) -> str:
    """Read the current record row's plaintext header without the data key.

    The header is the lineage witness the record store writes beside the
    ciphertext; reading it decrypts nothing. Anything but exactly one row is
    refused, as the record store itself refuses it.
    """
    capsule_path = _committed_capsule(profile_id, root=root)
    with closing(_record_database(capsule_path)) as database:
        rows = database.execute(
            "SELECT write_provenance FROM secure_objects WHERE namespace = ?", (_RECORD_NAMESPACE,)
        ).fetchall()
    if len(rows) != 1 or not isinstance(rows[0][0], str):
        raise ProfileCustodyRecordError("profile capsule must hold exactly one headed current record row")
    return rows[0][0]


def make_profile_record_durable(profile_id: UUID, *, root: Path) -> None:
    """Make every committed record write durable before a step that relies on it.

    The record database runs in WAL mode with ``synchronous=NORMAL``, under
    which a committed transaction survives a process crash but can be lost on
    power failure. A full checkpoint syncs the log and copies it into the
    database file, so after it returns the re-head is on disk however the
    host stops. A checkpoint that a reader keeps from completing is refused
    rather than taken as durable.
    """
    capsule_path = _committed_capsule(profile_id, root=root)
    with closing(_record_database(capsule_path)) as database:
        database.execute("PRAGMA synchronous=FULL")
        busy, _log_frames, _checkpointed = database.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
    if busy:
        raise ProfileCustodyRecordError("profile record database could not be checkpointed durably")


def _committed_capsule(profile_id: UUID, *, root: Path) -> Path:
    capsule_path = recognize_current_profile_capsule(profile_id, root=root)
    if capsule_path is None:
        raise ProfileCustodyRecordError("profile capsule is not committed")
    return capsule_path


def resolve_profile_password_replacement(profile_id: UUID, *, root: Path) -> ProfilePasswordReplacementResolution:
    """Settle ``profile_id``'s in-flight replacement, if any, into exactly one consistent state.

    The caller holds the custody transaction lock. Read without the data key:
    the committed envelope's digest and the record row's header decide it.
    Every combination the replacement's own step order cannot produce is
    refused and the intent is kept, so nothing is guessed and nothing is lost.
    """
    intent = _load_intent(profile_id, root=root)
    if intent is None:
        return ProfilePasswordReplacementResolution.NONE
    capsule_path = _committed_capsule(profile_id, root=root)
    committed_sha256 = prefixed_digest(
        read_regular_file(
            capsule_path / "custody" / PROFILE_CUSTODY_ENVELOPE_FILENAME,
            maximum_bytes=PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
        )
    )
    row_provenance = profile_record_row_provenance(profile_id, root=root)
    if committed_sha256 == intent.proposed_envelope_sha256:
        if row_provenance != intent.rehead_row_provenance:
            # The swap follows a durable re-head, so this state needs a lost write the order rules out.
            raise ProfileCustodyRecordError("replacement envelope is published over a record that was not re-headed")
        resolution = ProfilePasswordReplacementResolution.COMPLETED
    elif committed_sha256 != intent.expected_envelope_sha256:
        raise ProfileCustodyRecordError("committed password envelope matches neither side of the replacement")
    elif row_provenance == intent.previous_row_provenance:
        resolution = ProfilePasswordReplacementResolution.ROLLED_BACK
    elif row_provenance == intent.rehead_row_provenance:
        make_profile_record_durable(profile_id, root=root)
        replace_committed_profile_custody_envelope(
            profile_id,
            intent.proposed_envelope_bytes,
            expected_sha256=intent.expected_envelope_sha256,
            root=root,
        )
        resolution = ProfilePasswordReplacementResolution.ROLLED_FORWARD
    else:
        raise ProfileCustodyRecordError("profile record header matches neither side of the replacement")
    clear_profile_password_replacement_intent(profile_id, root=root)
    return resolution


__all__ = [
    "PROFILE_PASSWORD_REPLACEMENT_INTENT_MAX_BYTES",
    "ProfilePasswordReplacementIntent",
    "ProfilePasswordReplacementResolution",
    "clear_profile_password_replacement_intent",
    "make_profile_record_durable",
    "profile_password_replacement_intent_path",
    "profile_record_row_provenance",
    "resolve_profile_password_replacement",
    "stage_profile_password_replacement_intent",
]
