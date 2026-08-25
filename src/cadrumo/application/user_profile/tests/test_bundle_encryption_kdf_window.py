"""The encrypted-bundle envelope validates its Argon2 record like its siblings.

This envelope was the one storage-adjacent KDF record whose cost axes and salt
were unbounded: ``memory_cost``, ``time_cost`` and ``parallelism`` were bare
integers and ``salt_b64`` a bare string, while the two records it derives
alongside both validate the same axes against a shared window.

Nothing this build wrote was ever weak -- the writer stamps
:meth:`KdfParams.default`, which is the OWASP baseline -- so the looseness was a
hardening gap rather than a live weakening. What it cost was that a re-exported
envelope could circulate as an application-grade encrypted bundle while
declaring an eight-kibibyte, single-iteration derivation, and that a
structurally invalid salt was indistinguishable at the boundary from a wrong
passphrase.

The positive control is the load-bearing half here. A window that refuses the
parameters this build's own writer stamps would be a worse defect than the one
it closes, so the writer's output is round-tripped through the constrained model
rather than assumed to fit.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage import KDF_SALT_BYTES
from ....adapters.persistence.storage.master_key import (
    MAX_PARALLELISM,
    MIN_MEMORY_COST_KIB,
    MIN_TIME_COST,
    KdfParams,
)
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfilePortableExport, UserProfileRecord
from cadrumo.application.user_profile.bundle_encryption import EncryptedProfileBundleError, EncryptedProfileBundleExport, decrypt_profile_bundle_with_passphrase, encrypt_profile_bundle_for_passphrase

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PASSPHRASE = "a real operator " + "passphrase" + " 123"
_PROFILE_ID = "a4f1c2e0-1111-4222-8333-444455556666"
_INSTANT = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)


def _bundle() -> UserProfilePortableExport:
    return UserProfilePortableExport(
        bundle_schema_version=3,
        exported_at=_INSTANT,
        profile=UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_PROFILE_ID,
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        ),
    )


def test_the_writers_own_envelope_survives_the_window_and_a_strict_roundtrip() -> None:
    """The positive control: this build's own bundle still encrypts, parses and decrypts."""
    bundle = _bundle()
    envelope = encrypt_profile_bundle_for_passphrase(bundle, passphrase=_PASSPHRASE)

    canonical = KdfParams.default()
    assert envelope.memory_cost == canonical.memory_cost
    assert envelope.time_cost == canonical.time_cost
    assert envelope.parallelism == canonical.parallelism

    reparsed = EncryptedProfileBundleExport.model_validate_json(envelope.model_dump_json())
    assert reparsed == envelope

    assert decrypt_profile_bundle_with_passphrase(reparsed, passphrase=_PASSPHRASE) == bundle


@pytest.mark.parametrize(
    "field_name,value",
    (
        ("memory_cost", 8),
        ("memory_cost", MIN_MEMORY_COST_KIB - 1),
        ("time_cost", MIN_TIME_COST - 1),
        ("parallelism", MAX_PARALLELISM + 1),
    ),
    ids=("memory-far-below", "memory-just-below", "iterations-below", "lanes-above"),
)
def test_an_out_of_window_cost_axis_refuses_at_load(field_name: str, value: int) -> None:
    """A stored envelope declaring a weaker derivation than the window never loads.

    ``memory-just-below`` is the case that matters: an off-by-one below the
    floor proves the bound is the OWASP baseline itself rather than some looser
    number that merely happens to reject an absurd value.
    """
    payload = json.loads(encrypt_profile_bundle_for_passphrase(_bundle(), passphrase=_PASSPHRASE).model_dump_json())
    payload[field_name] = value

    with pytest.raises(ValidationError):
        EncryptedProfileBundleExport.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "salt_b64",
    (
        base64.b64encode(b"x").decode("ascii"),
        base64.b64encode(b"S" * (KDF_SALT_BYTES - 1)).decode("ascii"),
        base64.b64encode(b"S" * (KDF_SALT_BYTES * 2)).decode("ascii"),
        "not base64!!",
    ),
    ids=("one-byte", "one-short", "double-length", "not-base64"),
)
def test_a_salt_that_is_not_exactly_one_kdf_salt_refuses_at_load(salt_b64: str) -> None:
    """A short salt derives a different key and reads as a wrong passphrase; refuse it first."""
    payload = json.loads(encrypt_profile_bundle_for_passphrase(_bundle(), passphrase=_PASSPHRASE).model_dump_json())
    payload["salt_b64"] = salt_b64

    with pytest.raises(ValidationError):
        EncryptedProfileBundleExport.model_validate_json(json.dumps(payload))


def test_an_unvalidated_envelope_still_meets_the_typed_refusal_at_the_decrypt_boundary() -> None:
    """The backstop: a caller bypassing validation gets the registered error, not a raw one.

    ``model_construct`` is pydantic's documented validation bypass, so this is a
    reachable path rather than a manufactured one. The assertion is that the
    third-party hashing failure underneath is still translated at the boundary
    into the module's registered error type.
    """
    payload = json.loads(encrypt_profile_bundle_for_passphrase(_bundle(), passphrase=_PASSPHRASE).model_dump_json())
    bypassed = EncryptedProfileBundleExport.model_construct(
        **(payload | {"memory_cost": 8, "salt_b64": base64.b64encode(b"x").decode("ascii")}),
    )

    with pytest.raises(EncryptedProfileBundleError):
        decrypt_profile_bundle_with_passphrase(bypassed, passphrase=_PASSPHRASE)
