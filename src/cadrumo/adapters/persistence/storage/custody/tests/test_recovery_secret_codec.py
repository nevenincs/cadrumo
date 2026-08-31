"""Regression contract for policy-free recovery-secret representation."""

from __future__ import annotations

from pathlib import Path

import pytest

from .._recovery_secret_codec import decode_recovery_secret, encode_recovery_secret
from ..errors import ProfileCustodyRecoverySecretError

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@pytest.mark.parametrize("candidate", ["", "short", "correct horse battery staple", "cafe\u0301", "café", "🔐" * 300])
def test_recovery_secret_roundtrip_is_byte_exact_and_not_password_shaped(candidate: str) -> None:
    encoded = encode_recovery_secret(candidate)

    assert encoded == candidate.encode("utf-8", errors="strict")
    assert decode_recovery_secret(encoded) == candidate


def test_recovery_secret_codec_preserves_distinct_unicode_representations() -> None:
    composed = "café"
    decomposed = "cafe\u0301"

    assert encode_recovery_secret(composed) != encode_recovery_secret(decomposed)
    assert decode_recovery_secret(encode_recovery_secret(composed)) == composed
    assert decode_recovery_secret(encode_recovery_secret(decomposed)) == decomposed


def test_recovery_secret_codec_refuses_malformed_transport() -> None:
    with pytest.raises(ProfileCustodyRecoverySecretError, match="transport is not strict UTF-8"):
        decode_recovery_secret(b"\xff")


def test_recovery_paths_have_no_profile_password_policy_dependency() -> None:
    custody_root = Path(__file__).parents[1]
    recovery_sources = "\n".join(
        (custody_root / name).read_text(encoding="utf-8")
        for name in ("recovery.py", "recovery_artifact.py", "_recovery_secret_codec.py")
    )
    supervision = (custody_root / "kdf_supervision.py").read_text(encoding="utf-8")
    recovery_supervision = supervision[supervision.index("def unlock_profile_custody_recovery_material") :]
    worker = (custody_root / "_kdf_worker.py").read_text(encoding="utf-8")

    assert "assess_profile_password" not in recovery_sources + recovery_supervision + worker
    assert "_encode_profile_password" not in recovery_sources + recovery_supervision
    assert "_decode_profile_password" not in recovery_sources + recovery_supervision
    assert worker.count("decode_recovery_secret(encoded) if recovery else _decode_profile_password(encoded)") == 2


def test_obsolete_conflated_material_entry_points_are_absent() -> None:
    from .. import kdf_supervision

    assert not hasattr(kdf_supervision, "wrap_profile_custody_material")
    assert not hasattr(kdf_supervision, "unlock_profile_custody_material")
