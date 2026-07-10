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


@pytest.mark.parametrize(
    ("holder", "field_name", "payload"),
    (
        (_BundleHolder, "bundle_id", b"bundle-payload"),
        (_EvidenceHolder, "evidence_id", b"evidence-payload"),
    ),
)
def test_ids_accept_canonical_sha256_hex_digest(
    holder: type[BaseModel],
    field_name: str,
    payload: bytes,
) -> None:
    digest = hashlib.sha256(payload).hexdigest()
    instance = holder.model_validate({field_name: digest})
    assert getattr(instance, field_name) == digest


@pytest.mark.parametrize(
    ("holder", "field_name", "raw_id"),
    (
        (_BundleHolder, "bundle_id", "A" * 64),
        (_BundleHolder, "bundle_id", "a" * 63),
        (_BundleHolder, "bundle_id", "a" * 65),
        (_EvidenceHolder, "evidence_id", "z" * 64),
    ),
)
def test_ids_reject_noncanonical_digest_shapes(
    holder: type[BaseModel],
    field_name: str,
    raw_id: str,
) -> None:
    with pytest.raises(ValidationError):
        holder.model_validate({field_name: raw_id})
