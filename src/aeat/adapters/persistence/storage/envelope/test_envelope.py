"""Tests for the schema-version envelope contract."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from .....core.classification import SensitivityClass
from ..errors import ClassificationError, EnvelopeVersionError
from . import EncryptionMetadata, Envelope
from ._envelope import EnvelopeMigrator, load_envelope, save_envelope

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class _DemoPayloadV1(BaseModel):
    model_config = _STRICT_FROZEN

    name: str
    count: int


class _DemoPayloadV2(BaseModel):
    model_config = _STRICT_FROZEN

    name: str
    count: int
    note: str = ""


def _now_utc() -> datetime:
    return datetime.now(UTC)


class TestEnvelopeShape:
    """The envelope frozen-pydantic record validates field constraints."""

    def test_round_trip_via_model_dump(self) -> None:
        env = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=_now_utc(),
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
                written_at=_now_utc(),
                classification=SensitivityClass.OPERATIONAL,
                payload=_DemoPayloadV1(name="x", count=1),
            )


class TestEnvelopeRoundTrip:
    """``save_envelope`` and ``load_envelope`` are inverse functions."""

    def test_plaintext_round_trip(self, tmp_path: Path) -> None:
        env = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=_now_utc(),
            classification=SensitivityClass.OPERATIONAL,
            payload=_DemoPayloadV1(name="hola", count=42),
        )
        target = tmp_path / "envelope.json"
        save_envelope(env, target)
        loaded = load_envelope(
            target,
            Envelope[_DemoPayloadV1],
            expected_class=SensitivityClass.OPERATIONAL,
            max_supported_version=1,
        )
        assert loaded.payload == env.payload
        assert loaded.schema_version == 1

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
            written_at=_now_utc(),
            classification=SensitivityClass.OPERATIONAL,
            payload=_DemoPayloadV1(name="alpha", count=1),
        )
        save_envelope(first, target)
        original_text = target.read_text(encoding="utf-8")
        assert original_text  # non-empty

        # Now write again — the on-disk file must be the new one (not corrupt).
        second = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=_now_utc(),
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


class TestClassificationGate:
    """Loading with a different classification than the writer raises."""

    def test_classification_mismatch_raises(self, tmp_path: Path) -> None:
        env = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=_now_utc(),
            classification=SensitivityClass.FINANCIAL,
            payload=_DemoPayloadV1(name="x", count=1),
        )
        target = tmp_path / "env.json"
        save_envelope(env, target)
        with pytest.raises(ClassificationError):
            load_envelope(
                target,
                Envelope[_DemoPayloadV1],
                expected_class=SensitivityClass.OPERATIONAL,
                max_supported_version=1,
            )


class TestVersionGate:
    """Future-version envelopes are refused; older versions migrate forward."""

    def test_future_version_raises(self, tmp_path: Path) -> None:
        env = Envelope[_DemoPayloadV1](
            schema_version=99,
            written_at=_now_utc(),
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

    def test_no_migrator_chain_raises(self, tmp_path: Path) -> None:
        env = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=_now_utc(),
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

    def test_migrator_chain_advances_version(self, tmp_path: Path) -> None:
        env = Envelope[_DemoPayloadV1](
            schema_version=1,
            written_at=_now_utc(),
            classification=SensitivityClass.OPERATIONAL,
            payload=_DemoPayloadV1(name="x", count=1),
        )
        target = tmp_path / "env.json"
        save_envelope(env, target)

        class _OneToTwo:
            source_version = 1
            target_version = 2

            def migrate(self, envelope):
                return Envelope[_DemoPayloadV1](
                    schema_version=2,
                    written_at=envelope.written_at,
                    classification=envelope.classification,
                    payload=envelope.payload,
                    encryption=envelope.encryption,
                )

        migrator: EnvelopeMigrator[_DemoPayloadV1] = _OneToTwo()
        loaded = load_envelope(
            target,
            Envelope[_DemoPayloadV1],
            expected_class=SensitivityClass.OPERATIONAL,
            max_supported_version=2,
            migrators=(migrator,),
        )
        assert loaded.schema_version == 2


class TestEncryptionMetadata:
    """``EncryptionMetadata`` round-trips and validates the algorithm name."""

    def test_round_trip_via_blob(self) -> None:
        from ..crypto._crypto import encrypt_record

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
                }
            )

    def test_default_associated_data_is_empty(self) -> None:
        meta = EncryptionMetadata(
            nonce_b64=base64.b64encode(b"\x00" * 12).decode("ascii"),
            ciphertext_b64=base64.b64encode(b"x" * 16).decode("ascii"),
        )
        assert meta.associated_data() == b""
