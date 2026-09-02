"""Real contract tests for strict profile-custody records."""

from __future__ import annotations

import base64
import json
from typing import Literal
from uuid import UUID

import pytest

from ......core.credentials import (
    PROFILE_PASSWORD_MAX_SCALARS,
    PROFILE_PASSWORD_MAX_UTF8_BYTES,
    PROFILE_PASSWORD_MIN_SCALARS,
    ProfilePasswordRefusalReason,
    assess_profile_password,
)
from ......core.storage_taxonomy import StorageCategory
from ......core.storage_taxonomy_locations import storage_location
from ... import __all__ as storage_exports
from .. import __all__ as custody_exports
from ..errors import (
    ProfileCustodyPasswordError,
    ProfileCustodyRecordError,
    ProfileCustodyRecoveryGuidance,
    ProfileCustodyRefusal,
    ProfileCustodyRefusedError,
)
from ..paths import profile_custody_path
from ..records import (
    PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
    PROFILE_CUSTODY_PASSWORD_GENERATION_MAX,
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    decode_profile_password,
    encode_profile_password,
    parse_profile_custody_envelope,
)
from ..records import __all__ as record_exports

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("b6af9dd0-7c7d-46d1-bb8d-4c842c62be4d")


def _b64(byte: int, length: int) -> str:
    return base64.b64encode(bytes([byte]) * length).decode("ascii")


def _envelope(
    *,
    password_generation: int = 1,
    previous_envelope_digest: str | None = None,
    memory_mib: Literal[19, 32, 64, 128, 256] = 64,
    iterations: Literal[2, 3, 4, 6, 8, 10] = 3,
    parallelism: Literal[1, 2, 4] = 1,
) -> ProfileCustodyEnvelope:
    return ProfileCustodyEnvelope.create(
        profile_id=_PROFILE_ID,
        password_generation=password_generation,
        dek_epoch=_b64(1, 16),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=memory_mib,
            iterations=iterations,
            parallelism=parallelism,
            salt_b64=_b64(2, 16),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=_b64(3, 12),
            ciphertext_b64=_b64(4, 32),
            tag_b64=_b64(5, 16),
        ),
        previous_envelope_digest=previous_envelope_digest,
    )


def test_current_envelope_roundtrips_through_the_raw_persisted_boundary() -> None:
    envelope = _envelope()

    assert parse_profile_custody_envelope(envelope.canonical_json_bytes()) == envelope


def test_canonical_envelope_has_exact_byte_ceiling_and_refuses_one_extra_raw_byte() -> None:
    envelope = _envelope(
        password_generation=PROFILE_CUSTODY_PASSWORD_GENERATION_MAX,
        previous_envelope_digest="sha256:" + "f" * 64,
        memory_mib=256,
        iterations=10,
        parallelism=4,
    )
    canonical = envelope.canonical_json_bytes()

    assert len(canonical) == PROFILE_CUSTODY_ENVELOPE_MAX_BYTES
    assert parse_profile_custody_envelope(canonical) == envelope
    with pytest.raises(ProfileCustodyRecordError, match="byte canonical limit"):
        parse_profile_custody_envelope(canonical + b" ")


def test_envelope_generation_is_bounded_before_canonical_serialization() -> None:
    with pytest.raises(ProfileCustodyRecordError):
        _envelope(password_generation=PROFILE_CUSTODY_PASSWORD_GENERATION_MAX + 1)


def test_parser_refuses_duplicate_unknown_digest_and_noncanonical_records() -> None:
    envelope = _envelope()
    document = envelope.canonical_json_bytes().decode("utf-8")
    duplicate = document.replace('"schema_version":1', '"schema_version":1,"schema_version":1', 1).encode("utf-8")
    unknown = document.replace("{", '{"unexpected":true,', 1).encode("utf-8")
    foreign_version = document.replace('"schema_version":1', '"schema_version":2', 1).encode("utf-8")
    altered = document.replace(envelope.self_digest, "sha256:" + "f" * 64).encode("utf-8")
    parsed = json.loads(document)
    reordered = json.dumps(dict(reversed(tuple(parsed.items()))), separators=(",", ":")).encode("utf-8")
    alternate_separators = json.dumps(parsed).encode("utf-8")
    whitespace = document.replace("{", "{ ", 1).encode("utf-8")
    upper_case_uuid = document.replace(str(_PROFILE_ID), str(_PROFILE_ID).upper()).encode("utf-8")
    compact_uuid = document.replace(str(_PROFILE_ID), _PROFILE_ID.hex).encode("utf-8")

    for corrupted in (
        duplicate,
        unknown,
        foreign_version,
        altered,
        reordered,
        alternate_separators,
        whitespace,
        upper_case_uuid,
        compact_uuid,
    ):
        with pytest.raises(ProfileCustodyRecordError):
            parse_profile_custody_envelope(corrupted)


