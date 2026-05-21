"""Cross-store integrity validation for a logical profile.

A logical profile fragments across a bucket directory, a plaintext
manifest, and an encrypted secure-object row. Each store independently
records the profile UUID; a torn write, a hand-edited manifest, or a
half-rolled-back create can leave them disagreeing. Serving such a
profile silently is the ``missing_profile_record`` / ghost-profile
defect class.

:func:`verify_profile_integrity` is the read-time gate
:class:`ProfileRepository.load` runs on every load. It checks that the
manifest ``bucket_id``, the on-disk directory name, and the
:class:`UserProfileRecord.profile_id` all agree on the profile UUID.
Decryption and pydantic validation of the record happen earlier in
``load`` itself — by the time this gate runs the record is already a
validated object, so this function is a pure cross-store identity
comparison. It raises :class:`ProfileIntegrityError` on any
disagreement — the repository never returns an inconsistent aggregate.
"""

from __future__ import annotations

from ...domain.user_profile import ProfileNotFoundError


class ProfileIntegrityError(ProfileNotFoundError):
    """Raised when a profile's physical stores disagree on its identity.

    Inherits from :class:`ProfileNotFoundError` so existing handlers
    that catch the broader profile-resolution family also catch
    cross-store drift; an inconsistent profile is, for every consumer
    purpose, not a usable profile.
    """


def verify_profile_integrity(
    *,
    profile_id: str,
    directory_name: str,
    manifest_bucket_id: str,
    record_profile_id: str,
    manifest_status: str,
    record_status: str,
) -> None:
    """Assert every physical store agrees on the profile UUID and status.

    The three cross-store identity claims are:

    - ``directory_name`` — the ``<root>/buckets/<name>/`` directory the
      bucket lives in.
    - ``manifest_bucket_id`` — the ``bucket_id`` key in the plaintext
      ``manifest.toml``.
    - ``record_profile_id`` — the ``profile_id`` on the decrypted
      :class:`UserProfileRecord`.

    All three must equal ``profile_id``.

    The lifecycle status is denormalised: the encrypted
    :class:`UserProfileRecord` carries the authoritative status and the
    plaintext manifest mirrors it so the manifest scan can exclude a
    tombstoned profile without decryption. ``manifest_status`` and
    ``record_status`` are the two copies of that mirror, compared by
    their string value. A disagreement is the drift state that
    re-opens the tombstone leak — a manifest saying ``active`` over a
    tombstoned record would let ``list`` / ``switch`` serve a deleted
    profile — so it must be surfaced, never served.

    A mismatch raises :class:`ProfileIntegrityError` naming the
    disagreeing stores so a ``repair`` surface — or the operator — can
    act on a concrete delta rather than a silent inconsistency.

    Raises:
        ProfileIntegrityError: If any store disagrees on the UUID, or
            the manifest and record disagree on the lifecycle status.
    """

    mismatches: list[str] = []
    if directory_name != profile_id:
        mismatches.append(f"bucket directory {directory_name!r}")
    if manifest_bucket_id != profile_id:
        mismatches.append(f"manifest bucket_id {manifest_bucket_id!r}")
    if record_profile_id != profile_id:
        mismatches.append(f"secure-record profile_id {record_profile_id!r}")
    if mismatches:
        raise ProfileIntegrityError(
            f"profile {profile_id!r} has cross-store drift: "
            + ", ".join(mismatches)
            + f" do not agree with the profile id {profile_id!r}"
        )
    if manifest_status != record_status:
        raise ProfileIntegrityError(
            f"profile {profile_id!r} has cross-store lifecycle drift: "
            f"manifest status {manifest_status!r} does not agree with "
            f"secure-record status {record_status!r}"
        )


__all__ = ["ProfileIntegrityError", "verify_profile_integrity"]
