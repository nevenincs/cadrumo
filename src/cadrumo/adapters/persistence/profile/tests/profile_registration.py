"""Real persisted-profile registration fixtures for outer integration tests.

Both doors below publish an encrypted profile capsule through the production
lifecycle.  The CLI-shaped door additionally exercises credential
registration and login, while the minimal door seeds a ready record directly.
They are persistence-backed test setup, so the concrete implementations live
with the persistence adapter test tree rather than ``cadrumo.tests``.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import keyring
import pytest
from keyring.backends.null import Keyring as NullKeyring

from .....application.user_profile.lifecycle import ProfileCapsuleLifecycle
from .....core.hashing import sha256_hex
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from .....domain.calculations.registry.tax_id_runtime import runtime_nif_check_letter
from .....domain.user_profile.tests.schema_value_support import REQUIRED_PROFILE_PLACEHOLDERS
from .....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from .....tests.env import temporary_env
from .....tests.live_gate import requires_live_enabled
from ...storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    seed_test_profile_record,
)
from ...storage.tests.secure_sql import isolated_profile_storage_root


@contextmanager
def _profile_authority_scope() -> Iterator[PinnedAuthorityOperation]:
    """Build profile fixtures under the same published authority the product reads.

    The profile a fixture seeds is read back by real CLI and TUI invocations,
    which lease the bundled published authority. A record authority minted
    under any other generation pin is refused at the generation guard on the
    first read -- correctly -- so the fixture must lease that same authority
    rather than a source-compiled stand-in with a pin of its own.
    """
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _distinct_valid_nif(profile_id: str, *, operation: PinnedAuthorityOperation) -> str:
    """Return a stable checksum-valid Spanish NIF for ``profile_id``."""
    digest = sha256_hex(profile_id.encode("utf-8"))
    number = int(digest, 16) % 100_000_000
    with validating_governed_facts(operation):
        return f"{number:08d}{runtime_nif_check_letter(number)}"


def register_minimal_profile(
    *,
    profile_id: str | UUID,
    display_name: str | None = None,
    overrides: Mapping[str, str] | None = None,
    record_empty_legal_hold: bool = False,
) -> UserProfileRecord:
    """Publish a complete profile capsule and select it for an integration test."""
    from .....application.evidence.profile_legal_hold import LegalHoldCaseAuthority
    from .....application.filing.retention import try_record_filing_retention_snapshot
    from .....core.identity.profile import canonical_profile_bucket_id

    with _profile_authority_scope() as operation:
        profile_id = canonical_profile_bucket_id(profile_id)
        merged: dict[str, str] = dict(REQUIRED_PROFILE_PLACEHOLDERS)
        merged["identity.tax_id"] = _distinct_valid_nif(profile_id, operation=operation)
        if overrides:
            merged.update(overrides)
        facts = tuple(UserProfileFact(path=path, value=value) for path, value in merged.items() if value)
        record = create_user_profile_record(
            context=operation.profile_create_context(),
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


def register_cli_profile(
    *,
    label: str,
    facts: Mapping[str, str] | None = None,
    complete: bool = True,
    log_in: bool = True,
) -> str:
    """Register and log in a profile for a real CLI-surface test.

    Registration already publishes the new profile's session for this process,
    exactly as a login does, except that it mints no acceleration receipt; the
    receipt is what lets a LATER process resume the session. ``log_in=False``
    skips the second authentication -- one supervised Argon2id derivation --
    for a test that only drives the CLI in this process and so never needs the
    receipt.
    """
    from .....application.user_profile.login_session import login_profile
    from .....application.user_profile.registration import register_profile_with_credentials
    from .....core.config import load_settings, override_settings

    with _profile_authority_scope() as operation:
        merged: dict[str, str] = dict(REQUIRED_PROFILE_PLACEHOLDERS)
        merged["identity.tax_id"] = _distinct_valid_nif(label, operation=operation)
        if facts:
            merged.update(facts)
        passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
        create_context = operation.profile_create_context()
        decode_context = operation.profile_decode_context()
        with override_settings(cadrumo_profile_kdf_measure_calibration=False):
            outcome = register_profile_with_credentials(
                label=label,
                passphrase=passphrase,
                facts=tuple(UserProfileFact(path=path, value=value) for path, value in merged.items() if value),
                profile_create_context=create_context,
                profile_decode_context=decode_context,
            )
        if log_in:
            login_profile(
                name=label,
                passphrase_callback=lambda: passphrase,
                profile_decode_context=decode_context,
            )
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


_LIVE_PROFILE_LABEL = "live-tests"
_LIVE_PROFILE_BASE = Path(__file__).resolve().parents[6] / ".tmp" / "live-tests"
"""Checkout-local base the live lane keeps its profile and AEAT session state under."""


@dataclass(frozen=True)
class LiveAeatProfile:
    """The logged-in profile the live lane authenticates against AEAT through."""

    storage_root: Path
    label: str
    profile_id: str


@contextmanager
def live_clave_movil_profile_scope(base: Path) -> Iterator[LiveAeatProfile]:
    """Create on first use, then log in, the Cl@ve Movil profile named by the environment.

    The profile's fiscal identity is ``CADRUMO_CLAVE_MOVIL_DNI_NIE`` and its
    passphrase the development test password, so a clean checkout can run the
    live lane without a login left behind by an earlier process. The keyring
    is pinned to a backend that stores nothing, in this process and in every
    child it starts: the login stays process-scoped and no session key reaches
    the operator's OS credential store.
    """
    from .....application.auth.preferences import set_profile_auth_preference
    from .....application.user_profile.login_session import login_profile
    from .....application.workflow.profile_bucket_scan import resolve_profile_bucket
    from .....core.auth_provider import AuthProviderKind
    from .....core.config import load_settings
    from ...storage.master_key.active_session import close_active_bucket_session

    settings = load_settings()
    configured = settings.cadrumo_clave_movil_dni_nie
    tax_id = configured.get_secret_value().strip().upper() if configured is not None else ""
    if not tax_id:
        pytest.fail("CADRUMO_CLAVE_MOVIL_DNI_NIE is not configured after live opt-in")
    passphrase = settings.cadrumo_dev_test_database_password.get_secret_value()
    previous_keyring = keyring.get_keyring()
    keyring.set_keyring(NullKeyring())
    try:
        with (
            temporary_env(PYTHON_KEYRING_BACKEND="keyring.backends.null.Keyring"),
            isolated_profile_storage_root(tmp_path=base) as storage_root,
        ):
            try:
                if resolve_profile_bucket(_LIVE_PROFILE_LABEL) is None:
                    profile_id = register_cli_profile(
                        label=_LIVE_PROFILE_LABEL,
                        facts={"identity.tax_id": tax_id},
                        log_in=False,
                    )
                else:
                    with _profile_authority_scope() as operation:
                        profile_id = login_profile(
                            name=_LIVE_PROFILE_LABEL,
                            passphrase_callback=lambda: passphrase,
                            profile_decode_context=operation.profile_decode_context(),
                        ).bucket_id
                with _profile_authority_scope() as operation:
                    set_profile_auth_preference(
                        profile_id=profile_id,
                        provider=AuthProviderKind.CLAVE_MOVIL,
                        route=None,
                        profile_decode_context=operation.profile_decode_context(),
                    )
                yield LiveAeatProfile(storage_root=storage_root, label=_LIVE_PROFILE_LABEL, profile_id=profile_id)
            finally:
                close_active_bucket_session()
    finally:
        keyring.set_keyring(previous_keyring)


@pytest.fixture
def live_clave_movil_profile() -> Iterator[LiveAeatProfile]:
    """Yield the live lane's logged-in Cl@ve Movil profile, after the live opt-in gate."""
    requires_live_enabled()
    with live_clave_movil_profile_scope(_LIVE_PROFILE_BASE) as profile:
        yield profile


__all__ = [
    "LiveAeatProfile",
    "live_clave_movil_profile",
    "live_clave_movil_profile_scope",
    "register_cli_profile",
    "register_minimal_profile",
]
