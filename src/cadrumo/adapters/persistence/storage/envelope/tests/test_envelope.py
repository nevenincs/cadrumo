"""Tests for the schema-version envelope contract."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from ......core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ......core.classification import SensitivityClass
from ......core.external_constants import UTF_8_ENCODING
from ...errors import ClassificationError, DecryptionError, EnvelopeVersionError, StorageValidationError
from .. import EncryptionMetadata, Envelope
from .._envelope import load_envelope, save_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


class _DemoPayloadV1(BaseModel):
    model_config = _STRICT_FROZEN

    name: str
    count: int


class _DemoPayloadV2(BaseModel):
    model_config = _STRICT_FROZEN

    name: str
    count: int
    note: str = ""


_ENVELOPE_WRITTEN_AT = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)


class TestEnvelopeShape:
    """The envelope frozen-pydantic record validates field constraints."""

    def test_round_trip_via_model_dump(self) -> None:
        env = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.OPERATIONAL,
            payload=_DemoPayloadV1(name="x", count=1),
        )
        restored = Envelope[_DemoPayloadV1].model_validate(env.model_dump(mode="python"))
        assert restored == env

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Envelope[_DemoPayloadV1](
                schema_version=1,
                written_at=datetime(2026, 4, 27, 12, 0, 0),
                classification=SensitivityClass.OPERATIONAL,
                payload=_DemoPayloadV1(name="x", count=1),
            )

    def test_zero_version_rejected(self) -> None:
        invalid_version: int = 0
        with pytest.raises(ValidationError):
            Envelope[_DemoPayloadV1](
                schema_version=invalid_version,
                written_at=_ENVELOPE_WRITTEN_AT,
                classification=SensitivityClass.OPERATIONAL,
                payload=_DemoPayloadV1(name="x", count=1),
            )


class TestEnvelopeRoundTrip:
    """``save_envelope`` and ``load_envelope`` are inverse functions."""

    def test_plaintext_round_trip(self, tmp_path: Path) -> None:
        env = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC),
            classification=SensitivityClass.FINANCIAL,
            payload=_DemoPayloadV1(name="hola", count=42),
        )
        target = tmp_path / "envelope.json"
        save_envelope(env, target)
        loaded = load_envelope(
            target,
            Envelope[_DemoPayloadV1],
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=1,
        )
        assert loaded == env

    def test_load_round_trips_timezone(self, tmp_path: Path) -> None:
        explicit = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)
        env = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=explicit,
            classification=SensitivityClass.OPERATIONAL,
            payload=_DemoPayloadV1(name="x", count=1),
        )
        target = tmp_path / "tz.json"
        save_envelope(env, target)
        loaded = load_envelope(
            target,
            Envelope[_DemoPayloadV1],
            expected_class=SensitivityClass.OPERATIONAL,
            max_supported_version=1,
        )
        assert loaded.written_at == explicit

    def test_save_atomic_via_tempfile(self, tmp_path: Path) -> None:
        """A failed write must NOT leave the target partially written."""
        target = tmp_path / "envelope.json"
        # First successful write so the target exists with known content.
        first = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.OPERATIONAL,
            payload=_DemoPayloadV1(name="alpha", count=1),
        )
        save_envelope(first, target)
        original_text = target.read_text(encoding=UTF_8_ENCODING)
        assert original_text  # non-empty

        # Now write again — the on-disk file must be the new one (not corrupt).
        second = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.OPERATIONAL,
            payload=_DemoPayloadV1(name="beta", count=2),
        )
        save_envelope(second, target)
        loaded = load_envelope(
            target,
            Envelope[_DemoPayloadV1],
            expected_class=SensitivityClass.OPERATIONAL,
            max_supported_version=1,
        )
        assert loaded.payload.name == "beta"

    def test_save_write_failure_raises_storage_validation_without_path(self, tmp_path: Path) -> None:
        env = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.OPERATIONAL,
            payload=_DemoPayloadV1(name="x", count=1),
        )
        parent_file = tmp_path / "not-a-directory"
        parent_file.write_text("occupied", encoding=UTF_8_ENCODING)
        target = parent_file / "env.json"

        with pytest.raises(StorageValidationError) as excinfo:
            save_envelope(env, target)

        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"
        assert str(tmp_path) not in str(excinfo.value)

    def test_load_missing_file_raises_storage_validation_without_path(self, tmp_path: Path) -> None:
        target = tmp_path / "missing.json"

        with pytest.raises(StorageValidationError) as excinfo:
            load_envelope(
                target,
                Envelope[_DemoPayloadV1],
                expected_class=SensitivityClass.OPERATIONAL,
                max_supported_version=1,
            )

        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"
        assert str(tmp_path) not in str(excinfo.value)


class TestClassificationGate:
    """Loading with a different classification than the writer raises."""

    def test_classification_mismatch_raises(self, tmp_path: Path) -> None:
        env = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.FINANCIAL,
            payload=_DemoPayloadV1(name="x", count=1),
        )
        target = tmp_path / "env.json"
        save_envelope(env, target)
        with pytest.raises(ClassificationError) as excinfo:
            load_envelope(
                target,
                Envelope[_DemoPayloadV1],
                expected_class=SensitivityClass.OPERATIONAL,
                max_supported_version=1,
            )
        assert str(tmp_path) not in str(excinfo.value)


class TestVersionGate:
    """Envelope versions must match the consumer's current contract."""

    def test_future_version_raises(self, tmp_path: Path) -> None:
        env = Envelope[_DemoPayloadV1](
            schema_version=99,
            written_at=_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.OPERATIONAL,
            payload=_DemoPayloadV1(name="x", count=1),
        )
        target = tmp_path / "env.json"
        save_envelope(env, target)
        with pytest.raises(EnvelopeVersionError):
            load_envelope(
                target,
                Envelope[_DemoPayloadV1],
                expected_class=SensitivityClass.OPERATIONAL,
                max_supported_version=1,
            )

    def test_older_version_raises(self, tmp_path: Path) -> None:
        env = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=_ENVELOPE_WRITTEN_AT,
            classification=SensitivityClass.OPERATIONAL,
            payload=_DemoPayloadV1(name="x", count=1),
        )
        target = tmp_path / "env.json"
        save_envelope(env, target)
        with pytest.raises(EnvelopeVersionError):
            load_envelope(
                target,
                Envelope[_DemoPayloadV1],
                expected_class=SensitivityClass.OPERATIONAL,
                max_supported_version=2,
            )


