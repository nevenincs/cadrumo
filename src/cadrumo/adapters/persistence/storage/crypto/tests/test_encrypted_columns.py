"""Tests for the encrypted-column TypeDecorator set.

The tests run against a real in-memory SQLAlchemy session bound to
a deliberately-isolated declarative base so we never touch the live
``cadrumo.adapters.persistence.storage._orm`` schema. The master key is supplied by an
:class:`EphemeralMasterKeyProvider` whose ``__enter__`` activates a
:class:`BucketSession` for the duration of the test.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Annotated, cast

import pytest
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from ......tests.master_key import EphemeralMasterKeyProvider
from ...errors import DecryptionError, StorageValidationError
from .. import EncryptedBytes, EncryptedJSON, EncryptedPayload, EncryptedString, HashedLookup
from .._crypto import encrypt_record
from .._encrypted_columns import _AAD_JSON, _AAD_STRING

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_ENCRYPTED_STRING_CASES = (
    "hello world",
    "movimientos bancarios — autónomo año 2025",
    None,
)
_ENCRYPTED_BYTES_CASES = (
    bytes(range(64)),
    b"",
)
_ENCRYPTED_JSON_CASES = (
    {"nombre": "Juan", "edad": 42, "tags": ["a", "b"]},
    [{"k": 1}, {"k": 2}],
    None,
)


class _TestBase(DeclarativeBase):
    """Declarative base local to this test module — never touches the live schema."""


_intpk = Annotated[int, mapped_column(primary_key=True, autoincrement=True)]
_secret_text = Annotated[str | None, mapped_column(EncryptedString, nullable=True)]
_secret_bytes = Annotated[bytes | None, mapped_column(EncryptedBytes, nullable=True)]
_secret_json = Annotated[object | None, mapped_column(EncryptedJSON, nullable=True)]
_lookup_key = Annotated[bytes | None, mapped_column(HashedLookup, nullable=True, index=True)]


class _CryptoRow(_TestBase):
    """One mapper class exercising every encrypted column type."""

    __tablename__ = "encrypted_column_smoke"

    id: Mapped[_intpk]
    secret_text: Mapped[_secret_text]
    secret_bytes: Mapped[_secret_bytes]
    secret_json: Mapped[_secret_json]
    lookup_key: Mapped[_lookup_key]


@pytest.fixture(autouse=True)
def _patch_master_key(fixed_master_key: bytes) -> Iterator[None]:
    """Inject a deterministic master key for every test in this module."""
    with EphemeralMasterKeyProvider(key=fixed_master_key):
        yield


@pytest.fixture
def engine() -> Iterator[Engine]:
    """Yield a clean in-memory SQLite engine bound to the test schema."""
    eng = create_engine("sqlite:///:memory:", future=True)
    _TestBase.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as sess:
        yield sess


class TestEncryptedString:
    """``EncryptedString`` round-trips str values and stores ciphertext on disk."""

    def test_round_trips(self, session: Session) -> None:
        rows = [_CryptoRow(secret_text=value) for value in _ENCRYPTED_STRING_CASES]
        session.add_all(rows)
        session.commit()
        session.expire_all()
        loaded = session.scalars(select(_CryptoRow).order_by(_CryptoRow.id)).all()
        assert [row.secret_text for row in loaded] == list(_ENCRYPTED_STRING_CASES)

    def test_storage_is_ciphertext(self, engine: Engine) -> None:
        plaintext = "extremely-sensitive-secret-value"
        with Session(engine) as sess:
            sess.add(_CryptoRow(secret_text=plaintext))
            sess.commit()
        # Inspect the raw stored bytes via a fresh connection and confirm
        # they do NOT contain the plaintext anywhere.
        with engine.connect() as conn:
            raw_value = conn.exec_driver_sql(
                "SELECT secret_text FROM encrypted_column_smoke",
            ).scalar()
        assert raw_value is not None
        assert plaintext.encode("utf-8") not in raw_value
        # nonce(12) + min ciphertext(0) + tag(16) = 28 bytes minimum.
        assert len(raw_value) >= 12 + 16


class TestEncryptedBytes:
    def test_round_trips(self, session: Session) -> None:
        rows = [_CryptoRow(secret_bytes=value) for value in _ENCRYPTED_BYTES_CASES]
        session.add_all(rows)
        session.commit()
        session.expire_all()
        loaded = session.scalars(select(_CryptoRow).order_by(_CryptoRow.id)).all()
        assert [row.secret_bytes for row in loaded] == list(_ENCRYPTED_BYTES_CASES)


class TestEncryptedJSON:
    def test_round_trips(self, session: Session) -> None:
        rows = [_CryptoRow(secret_json=value) for value in _ENCRYPTED_JSON_CASES]
        session.add_all(rows)
        session.commit()
        session.expire_all()
        loaded = session.scalars(select(_CryptoRow).order_by(_CryptoRow.id)).all()
        assert [row.secret_json for row in loaded] == list(_ENCRYPTED_JSON_CASES)

    def test_rejects_unserialisable(self, session: Session) -> None:
        from sqlalchemy.exc import StatementError

        class _NotJSON:
            pass

        session.add(_CryptoRow(secret_json=_NotJSON()))
        with pytest.raises(StatementError):
            session.flush()

    def test_invalid_bind_value_carries_storage_validation_locale_key(self, engine: Engine) -> None:
        with pytest.raises(StorageValidationError) as excinfo:
            EncryptedJSON().process_bind_param({object(): "not-json"}, engine.dialect)
        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"

    def test_invalid_stored_json_is_decryption_error(self, engine: Engine, fixed_master_key: bytes) -> None:
        wire = encrypt_record(
            b"{",
            key=fixed_master_key,
            associated_data=_AAD_JSON,
        ).to_wire()

        with pytest.raises(DecryptionError):
            EncryptedJSON().process_result_value(wire, engine.dialect)


class TestCrossTypeReplayPrevention:
    """Ciphertext minted for one column-type AAD must refuse to decrypt as another."""

    def test_string_ciphertext_does_not_decrypt_as_bytes(
        self,
        engine: Engine,
        session: Session,
    ) -> None:
        session.add(_CryptoRow(secret_text="payload"))
        session.commit()
        with engine.connect() as conn:
            ciphertext = conn.exec_driver_sql(
                "SELECT secret_text FROM encrypted_column_smoke",
            ).scalar()
            assert ciphertext is not None
            conn.exec_driver_sql(
                "INSERT INTO encrypted_column_smoke (secret_bytes) VALUES (?)",
                (ciphertext,),
            )
            conn.commit()
        with pytest.raises(DecryptionError):
            session.execute(
                select(_CryptoRow.secret_bytes).where(_CryptoRow.secret_bytes.is_not(None)),
            ).all()

    def test_encrypted_string_result_rejects_invalid_utf8(self, engine: Engine, fixed_master_key: bytes) -> None:
        wire = encrypt_record(
            b"\xff\xfe",
            key=fixed_master_key,
            associated_data=_AAD_STRING,
        ).to_wire()

        with pytest.raises(DecryptionError):
            EncryptedString().process_result_value(wire, engine.dialect)


class TestHashedLookup:
    """The deterministic HMAC keeps equality semantics without leaking plaintext."""

    def test_same_plaintext_same_digest(self, session: Session) -> None:
        digest_a = HashedLookup.compute("operator-secret-key")
        digest_b = HashedLookup.compute("operator-secret-key")
        assert digest_a == digest_b
        assert len(digest_a) == 32

    def test_different_plaintexts_different_digests(self) -> None:
        a = HashedLookup.compute("alpha")
        b = HashedLookup.compute("beta")
        assert a != b

    def test_short_plaintext_digest_does_not_emit_runtime_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(
            logging.WARNING,
            logger="cadrumo.adapters.persistence.storage.crypto._encrypted_columns",
        )

        digest = HashedLookup.compute("alpha")

        assert len(digest) == 32
        assert not [
            record
            for record in caplog.records
            if record.name == "cadrumo.adapters.persistence.storage.crypto._encrypted_columns"
        ]

    def test_round_trip_via_sqlalchemy(self, session: Session) -> None:
        row = _CryptoRow(lookup_key="natural-key-1")
        session.add(row)
        session.commit()
        session.expire_all()
        loaded = session.execute(select(_CryptoRow)).scalar_one()
        # The stored representation is the digest, not the plaintext.
        assert loaded.lookup_key == HashedLookup.compute("natural-key-1")

    def test_query_by_natural_key(self, session: Session) -> None:
        session.add_all(
            [
                _CryptoRow(lookup_key="alpha"),
                _CryptoRow(lookup_key="beta"),
                _CryptoRow(lookup_key="gamma"),
            ],
        )
        session.commit()
        # The decorator digests the bound parameter, so consumers can
        # query with the natural-key plaintext rather than precomputing
        # the digest themselves.
        match = session.execute(
            select(_CryptoRow).where(_CryptoRow.lookup_key == "beta"),
        ).scalar_one()
        assert match.lookup_key == HashedLookup.compute("beta")

    def test_digest_changes_with_master_key(self) -> None:
        digest_a = HashedLookup.compute("payload")
        # Switch to a different master key; the digest must change.
        with EphemeralMasterKeyProvider():
            digest_b = HashedLookup.compute("payload")
        assert digest_a != digest_b

    def test_invalid_plaintext_type_carries_storage_validation_locale_key(self) -> None:
        with pytest.raises(StorageValidationError) as excinfo:
            HashedLookup.compute(cast(str, b"not-str"))
        assert excinfo.value.translated_message == "errors.integrity.integrity_storage_validation"


class TestEncryptedPayload:
    """``EncryptedPayload`` validates the boundary output of :class:`EncryptedJSON`."""

    def test_roundtrip_dict_produces_encrypted_payload(self, session: Session) -> None:
        """Saving a dict via EncryptedJSON and reloading must round-trip the value.

        The EncryptedJSON.process_result_value path wraps the decrypted JSON in
        EncryptedPayload internally before returning .data.  The caller sees the
        original value; this test confirms the validated payload equals the stored dict.
        """
        payload = {"nombre": "Ana", "importe": 1234, "tags": ["iva", "irpf"]}
        session.add(_CryptoRow(secret_json=payload))
        session.commit()
        session.expire_all()
        loaded = session.execute(select(_CryptoRow)).scalar_one()
        assert loaded.secret_json == payload

    def test_encrypted_payload_validates_json_value(self) -> None:
        """EncryptedPayload must accept any JSON-compatible value."""
        assert EncryptedPayload(data={"k": 1}).data == {"k": 1}
        assert EncryptedPayload(data=[1, 2, 3]).data == [1, 2, 3]
        assert EncryptedPayload(data="text").data == "text"
        assert EncryptedPayload(data=42).data == 42
        assert EncryptedPayload(data=None).data is None

    def test_encrypted_payload_rejects_missing_data_field(self) -> None:
        """EncryptedPayload.model_validate must raise ValidationError when 'data' is absent."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EncryptedPayload.model_validate({})

    def test_encrypted_columns_write_encrypted_bytes_on_disk(self, engine: Engine) -> None:
        """The stored wire bytes must NOT contain the plaintext JSON for EncryptedJSON.

        This is an anti-tautology proof: decrypt path wraps in EncryptedPayload,
        so if the plaintext leaked to disk the round-trip contract would be broken.
        """
        payload = {"secret": "should-not-appear-in-storage"}
        with Session(engine) as sess:
            sess.add(_CryptoRow(secret_json=payload))
            sess.commit()
        with engine.connect() as conn:
            raw = conn.exec_driver_sql(
                "SELECT secret_json FROM encrypted_column_smoke",
            ).scalar()
        assert raw is not None
        assert b"should-not-appear-in-storage" not in raw


class TestNullSafety:
    """Every decorator's bind/result handler returns None for None inputs."""

    def test_string_none(self, session: Session) -> None:
        session.add(_CryptoRow())
        session.commit()
        session.expire_all()
        loaded = session.execute(select(_CryptoRow)).scalar_one()
        assert loaded.secret_text is None
        assert loaded.secret_bytes is None
        assert loaded.secret_json is None
        assert loaded.lookup_key is None
