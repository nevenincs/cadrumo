"""Real-behavior tests for the :data:`BundleId` and :data:`EvidenceId` aliases."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import BaseModel, ValidationError

from .._ids import BundleId, EvidenceId

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _BundleHolder(BaseModel):
    bundle_id: BundleId


class _EvidenceHolder(BaseModel):
    evidence_id: EvidenceId


def test_bundle_id_accepts_canonical_sha256_hex_digest() -> None:
    digest = hashlib.sha256(b"bundle-payload").hexdigest()
    assert _BundleHolder(bundle_id=digest).bundle_id == digest


def test_evidence_id_accepts_canonical_sha256_hex_digest() -> None:
    digest = hashlib.sha256(b"evidence-payload").hexdigest()
    assert _EvidenceHolder(evidence_id=digest).evidence_id == digest


def test_bundle_id_rejects_uppercase_hex() -> None:
    with pytest.raises(ValidationError):
        _BundleHolder(bundle_id="A" * 64)


def test_bundle_id_rejects_wrong_length() -> None:
    with pytest.raises(ValidationError):
        _BundleHolder(bundle_id="a" * 63)
    with pytest.raises(ValidationError):
        _BundleHolder(bundle_id="a" * 65)


def test_evidence_id_rejects_non_hex_characters() -> None:
    with pytest.raises(ValidationError):
        _EvidenceHolder(evidence_id="z" * 64)