class TestEncryptionMetadata:
    """``EncryptionMetadata`` round-trips and validates the algorithm name."""

    def test_round_trip_via_blob(self) -> None:
        from ...crypto.aead import encrypt_record

        key = b"\x00" * 32
        blob = encrypt_record(b"hello", key=key)
        meta = EncryptionMetadata.from_blob(blob, associated_data=b"context")
        restored_blob = meta.to_blob()
        assert restored_blob == blob
        assert meta.associated_data() == b"context"

    def test_unknown_algorithm_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EncryptionMetadata.model_validate(
                {
                    # Closed enum: pydantic rejects unknown values at validate time.
                    "algorithm": "some-future-thing",
                    "nonce_b64": base64.b64encode(b"\x00" * 12).decode("ascii"),
                    "ciphertext_b64": base64.b64encode(b"x" * 16).decode("ascii"),
                },
            )

    def test_explicit_empty_associated_data_is_empty(self) -> None:
        meta = EncryptionMetadata(
            nonce_b64=base64.b64encode(b"\x00" * 12).decode("ascii"),
            ciphertext_b64=base64.b64encode(b"x" * 16).decode("ascii"),
            associated_data_b64="",
        )
        assert meta.associated_data() == b""

    def test_missing_associated_data_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="associated_data_b64"):
            EncryptionMetadata.model_validate(
                {
                    "nonce_b64": base64.b64encode(b"\x00" * 12).decode("ascii"),
                    "ciphertext_b64": base64.b64encode(b"x" * 16).decode("ascii"),
                },
            )

    def test_invalid_base64_metadata_raises_decryption_error(self) -> None:
        meta = EncryptionMetadata(
            nonce_b64="not-base64!!",
            ciphertext_b64=base64.b64encode(b"x" * 16).decode("ascii"),
            associated_data_b64="",
        )

        with pytest.raises(DecryptionError):
            meta.to_blob()
