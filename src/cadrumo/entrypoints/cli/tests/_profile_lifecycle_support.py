"""Shared helpers for the profile-lifecycle CLI verb tests.

Both ``test_profile_lifecycle_verbs`` (record-level show / create / edit /
switch / repair) and ``test_profile_lifecycle_navigation`` (per-bucket
rename / import / delete / navigation from a no-active-session state) drive
the same ``aeat config profile`` surface, so they share one ``seed`` primitive
and one torn-bucket stager. Keeping those helpers in one module avoids
duplicating the storage-provisioning subtleties (key material, active-pointer
clearing) across two test files. The storage fixtures themselves stay local to
each test module so they cannot leak into the wider CLI test package.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from ....core.config import load_settings
from ....core.identity import nif_check_letter
from ....tests.bucket_layout import provision_bucket_directory
from ....tests.profile_capsule import open_test_profile_session
from ....tests.user_profile import register_cli_profile, register_minimal_profile


def _profile_id_for_label(label: str) -> str:
    digest = bytearray(hashlib.sha256(label.encode("utf-8")).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(UUID(bytes=bytes(digest)))


def stage_bucket_manifest(bucket_id: str, *, label: str) -> None:
    """Stage a ``missing_profile_record`` torn-bucket state under a real key.

    A bucket directory with no encrypted profile-value row is exactly the
    ``missing_profile_record`` torn state these CLI verbs must detect; this
    helper materialises that state directly through the bucket-layout
    primitives, since ``CommittedProfileRepository`` always writes the record
    alongside. The retired plaintext ``manifest.toml`` is staged as a STUB
    rather than a real record: the surfaces under test check the member's
    PRESENCE, never its content, and the model that once parsed it is gone.
    Reconstructing a schema nothing reads would be dressing up a fossil.

    Unlike the unsecured-backend version, this implementation uses
    ``open_test_profile_session`` to provision real key material for
    the bucket so the CLI can open a ``open_test_profile_session`` and
    reach the point where the missing record is detected. Without key
    material the session open fails before the torn state is observable.
    """

    # Provision the master key for the staged bucket so CLI commands can
    # open a session and reach the profile-record-missing detection point.
    with open_test_profile_session(bucket_id):
        pass

    root = load_settings().cadrumo_local_storage_root
    paths = provision_bucket_directory(root, bucket_id)
    (paths.bucket_dir / "manifest.toml").write_text(
        "\n".join(
            (
                "# Retired bucket manifest, staged for PRESENCE only.",
                f'bucket_id = "{bucket_id}"',
                f'label = "{label}"',
                "",
            )
        ),
        encoding="utf-8",
    )
    # Clear the active-profile pointer after provisioning so the staged
    # profile is not reported as the active one; the torn-state tests
    # specifically test non-active torn profiles.
    from ....application.user_profile import logout_active_profile

    logout_active_profile()


def seed(name: str = "default", *, tax_id: str | None = None) -> None:
    # ``register_minimal_profile`` derives a profile-unique NIF by
    # default so two ``seed`` calls never collide on the
    # duplicate-tax-id refusal; a test that asserts a specific tax id
    # passes it explicitly.
    #
    # open_test_profile_session provisions key material for the named
    # bucket and activates a real session so the profile lifecycle service
    # can resolve the file-backed secure-object repository.
    #
    overrides = {"identity.tax_id": tax_id} if tax_id is not None else None
    profile_id = _profile_id_for_label(name)
    with open_test_profile_session(profile_id):
        register_minimal_profile(profile_id=profile_id, display_name=name, overrides=overrides)


def distinct_nif(name: str) -> str:
    """Return a checksum-valid NIF derived deterministically from ``name``.

    ``profile create`` refuses two profiles that share a tax id, so a
    test creating several profiles needs a distinct, valid NIF per
    profile rather than one hard-coded literal.
    """

    number = int(hashlib.sha256(name.encode("utf-8")).hexdigest(), 16) % 100_000_000
    return f"{number:08d}{nif_check_letter(number)}"


def create_profile_via_cli(name: str, *, tax_id: str | None = None) -> None:
    """Register a profile through the shared CLI registration door."""
    register_cli_profile(
        label=name,
        facts={
            "identity.tax_id": tax_id or distinct_nif(name),
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": name.capitalize(),
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
        },
    )
