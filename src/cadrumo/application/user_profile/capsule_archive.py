"""Back a profile up to a sealed archive, and bring it back on another machine.

The archive is the operator's answer to "this machine is gone". It carries a
published capsule's custody material and its encrypted database, and it
restores through the SAME publication path a directory restore uses: both
readers produce a
:class:`~cadrumo.application.user_profile.ProfileCapsuleSource`, and exactly
one thing knows how to turn that into a published profile.

**Nothing here encrypts anything, and that is the design rather than an
omission.** Every member is already ciphertext under the operator's password:
the database is authenticated-encrypted under the profile's data key, and the
password envelope and sentinel protect that data key under supervised
Argon2id. Recovery is deliberately external. Wrapping the bundle a second time under the
same password would double the derivation cost at both ends, guard nothing an
attacker was not already facing, and mint a second key schedule over one
secret. The archive is exactly as strong as the password that already protects
the profile, and no stronger claim is made for it.

Three properties are enforced rather than documented.

The member set is INVARIANT. The schema-v1 recovery slot remains constant-size
but is required to carry the absent marker. Recovery artifacts are separate
restore proofs and never normal backup cargo.

The label never enters the archive. It lives in the published capsule as a
plaintext projection beside the ciphertext, so an archive built by copying the
capsule directory would publish the operator's chosen label to anyone who can
read a tar. Building from the capsule source excludes it structurally, because
that reader does not read it; the label is supplied again at import.

Identity is preserved verbatim. Bucket identity IS profile identity, so an
import that minted a new one would have cloned the profile rather than
restored it.
"""

from __future__ import annotations

from base64 import b64decode, b64encode
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ...core.product_identity import PRODUCT_IDENTITY
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import bounded_canonical_json_bytes, sha256_hex
from ...core.identity import BucketId
from ...core.time import now as _now
from .capsule_restore import ProfileCapsuleSource, read_profile_capsule_source
from .custody_ports import (
    ProfileCapsuleArchiveHeaderMaterial,
    load_profile_custody_password_material,
    parse_profile_custody_capsule_members,
    profile_capsule_archive_schema_version,
    profile_custody_recovery_envelope_path,
    read_profile_capsule_archive_container,
    write_profile_capsule_archive_container,
)

if TYPE_CHECKING:
    from pathlib import Path

_CAPSULE_ARCHIVE_PAYLOAD_SCHEMA_VERSION: Final[int] = 1

RECOVERY_SLOT_BYTES: Final[int] = 4096
"""Constant width of the recovery slot, enrolled or not.

Sized well above a real recovery wrapper (684 bytes measured) so the padding
never has to be revisited for an ordinary record, and refused rather than
truncated if one ever exceeds it. The width is what makes enrolment
un-inferable: a slot that shrank when absent would signal the absence just as
loudly as omitting it.
"""

_ABSENT_RECOVERY_LENGTH: Final[int] = 0
_SLOT_LENGTH_PREFIX_BYTES: Final[int] = 4
#: The largest capsule-archive payload this product will write.
#:
#: Public because it is a CROSS-LAYER contract, not an internal bound: the
#: sealed-archive reader in the storage adapter sets its own member ceiling at
#: or above this value, so no archive this product produced can carry a member
#: the reader refuses. The adapter deliberately keeps its own constant rather
#: than importing this one -- an adapter importing the application layer would
#: invert the dependency -- so the two are held equal by a test, and that test
#: needs a public name to compare against.
PROFILE_CAPSULE_ARCHIVE_MAX_PAYLOAD_BYTES: Final[int] = 512 * 1024 * 1024


class ProfileCapsuleArchiveError(CadrumoError):
    """Raised when an archive cannot be written or cannot be read back."""


class ProfileCapsuleArchiveReceipt(BaseModel):
    """Non-secret record of one archive export."""

    model_config = ConfigDict(frozen=True)

    bucket_id: BucketId
    target: str
    archive_schema_version: int
    recovery_enrolled: bool
    """Whether the source profile was enrolled when the archive was made.

    Recovery itself is never archive cargo; this receipt reports only the
    source state already visible to the authenticated local operator.
    """