def test_password_contract_preserves_exact_unicode_at_every_accepted_boundary() -> None:
    password = "  p\u0001ass phrase with spaces  "  # noqa: S105 - synthetic boundary input
    byte_boundary_password = "😀" * 256
    composed = "é" * PROFILE_PASSWORD_MIN_SCALARS
    decomposed = "e\u0301" * PROFILE_PASSWORD_MIN_SCALARS

    for candidate in (
        password,
        "a" * PROFILE_PASSWORD_MIN_SCALARS,
        "a" * PROFILE_PASSWORD_MAX_SCALARS,
        byte_boundary_password,
        composed,
        decomposed,
    ):
        assert decode_profile_password(encode_profile_password(candidate)) == candidate

    assert len(byte_boundary_password.encode("utf-8")) == PROFILE_PASSWORD_MAX_UTF8_BYTES
    assert composed != decomposed
    assert decode_profile_password(encode_profile_password(composed)) != decomposed


@pytest.mark.parametrize(
    ("candidate", "reason"),
    (
        # One scalar short of PROFILE_PASSWORD_MIN_SCALARS, so the refusal is
        # this reason and not another: the classes are all valid and the byte
        # count is well inside the ceiling.
        ("Q7!Ω🔒" + "x" * (PROFILE_PASSWORD_MIN_SCALARS - 6), ProfilePasswordRefusalReason.TOO_FEW_SCALARS),
        ("leak-marker-" + "x" * 245, ProfilePasswordRefusalReason.TOO_MANY_SCALARS),
        (
            "😀" * PROFILE_PASSWORD_MAX_SCALARS + "a",
            ProfilePasswordRefusalReason.TOO_MANY_UTF8_BYTES,
        ),
        ("\udfffS3cr3t-Ω-marker", ProfilePasswordRefusalReason.CONTAINS_SURROGATE),
    ),
)
def test_password_contract_maps_every_canonical_reason_to_a_safe_custody_error(
    candidate: str,
    reason: ProfilePasswordRefusalReason,
) -> None:
    assessment = assess_profile_password(candidate)
    with pytest.raises(ProfileCustodyPasswordError) as captured:
        encode_profile_password(candidate)

    message = str(captured.value)
    assert message == f"profile password refused by canonical policy: {reason.value}"
    assert candidate not in message
    assert "scalar_count" not in message
    assert "utf8_byte_count" not in message
    assert repr(assessment) not in message
    assert str(assessment.scalar_count) not in message
    if assessment.utf8_byte_count is not None:
        assert str(assessment.utf8_byte_count) not in message


def test_password_transport_refuses_non_utf8_bytes() -> None:
    with pytest.raises(ProfileCustodyPasswordError):
        decode_profile_password(b"\xff" * PROFILE_PASSWORD_MIN_SCALARS)


def test_obsolete_custody_password_policy_symbols_are_absent_from_every_facade() -> None:
    obsolete = {
        "PROFILE_CUSTODY_PASSWORD_MAX_BYTES",
        "PROFILE_CUSTODY_PASSWORD_MAX_SCALARS",
        "PROFILE_CUSTODY_PASSWORD_MIN_SCALARS",
        "decode_profile_password",
        "validate_profile_password",
    }

    assert obsolete.isdisjoint(record_exports)
    assert obsolete.isdisjoint(custody_exports)
    assert obsolete.isdisjoint(storage_exports)


def test_custody_taxonomy_is_closed_to_current_profile_capsule_artifacts() -> None:
    assert storage_location(StorageCategory.PROFILE_CAPSULE_PASSWORD_ENVELOPE).subpath == "custody/envelope.v1.json"
    assert storage_location(StorageCategory.PROFILE_CAPSULE_COMMIT).subpath == "profile.commit.v1.json"
    with pytest.raises(ValueError):
        profile_custody_path(_PROFILE_ID, StorageCategory.BUCKET_LOCK)


def test_refusal_taxonomy_carries_the_hard_cutover_and_supervision_outcomes() -> None:
    assert set(ProfileCustodyRefusal) == {
        ProfileCustodyRefusal.LEGACY_CUSTODY_DETECTED,
        ProfileCustodyRefusal.DEK_ROTATION_UNSUPPORTED,
        ProfileCustodyRefusal.KDF_RESOURCE_LIMIT,
        ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE,
    }
    assert tuple(ProfileCustodyRecoveryGuidance) == (
        ProfileCustodyRecoveryGuidance.DESTRUCTIVE_RESET,
        ProfileCustodyRecoveryGuidance.REENROLL_PROFILE,
    )
    error = ProfileCustodyRefusedError(
        ProfileCustodyRefusal.LEGACY_CUSTODY_DETECTED,
        context={"refusal": "forged-refusal", "profile_id": str(_PROFILE_ID)},
    )
    assert error.context == {"refusal": "LEGACY_CUSTODY_DETECTED", "profile_id": str(_PROFILE_ID)}
