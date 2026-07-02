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


def test_ids_accept_canonical_sha256_hex_digest() -> None:
    cases = (
        (_BundleHolder, "bundle_id", b"bundle-payload"),
        (_EvidenceHolder, "evidence_id", b"evidence-payload"),
    )

    for holder, field_name, payload in cases:
        digest = hashlib.sha256(payload).hexdigest()
        instance = holder.model_validate({field_name: digest})
        assert getattr(instance, field_name) == digest, field_name


def test_ids_reject_noncanonical_digest_shapes() -> None:
    cases = (
        (_BundleHolder, "bundle_id", "A" * 64),
        (_BundleHolder, "bundle_id", "a" * 63),
        (_BundleHolder, "bundle_id", "a" * 65),
        (_EvidenceHolder, "evidence_id", "z" * 64),
    )

    for holder, field_name, raw_id in cases:
        with pytest.raises(ValidationError):
            holder.model_validate({field_name: raw_id})