class ProfileCapsuleArchiveInspection(BaseModel):
    """What an archive discloses without any key at all.

    Exactly the plaintext header. Every field here is readable by anyone
    holding the file, so nothing may be added to it that is a fact about the
    operator rather than about the archive.
    """

    model_config = ConfigDict(frozen=True)

    product: str
    bucket_id: BucketId
    archive_schema_version: int
    created_at: datetime
    manifest_digest: str


def export_profile_capsule_archive(
    *,
    profile_id: UUID,
    target: Path,
    root: Path | None = None,
    now: datetime | None = None,
) -> ProfileCapsuleArchiveReceipt:
    """Write the published capsule for ``profile_id`` to a sealed archive.

    Args:
        profile_id: The published profile to back up.
        target: Destination archive path. Refused if it already exists.
        root: Storage root override; the effective root when omitted.
        now: Creation instant for the header; the clock when omitted.

    Returns:
        A :class:`ProfileCapsuleArchiveReceipt` naming what was written.

    Raises:
        ProfileCapsuleArchiveError: When the capsule is not published, or a
            member does not fit the archive's invariant layout.
    """
    material = load_profile_custody_password_material(profile_id, root=root)
    source = read_profile_capsule_source(material.capsule_path)
    if source.password_envelope.profile_id != profile_id:
        raise ProfileCapsuleArchiveError("published capsule names a different profile than the export target")
    payload = _encode_payload(source)
    archive_schema_version = profile_capsule_archive_schema_version()
    header = ProfileCapsuleArchiveHeaderMaterial(
        product=PRODUCT_IDENTITY.python_package,
        bucket_id=str(profile_id),
        manifest_digest=sha256_hex(payload),
        archive_schema_version=archive_schema_version,
        created_at=(now or _now()).astimezone(UTC),
    )
    write_profile_capsule_archive_container(target, header=header, payload_bytes=payload)
    return ProfileCapsuleArchiveReceipt(
        bucket_id=str(profile_id),
        target=str(target),
        archive_schema_version=archive_schema_version,
        recovery_enrolled=profile_custody_recovery_envelope_path(material.capsule_path).exists(),
    )


def inspect_profile_capsule_archive(source: Path) -> ProfileCapsuleArchiveInspection:
    """Report what ``source`` discloses without decrypting anything.

    Reads the plaintext header only. This is what an operator can learn about
    an archive they are unsure of, and equally what anyone else can learn from
    a copy of it.
    """
    contents = read_profile_capsule_archive_container(source)
    return ProfileCapsuleArchiveInspection(
        product=contents.header.product,
        bucket_id=contents.header.bucket_id,
        archive_schema_version=contents.header.archive_schema_version,
        created_at=contents.header.created_at,
        manifest_digest=contents.header.manifest_digest,
    )


def read_profile_capsule_archive(source: Path) -> ProfileCapsuleSource:
    """Return the restorable capsule material carried by ``source``.

    The digest check below is the ONLY integrity check the payload gets. The
    sealed-archive transport is deliberately opaque: it stores and returns the
    bytes it was handed verbatim, names no payload type, and carries the
    header's ``manifest_digest`` without verifying it. So this is not
    belt-and-braces over a self-validating container -- match the header's
    digest against the payload it labels here, before any member is parsed, or
    a truncated or edited archive is partially believed.

    The result is the same type a capsule DIRECTORY produces, which is what
    lets an import and a directory restore converge on one publication path
    instead of growing a second one.

    Raises:
        ProfileCapsuleArchiveError: When the archive's digest does not match
            its payload, or a member is missing or will not parse.
    """
    contents = read_profile_capsule_archive_container(source)
    payload = contents.payload_bytes
    if sha256_hex(payload) != contents.header.manifest_digest:
        raise ProfileCapsuleArchiveError("archive payload does not match the digest its header declares")
    return _decode_payload(payload, expected_bucket_id=contents.header.bucket_id)


def _encode_payload(source: ProfileCapsuleSource) -> bytes:
    """Serialise one capsule source into the archive's invariant layout."""
    return bounded_canonical_json_bytes(
        {
            "schema_version": _CAPSULE_ARCHIVE_PAYLOAD_SCHEMA_VERSION,
            "profile_id": str(source.password_envelope.profile_id),
            "password_envelope": b64encode(source.password_envelope.canonical_json_bytes()).decode("ascii"),
            "sentinel": b64encode(source.sentinel.canonical_json_bytes()).decode("ascii"),
            "recovery_slot": b64encode(_encode_recovery_slot(source)).decode("ascii"),
            "database": b64encode(source.database_bytes).decode("ascii"),
        },
        maximum_bytes=PROFILE_CAPSULE_ARCHIVE_MAX_PAYLOAD_BYTES,
        subject="profile capsule archive payload",
    )


def _encode_recovery_slot(source: ProfileCapsuleSource) -> bytes:
    """Return the permanently empty recovery slot.

    The slot remains in schema v1 for layout stability, but portable recovery
    is a separate restore proof and never travels inside a normal archive.
    """
    body = b""
    capacity = RECOVERY_SLOT_BYTES - _SLOT_LENGTH_PREFIX_BYTES
    if len(body) > capacity:
        raise ProfileCapsuleArchiveError("recovery wrapper exceeds the archive's constant recovery slot")
    length = len(body) if body else _ABSENT_RECOVERY_LENGTH
    return length.to_bytes(_SLOT_LENGTH_PREFIX_BYTES, "big") + body + bytes(capacity - len(body))


def _decode_payload(payload_bytes: bytes, *, expected_bucket_id: str) -> ProfileCapsuleSource:
    """Parse the archive payload back into restorable capsule material."""
    import json

    try:
        decoded_payload: object = json.loads(payload_bytes.decode(UTF_8_ENCODING))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProfileCapsuleArchiveError("archive payload is not readable canonical JSON") from exc
    if not isinstance(decoded_payload, dict):
        raise ProfileCapsuleArchiveError("archive payload is not a canonical JSON object")
    payload = cast(dict[str, object], decoded_payload)
    if payload.get("schema_version") != _CAPSULE_ARCHIVE_PAYLOAD_SCHEMA_VERSION:
        raise ProfileCapsuleArchiveError("archive payload does not declare the current layout")
    if payload.get("profile_id") != expected_bucket_id:
        raise ProfileCapsuleArchiveError("archive payload names a different profile than its header")
    source = parse_profile_custody_capsule_members(
        envelope_bytes=_member(payload, "password_envelope"),
        sentinel_bytes=_member(payload, "sentinel"),
        database_bytes=_member(payload, "database"),
    )
    _decode_recovery_slot(_member(payload, "recovery_slot"))
    if (
        str(source.password_envelope.profile_id) != expected_bucket_id
        or source.sentinel.profile_id != source.password_envelope.profile_id
    ):
        raise ProfileCapsuleArchiveError("archive members do not agree on one profile identity")
    return ProfileCapsuleSource(
        password_envelope=source.password_envelope,
        sentinel=source.sentinel,
        database_bytes=source.database_bytes,
    )


def _decode_recovery_slot(slot: bytes) -> None:
    """Require the archive's recovery slot to be empty."""
    if len(slot) != RECOVERY_SLOT_BYTES:
        raise ProfileCapsuleArchiveError("archive recovery slot is not the constant width")
    length = int.from_bytes(slot[:_SLOT_LENGTH_PREFIX_BYTES], "big")
    if length == _ABSENT_RECOVERY_LENGTH:
        return None
    raise ProfileCapsuleArchiveError("archive recovery slot must not carry recovery material")


def _member(decoded: dict[str, object], key: str) -> bytes:
    """Return one base64 member, refusing a missing or malformed one by name."""
    raw = decoded.get(key)
    if not isinstance(raw, str):
        raise ProfileCapsuleArchiveError(f"archive payload is missing its {key}")
    try:
        return b64decode(raw, validate=True)
    except ValueError as exc:
        raise ProfileCapsuleArchiveError(f"archive payload carries a malformed {key}") from exc


__all__ = [
    "RECOVERY_SLOT_BYTES",
    "ProfileCapsuleArchiveError",
    "ProfileCapsuleArchiveInspection",
    "ProfileCapsuleArchiveReceipt",
    "export_profile_capsule_archive",
    "inspect_profile_capsule_archive",
    "read_profile_capsule_archive",
]
