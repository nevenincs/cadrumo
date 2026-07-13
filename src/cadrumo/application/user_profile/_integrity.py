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

_INTEGRITY_IDENTITY_DRIFT_MESSAGE = "profile physical stores disagree on identity"
_INTEGRITY_STATUS_DRIFT_MESSAGE = "profile physical stores disagree on lifecycle status"
_INTEGRITY_LABEL_DRIFT_MESSAGE = "profile physical stores disagree on label"


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
    manifest_label: str,
    record_display_name: str,
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

    The display label is denormalised the same way: ``rename`` writes the
    encrypted record ``display_name`` and the plaintext manifest ``label`` as
    two copies of one value. A crash between those two writes leaves them
    divergent, and without this gate ``load`` would silently serve the stale
    manifest label over the renamed record forever, with no signal for
    ``repair``. ``manifest_label`` and ``record_display_name`` are compared by
    their string value and a disagreement is surfaced, never served.

    A mismatch raises :class:`ProfileIntegrityError` with sanitized
    context naming the disagreeing stores so a ``repair`` surface can
    act on a concrete delta without echoing raw profile identifiers.

    Args:
        profile_id: The canonical UUID the caller expects all stores to agree on.
        directory_name: The ``<root>/buckets/<name>/`` directory name.
        manifest_bucket_id: The ``bucket_id`` key from the plaintext manifest.
        record_profile_id: The ``profile_id`` from the decrypted record.
        manifest_status: The lifecycle status mirrored in the manifest.
        record_status: The authoritative lifecycle status from the record.
        manifest_label: The display label mirrored in the manifest.
        record_display_name: The authoritative display label from the record.

    Raises:
        ProfileIntegrityError: If any store disagrees on the UUID, the
            manifest and record disagree on the lifecycle status, or they
            disagree on the display label.
    """
    mismatches: list[str] = []
    if directory_name != profile_id:
        mismatches.append("bucket_directory")
    if manifest_bucket_id != profile_id:
        mismatches.append("manifest_bucket_id")
    if record_profile_id != profile_id:
        mismatches.append("secure_record_profile_id")
    if mismatches:
        raise ProfileIntegrityError(
            _INTEGRITY_IDENTITY_DRIFT_MESSAGE,
            translated_message="application.user_profile.errors.profile_integrity_identity_mismatch",
            context={"mismatches": tuple(mismatches)},
        )
    if manifest_status != record_status:
        raise ProfileIntegrityError(
            _INTEGRITY_STATUS_DRIFT_MESSAGE,
            translated_message="application.user_profile.errors.profile_integrity_status_mismatch",
            context={"mismatches": ("manifest_status", "secure_record_status")},
        )
    if manifest_label != record_display_name:
        raise ProfileIntegrityError(
            _INTEGRITY_LABEL_DRIFT_MESSAGE,
            translated_message="application.user_profile.errors.profile_integrity_label_mismatch",
            context={"mismatches": ("manifest_label", "secure_record_display_name")},
        )


__all__ = ["ProfileIntegrityError", "verify_profile_integrity"]
