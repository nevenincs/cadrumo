"""Real persisted-profile registration fixtures for outer integration tests.

Both doors below publish an encrypted profile capsule through the production
lifecycle.  The CLI-shaped door additionally exercises credential
registration and login, while the minimal door seeds a ready record directly.
They are persistence-backed test setup, so the concrete implementations live
with the persistence adapter test tree rather than ``cadrumo.tests``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    seed_test_profile_record,
)
from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle
from cadrumo.core.hashing import sha256_hex
from cadrumo.domain.calculations.registry.tax_id_runtime import runtime_nif_check_letter
from cadrumo.domain.user_profile.tests.schema_value_support import REQUIRED_PROFILE_PLACEHOLDERS
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord


def _distinct_valid_nif(profile_id: str) -> str:
    """Return a stable checksum-valid Spanish NIF for ``profile_id``."""
    digest = sha256_hex(profile_id.encode("utf-8"))
    number = int(digest, 16) % 100_000_000
    return f"{number:08d}{runtime_nif_check_letter(number)}"


def register_minimal_profile(
    *,
    profile_id: str | UUID,
    display_name: str | None = None,
    overrides: Mapping[str, str] | None = None,
    record_empty_legal_hold: bool = False,
) -> UserProfileRecord:
    """Publish a complete profile capsule and select it for an integration test."""
    from cadrumo.application.evidence.profile_legal_hold import LegalHoldCaseAuthority
    from cadrumo.application.filing.retention import try_record_filing_retention_snapshot
    from cadrumo.core.identity.profile import canonical_profile_bucket_id

    profile_id = canonical_profile_bucket_id(profile_id)
    merged: dict[str, str] = dict(REQUIRED_PROFILE_PLACEHOLDERS)
    merged["identity.tax_id"] = _distinct_valid_nif(profile_id)
    if overrides:
        merged.update(overrides)
    facts = tuple(UserProfileFact(path=path, value=value) for path, value in merged.items() if value)
    record = UserProfileRecord(
        profile_id=profile_id,
        facts=facts,
        setup_state=ProfileSetupState.COMPLETE,
    )
    seeded = seed_test_profile_record(
        record,
        label=display_name or f"profile-{profile_id}",
    )
    try_record_filing_retention_snapshot(
        bucket_id=profile_id,
        records=(),
        observed_at=datetime.now(UTC),
    )
    if record_empty_legal_hold:
        LegalHoldCaseAuthority().record_open_case_snapshot(
            profile_id=UUID(profile_id),
            open_case_ids=(),
            observed_at=datetime.now(UTC),
        )
    ProfileCapsuleLifecycle().select(profile_id)
    return seeded


def register_cli_profile(*, label: str, facts: Mapping[str, str] | None = None, complete: bool = True) -> str:
    """Register and log in a profile for a real CLI-surface test."""
    from cadrumo.application.user_profile.login_session import login_profile
    from cadrumo.application.user_profile.registration import register_profile_with_credentials
    from cadrumo.core.config import load_settings, override_settings

    merged: dict[str, str] = dict(REQUIRED_PROFILE_PLACEHOLDERS)
    merged["identity.tax_id"] = _distinct_valid_nif(label)
    if facts:
        merged.update(facts)
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    with override_settings(cadrumo_profile_kdf_measure_calibration=False):
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label=label,
            passphrase=passphrase,
            facts=tuple(UserProfileFact(path=path, value=value) for path, value in merged.items() if value),
        )
    login_profile(name=label, passphrase_callback=lambda: passphrase)
    if complete:
        identity = UUID(outcome.profile_id)
        with bound_test_profile_record(identity) as repository:
            current = repository.load(identity)
            repository.complete_setup(
                identity,
                expected_revision=current.record_revision,
                expected_content_digest=current.content_digest,
            )
    return outcome.profile_id


__all__ = ["register_cli_profile", "register_minimal_profile"]
