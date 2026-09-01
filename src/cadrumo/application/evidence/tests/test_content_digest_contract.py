"""Evidence content digests carry the canonical hex-64 contract.

An evidence record's ``content_sha256`` is a re-computable claim about the
referenced payload's bytes. A digest that is not lowercase hex-64 can never
match a recomputed hash, so accepting one only defers the failure to a later
verification pass -- and lets the machine-facing CLI boundary emit a digest
the application model would refuse. Both the record and its CLI projection
therefore pin :data:`~core.identity.ContentDigest`.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ....core.identity import ContentDigest
from ....domain.buckets.event import BucketEventObjectType
from ....entrypoints.cli._modelo_aux_payloads import EvidenceRecordRefPayload
from ..models import EvidenceRecordRef

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_VALID_DIGEST = "a1b2c3d4" * 8
_NON_HEX_DIGEST = "z" * 64
_UPPERCASE_DIGEST = "A1B2C3D4" * 8


class TestEvidenceRecordRefDigest:
    """The application record refuses a digest no payload can produce."""

    def test_valid_hex64_digest_is_accepted(self) -> None:
        record = EvidenceRecordRef(
            object_type=BucketEventObjectType.WORK_UNIT,
            object_id="wu-1",
            content_sha256=_VALID_DIGEST,
            payload_size_bytes=3,
        )

        assert record.content_sha256 == _VALID_DIGEST

    @pytest.mark.parametrize("digest", [_NON_HEX_DIGEST, _UPPERCASE_DIGEST, "abc"])
    def test_non_hex64_digest_is_refused(self, digest: str) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecordRef(
                object_type=BucketEventObjectType.WORK_UNIT,
                object_id="wu-1",
                content_sha256=digest,
                payload_size_bytes=3,
            )


class TestEvidenceRecordRefPayloadDigest:
    """The CLI projection cannot be looser than the record it mirrors."""

    def test_valid_hex64_digest_is_accepted(self) -> None:
        payload = EvidenceRecordRefPayload(
            object_type=BucketEventObjectType.WORK_UNIT,
            object_id="wu-1",
            content_sha256=_VALID_DIGEST,
            payload_size_bytes=3,
        )

        assert payload.content_sha256 == _VALID_DIGEST

    @pytest.mark.parametrize("digest", [_NON_HEX_DIGEST, _UPPERCASE_DIGEST, "abc"])
    def test_non_hex64_digest_is_refused(self, digest: str) -> None:
        with pytest.raises(ValidationError):
            EvidenceRecordRefPayload(
                object_type=BucketEventObjectType.WORK_UNIT,
                object_id="wu-1",
                content_sha256=digest,
                payload_size_bytes=3,
            )

    def test_payload_digest_agrees_with_the_canonical_alias(self) -> None:
        """Neither side may drift from the shared alias's verdict."""
        adapter = TypeAdapter(ContentDigest)

        for candidate in (_VALID_DIGEST, _NON_HEX_DIGEST, _UPPERCASE_DIGEST, "abc"):
            canonical_accepts = True
            try:
                adapter.validate_python(candidate)
            except ValidationError:
                canonical_accepts = False

            payload_accepts = True
            try:
                EvidenceRecordRefPayload(
                    object_type=BucketEventObjectType.WORK_UNIT,
                    object_id="wu-1",
                    content_sha256=candidate,
                    payload_size_bytes=3,
                )
            except ValidationError:
                payload_accepts = False

            assert payload_accepts is canonical_accepts, candidate
