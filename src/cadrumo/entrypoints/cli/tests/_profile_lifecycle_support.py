"""Shared helpers for the profile-lifecycle CLI verb tests.

Both ``test_profile_lifecycle_verbs`` (record-level show / create / edit /
switch / repair) and ``test_profile_lifecycle_navigation`` (per-bucket
rename / import / delete / navigation from a no-active-session state) drive
the same ``aeat config profile`` surface, so they share one ``seed`` primitive.
Keeping those helpers in one module avoids duplicating the storage-provisioning
subtleties (key material, active-pointer clearing) across two test files. The
storage fixtures themselves stay local to each test module so they cannot leak
into the wider CLI test package.

A prior ``stage_bucket_manifest`` helper staged a retired plaintext
``manifest.toml`` stub with no committed custody capsule behind it, to
simulate a ``missing_profile_record`` torn bucket. Listing and every
resolution path (``list_profile_buckets``, ``resolve_profile_bucket``,
``login_profile``) now project committed capsules exclusively and never
read the manifest, so a manifest-only, capsule-less bucket is invisible to
every operator-facing verb -- unreachable, not merely awkward -- and the
helper was retired along with the tests it staged for.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from ....core.identity import nif_check_letter
from ....tests.profile_capsule import open_test_profile_session
from ....tests.user_profile import register_cli_profile, register_minimal_profile


def _profile_id_for_label(label: str) -> str:
    digest = bytearray(hashlib.sha256(label.encode("utf-8")).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(UUID(bytes=bytes(digest)))


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


def create_profile_via_cli(name: str, *, tax_id: str | None = None, complete: bool = True) -> None:
    """Register a profile through the shared CLI registration door.

    ``complete=False`` stops after registration, leaving the profile in the
    state registration itself produces: a real, addressable, writable bucket
    whose setup was never committed. That is the only supported way to reach
    the incomplete state, because completion is a separate compare-and-swap
    rather than part of registration.
    """
    register_cli_profile(
        label=name,
        complete=complete,
        facts={
            "identity.tax_id": tax_id or distinct_nif(name),
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": name.capitalize(),
            "identity.surnames": "Operator",
            "activities.description": "design",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )
