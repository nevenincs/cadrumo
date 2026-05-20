"""Cross-store integrity validation for a logical profile.

A logical profile fragments across a bucket directory, a plaintext
manifest, and an encrypted secure-object row. Each store independently
records the profile UUID; a torn write, a hand-edited manifest, or a
half-rolled-back create can leave them disagreeing. Serving such a
profile silently is the ``missing_profile_record`` / ghost-profile
defect class.

:func:`verify_profile_integrity` is the read-time gate
:class:`ProfileRepository.load` runs on every load. It checks the
manifest ``bucket_id``, the on-disk directory name, and the decrypted
:class:`UserProfileRecord.profile_id` all agree, and that the record
decrypts and validates. It raises :class:`ProfileIntegrityError` —
never returns an inconsistent aggregate.
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
) -> None:
    """Assert every physical store agrees on the profile UUID.

    The three cross-store identity claims are:

    - ``directory_name`` — the ``<root>/buckets/<name>/`` directory the
      bucket lives in.
    - ``manifest_bucket_id`` — the ``bucket_id`` key in the plaintext
      ``manifest.toml``.
    - ``record_profile_id`` — the ``profile_id`` on the decrypted
      :class:`UserProfileRecord`.

    All three must equal ``profile_id``. A mismatch raises
    :class:`ProfileIntegrityError` naming the disagreeing stores so a
    ``repair`` surface — or the operator — can act on a concrete delta
    rather than a silent inconsistency.

    Raises:
        ProfileIntegrityError: If any store disagrees on the UUID.
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


__all__ = ["ProfileIntegrityError", "verify_profile_integrity"]
