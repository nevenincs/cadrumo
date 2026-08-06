"""Real-behaviour proofs for credential-first profile registration.

These tests drive the production create path against a real storage root,
a real file-backed secret store, and real Argon2id key derivation. No
provider is faked: the assertion that the operator's passphrase protects
the bucket is made by *unwrapping the master key with it*, and the
assertion that a wrong passphrase does not is made by watching the real
AEAD unwrap fail.

The load-bearing test is
:func:`test_operator_passphrase_keys_the_bucket_not_the_ambient_setting`.
The isolated storage fixture configures an ambient
``cadrumo_secret_passphrase``, so a registration that ignored its
passphrase argument would still succeed and still produce a working
bucket — keyed to the wrong secret, silently. That test registers under a
passphrase deliberately different from the ambient one and proves the
bucket answers to the operator's choice and refuses the ambient value.
It is the regression for exactly that defect.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.errors import MasterKeyPassphraseMismatchError
from ....adapters.persistence.storage.master_key import get_master_key_provider
from ....core import PassphraseStrength
from ....domain.user_profile import UserProfileStatus
from ....tests.secure_sql import isolated_profile_storage_root
from .. import (
    PASSPHRASE_MINIMUM_LENGTH,
    ProfileAlreadyRegisteredError,
    ProfileRegistrationError,
    assess_passphrase,
    register_profile_with_credentials,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_OPERATOR_PASSPHRASE = "operator-chosen-registration-secret"  # noqa: S105 - synthetic test fixture
_WRONG_PASSPHRASE = "not-the-operator-chosen-secret"  # noqa: S105 - synthetic test fixture


# ── the credential actually protects the bucket ─────────────────────────────


def test_operator_passphrase_keys_the_bucket_not_the_ambient_setting(tmp_path: Path) -> None:
    """The registered bucket answers to the operator's passphrase alone.

    The fixture configures an ambient ``cadrumo_secret_passphrase``. If the
    registration door dropped its ``passphrase`` argument, the create span
    would resolve that ambient value and mint key material under it — the
    profile would still be created and every other assertion in this module
    would still pass, while the operator's chosen credential opened nothing.

    Proving the operator's passphrase unwraps the real master key, and that
    the ambient one does not, is what distinguishes a threaded callback from
    a discarded one.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            label="Registration Subject",
            passphrase=_OPERATOR_PASSPHRASE,
        )
        assert outcome.status is UserProfileStatus.SETUP_INCOMPLETE
        assert outcome.bucket_id == outcome.profile_id

        # Real Argon2id derivation + real AEAD unwrap under the operator's
        # secret; a mismatch would raise rather than return key bytes.
        operator_key = get_master_key_provider(
            passphrase_callback=lambda: _OPERATOR_PASSPHRASE,
        ).get_master_key()
        assert len(operator_key) == 32

        with pytest.raises(MasterKeyPassphraseMismatchError):
            get_master_key_provider(
                passphrase_callback=lambda: _WRONG_PASSPHRASE,
            ).get_master_key()


def test_registration_creates_an_addressable_profile_with_no_tax_facts(tmp_path: Path) -> None:
    """A profile exists from a label and a passphrase — no tax data required.

    This is the paradigm the door exists to serve: creation is instantaneous
    on credentials, and completeness is filled in afterwards against a live
    record rather than gated behind a wizard.

    Reading the record back through the profile repository is also the proof
    that registration leaves the operator *logged in*: profile-bound storage
    refuses outright without an active bucket session, so a successful load
    here means the session the manager needs is already open.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            label="Minimal Subject",
            passphrase=_OPERATOR_PASSPHRASE,
        )

        from .. import ProfileRepository

        aggregate = ProfileRepository().load(outcome.profile_id)
        assert aggregate is not None
        assert aggregate.status is UserProfileStatus.SETUP_INCOMPLETE
        assert aggregate.label == "Minimal Subject"
        tax_id_facts = [fact for fact in aggregate.record.facts if fact.path == "identity.tax_id"]
        assert tax_id_facts == []


# ── refusals ────────────────────────────────────────────────────────────────


def test_blank_label_is_refused_before_any_bucket_is_created(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        with pytest.raises(ProfileRegistrationError):
            register_profile_with_credentials(label="   ", passphrase=_OPERATOR_PASSPHRASE)
        assert not list(storage_root.glob("*/manifest.json")), "no bucket may survive a refused registration"


def test_short_passphrase_is_refused_before_any_bucket_is_created(tmp_path: Path) -> None:
    """The refusal lands before the span, so no half-made profile is stranded.

    The provider would refuse a short passphrase on its own, but only once
    the create span had already written a provisional pointer and bucket
    directory. Refusing up front is what keeps a failed attempt from leaving
    artefacts the operator has to clear by hand.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        with pytest.raises(ProfileRegistrationError):
            register_profile_with_credentials(label="Too Short", passphrase="a" * (PASSPHRASE_MINIMUM_LENGTH - 1))
        assert not list(storage_root.glob("*/manifest.json")), "no bucket may survive a refused registration"


def test_duplicate_label_is_refused(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label="Same Label", passphrase=_OPERATOR_PASSPHRASE)
        with pytest.raises(ProfileAlreadyRegisteredError):
            register_profile_with_credentials(label="Same Label", passphrase=_OPERATOR_PASSPHRASE)


# ── advisory banding ────────────────────────────────────────────────────────


def test_the_enforced_floor_is_the_only_hard_gate() -> None:
    """A short candidate is refused; a weak but long-enough one is accepted.

    NIST SP 800-63B §5.1.1.2 advises against composition requirements, so an
    all-lowercase passphrase at the minimum length must be *acceptable* even
    though it bands weak. Asserting acceptance here pins that the band is
    advice, not a second gate.
    """
    too_short = assess_passphrase("a" * (PASSPHRASE_MINIMUM_LENGTH - 1))
    assert too_short.strength is PassphraseStrength.TOO_SHORT
    assert not too_short.acceptable

    weak_but_long_enough = assess_passphrase("a" * PASSPHRASE_MINIMUM_LENGTH)
    assert weak_but_long_enough.strength is PassphraseStrength.WEAK
    assert weak_but_long_enough.acceptable


def test_a_long_single_class_passphrase_bands_strong() -> None:
    """Length is the dominant entropy term, so a passphrase clears on it alone."""
    assert assess_passphrase("correct horse battery staple").strength is PassphraseStrength.STRONG


def test_the_assessment_never_carries_the_candidate() -> None:
    """The advisory model holds a length, never the secret it measured."""
    candidate = "a-very-distinctive-candidate-value"
    assessment = assess_passphrase(candidate)
    assert candidate not in assessment.model_dump_json()
